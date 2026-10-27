"""A choice question's grid pages: how its options are laid out on the
film's one grid slide (docs/SCRIPT-FORMAT.md, STANDARD.md section 8).

Pure arithmetic, shared by the checks (one `choices` visual per page) and
the film (film/measure.py draws each page). A grid is (columns, rows) on
the 9:16 portrait frame: "1x2" is one column of two stacked cells, "2x3"
two columns by three rows. Only four exist, and a page takes the smallest
that holds its options; more than PER_PAGE options go on several pages,
split as evenly as possible in ballot order, earlier pages taking any
extra one.
"""

from __future__ import annotations

import math

# (columns, rows), smallest first
GRIDS = ((1, 2), (1, 3), (2, 2), (2, 3))
PER_PAGE = max(c * r for c, r in GRIDS)


def grid_for(count: int) -> tuple[int, int]:
    """The smallest grid holding `count` options (1 to PER_PAGE): 2 -> 1x2,
    3 -> 1x3, 4 -> 2x2, 5 or 6 -> 2x3. One option, which no question has,
    takes the smallest."""
    if not 1 <= count <= PER_PAGE:
        raise ValueError(f"a grid page holds 1 to {PER_PAGE} options, "
                         f"not {count}")
    return next(g for g in GRIDS if g[0] * g[1] >= count)


def page_sizes(count: int) -> tuple[int, ...]:
    """How many options each grid page shows, in order: ceil(count /
    PER_PAGE) pages, as even as possible, the earlier ones taking any
    extra (7 -> 4, 3; 8 -> 4, 4; 13 -> 5, 4, 4)."""
    if count < 1:
        return ()
    n = math.ceil(count / PER_PAGE)
    base, extra = divmod(count, n)
    return tuple(base + (1 if i < extra else 0) for i in range(n))


def pages(count: int) -> tuple[range, ...]:
    """The options (0-based indices in ballot order) on each grid page."""
    out = []
    start = 0
    for size in page_sizes(count):
        out.append(range(start, start + size))
        start += size
    return tuple(out)


def cells(count: int) -> tuple[tuple[int, int], ...]:
    """Where a page's `count` options sit, in ballot order: (column, row)
    in reading order, left to right then top to bottom, on grid_for(count).
    A partly filled grid leaves its last cells empty."""
    cols, _ = grid_for(count)
    return tuple((i % cols, i // cols) for i in range(count))
