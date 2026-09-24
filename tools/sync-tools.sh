#!/usr/bin/env bash
# Copy the ops tooling and its records into the game repo under tools/ (run after each phase merge).
set -euo pipefail
OPS="$(cd "$(dirname "$0")" && pwd)"
DEST="$OPS/../swarm-control/tools"
mkdir -p "$DEST/prompts" "$DEST/records" "$DEST/shots"
cp "$OPS"/swarm.py "$OPS"/playtest.py "$OPS"/dashboard.html "$OPS"/sync-tools.sh "$DEST/"
cp "$OPS"/prompts/*.md "$DEST/prompts/"
cp "$OPS"/data/events.jsonl "$OPS"/data/ledger.jsonl "$DEST/records/"
for d in "$OPS"/shots/*/; do n=$(basename "$d"); mkdir -p "$DEST/shots/$n"; cp "$d"*.png "$DEST/shots/$n/" 2>/dev/null || true; done
echo "synced to $DEST"
