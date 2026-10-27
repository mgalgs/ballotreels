#!/usr/bin/env bash
# Narrate one or more contests: export each script's narration text, then
# synthesize it with videobuilder's Chatterbox engine.
#
# Usage: scripts/narrate.sh <contest-dir>...
#
# Needs the project .venv (see README.md) and a Chatterbox interpreter, found
# at $VIDEOBUILDER_CHATTERBOX_PYTHON or else ~/.local/chatterbox/bin/python
# (videobuilder's README has the install).
set -euo pipefail

repo=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
python="$repo/.venv/bin/python"
export VIDEOBUILDER_CHATTERBOX_PYTHON="${VIDEOBUILDER_CHATTERBOX_PYTHON:-$HOME/.local/chatterbox/bin/python}"

if [ $# -eq 0 ]; then
    echo "usage: $0 <contest-dir>..." >&2
    exit 2
fi

for dir in "$@"; do
    "$python" -m ballotreels narration "$dir"
    "$python" -m videobuilder say "$dir/narration.txt" \
        --engine chatterbox --voice "$repo/voices/narrator.wav" --gap 1.0 --cfg-weight 0.3 \
        --out "$dir/narration.wav"
done
