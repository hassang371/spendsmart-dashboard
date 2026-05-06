#!/usr/bin/env bash
# Mirror orchestra-dev/ (SCALE) -> orchestra/docs/ (orchestra repo)
# Run after each material edit. SCALE is source of truth during v1.1 dev phase.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST="${SRC}/../../orchestra/docs"

if [[ ! -d "${DST}" ]]; then
  echo "Error: ${DST} does not exist. Run from SCALE/orchestra-dev/." >&2
  exit 1
fi

rsync -av --delete \
  --exclude 'sync-orchestra-dev.sh' \
  --exclude '.DS_Store' \
  "${SRC}/" "${DST}/"

echo ""
echo "Synced: ${SRC}/ -> ${DST}/"
echo "Next: cd ${DST}/.. && git status"
