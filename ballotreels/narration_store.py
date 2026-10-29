"""Where narration audio lives: not in git. A contest's narration.json
records its take's identity, the SHA-256 of narration.wav's bytes and its
length (under "take"; videobuilder's own top-level "sha256" hashes the
decoded samples, not the file), and the audio itself is kept by that hash:
in the serve tier's store, `<data-dir>/narration/<sha256>.wav`, reached
through the private listener's /worker/narration/<sha256> routes, and in a
local cache of the same shape on each machine that needs it.

A contest is narrated when its narration.json records a take. Wherever a
stage reads `<contest>/narration.wav`, `materialize` first puts the take
there, from the cache or the server, checked against its hash.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

TAKE_KEY = "take"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
# Longest take the store accepts. A real one is ~5 MB (the long Prop 2
# fixture, ~3.5 minutes, is 10 MB).
MAX_TAKE_BYTES = 64 * 1024 * 1024
_CHUNK = 1024 * 1024


class TakeError(Exception):
    """A take that is missing, unreadable, or not the bytes its hash
    names; the message names the contest and the hash."""


@dataclass(frozen=True)
class Take:
    sha256: str
    bytes: int


def hash_file(path: str | Path) -> Take:
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
            n += len(chunk)
    return Take(h.hexdigest(), n)


def hash_bytes(data: bytes) -> Take:
    return Take(hashlib.sha256(data).hexdigest(), len(data))


def _read_sidecar(contest_dir: Path) -> dict | None:
    path = Path(contest_dir) / "narration.json"
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def recorded_take(contest_dir: str | Path) -> Take | None:
    """The take narration.json records, or None when there is no
    narration.json or it records none (yet: `narration record`)."""
    doc = _read_sidecar(Path(contest_dir))
    take = doc.get(TAKE_KEY) if doc is not None else None
    if not isinstance(take, dict):
        return None
    sha, size = take.get("sha256"), take.get("bytes")
    if (not isinstance(sha, str) or not SHA256_RE.fullmatch(sha)
            or not isinstance(size, int) or isinstance(size, bool)):
        return None
    return Take(sha, size)


def _write_atomic(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def record(contest_dir: str | Path) -> bool:
    """Write narration.wav's hash and length into narration.json; True
    when that changed narration.json. Raises TakeError when either file
    is missing."""
    contest_dir = Path(contest_dir)
    wav = contest_dir / "narration.wav"
    sidecar = contest_dir / "narration.json"
    if not sidecar.is_file():
        raise TakeError(f"{contest_dir}: no narration.json")
    if not wav.is_file():
        raise TakeError(f"{contest_dir}: no narration.wav to record")
    doc = json.loads(sidecar.read_text(encoding="utf-8"))
    take = hash_file(wav)
    want = {"sha256": take.sha256, "bytes": take.bytes}
    if doc.get(TAKE_KEY) == want:
        return False
    doc[TAKE_KEY] = want
    # as videobuilder's `say` writes it, so a diff shows only this key
    _write_atomic(sidecar, (json.dumps(doc, indent=2, ensure_ascii=False)
                            + "\n").encode("utf-8"))
    return True
