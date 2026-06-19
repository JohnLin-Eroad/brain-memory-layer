#!/usr/bin/env bash
# Conformance / smoke test for the Brain Memory Layer.
# Exercises every command against a throwaway DB and asserts behaviour.
# Usage:  tests/test_brain.sh            (uses ../bin/brain)
#         BRAIN_BIN=/path/to/brain tests/test_brain.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRAIN_BIN="${BRAIN_BIN:-$HERE/../bin/brain}"
export BRAIN_DB="$(mktemp -d)/brain.db"
PASS=0; FAIL=0
b() { python3 "$BRAIN_BIN" "$@"; }
check() { # check "desc" "expected_substr" <<< actual
  local desc="$1" exp="$2"; local got; got="$(cat)"
  if printf '%s' "$got" | grep -qF -- "$exp"; then
    printf '  \033[32mok\033[0m   %s\n' "$desc"; PASS=$((PASS+1))
  else
    printf '  \033[31mFAIL\033[0m %s\n       expected to contain: %s\n       got: %s\n' "$desc" "$exp" "$got"; FAIL=$((FAIL+1))
  fi
}

echo "Brain Memory Layer — conformance test"
echo "DB: $BRAIN_DB"

check "init"           "schema v1"      <<< "$(b init --owner tester 2>&1)"
check "doctor (empty)" "passed"         <<< "$(b doctor 2>&1)"

b add "Use trunk-based development everywhere" --type decision --level global --confidence verified >/dev/null
check "add learning"   "added"          <<< "$(b learn '[GOTCHA] Flyway needs explicit baseline on legacy DBs' --level repo --scope billing 2>&1)"
check "dedup"          "duplicate"      <<< "$(b learn '[GOTCHA] Flyway needs explicit baseline on legacy DBs' --level repo --scope billing 2>&1)"

check "search finds"   "trunk-based"    <<< "$(b search 'trunk based development' 2>&1)"
check "search json"    '"id"'           <<< "$(b search 'flyway' --json --no-reinforce 2>&1)"
check "search level"   "flyway"         <<< "$(b search 'flyway' --level repo --no-reinforce 2>&1)"

check "get by prefix"  "trunk-based"    <<< "$(b get 'global/decision/use-trunk' --no-reinforce 2>&1)"

b add "Adopt mob programming Fridays" --type decision --level global >/dev/null
check "link"           "relates_to"     <<< "$(b link 'global/decision/use-trunk' 'global/decision/adopt-mob' --type relates_to 2>&1)"
check "traverse"       "adopt-mob"      <<< "$(b traverse 'global/decision/use-trunk' 2>&1)"

check "supersede"      "supersedes"     <<< "$(b supersede 'global/decision/use-trunk' 'global/decision/adopt-mob' 2>&1)"
check "stale shown"    "superseded"     <<< "$(b search 'trunk' --no-reinforce 2>&1)"

check "confidence"     "= observed"     <<< "$(b confidence 'global/decision/adopt-mob' observed 2>&1)"
check "forget"         "tombstoned"     <<< "$(b forget 'repo/billing' 2>&1)"
check "sleep"          "sleep complete" <<< "$(b sleep 2>&1)"
check "stats"          "memories:"      <<< "$(b stats 2>&1)"

EXPORT_DIR="$(dirname "$BRAIN_DB")/export"
check "export"         "exported"       <<< "$(b export "$EXPORT_DIR" 2>&1)"
check "doctor (final)" "passed"         <<< "$(b doctor 2>&1)"

# Ambiguity must fail loudly.
b add "Cache layer A" --type note --level global >/dev/null
b add "Cache layer B" --type note --level global >/dev/null
check "ambiguous ref"  "ambiguous"      <<< "$(b get 'cache-layer' --no-reinforce 2>&1)"

echo
echo "Result: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
