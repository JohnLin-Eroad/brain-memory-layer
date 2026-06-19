-- ============================================================================
-- Brain Memory Layer — Canonical Schema  (schema_version = 1)
-- ============================================================================
-- Source of truth: this SQLite database. Markdown vaults (if used) are an
-- OPTIONAL, regenerable export — never authoritative.
--
-- Design: memory-first. A "memory" is a first-class durable record, not a
-- mirror of a file. Each memory carries:
--   * classification  (type + level + scope)
--   * a recall model  (memory_state: strength, decay, confidence, supersession)
--   * relationships   (edges)
--   * usage telemetry (access_log)
--
-- Portable: SQLite + FTS5 only. No extensions, no external services.
-- ============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- meta: key-value store for schema version, owner, provenance.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- memories: one row per durable knowledge item.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS memories (
    id            TEXT PRIMARY KEY,          -- stable slug or uuid (e.g. 'global/preference/concise-commits')
    title         TEXT NOT NULL,
    body          TEXT NOT NULL DEFAULT '',  -- markdown body; backs FTS + display

    -- Classification ---------------------------------------------------------
    type          TEXT NOT NULL DEFAULT 'note'
                  CHECK (type IN ('note','learning','decision','pattern',
                                  'gotcha','workflow','preference','tool','entity')),
    level         TEXT NOT NULL DEFAULT 'global'
                  CHECK (level IN ('repo','project','domain','global','tooling')),
    scope         TEXT,                      -- repo/project/domain name; NULL for global/tooling

    -- Provenance -------------------------------------------------------------
    source        TEXT,                      -- session id, file path, url, agent name
    content_hash  TEXT NOT NULL,             -- sha256 of title+body, for dedup/change detection

    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    tombstone     INTEGER NOT NULL DEFAULT 0 -- 1 = soft-deleted, retained for history
);

CREATE INDEX IF NOT EXISTS idx_mem_type      ON memories(type);
CREATE INDEX IF NOT EXISTS idx_mem_level      ON memories(level);
CREATE INDEX IF NOT EXISTS idx_mem_scope      ON memories(scope);
CREATE INDEX IF NOT EXISTS idx_mem_tombstone  ON memories(tombstone);
CREATE INDEX IF NOT EXISTS idx_mem_hash       ON memories(content_hash);

-- ----------------------------------------------------------------------------
-- FTS5 full-text index over memories (replaces grep).
-- External-content table kept in sync via triggers.
-- ----------------------------------------------------------------------------
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    id, title, body, type, scope,
    content='memories',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, id, title, body, type, scope)
    VALUES (new.rowid, new.id, new.title, new.body, new.type, new.scope);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, id, title, body, type, scope)
    VALUES ('delete', old.rowid, old.id, old.title, old.body, old.type, old.scope);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, id, title, body, type, scope)
    VALUES ('delete', old.rowid, old.id, old.title, old.body, old.type, old.scope);
    INSERT INTO memories_fts(rowid, id, title, body, type, scope)
    VALUES (new.rowid, new.id, new.title, new.body, new.type, new.scope);
END;

-- ----------------------------------------------------------------------------
-- memory_state: the recall model. Exponential-decay + reinforcement.
-- One row per memory (created on insert). Hippo-memory inspired.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS memory_state (
    memory_id         TEXT PRIMARY KEY
                      REFERENCES memories(id) ON UPDATE CASCADE ON DELETE CASCADE,
    strength          REAL NOT NULL DEFAULT 1.0  CHECK (strength BETWEEN 0 AND 1),
    half_life_days    REAL NOT NULL DEFAULT 7.0  CHECK (half_life_days > 0),
    last_retrieved_at TEXT,
    retrieval_count   INTEGER NOT NULL DEFAULT 0,
    confidence        TEXT CHECK (confidence IS NULL OR confidence IN
                                  ('verified','observed','inferred','stale')),
    valence           TEXT NOT NULL DEFAULT 'neutral'
                      CHECK (valence IN ('neutral','positive','negative')),
    superseded_by     TEXT REFERENCES memories(id) ON UPDATE CASCADE,
    superseded_at     TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_state_strength      ON memory_state(strength);
CREATE INDEX IF NOT EXISTS idx_state_last_retrieved ON memory_state(last_retrieved_at);
CREATE INDEX IF NOT EXISTS idx_state_confidence    ON memory_state(confidence) WHERE confidence IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_state_superseded    ON memory_state(superseded_by) WHERE superseded_by IS NOT NULL;

-- ----------------------------------------------------------------------------
-- edges: directed, typed relationships between memories.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS edges (
    source_id  TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    target_id  TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    edge_type  TEXT NOT NULL DEFAULT 'relates_to'
               CHECK (edge_type IN ('relates_to','depends_on','supersedes',
                                     'derived_from','refines','contradicts')),
    weight     REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (source_id, target_id, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_type   ON edges(edge_type);

-- ----------------------------------------------------------------------------
-- access_log: append-only usage telemetry. Drives reinforcement + decay reset.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS access_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id   TEXT NOT NULL,
    accessed_at TEXT NOT NULL DEFAULT (datetime('now')),
    source      TEXT CHECK (source IN ('search','traverse','fetch')),
    query_hash  TEXT
);

CREATE INDEX IF NOT EXISTS idx_access_memory ON access_log(memory_id, accessed_at);
CREATE INDEX IF NOT EXISTS idx_access_time   ON access_log(accessed_at);

-- ----------------------------------------------------------------------------
-- Seed schema version (idempotent).
-- ----------------------------------------------------------------------------
INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1');
INSERT OR IGNORE INTO meta (key, value) VALUES ('created_at', datetime('now'));
