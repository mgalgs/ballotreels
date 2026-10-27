"""Serve-tier configuration: flag > environment variable > default for
every option (every name here is documented in the README)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_ROOT = REPO_ROOT / "data"

DEFAULT_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder"


def _resolve(flag, env_name: str, default, cast):
    if flag is not None:
        return cast(flag)
    raw = os.environ.get(env_name)
    if raw is not None and raw != "":
        return cast(raw)
    return default


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    data_dir: Path
    election: str | None
    public_host: str
    public_port: int
    private_host: str
    private_port: int
    token: str | None
    generate_limit: int
    generate_window: int
    trust_forwarded_for: bool
    heartbeat_timeout: float
    eta_default_minutes: float
    max_upload_mb: int
    geocoder_url: str
    generate_global_limit: int = 30
    address_limit: int = 30


def load_config(args) -> Config:
    token = os.environ.get("BALLOTREELS_TOKEN")
    if token is not None and not token.strip():
        token = None
    return Config(
        data_dir=Path(_resolve(args.data_dir, "BALLOTREELS_DATA_DIR",
                               str(REPO_ROOT / "var"), str)),
        election=_resolve(args.election, "BALLOTREELS_ELECTION", None, str),
        public_host=_resolve(args.public_host, "BALLOTREELS_PUBLIC_HOST",
                             "127.0.0.1", str),
        public_port=_resolve(args.public_port, "BALLOTREELS_PUBLIC_PORT",
                             8080, int),
        private_host=_resolve(args.private_host, "BALLOTREELS_PRIVATE_HOST",
                              "127.0.0.1", str),
        private_port=_resolve(args.private_port, "BALLOTREELS_PRIVATE_PORT",
                              8081, int),
        token=token,
        generate_limit=_resolve(args.generate_limit,
                                "BALLOTREELS_GENERATE_LIMIT", 5, int),
        generate_window=_resolve(args.generate_window,
                                 "BALLOTREELS_GENERATE_WINDOW", 3600, int),
        trust_forwarded_for=_resolve(args.trust_forwarded_for,
                                     "BALLOTREELS_TRUST_FORWARDED_FOR",
                                     False, _bool),
        heartbeat_timeout=_resolve(args.heartbeat_timeout,
                                   "BALLOTREELS_HEARTBEAT_TIMEOUT", 120.0,
                                   float),
        eta_default_minutes=_resolve(args.eta_default_minutes,
                                     "BALLOTREELS_ETA_DEFAULT_MINUTES", 10.0,
                                     float),
        max_upload_mb=_resolve(args.max_upload_mb, "BALLOTREELS_MAX_UPLOAD_MB",
                               500, int),
        geocoder_url=_resolve(args.geocoder_url, "BALLOTREELS_GEOCODER_URL",
                              DEFAULT_GEOCODER_URL, str),
        generate_global_limit=_resolve(
            getattr(args, "generate_global_limit", None),
            "BALLOTREELS_GENERATE_GLOBAL_LIMIT", 30, int),
        address_limit=_resolve(getattr(args, "address_limit", None),
                               "BALLOTREELS_ADDRESS_LIMIT", 30, int),
    )


class ElectionResolutionError(Exception):
    """No election could be chosen (A21): none found, an unknown one
    named, or several found with none named."""


def resolve_election_dir(election: str | None,
                         data_root: Path | None = None) -> Path:
    if data_root is None:
        data_root = DATA_ROOT  # a live lookup, so tests can monkeypatch it
    if election:
        path = data_root / election
        if not (path / "contests.toml").is_file():
            raise ElectionResolutionError(
                f"no such election {election!r} under {data_root}")
        return path
    candidates = sorted(p.parent.name for p in data_root.glob("*/contests.toml"))
    if not candidates:
        raise ElectionResolutionError(f"no elections found under {data_root}")
    if len(candidates) > 1:
        raise ElectionResolutionError("several elections; pass --election")
    return data_root / candidates[0]


_STATE_RE = re.compile(r"/state:([a-z]{2})(?:/|$)")


def state_abbr(division: str) -> str | None:
    """The 2-letter state abbreviation in an OCD-ID, or None."""
    m = _STATE_RE.search(division)
    return m.group(1) if m else None
