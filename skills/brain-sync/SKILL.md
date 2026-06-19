---
name: brain-sync
description: >
  Invoke at the START of every task to recall relevant knowledge from the local
  brain, and at the END of every task to persist new learnings. The brain is a
  local SQLite memory store (the `brain` CLI) and is the single source of truth
  for durable engineering knowledge.
---

# Brain Sync — local memory integration

The brain is a per-engineer SQLite store, accessed **only** through the `brain`
CLI (never read or write the database file directly). SQL is the source of
truth; any markdown export is a regenerable view.

> Store: `~/.brain/brain.db` (override `$BRAIN_DB`). Verify with `brain doctor`.

## When to use

- **Start of every task** — recall context before doing the work.
- **Mid-task** — when you discover something durable, capture it immediately.
- **End of every task** — write 1–3 learnings; resolve any contradictions.

## Recall (task start)

```bash
# Keyword search, decay-blended ranking. Use --json for structured reading.
brain search "KEYWORDS FROM THE TASK" --json --no-reinforce

# Narrow by scope when you know it:
brain search "KEYWORDS" --level repo --scope "$(basename "$PWD")" --no-reinforce
brain search "KEYWORDS" --level domain --scope backend --no-reinforce

# Pull a specific memory + its graph neighbours:
brain get "<id-or-unique-prefix>" --json
brain traverse "<id-or-unique-prefix>" --depth 2
```

Read the top hits before planning. **Respect the flags:** skip or down-weight
results marked `⚠superseded` or `[stale]`.

> Use `--no-reinforce` for recall reads done purely to orient yourself, so you
> don't artificially strengthen memories you didn't actually rely on. Drop the
> flag when a memory genuinely informed your work (a real recall).

## Capture (mid-task & task end)

```bash
# Fast path — a tagged learning. The [CATEGORY] maps to a memory type.
brain learn "[GOTCHA] @Transactional self-invocation bypasses the Spring proxy" \
  --level domain --scope backend

# Structured / longer memory (body via stdin):
brain add "Payment retry policy" --type workflow --level repo --scope payments \
  --source "session:$SESSION_ID" --body - <<'MD'
Retries: 3 attempts, exponential backoff 1s/4s/16s; idempotency key required.
MD
```

Categories → types: `[DECISION] [PATTERN] [GOTCHA] [WORKFLOW] [PREFERENCE] [TOOL]`.

## Levels — store at the most specific level that is still true

| level | `--scope` | use for |
|---|---|---|
| `repo` | repo name | true only for this repository |
| `project` | project name | spans repos in one initiative |
| `domain` | domain name | a whole business/technical domain |
| `global` | — | all of your work |
| `tooling` | — | the agent/toolchain itself |

## Resolve contradictions — supersede, never overwrite

```bash
brain supersede "<old-id-or-prefix>" "<new-id-or-prefix>"
```
The old memory is kept but marked stale and down-ranked. This stops agents
flip-flopping between conflicting facts.

## Rules

- **Always use the `brain` CLI** — never `sqlite3` the DB directly; FTS + the
  recall model are handled internally.
- **Search before you write** — `brain` dedups identical content by hash, but
  you should still avoid near-duplicates; link related memories instead
  (`brain link A B --type relates_to|derived_from|refines`).
- **Don't duplicate across levels** — write once at the right level, then link.
- **No secrets / PII** — it's a plaintext SQLite file. Engineering knowledge only.
- **One memory = one durable fact** — atomic memories decay and supersede cleanly.

See the package docs: `SPEC.md`, `MEMORY-MODEL.md`, `CONVENTIONS.md`.
