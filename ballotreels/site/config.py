"""Serve-tier configuration: flag > environment variable > default for
every option (every name here is documented in the README)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_ROOT = REPO_ROOT / "data"

DEFAULT_SITE_URL = "https://ballotreels.org"


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


def _join(value):
    """A repeatable flag's list as one comma-separated string."""
    if isinstance(value, (list, tuple)):
        return ",".join(value) if value else None
    return value


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
    generate_global_limit: int = 30
    require_approval: bool = True
    # The base of the absolute URLs in link-preview tags; never taken
    # from a request's Host header.
    site_url: str = DEFAULT_SITE_URL


def load_config(args) -> Config:
    token = os.environ.get("BALLOTREELS_TOKEN")
    if token is not None and not token.strip():
        token = None
    return Config(
        data_dir=Path(_resolve(args.data_dir, "BALLOTREELS_DATA_DIR",
                               str(REPO_ROOT / "var"), str)),
        election=_resolve(_join(args.election), "BALLOTREELS_ELECTION",
                          None, str),
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
        generate_global_limit=_resolve(
            getattr(args, "generate_global_limit", None),
            "BALLOTREELS_GENERATE_GLOBAL_LIMIT", 30, int),
        require_approval=_resolve(getattr(args, "require_approval", None),
                                  "BALLOTREELS_REQUIRE_APPROVAL", True,
                                  _bool),
        site_url=_resolve(getattr(args, "site_url", None),
                          "BALLOTREELS_SITE_URL", DEFAULT_SITE_URL,
                          str).rstrip("/"),
    )


class ElectionResolutionError(Exception):
    """The elections to serve could not be chosen: none found, or an
    unknown one named."""


def election_names(election: str | None) -> list[str]:
    """The names in a comma-separated --election / BALLOTREELS_ELECTION
    value (empty: serve every election)."""
    return [n.strip() for n in (election or "").split(",") if n.strip()]


def resolve_election_dirs(election: str | None,
                          data_root: Path | None = None) -> list[Path]:
    """The election directories to serve: the ones named in `election`
    (comma-separated), or else every `data/*/contests.toml`."""
    if data_root is None:
        data_root = DATA_ROOT  # a live lookup, so tests can monkeypatch it
    names = election_names(election)
    if names:
        missing = [n for n in names
                   if not (data_root / n / "contests.toml").is_file()]
        if missing:
            raise ElectionResolutionError(
                f"no such election {', '.join(map(repr, missing))} "
                f"under {data_root}")
        return [data_root / n for n in dict.fromkeys(names)]
    candidates = sorted(p.parent.name for p in data_root.glob("*/contests.toml"))
    if not candidates:
        raise ElectionResolutionError(f"no elections found under {data_root}")
    return [data_root / c for c in candidates]


# D.C.'s own OCD-ID is `district:dc`; the site uses `state:dc`, and
# accepts either.
_STATE_RE = re.compile(r"/(?:state|district):([a-z]{2})(?:/|$)")


def state_abbr(division: str) -> str | None:
    """The 2-letter state abbreviation in an OCD-ID, or None."""
    m = _STATE_RE.search(division)
    return m.group(1) if m else None
