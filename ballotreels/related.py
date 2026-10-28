"""Related measures: data/related.toml.

Hand-curated groups of measures on the same subject, each a named list
of contest ids. Membership is symmetric: every measure in a group is
related to every other member, and a pair two groups share counts once.
The group names are internal and never shown to readers.
"""

from __future__ import annotations

import tomllib
from pathlib import Path


class RelatedError(Exception):
    """A related.toml that cannot be loaded, or a group that breaks a
    rule of its format."""


def load_related(path: str | Path) -> dict[str, tuple[str, ...]]:
    """The groups in `path`, by name; none if there is no such file."""
    path = Path(path)
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as e:
        raise RelatedError(f"{path}: {e}") from None
    groups: dict[str, tuple[str, ...]] = {}
    for name, ids in data.items():
        where = f"{path}: group {name!r}"
        if not isinstance(ids, list) or not all(isinstance(i, str)
                                                for i in ids):
            raise RelatedError(f"{where}: must be a list of contest ids")
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            raise RelatedError(f"{where}: repeats {', '.join(repeated)}")
        groups[name] = tuple(ids)
    return groups


def related_to(groups: dict[str, tuple[str, ...]],
               contest_id: str) -> set[str]:
    """Every contest sharing a group with `contest_id`, never itself."""
    out: set[str] = set()
    for ids in groups.values():
        if contest_id in ids:
            out.update(ids)
    out.discard(contest_id)
    return out


def unknown_ids(groups: dict[str, tuple[str, ...]],
                known: set[str]) -> list[str]:
    """The ids in `groups` that are not in `known`, in file order."""
    return list(dict.fromkeys(i for ids in groups.values() for i in ids
                              if i not in known))
