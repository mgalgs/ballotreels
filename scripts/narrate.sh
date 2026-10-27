#!/usr/bin/env bash
# Narrate one or more contests: export each script's narration text, then
# synthesize it with videobuilder's Gemini engine in the one narrator voice.
#
# Usage: scripts/narrate.sh <contest-dir>...
#
# Needs the project .venv (see README.md) and GEMINI_API_KEY. The transcript
# check that catches a reworded take runs faster-whisper in the Chatterbox
# interpreter, found at $VIDEOBUILDER_CHATTERBOX_PYTHON or else
# ~/.local/chatterbox/bin/python (videobuilder's README has the install).
set -euo pipefail

repo=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
python="$repo/.venv/bin/python"
export VIDEOBUILDER_CHATTERBOX_PYTHON="${VIDEOBUILDER_CHATTERBOX_PYTHON:-$HOME/.local/chatterbox/bin/python}"

if [ $# -eq 0 ]; then
    echo "usage: $0 <contest-dir>..." >&2
    exit 2
fi

style=$(cat "$repo/voices/narration-style.txt")

for dir in "$@"; do
    "$python" -m ballotreels narration "$dir"
    "$python" -m videobuilder say "$dir/narration.txt" \
        --engine gemini --voice Rasalgethi --style "$style" --gap 0.6 \
        --out "$dir/narration.wav"
done
