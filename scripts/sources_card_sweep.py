"""Lists the contests under data/ whose closing sources card, written at
its usual speed, is not done SOURCES_HOLD before the film's last frame:
those the measure film now writes faster, so their videos change when
re-rendered. Not used by the render. Run from the repo root:

    .venv/bin/python -B scripts/sources_card_sweep.py
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ballotreels.contest import load_contest  # noqa: E402
from ballotreels.storyboard import SOURCES_CARD_SECONDS, cited_sources  # noqa: E402
from film import measure as m  # noqa: E402

END = m.to_frame(SOURCES_CARD_SECONDS, m.FPS)  # the card's length; it starts at 0
DONE_BY = END - 1 - m.to_frame(m.SOURCES_HOLD, m.FPS)


def last_write(cited):
    """The card's last written frame at its usual speed, in either format."""
    with mock.patch.object(m, 'BOARD', SimpleNamespace(cited=cited)):
        return max(it.f1 for fmt in m.LAYOUTS for it in m.sources_card(m.LAYOUTS[fmt], 8, 10 ** 6)[0])


def main():
    unfinished, short_hold = [], []
    for d in sorted(p.parent for p in Path('data').glob('*/*/script.toml')):
        cited = cited_sources(load_contest(d))
        last = last_write(cited)
        cid = f'{d.parent.name}/{d.name}'
        if last > END - 1:
            unfinished.append(f'{cid}  ({len(cited)} sources)')
        elif last > DONE_BY:
            short_hold.append(f'{cid}  ({len(cited)} sources, still {(END - 1 - last) / m.FPS:.2f} s)')
    print(f'Unfinished at the last frame ({len(unfinished)}):')
    print('\n'.join(f'  {c}' for c in unfinished))
    print(f'Finished, but still for under {m.SOURCES_HOLD} s ({len(short_hold)}):')
    print('\n'.join(f'  {c}' for c in short_hold))


if __name__ == '__main__':
    main()
