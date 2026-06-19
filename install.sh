#!/usr/bin/env bash
# ============================================================================
# Brain Memory Layer — one-command bootstrap installer.
#
#   curl -fsSL .../install.sh | bash      # or just: ./install.sh
#
# Idempotent. Installs the standardized per-engineer memory layer:
#   * copies the package to        ~/.local/share/brain-memory-layer
#   * symlinks the `brain` CLI to   ~/.local/bin/brain
#   * initialises the database at   ~/.brain/brain.db   (override: BRAIN_DB)
#   * prints Copilot CLI integration guidance
#
# Requirements: bash, python3 (>=3.8, stdlib sqlite3 with FTS5 — standard).
# No network, no pip, no sudo.
# ============================================================================
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
SHARE_DIR="$PREFIX/share/brain-memory-layer"
BIN_DIR="$PREFIX/bin"
BRAIN_DB_DEFAULT="$HOME/.brain/brain.db"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

say()  { printf '\033[1;36m▶\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✅\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m⚠\033[0m  %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m  %s\n' "$*" >&2; exit 1; }

# ---- 1. Preflight ---------------------------------------------------------
command -v python3 >/dev/null 2>&1 || die "python3 not found — please install Python 3.8+."
PYV=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
say "Found python3 $PYV"
python3 - <<'PY' || die "Your python3 lacks sqlite3 FTS5 support (very unusual). Install a standard CPython build."
import sqlite3
c = sqlite3.connect(":memory:")
c.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
PY
ok "sqlite3 + FTS5 available"

# ---- 2. Install package files --------------------------------------------
say "Installing package → $SHARE_DIR"
mkdir -p "$SHARE_DIR" "$BIN_DIR"
# Copy bin/ and sql/ (and docs for reference) preserving layout.
for d in bin sql docs; do
  if [ -d "$SRC_DIR/$d" ]; then
    rm -rf "${SHARE_DIR:?}/$d"
    cp -R "$SRC_DIR/$d" "$SHARE_DIR/$d"
  fi
done
chmod +x "$SHARE_DIR/bin/brain"

# ---- 3. Symlink the CLI ---------------------------------------------------
ln -sf "$SHARE_DIR/bin/brain" "$BIN_DIR/brain"
ok "Linked CLI → $BIN_DIR/brain"

# ---- 4. Initialise the database ------------------------------------------
BRAIN_DB="${BRAIN_DB:-$BRAIN_DB_DEFAULT}"
mkdir -p "$(dirname "$BRAIN_DB")"
if [ -f "$BRAIN_DB" ]; then
  warn "Database already exists at $BRAIN_DB — running init (idempotent migrate)."
fi
BRAIN_DB="$BRAIN_DB" "$BIN_DIR/brain" init --owner "${USER:-engineer}"

# ---- 5. PATH check --------------------------------------------------------
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR is not on your PATH. Add this to your shell profile:"
     printf '\n    export PATH="%s:$PATH"\n\n' "$BIN_DIR" ;;
esac

# ---- 6. Copilot integration hint -----------------------------------------
cat <<EOF

$(ok "Brain Memory Layer installed.")

Quickstart:
    brain add "Use trunk-based development" --type decision --level global
    brain learn "[GOTCHA] Flyway needs explicit baseline on legacy DBs" --scope my-repo --level repo
    brain search "flyway"
    brain stats

Copilot CLI integration (optional but recommended):
    Add to ~/.copilot/copilot-instructions.md (or your team template):

      ## Memory layer
      - Task start: run \`brain search "<keywords>"\` to recall relevant memories.
      - Task end:   run \`brain learn "[CATEGORY] <insight>"\` for durable learnings.
      - Daily:      \`brain sleep\` (decay housekeeping). See docs/INTEGRATION.md.

Docs: $SHARE_DIR/docs/   (SPEC.md, MEMORY-MODEL.md, INTEGRATION.md, CONVENTIONS.md)
EOF
