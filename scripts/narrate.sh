#!/usr/bin/env bash
# Narrate one or more contests: export each script's narration text, then
# synthesize it with videobuilder's Gemini engine in the one narrator voice.
#
# Usage: scripts/narrate.sh <contest-dir>...
#
# The audio lives in the serve tier's narration store, by the SHA-256
# narration.json records (`python -m ballotreels narration record`, run here
# after each take); `python -m ballotreels narration push` uploads it.
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
    # `say` reuses the unchanged phrases of the take narration.json records,
    # so put that take's audio here first (from the local cache, or the
    # serve tier at $BALLOTREELS_SERVER with $BALLOTREELS_TOKEN): without
    # it every phrase would be synthesised afresh. That is all a failed
    # fetch costs (no server, a leftover take from an interrupted `say`),
    # so it warns and carries on.
    if ! "$python" -m ballotreels narration fetch "$dir"; then
        echo "$0: $dir: could not fetch its recorded take; every phrase" \
            "will be synthesised afresh" >&2
    fi
    "$python" -m videobuilder say "$dir/narration.txt" \
        --engine gemini --voice Rasalgethi --style "$style" --gap 0.6 \
        --out "$dir/narration.wav"
    # The new take's identity, in narration.json: commit that; upload the
    # audio with `python -m ballotreels narration push`.
    "$python" -m ballotreels narration record "$dir"
    # The airtime and transcript checks need the new take, so a narration
    # is not done until it passes here.
    "$python" -m ballotreels check "$dir"
done
