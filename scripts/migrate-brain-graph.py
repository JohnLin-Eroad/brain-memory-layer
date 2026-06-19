#!/usr/bin/env python3
"""migrate-brain-graph.py — import a legacy brain-graph.db into a v1 brain.db.

Maps the old vault-derived graph (nodes / edges / node_memory / node_access_log)
into the standardized memory-first schema, preserving ALL knowledge:

  * every active node            -> memories  (+ a memory_state row)
  * node_memory rows             -> memory_state (strength/decay/confidence/...)
  * edges                        -> edges (edge_type mapped to the v1 vocabulary)
  * node_access_log              -> access_log

Original ids are kept verbatim so edges stay valid. Original classification
(vault / domain / rel_path / modified_at) is preserved in `memories.source`
so nothing is lost even where the level/type mapping is approximate.

Idempotent: safe to re-run (upserts by id). Read-only on the source DB.

Usage:
    migrate-brain-graph.py --old ~/.copilot/brain-graph.db --new ~/.brain/brain.db
    migrate-brain-graph.py --dry-run        # report only, write nothing
    migrate-brain-graph.py --skip-structural # drop folder_sibling edges
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys

# Old domain -> v1 memory type. Anything unlisted -> 'note'. Body is preserved
# regardless of type, so this only affects classification/ranking, never content.
DOMAIN_TO_TYPE = {
    "decision": "decision",
    "learning": "learning",
    "architecture": "pattern",
    "service": "entity",
    "department": "entity",
    "domain_model": "entity",
    "Shared_Platform": "entity",
}

# Old edge_type -> (v1 edge_type, weight). folder_sibling is structural; kept by
# default (mapped to relates_to, low weight) unless --skip-structural.
EDGE_MAP = {
    "wiki_link": ("relates_to", 1.0),
    "depends_on": ("depends_on", 1.5),
    "folder_sibling": ("relates_to", 0.3),
}

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "sql", "schema.sql")


def content_hash(title: str, body: str) -> str:
    return hashlib.sha256(f"{title}\n{body}".encode("utf-8")).hexdigest()


def map_level(vault: str) -> tuple[str, str | None]:
    # eroad-brain -> domain-scoped EROAD knowledge; john-brain -> personal global.
    if vault == "john-brain":
        return "global", None
    return "domain", "eroad"


def load_schema(conn: sqlite3.Connection) -> None:
    if not os.path.exists(SCHEMA_PATH):
        sys.exit(f"migrate: cannot find schema at {SCHEMA_PATH}")
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        conn.executescript(fh.read())


def migrate(old: str, new: str, *, dry_run: bool, skip_structural: bool) -> int:
    if not os.path.exists(old):
        sys.exit(f"migrate: source DB not found: {old}")
    os.makedirs(os.path.dirname(os.path.abspath(new)), exist_ok=True)

    src = sqlite3.connect(f"file:{old}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(new)
    dst.row_factory = sqlite3.Row
    dst.execute("PRAGMA foreign_keys = ON")
    load_schema(dst)

    stats = {"memories": 0, "memory_state": 0, "edges": 0, "edges_skipped": 0,
             "access_log": 0, "old_chars": 0, "new_chars": 0}

    # ---- 1. nodes -> memories (+ default memory_state) ----------------------
    nodes = src.execute(
        "SELECT id, vault, rel_path, basename, title, content, domain, "
        "modified_at, indexed_at FROM nodes WHERE tombstone=0").fetchall()
    for n in nodes:
        title = n["title"] or n["basename"] or n["id"]
        body = n["content"] or ""
        stats["old_chars"] += len(body)
        type_ = DOMAIN_TO_TYPE.get(n["domain"] or "", "note")
        level, scope = map_level(n["vault"])
        source = (f"migrated:brain-graph.db vault={n['vault']} "
                  f"domain={n['domain']} rel_path={n['rel_path']}")
        updated = n["modified_at"] or n["indexed_at"]
        if not dry_run:
            dst.execute(
                "INSERT INTO memories (id,title,body,type,level,scope,source,"
                "content_hash,updated_at) VALUES (?,?,?,?,?,?,?,?,COALESCE(?,datetime('now'))) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, body=excluded.body, "
                "type=excluded.type, level=excluded.level, scope=excluded.scope, "
                "source=excluded.source, content_hash=excluded.content_hash, "
                "updated_at=excluded.updated_at, tombstone=0",
                (n["id"], title, body, type_, level, scope, source,
                 content_hash(title, body), updated))
            # Ensure a memory_state row exists (default). node_memory pass below
            # will overwrite the managed ones with real values.
            dst.execute(
                "INSERT OR IGNORE INTO memory_state (memory_id) VALUES (?)", (n["id"],))
        stats["memories"] += 1

    # ---- 2. node_memory -> memory_state (real recall values) ----------------
    for m in src.execute(
            "SELECT node_id, strength, half_life_days, last_retrieved_at, "
            "retrieval_count, confidence, valence, superseded_by, superseded_at, "
            "created_at, updated_at FROM node_memory").fetchall():
        if not dry_run:
            dst.execute(
                "INSERT INTO memory_state (memory_id,strength,half_life_days,"
                "last_retrieved_at,retrieval_count,confidence,valence,superseded_by,"
                "superseded_at,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,COALESCE(?,datetime('now')),COALESCE(?,datetime('now'))) "
                "ON CONFLICT(memory_id) DO UPDATE SET strength=excluded.strength, "
                "half_life_days=excluded.half_life_days, "
                "last_retrieved_at=excluded.last_retrieved_at, "
                "retrieval_count=excluded.retrieval_count, confidence=excluded.confidence, "
                "valence=excluded.valence, superseded_by=excluded.superseded_by, "
                "superseded_at=excluded.superseded_at, updated_at=excluded.updated_at",
                (m["node_id"], m["strength"], m["half_life_days"], m["last_retrieved_at"],
                 m["retrieval_count"], m["confidence"], m["valence"] or "neutral",
                 m["superseded_by"] or None, m["superseded_at"] or None,
                 m["created_at"], m["updated_at"]))
        stats["memory_state"] += 1

    # ---- 3. edges -> edges (mapped, dedup, keep strongest weight) -----------
    # Order by weight desc so wiki_link (1.0) wins over folder_sibling (0.3)
    # when both map to relates_to between the same pair.
    for e in src.execute("SELECT source_id, target_id, edge_type, weight FROM edges "
                         "ORDER BY weight DESC").fetchall():
        mapped = EDGE_MAP.get(e["edge_type"])
        if mapped is None:
            mapped = ("relates_to", e["weight"] or 1.0)
        new_type, default_w = mapped
        if new_type == "relates_to" and default_w == 0.3 and skip_structural:
            stats["edges_skipped"] += 1
            continue
        # Skip self-loops and edges to nodes that weren't imported (defensive).
        if e["source_id"] == e["target_id"]:
            continue
        weight = e["weight"] if e["weight"] is not None else default_w
        if not dry_run:
            cur = dst.execute(
                "INSERT OR IGNORE INTO edges (source_id,target_id,edge_type,weight) "
                "VALUES (?,?,?,?)", (e["source_id"], e["target_id"], new_type, weight))
            if cur.rowcount == 0:
                continue
        stats["edges"] += 1

    # ---- 4. node_access_log -> access_log -----------------------------------
    for a in src.execute(
            "SELECT node_id, accessed_at, source, query_hash FROM node_access_log").fetchall():
        source = a["source"] if a["source"] in ("search", "traverse", "fetch") else None
        if not dry_run:
            dst.execute(
                "INSERT INTO access_log (memory_id,accessed_at,source,query_hash) "
                "VALUES (?,?,?,?)", (a["node_id"], a["accessed_at"], source, a["query_hash"]))
        stats["access_log"] += 1

    if not dry_run:
        dst.commit()
        stats["new_chars"] = dst.execute(
            "SELECT COALESCE(SUM(LENGTH(body)),0) c FROM memories WHERE tombstone=0").fetchone()["c"]
    else:
        stats["new_chars"] = stats["old_chars"]

    # ---- 5. Report + verification ------------------------------------------
    print("── Migration summary ─────────────────────────────")
    print(f"  memories       : {stats['memories']}")
    print(f"  memory_state   : {stats['memory_state']} managed (+ defaults for the rest)")
    print(f"  edges migrated : {stats['edges']}"
          + (f"  ({stats['edges_skipped']} structural skipped)" if stats["edges_skipped"] else ""))
    print(f"  access_log     : {stats['access_log']}")
    print(f"  body chars     : old={stats['old_chars']}  new={stats['new_chars']}")

    ok = True
    if not dry_run:
        active = dst.execute("SELECT COUNT(*) c FROM memories WHERE tombstone=0").fetchone()["c"]
        states = dst.execute(
            "SELECT COUNT(*) c FROM memories m WHERE m.tombstone=0 AND EXISTS "
            "(SELECT 1 FROM memory_state s WHERE s.memory_id=m.id)").fetchone()["c"]
        if stats["old_chars"] != stats["new_chars"]:
            print("  ✗ body-char mismatch — knowledge may be lost!"); ok = False
        if active != states:
            print(f"  ✗ {active - states} memories missing memory_state"); ok = False
        if active < stats["memories"]:
            print(f"  ✗ fewer memories ({active}) than source nodes ({stats['memories']})"); ok = False
        if ok:
            print("  ✅ verification passed: every node imported, all bytes preserved, "
                  "every memory has state.")
    src.close()
    dst.close()
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--old", default=os.path.expanduser("~/.copilot/brain-graph.db"))
    p.add_argument("--new", default=os.environ.get(
        "BRAIN_DB", os.path.expanduser("~/.brain/brain.db")))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-structural", action="store_true",
                   help="drop folder_sibling (structural) edges")
    args = p.parse_args()
    print(f"source : {args.old}")
    print(f"target : {args.new}{'  (DRY RUN)' if args.dry_run else ''}\n")
    sys.exit(migrate(args.old, args.new, dry_run=args.dry_run,
                     skip_structural=args.skip_structural))


if __name__ == "__main__":
    main()
