# Drawing-sound recordings

Two short excerpts, used by `film/draw_sound.py` as the raw bed each pencil
or highlighter stroke slices its sound from.

| File | Source | Trim |
|---|---|---|
| `pencil.wav` | [3234-pencil-3](https://www.bigsoundbank.com/sound-3234-pencil-3.html) (BigSoundBank) | seconds 1.0-5.5 of the original, resampled to mono 24 kHz |
| `highlighter.wav` | [0220-marker](https://www.bigsoundbank.com/sound-0220-marker.html) (BigSoundBank) | seconds 17.0-21.5 of the original, resampled to mono 24 kHz |

Both originals are released by BigSoundBank under CC0 (no rights reserved;
no attribution required), per each sound's own page. The trims keep the
part of the recording where the tool is audibly moving on paper, dropping
the silence and handling noise at the start and end of each original file.
The marker excerpt still has two short gaps inside it where the marker
lifts off the paper (about 1.1-1.55 s and 3.55-3.9 s), and a quiet first
0.1 s; `film/draw_sound.py` cuts those out when it loads the file
(`_drop_gaps`), so no stroke ever plays one.
