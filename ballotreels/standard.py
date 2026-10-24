"""The even-handedness standard's machine-readable parts.

docs/STANDARD.md is the one home for the standard's version number and
standard/judgment-words.txt for the judgment-word list; this module reads
them rather than repeating them.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Allowed source kinds, as listed in docs/SCRIPT-FORMAT.md (a test keeps
# the two in step).
SOURCE_KINDS = frozenset({
    "official-title-summary",
    "official-fiscal-analysis",
    "official-argument",
    "official-text",
    "candidate-statement",
    "candidate-website",
    "public-record",
})

_VERSION_RE = re.compile(r"^Standard version:\s*(\d+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Standard:
    version: int
    judgment_words: tuple[str, ...]


def read_version(path: Path) -> int:
    """The version from the last `Standard version: N` line in `path`."""
    found = _VERSION_RE.findall(path.read_text(encoding="utf-8"))
    if not found:
        raise ValueError(f"{path}: no 'Standard version: N' line")
    return int(found[-1])


def read_judgment_words(path: Path) -> tuple[str, ...]:
    """The entries of a judgment-word list: one per line, `#` and blank
    lines skipped."""
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line)
    return tuple(words)


def load_standard(root: str | Path = REPO_ROOT) -> Standard:
    root = Path(root)
    return Standard(
        version=read_version(root / "docs" / "STANDARD.md"),
        judgment_words=read_judgment_words(
            root / "standard" / "judgment-words.txt"),
    )


def judgment_word_pattern(words: tuple[str, ...]) -> re.Pattern[str]:
    """One case-insensitive regex matching any entry as a whole word.

    An entry matches only where it is not part of a longer word (`fair`
    does not match `affair` or `unfair`), and the spaces inside a
    multi-word entry match any run of whitespace. Longer entries are tried
    first so the longest match is the one reported.
    """
    alts = [r"\s+".join(re.escape(part) for part in w.split())
            for w in sorted(words, key=len, reverse=True)]
    return re.compile(r"(?<!\w)(?:" + "|".join(alts) + r")(?!\w)",
                      re.IGNORECASE)


def side_order(contest_id: str) -> tuple[str, str]:
    """Which measure side plays first (STANDARD.md rule 2.4).

    SHA-256 of the UTF-8 contest id: first byte even, ("yes", "no");
    odd, ("no", "yes"). Stable across runs and machines.
    """
    first = hashlib.sha256(contest_id.encode("utf-8")).digest()[0]
    return ("yes", "no") if first % 2 == 0 else ("no", "yes")
