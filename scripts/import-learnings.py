#!/usr/bin/env python3
"""import-learnings.py — import per-repo `.github/learnings.md` into brain.db.

Parses the standard bullet format written by add-learning.sh:

    - **[YYYY-MM-DD]** [CATEGORY] free text...
    - **[YYYY-MM-DD]** free text without a category...

Each bullet becomes a `repo`-level memory scoped to the repo directory name.
The date is preserved in `source` (and used as updated_at). The `[CATEGORY]`
tag maps to a memory type; untagged bullets become `learning`.

Idempotent: dedups by content hash, so re-runs and duplicated worktrees
(e.g. media-service-DRP-384) collapse into a single memory.

Usage:
    import-learnings.py REPO_DIR [REPO_DIR ...]          # auto-finds .github/learnings.md
    import-learnings.py --file path/to/learnings.md --scope myrepo
    import-learnings.py ~/IdeaProjects/media-service --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
import sys

CATEGORY_TO_TYPE = {
    "PATTERN": "pattern", "GOTCHA": "gotcha", "DECISION": "decision",
    "WORKFLOW": "workflow", "PREFERENCE": "preference", "TOOL": "tool",
}
DATE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
# `- **[DATE]** rest`  (dated bullet)
DATED_RE = re.compile(rf"^- \*\*\[(?P<date>{DATE})\]\*\*\s*(?P<rest>.+)$")
# `- rest`  (plain bullet — date may come from a section header)
PLAIN_RE = re.compile(r"^- (?!\*\*\[)(?P<rest>.+)$")
# `## YYYY-MM-DD — Title`  (section header carrying a fallback date)
HEADER_RE = re.compile(rf"^#{{1,6}}\s+(?P<date>{DATE})\b")
CAT_RE = re.compile(r"^\[(?P<cat>\w+)\]\s*(?P<text>.+)$", re.DOTALL)

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "sql", "schema.sql")


def db_path() -> str:
    return os.environ.get("BRAIN_DB",
                          os.path.join(os.path.expanduser("~"), ".brain", "brain.db"))


def content_hash(title: str, body: str) -> str:
    return hashlib.sha256(f"{title}\n{body}".encode("utf-8")).hexdigest()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-") or "memory"


def resolve_file(path: str) -> tuple[str, str] | None:
    """Return (learnings_file, scope) for a repo dir or a direct file."""
    if os.path.isdir(path):
        f = os.path.join(path, ".github", "learnings.md")
        return (f, os.path.basename(os.path.abspath(path))) if os.path.exists(f) else None
    if os.path.isfile(path):
        # scope = repo dir = two levels up from .github/learnings.md
        scope = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(path))))
        return (path, scope)
    return None


def parse_bullets(text: str):
    """Yield (date_or_None, type, title, body) for every learning bullet.

    Handles three bullet shapes:
      - **[DATE]** [CAT] text     (dated + category)
      - **[DATE]** text           (dated)
      - [CAT] text  /  text       (undated — date inherited from `## DATE` header)
    """
    header_date = None
    for raw in text.splitlines():
        line = raw.rstrip()
        h = HEADER_RE.match(line)
        if h:
            header_date = h.group("date")
            continue
        m = DATED_RE.match(line)
        if m:
            date, rest = m.group("date"), m.group("rest").strip()
        else:
            m = PLAIN_RE.match(line)
            if not m:
                continue
            date, rest = header_date, m.group("rest").strip()
        cm = CAT_RE.match(rest)
        if cm and cm.group("cat").upper() in CATEGORY_TO_TYPE:
            type_ = CATEGORY_TO_TYPE[cm.group("cat").upper()]
            body = cm.group("text").strip()
        else:
            # unknown tag (e.g. [SECURITY]) or no tag: keep text intact, classify as learning
            type_, body = "learning", rest
        title = body.split("\n", 1)[0][:80]
        yield date, type_, title, body


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("repos", nargs="*", help="repo dirs containing .github/learnings.md")
    p.add_argument("--file", help="a learnings.md file directly")
    p.add_argument("--scope", help="override scope for --file")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    targets = []
    for r in args.repos:
        rf = resolve_file(r)
        if rf:
            targets.append(rf)
        else:
            print(f"⚠  no .github/learnings.md under {r} — skipping")
    if args.file:
        scope = args.scope or (resolve_file(args.file) or (args.file, "unknown"))[1]
        targets.append((args.file, scope))
    if not targets:
        sys.exit("import-learnings: nothing to import")

    new = db_path()
    if not os.path.exists(new):
        sys.exit(f"import-learnings: brain DB not found at {new} — run `brain init` first.")
    conn = sqlite3.connect(new)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        conn.executescript(fh.read())

    totals = {"added": 0, "dup": 0, "files": 0}
    for fpath, scope in targets:
        with open(fpath, encoding="utf-8") as fh:
            text = fh.read()
        n_add = n_dup = 0
        for date, type_, title, body in parse_bullets(text):
            chash = content_hash(title, body)
            dup = conn.execute(
                "SELECT id FROM memories WHERE content_hash=? AND tombstone=0",
                (chash,)).fetchone()
            if dup:
                n_dup += 1
                continue
            mem_id = f"repo/{slugify(scope)}/{type_}/{slugify(title)}"
            # disambiguate id collisions (different content, same slug)
            if conn.execute("SELECT 1 FROM memories WHERE id=?", (mem_id,)).fetchone():
                mem_id = f"{mem_id}-{chash[:6]}"
            source = f"learnings.md repo={scope}" + (f" date={date}" if date else "")
            if not args.dry_run:
                if date:
                    conn.execute(
                        "INSERT INTO memories (id,title,body,type,level,scope,source,"
                        "content_hash,created_at,updated_at) "
                        "VALUES (?,?,?,?,'repo',?,?,?,?,?)",
                        (mem_id, title, body, type_, scope, source, chash, date, date))
                else:
                    conn.execute(
                        "INSERT INTO memories (id,title,body,type,level,scope,source,"
                        "content_hash) VALUES (?,?,?,?,'repo',?,?,?)",
                        (mem_id, title, body, type_, scope, source, chash))
                conn.execute("INSERT OR IGNORE INTO memory_state (memory_id, confidence) "
                             "VALUES (?, 'observed')", (mem_id,))
            n_add += 1
        if not args.dry_run:
            conn.commit()
        totals["added"] += n_add
        totals["dup"] += n_dup
        totals["files"] += 1
        print(f"  {scope:<28} +{n_add} added, {n_dup} dup-skipped   ({fpath})")

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}imported {totals['added']} learnings "
          f"from {totals['files']} repo(s); {totals['dup']} duplicates skipped.")
    conn.close()


if __name__ == "__main__":
    main()
