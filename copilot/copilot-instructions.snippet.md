<!--
Drop-in block for ~/.copilot/copilot-instructions.md (or your team template).
This is the REQUIRED wiring for the Brain Memory Layer. Paste it verbatim;
adjust nothing except the optional scheduling note. Keep it short on purpose —
the `brain` CLI and the brain-sync skill carry the detail.
-->

## Memory layer (brain)

A local SQLite memory store accessed **only** through the `brain` CLI
(`~/.local/bin/brain`, DB at `~/.brain/brain.db`). SQL is the single source of
truth — never read or write the database file directly, and never grep markdown
vaults for knowledge.

**Every task:**
- **Start** — recall before planning:
  `brain search "<task keywords>" --json --no-reinforce`
  Read the top hits; ignore results flagged `⚠superseded` or `[stale]`.
- **During** — capture durable insights the moment you find them:
  `brain learn "[GOTCHA|PATTERN|DECISION|WORKFLOW|PREFERENCE|TOOL] <insight>" --level <repo|project|domain|global|tooling> [--scope <name>]`
- **Conflicts** — when new knowledge replaces old:
  `brain supersede <old-id-or-prefix> <new-id-or-prefix>`
- **End** — write 1–3 learnings at the **most specific level that is still
  true**. Don't duplicate across levels — `brain link A B` instead.

**Rules:** use the `brain` CLI for all reads/writes; one memory = one atomic
fact; no secrets or PII (plaintext store); pass `--no-reinforce` for orientation
reads so the recall model isn't skewed.

When more detail is needed, invoke the **brain-sync** skill. Daily housekeeping:
`brain sleep` (schedule via cron/launchd).
