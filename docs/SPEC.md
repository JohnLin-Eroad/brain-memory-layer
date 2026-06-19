# Brain Memory Layer — Standard Specification

> **Status:** v1 (schema_version = 1)
> **Audience:** every engineer adopting the shared memory-layer standard.
> **Scope:** per-engineer **local** memory. No shared/central store in v1.

This document is the authoritative contract. Tooling, agents, and integrations
MUST conform to it. If behaviour and this spec disagree, the spec wins (file a
change, don't fork the behaviour).

---

## 1. Goals & non-goals

**Goals**
- One canonical, portable memory store per engineer, identical schema everywhere.
- SQL is the **single source of truth**. No dependency on Obsidian/markdown.
- A recall model that forgets gracefully (decay), prefers used knowledge
  (reinforcement), and resolves contradictions (supersession).
- Zero-friction install: `python3` + a single SQLite file. No services, no pip.

**Non-goals (v1)**
- No shared/central/team database. Each engineer owns their own DB.
- No network sync, no multi-writer concurrency beyond SQLite WAL.
- No automatic code/repo ingestion (memories are written deliberately).

---

## 2. Source of truth

The SQLite database (default `~/.brain/brain.db`, override with `$BRAIN_DB`) is
**authoritative**. Markdown export (`brain export`) is a *regenerable view* for
human browsing or Obsidian — it is never read back as truth. Do not hand-edit
exported markdown and expect it to flow back; it won't.

---

## 3. Data model

Five tables (full DDL in [`sql/schema.sql`](../sql/schema.sql)).

### 3.1 `memories` — durable knowledge items
| column | type | notes |
|---|---|---|
| `id` | TEXT PK | stable slug: `level[/scope]/type/title-slug` |
| `title` | TEXT | one-line summary |
| `body` | TEXT | markdown body (backs FTS) |
| `type` | TEXT | see §4 |
| `level` | TEXT | see §5 |
| `scope` | TEXT | repo/project/domain name; NULL for `global`/`tooling` |
| `source` | TEXT | provenance (session id, path, url, agent) |
| `content_hash` | TEXT | sha256(title+body); dedup key |
| `created_at`/`updated_at` | TEXT | UTC `datetime('now')` |
| `tombstone` | INT | 1 = soft-deleted, retained for history |

### 3.2 `memory_state` — the recall model (1:1 with memories)
`strength` (0–1), `half_life_days`, `last_retrieved_at`, `retrieval_count`,
`confidence` (`verified|observed|inferred|stale`), `valence`
(`neutral|positive|negative`), `superseded_by`, `superseded_at`. See
[MEMORY-MODEL.md](MEMORY-MODEL.md).

### 3.3 `edges` — typed relationships
`(source_id, target_id, edge_type, weight)`. `edge_type ∈ {relates_to,
depends_on, supersedes, derived_from, refines, contradicts}`.

### 3.4 `access_log` — append-only telemetry
One row per read (`search|traverse|fetch`). Drives reinforcement; pruned after
90 days by `brain sleep`.

### 3.5 `memories_fts` — FTS5 index
External-content FTS5 over `id, title, body, type, scope`, kept in sync by
triggers. Tokenizer: `porter unicode61`.

---

## 4. Memory types (`type`)

| type | when to use |
|---|---|
| `decision` | a choice made and why (ADR-lite) |
| `pattern` | a reusable approach that works |
| `gotcha` | a trap, surprising behaviour, or bug class |
| `workflow` | a repeatable process / sequence of steps |
| `preference` | a stable personal/team style choice |
| `tool` | how a specific tool behaves / is used |
| `learning` | generic insight not matching the above |
| `note` | freeform default |
| `entity` | a stable thing (service, system, person, component) |

The `[CATEGORY]` tags from legacy `learnings.md` map directly:
`[PATTERN]→pattern, [GOTCHA]→gotcha, [DECISION]→decision, [WORKFLOW]→workflow,
[PREFERENCE]→preference, [TOOL]→tool`. See `brain learn`.

---

## 5. Memory levels (`level`) — the scope hierarchy

| level | meaning | `scope` |
|---|---|---|
| `repo` | specific to one repository | repo name (required) |
| `project` | spans repos within one project/initiative | project name (required) |
| `domain` | a business/technical domain | domain name (required) |
| `global` | applies to all of an engineer's work | NULL |
| `tooling` | about the agent/toolchain itself | NULL |

**Placement rule:** store knowledge at the **most specific level that is still
true**. A gotcha about one repo is `repo`; a preference for all your work is
`global`. Never duplicate the same fact across levels — link instead.

---

## 6. Read/write contracts

### 6.1 Writing
- Prefer `brain learn "[CATEGORY] text"` for end-of-task insights.
- Use `brain add` for structured/longer memories (with `--body -` for stdin).
- Writes are **idempotent by content**: identical `content_hash` is deduped;
  same `id` updates in place.
- Set `--confidence verified` only for facts you have confirmed.

### 6.2 Reading
- `brain search QUERY` returns decay-blended, supersession-aware results.
- Reads **reinforce** matched memories unless `--no-reinforce` is passed.
  Programmatic/eval reads MUST pass `--no-reinforce` to avoid skewing the model.
- `--json` is the stable machine interface for agents.

### 6.3 ID references
Any command taking an id accepts an exact id, a unique **prefix**, or a unique
**substring**. Ambiguous references fail loudly with candidates.

### 6.4 Conflict resolution
When new knowledge replaces old: `brain supersede OLD NEW`. The old memory is
marked `stale`, gains a `supersedes` edge from NEW, and is penalised in ranking
(never deleted — history is preserved).

---

## 7. Lifecycle / housekeeping

`brain sleep` (run daily; schedule via cron/launchd):
1. Marks memories whose effective strength ≤ 0.10 as `confidence='stale'`.
2. Prunes `access_log` rows older than 90 days.

Nothing is ever hard-deleted by housekeeping. `brain forget ID` tombstones a
memory (excluded from search, retained in the table).

---

## 8. Invariants (tooling MUST uphold)

1. Every active (`tombstone=0`) memory has exactly one `memory_state` row.
2. `effective_strength ∈ [0.05, 1.0]` — memories never reach 0 / never vanish.
3. FTS stays consistent with `memories` (enforced by triggers — never write FTS
   directly).
4. `supersede` is reversible (clear `superseded_by` + remove the edge).
5. Exact-match relevance dominates: the decay blend multiplies relevance by a
   factor in `[0.125, 1.0]`; it reorders, it never fabricates relevance.
6. `brain doctor` MUST pass on a healthy database.

---

## 9. Versioning & migration

- `meta.schema_version` records the on-disk version (currently `1`).
- `brain init` is idempotent and safe to re-run (`CREATE TABLE IF NOT EXISTS`).
- Backwards-compatible changes (new tables/columns with defaults) bump nothing
  or are additive. Breaking changes increment `schema_version` and ship a
  migration step; `brain doctor` flags mismatches.

---

## 10. Conformance

An implementation conforms to **Brain Memory Layer v1** if it:
- uses exactly the schema in `sql/schema.sql` (schema_version 1),
- enforces every invariant in §8,
- honours the read/write contracts in §6,
- passes `tests/test_brain.sh` against its CLI.
