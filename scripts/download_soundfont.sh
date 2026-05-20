#!/usr/bin/env bash
# Download GeneralUser GS SoundFont (~31 MB, CC0/GPL-compatible).
# Bank 0, Preset 0 is Acoustic Grand Piano.
set -euo pipefail

DEST_DIR="$(cd "$(dirname "$0")/.." && pwd)/soundfonts"
DEST="$DEST_DIR/GeneralUser.sf2"
URL="https://raw.githubusercontent.com/bratpeki/soundfonts/main/SF2/GM/GeneralUser.sf2"

mkdir -p "$DEST_DIR"

if [[ -f "$DEST" ]]; then
  size=$(stat -f%z "$DEST" 2>/dev/null || stat -c%s "$DEST")
  if [[ "$size" -gt 30000000 ]]; then
    echo "Already have $DEST ($(($size / 1024 / 1024)) MB) — skipping."
    exit 0
  fi
  echo "Existing file looks truncated ($size bytes), re-downloading."
fi

echo "Downloading SoundFont -> $DEST"
curl -L --progress-bar "$URL" -o "$DEST"
echo "Done: $(ls -lh "$DEST" | awk '{print $5}')"
