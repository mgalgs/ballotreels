#!/usr/bin/env bash
# Rasterise the site icons into ../static from favicon.svg and
# full-bleed.svg. Needs rsvg-convert and ImageMagick (magick).
set -euo pipefail
here=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
static="$here/../static"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

for size in 16 32 48; do
    rsvg-convert -w "$size" -h "$size" "$static/favicon.svg" \
        -o "$tmp/favicon-$size.png"
done
magick "$tmp/favicon-16.png" "$tmp/favicon-32.png" "$tmp/favicon-48.png" \
    "$static/favicon.ico"
rsvg-convert -w 180 -h 180 "$here/full-bleed.svg" \
    -o "$static/apple-touch-icon.png"
for size in 192 512; do
    rsvg-convert -w "$size" -h "$size" "$here/full-bleed.svg" \
        -o "$static/icon-$size.png"
done
