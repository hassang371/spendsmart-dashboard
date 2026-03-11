#!/bin/bash
# next_doc_number.sh — Get the next auto-incremented doc number
# Usage: ./next_doc_number.sh <type>
#   type: features | bugs | rfcs

set -e

TYPE="${1:?Usage: next_doc_number.sh <features|bugs|rfcs>}"
DOCS_DIR="$(git rev-parse --show-toplevel)/docs"

case "$TYPE" in
  features)
    DIR="$DOCS_DIR/features"
    PREFIX=""
    ;;
  bugs)
    DIR="$DOCS_DIR/bugs"
    PREFIX="BUG-"
    ;;
  rfcs)
    DIR="$DOCS_DIR/rfcs"
    PREFIX="RFC-"
    ;;
  *)
    echo "Error: Unknown type '$TYPE'. Use: features, bugs, or rfcs" >&2
    exit 1
    ;;
esac

# Create dir if it doesn't exist
mkdir -p "$DIR"

# Find the highest number
HIGHEST=$(ls "$DIR" 2>/dev/null | grep -oE '^[A-Z]*-?[0-9]+' | grep -oE '[0-9]+' | sort -n | tail -1)

if [ -z "$HIGHEST" ]; then
  NEXT=1
else
  NEXT=$((HIGHEST + 1))
fi

# Pad to 3 digits
printf "%s%03d\n" "$PREFIX" "$NEXT"
