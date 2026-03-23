#!/usr/bin/env bash
# check-refs.sh — commit-msg hook
# Rejects fix:/feat: commits that lack a "Refs: docs/" line pointing to a real file.
#
# Usage (pre-commit passes commit message file path as $1):
#   bash scripts/check-refs.sh <commit-msg-file>

set -euo pipefail

COMMIT_MSG_FILE="$1"
FIRST_LINE=$(head -1 "$COMMIT_MSG_FILE")

# Only enforced on fix: and feat: prefixes
if [[ "$FIRST_LINE" != fix:* && "$FIRST_LINE" != feat:* ]]; then
  exit 0
fi

# Look for a "Refs: docs/" line anywhere in the message
REFS_LINE=$(grep -E '^Refs: docs/' "$COMMIT_MSG_FILE" || true)

if [ -z "$REFS_LINE" ]; then
  echo "ERROR: fix:/feat: commits require a 'Refs: docs/...' line."
  echo ""
  echo "Example:"
  echo "  fix: describe the fix"
  echo ""
  echo "  Refs: docs/bugs/BUG-NNN-name.md"
  exit 1
fi

# Extract path and verify the file exists
REFS_PATH=$(echo "$REFS_LINE" | sed 's/^Refs: //' | xargs)
if [ -z "$REFS_PATH" ]; then
  echo "ERROR: Refs: line is present but the path is empty."
  exit 1
fi
if [ ! -f "$REFS_PATH" ]; then
  echo "ERROR: Refs: points to non-existent file: $REFS_PATH"
  exit 1
fi

exit 0
