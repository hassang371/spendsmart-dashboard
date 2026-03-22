#!/usr/bin/env bash
# Test suite for check-refs.sh — run with: bash scripts/test-check-refs.sh
set -e

SCRIPT="$(dirname "$0")/check-refs.sh"
PASS=0
FAIL=0

run_test() {
  local name="$1" msg="$2" expected_exit="$3"
  local tmpfile
  tmpfile=$(mktemp)
  printf "%s" "$msg" > "$tmpfile"
  local actual_exit=0
  bash "$SCRIPT" "$tmpfile" >/dev/null 2>&1 || actual_exit=$?
  rm -f "$tmpfile"
  if [ "$actual_exit" -eq "$expected_exit" ]; then
    echo "PASS: $name"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $name (expected exit $expected_exit, got $actual_exit)"
    FAIL=$((FAIL + 1))
  fi
}

# fix: without Refs: → must fail
run_test "fix without refs" "fix: something broken" 1

# feat: without Refs: → must fail
run_test "feat without refs" "feat: add feature" 1

# fix: with valid Refs: pointing to real file → must pass
REAL_DOC="docs/features/006-ci-cd-pipeline-hardening.md"
MSG="fix: something broken

Refs: ${REAL_DOC}"
run_test "fix with valid refs" "$MSG" 0

# fix: with Refs: pointing to non-existent file → must fail
MSG_MISSING="fix: something broken

Refs: docs/bugs/BUG-999-nonexistent.md"
run_test "fix with missing file" "$MSG_MISSING" 1

# chore: without Refs: → must pass (not required)
run_test "chore without refs" "chore: update deps" 0

# docs: without Refs: → must pass
run_test "docs without refs" "docs: update README" 0

# Merge commit → must pass
run_test "merge commit" "Merge branch 'feat/foo' into 'main'" 0

# fix: with Refs: pointing outside docs/ → must fail (only docs/ paths accepted)
MSG_OUTSIDE="fix: something broken

Refs: scripts/check-refs.sh"
run_test "fix with refs outside docs/" "$MSG_OUTSIDE" 1

# fix: with Refs: line present but empty path → must fail
MSG_EMPTY="fix: something broken

Refs: "
run_test "fix with empty refs path" "$MSG_EMPTY" 1

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
