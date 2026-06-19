# Integration — wiring the brain into agents & workflows

The brain is a plain CLI with a stable `--json` interface. Anything that can run
a shell command can use it: Copilot CLI, editor agents, CI, git hooks, cron.

---

## 1. Copilot CLI (recommended)

Add a short block to your `~/.copilot/copilot-instructions.md` (or the shared
team template). Keep it tiny — the brain does the heavy lifting.

```markdown
## Memory layer (brain)
- **Task start:** run `brain search "<keywords from the task>" --json` and read
  the top results before planning. Respect `superseded`/`stale` flags.
- **During:** when you discover something durable, capture it immediately:
  `brain learn "[GOTCHA|PATTERN|DECISION|WORKFLOW|PREFERENCE|TOOL] <insight>" \
    --level <repo|project|domain|global> [--scope <name>]`.
- **Conflicts:** if new knowledge replaces old, `brain supersede <old> <new>`.
- **Task end:** write 1–3 learnings. Don't duplicate across levels — link.
```

That's the whole contract. No agent should read or write the SQLite file
directly; always go through `brain`.

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

## 6. Migrating from legacy `learnings.md`

A flat `learnings.md` (`- **[DATE]** [CATEGORY] text`) imports cleanly:

```bash
grep -E '^\- ' .github/learnings.md \
  | sed -E 's/^- \*\*\[[0-9-]+\]\*\* //' \
  | while IFS= read -r line; do
      brain learn "$line" --level repo --scope "$(basename "$PWD")" --source learnings.md
    done
```

`brain learn` parses the `[CATEGORY]` tag into the correct `type`; duplicates
are deduped by content hash, so re-running is safe.

---

## 7. Rollout checklist (per engineer)

1. `./install.sh` (or `curl … | bash`).
2. Ensure `~/.local/bin` is on `PATH`.
3. Add the Copilot block from §1.
4. Schedule `brain sleep` (§4).
5. `brain doctor` → should print all-checks-passed.
