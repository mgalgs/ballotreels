"""The illustration library: film/illustrations/illustrations.toml.

A script's `illustration` visual names one of these entries
(docs/SCRIPT-FORMAT.md). Each is a checked-in pencil drawing, made once
with the manifest's style prompt and approved by a person.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

LIBRARY = Path(__file__).resolve().parent.parent / "film" / "illustrations"
MANIFEST = LIBRARY / "illustrations.toml"


@dataclass(frozen=True)
class Illustration:
    name: str
    file: str
    subject: str

    @property
    def path(self) -> Path:
        return LIBRARY / self.file


@cache
def load_library() -> dict[str, Illustration]:
    """Every entry in the manifest, by name."""
    with MANIFEST.open("rb") as f:
        data = tomllib.load(f)
    return {e["name"]: Illustration(e["name"], e["file"], e["subject"])
            for e in data.get("illustration", [])}
