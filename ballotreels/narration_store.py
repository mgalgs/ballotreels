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


class TakeCache:
    """A local copy of the store, the same shape as the serve tier's:
    `<root>/<sha256>.wav`. Outside git; anything here can be fetched again."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def path(self, sha: str) -> Path:
        return self.root / f"{sha}.wav"

    def get(self, take: Take) -> Path | None:
        """The cached file for `take`, or None when there is none, or only
        one whose bytes are not that take's (it is dropped)."""
        path = self.path(take.sha256)
        if not path.is_file():
            return None
        if hash_file(path) != take:
            path.unlink(missing_ok=True)
            return None
        return path

    def put(self, take: Take, data: bytes) -> Path:
        path = self.path(take.sha256)
        self.root.mkdir(parents=True, exist_ok=True)
        _write_atomic(path, data)
        return path


def _mismatch(where, take: Take, got: Take, what: str) -> TakeError:
    return TakeError(
        f"{where}: {what} is not narration take {take.sha256} "
        f"({take.bytes} bytes) that narration.json records: its SHA-256 is "
        f"{got.sha256} ({got.bytes} bytes)")


def materialize(contest_dir: str | Path, cache: TakeCache, client=None,
                where: str | None = None) -> str:
    """Put the take narration.json records at `contest_dir/narration.wav`:
    from `cache`, else downloaded through `client` (a worker.WorkerClient)
    and cached, checked against its hash either way. Returns how: "none"
    (narration.json records no take), "present" (the right audio is
    already there), "cache" or "server". Raises TakeError naming `where`
    (default: the directory) and the hash when the take is nowhere to be
    had, or when the audio found is not that take; a narration.wav already
    there that is not the take is never replaced."""
    contest_dir = Path(contest_dir)
    where = where or str(contest_dir)
    take = recorded_take(contest_dir)
    if take is None:
        return "none"
    wav = contest_dir / "narration.wav"
    if wav.is_file():
        got = hash_file(wav)
        if got != take:
            raise _mismatch(where, take, got, "the narration.wav beside it")
        return "present"
    cached = cache.get(take)
    if cached is not None:
        _write_atomic(wav, cached.read_bytes())
        return "cache"
    if client is None:
        raise TakeError(
            f"{where}: narration take {take.sha256} is not in the local "
            f"cache ({cache.root}), and no server was given to fetch it from")
    data = client.narration_get(take.sha256)
    if data is None:
        raise TakeError(
            f"{where}: narration take {take.sha256} is not on the server; "
            f"upload it from a checkout that has it with `python -m "
            f"ballotreels narration push`")
    got = hash_bytes(data)
    if got != take:
        raise _mismatch(where, take, got, "the audio the server sent")
    cache.put(take, data)
    _write_atomic(wav, data)
    return "server"
