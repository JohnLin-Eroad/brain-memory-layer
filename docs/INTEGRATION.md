# Integration — wiring the brain into agents & workflows

The brain is a plain CLI with a stable `--json` interface. Anything that can run
a shell command can use it: Copilot CLI, editor agents, CI, git hooks, cron.

---

## 1. Copilot CLI (recommended)

The fastest path is the installer:

```bash
./install.sh --with-copilot
```

This installs the **brain-sync** skill, the optional brain agents, and appends
the required memory block to `~/.copilot/copilot-instructions.md`. The exact
block is in [`../copilot/copilot-instructions.snippet.md`](../copilot/copilot-instructions.snippet.md);
the skill detail is in [`../skills/brain-sync/SKILL.md`](../skills/brain-sync/SKILL.md).
See [`../copilot/README.md`](../copilot/README.md) for required-vs-optional.

The contract in one line: **search at task start, capture during, supersede on
conflict, write learnings at task end** — all through the `brain` CLI. No agent
should read or write the SQLite file directly.

---

## 2. Programmatic use (`--json`)

```bash
# Recall (no reinforcement when scripting / evaluating):
brain search "rate limiting redis" --level domain --json --no-reinforce \
  | jq -r '.[] | "\(.id)\t\(.title)"'

# Fetch one memory with state + edges:
brain get "<id-or-prefix>" --json --no-reinforce
```

`search --json` returns an array of
`{id, title, type, level, scope, score, effective_strength, confidence,
superseded_by, snippet}`, already ranked.

---

## 3. Capturing knowledge from a session

Pipe longer content via stdin:

```bash
brain add "Auth service token refresh flow" --type workflow --level repo \
  --scope auth-service --source "session:$SESSION_ID" --body - <<'MD'
1. Client posts refresh token to /oauth/refresh
2. Service validates against rotation table …
MD
```

---

## 4. Scheduling housekeeping

**macOS (launchd)** — `~/Library/LaunchAgents/com.you.brain-sleep.plist` runs
`brain sleep` daily. **Linux/cron:**

```cron
15 3 * * *  /home/$USER/.local/bin/brain sleep >> ~/.brain/sleep.log 2>&1
```

---

## 5. Optional: Obsidian / markdown browsing

The SQL store is the source of truth, but you can regenerate a browsable vault:

```bash
brain export ~/brain-vault     # one .md per memory, with front-matter
```

Re-run anytime; it is a one-way view. Never edit the vault and expect it to sync
back.

---

## 6. Optional: bulk-import existing `learnings.md` files

If you already keep per-repo `.github/learnings.md` notes (the common Copilot
pattern), you can bulk-load them into the brain with the bundled importer.
This is optional — new users with no notes can skip it.

```bash
python3 scripts/import-learnings.py --dry-run ~/code/my-repo   # preview
python3 scripts/import-learnings.py ~/code/repo-a ~/code/repo-b
```

Each bullet becomes a `repo`-level memory scoped to the repo directory name.
It handles dated bullets (`- **[DATE]** [CATEGORY] text`), plain bullets, and
bullets under `## DATE` headers; known `[CATEGORY]` tags map to the right
`type`. Duplicates are deduped by content hash, so re-running is safe.

---

## 7. Rollout checklist (per engineer)

1. `./install.sh` (or `curl … | bash`).
2. Ensure `~/.local/bin` is on `PATH`.
3. Add the Copilot block from §1.
4. Schedule `brain sleep` (§4).
5. `brain doctor` → should print all-checks-passed.
