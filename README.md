# Brain Memory Layer

A standardized, portable **per-engineer memory layer** for AI-assisted
engineering. One SQLite file, one CLI, a principled recall model — installable
in one command and identical on every engineer's machine.

> **Source of truth is SQL.** Markdown/Obsidian export is optional and
> regenerable. No services, no pip, no network — just `python3` + SQLite.

```
brain learn "[GOTCHA] Flyway needs an explicit baseline on legacy schemas" --level repo --scope billing
brain search "flyway baseline"
brain stats
```

---

## Why this exists

Most engineers accumulate hard-won knowledge in scattered places — chat logs,
`learnings.md`, their head. It rots, conflicts, and doesn't travel. This package
consolidates that into **one canonical store with a memory model**: knowledge
*decays* when unused, *strengthens* when recalled, and *supersedes* cleanly when
it changes — so your agents recall what's currently true, not whatever ranked
highest.

It is designed to be **rolled out across an engineering org**: every engineer
runs their own local brain on the exact same schema and tooling.

---

## Install

```bash
git clone <repo> brain-memory-layer && cd brain-memory-layer
./install.sh
```

This installs the `brain` CLI to `~/.local/bin`, creates the database at
`~/.brain/brain.db`, and prints integration guidance. Re-running is safe
(idempotent). Override location with `PREFIX=` and `BRAIN_DB=`.

Requirements: `bash`, `python3` ≥ 3.8 (stdlib `sqlite3` with FTS5 — standard in
CPython). Verify any install with `brain doctor`.

---

## Core commands

| command | purpose |
|---|---|
| `brain init` | create / migrate the database |
| `brain add TITLE [--body -]` | add a structured memory |
| `brain learn "[CATEGORY] text"` | add a learning (parses the tag → type) |
| `brain search QUERY` | decay-blended, supersession-aware full-text search |
| `brain get ID` | show a memory + state + edges (accepts id prefixes) |
| `brain link SRC DST --type` | create a typed relationship |
| `brain traverse ID --depth N` | walk the knowledge graph |
| `brain supersede OLD NEW` | resolve a contradiction (old → stale) |
| `brain confidence ID LEVEL` | set verified/observed/inferred/stale |
| `brain forget ID` | soft-delete (tombstone) |
| `brain sleep` | daily housekeeping (decay-mark stale, prune log) |
| `brain stats` / `brain doctor` | summary / health check |
| `brain export DIR` | optional markdown view (SQL stays authoritative) |

Every command supports `-h`. Reads return `--json` for agents.

---

## How it works (one paragraph)

Each memory has a **recall state**: a `strength` that decays exponentially with
a `half_life`, floored so nothing ever vanishes. Searches rank by FTS5 relevance
*blended* with effective strength, and every recall **reinforces** the hit
(stronger, longer half-life). Contradictions are handled by **supersession**
(old kept but penalised), and a nightly `sleep` flags decayed memories `stale`.
Full math in [docs/MEMORY-MODEL.md](docs/MEMORY-MODEL.md).

---

## Documentation

| doc | what's in it |
|---|---|
| [docs/SPEC.md](docs/SPEC.md) | the authoritative standard: schema, levels, types, invariants, contracts |
| [docs/MEMORY-MODEL.md](docs/MEMORY-MODEL.md) | decay / reinforcement / supersession math |
| [docs/INTEGRATION.md](docs/INTEGRATION.md) | wiring into Copilot CLI, agents, cron, Obsidian; migrating `learnings.md` |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | how to write good memories |
| [sql/schema.sql](sql/schema.sql) | canonical DDL (schema_version 1) |

---

## Repository layout

```
brain-memory-layer/
├── install.sh            one-command bootstrap (idempotent; --with-copilot)
├── bin/brain             the CLI (single-file, stdlib-only Python)
├── sql/schema.sql        canonical schema (also embedded in the CLI)
├── docs/                 SPEC, MEMORY-MODEL, INTEGRATION, CONVENTIONS
├── skills/brain-sync/    Copilot skill (recall at start, capture at end)
├── copilot/              Copilot wiring: instructions snippet + optional agents
└── tests/test_brain.sh   conformance / smoke test
```

---

## Copilot CLI rollout

```bash
./install.sh --with-copilot
```

Installs the **brain-sync** skill, the optional `brain-data-retrieval` /
`brain-consolidation` agents, and appends the required instructions block to
`~/.copilot/copilot-instructions.md` (idempotent). A single-agent user needs
only the skill + the instructions block; the two agents are for multi-agent
pipelines. See [copilot/README.md](copilot/README.md).

---

## Standardization status

- **v1** — per-engineer local brains, identical schema + tooling.
- Out of scope for v1: shared/central store, network sync, multi-writer.

Run `tests/test_brain.sh` to confirm an install conforms to the spec.
