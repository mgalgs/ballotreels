"""An election's divisions.tsv: every county, incorporated place and
school district the geo build has a shape for, as `<ocd-id>\t<display
name>` lines, sorted. `check` refuses a local contest whose division is
not listed there (ballotreels.checks.check_division), since the zip
lookup could never show it to a voter.

Written from `geo build`'s output (<data-dir>/geo/<state>/), so it needs
no download.
"""

from __future__ import annotations

import json
from pathlib import Path

# The division levels listed, each with the shapes file `geo build`
# writes for it.
LEVELS = ("county", "place", "school_district")

FILENAME = "divisions.tsv"


class DivisionsError(Exception):
    """A geo build that cannot be read for its divisions."""


def division_lines(geo_dir: str | Path) -> list[str]:
    """One `<ocd-id>\t<name>` line per district shape in `geo_dir`, of
    every LEVEL, sorted. A name shared by districts in different places
    (two "Jefferson Elementary School District"s) is one line per shape,
    as the build has them."""
    geo_dir = Path(geo_dir)
    lines = []
    for level in LEVELS:
        path = geo_dir / f"{level}.geojson"
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise DivisionsError(f"{path}: cannot read ({e}); run "
                                 f"`python -m ballotreels geo build` "
                                 f"first") from None
        for feature in doc.get("features", ()):
            props = feature.get("properties") or {}
            division, name = props.get("ocd_id"), props.get("name")
            if not division or not name:
                raise DivisionsError(
                    f"{path}: a feature has no ocd_id or name")
            lines.append(f"{division}\t{name}")
    return sorted(lines)


def write_divisions(geo_dir: str | Path, election_dir: str | Path) -> Path:
    """Writes `<election_dir>/divisions.tsv` from `geo_dir`; returns its
    path."""
    lines = division_lines(geo_dir)
    out = Path(election_dir) / FILENAME
    part = out.with_name(out.name + ".part")
    part.write_text("".join(f"{l}\n" for l in lines), encoding="utf-8",
                    newline="\n")
    part.replace(out)
    return out


def read_divisions(path: str | Path) -> dict[str, str]:
    """divisions.tsv's ocd-id -> display name."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        division, _, name = line.partition("\t")
        if division:
            out.setdefault(division, name)
    return out
