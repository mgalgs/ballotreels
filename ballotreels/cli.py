"""Command line:

    python -m ballotreels check <contest-dir>...
    python -m ballotreels narration <contest-dir>...
    python -m ballotreels render <contest-dir> [--format 9x16|16x9|all]
    python -m ballotreels measures ca-sos <election-dir> [--base-url URL]
    python -m ballotreels geo build [--state ca] [--data-dir DIR]
    python -m ballotreels geo zip <zip> [--state ca] [--data-dir DIR]
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

from .adapters.ca_sos import append_entries, build_contest_entries, fetch_measures
from .checks import check_contest, word_count
from .contest import ContestError, load_contest
from .index import ContestIndexError, load_index
from .narration import narration_text
from .standard import load_standard, side_order

REPO_ROOT = Path(__file__).resolve().parent.parent
FILM_TEMPLATE = REPO_ROOT / "film" / "measure.py"
CA_SOS_BASE_URL = "https://voterguide.sos.ca.gov"


def default_data_dir() -> Path:
    env = os.environ.get("BALLOTREELS_DATA_DIR")
    return Path(env) if env else REPO_ROOT / "var"


def _check_one(path: str, standard, out) -> bool:
    try:
        contest = load_contest(path)
    except ContestError as e:
        print(f"{path}: {e}", file=out)
        print(f"FAIL {path}: could not load", file=out)
        return False
    failures = check_contest(contest, standard)
    for f in failures:
        print(f"{path}: {f}", file=out)
    words = " ".join(f"{label}={word_count(s)}"
                     for label, s in contest.script.labelled())
    status = (f"FAIL {contest.id}: {len(failures)} failure"
              f"{'' if len(failures) == 1 else 's'}"
              if failures else f"PASS {contest.id}")
    summary = f"{status}; words {words}"
    if contest.script.template == "measure":
        summary += f"; {side_order(contest.id)[0]} plays first"
    print(summary, file=out)
    return not failures


def _narration_one(path: str, out) -> bool:
    try:
        contest = load_contest(path)
    except ContestError as e:
        print(f"{path}: {e}", file=out)
        print(f"FAIL {path}: could not load", file=out)
        return False
    text = narration_text(contest)
    dest = Path(path) / "narration.txt"
    dest.write_text(text, encoding="utf-8")
    print(f"{dest}: wrote {len(text.splitlines())} lines", file=out)
    return True


def _render_one(path: str, fmt_arg: str, out_dir: Path, out) -> bool:
    try:
        contest = load_contest(path)
    except ContestError as e:
        print(f"{path}: {e}", file=out)
        print(f"FAIL {path}: could not load", file=out)
        return False
    try:
        import videobuilder as vb
        from videobuilder.render import render
    except ImportError as e:
        print(f"{path}: videobuilder is required to render ({e})", file=out)
        return False
    # The film template reads the contest from this; see film/measure.py.
    os.environ["BALLOTREELS_CONTEST"] = str(Path(path).resolve())
    film = vb.load(str(FILM_TEMPLATE))
    fmts = film.formats if fmt_arg == "all" else [film.format(fmt_arg)]
    out_dir.mkdir(parents=True, exist_ok=True)
    for fmt in fmts:
        dest = out_dir / f"{contest.id}-{fmt.name}.mp4"
        render(film, str(dest), format=fmt, log=out)
        print(f"wrote {dest}", file=out)
    return True


def _fetch_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _measures_ca_sos(election_dir: str, base_url: str, start: str, out,
                     fetch=_fetch_url) -> bool:
    try:
        index = load_index(election_dir)
    except ContestIndexError as e:
        print(f"{election_dir}: {e}", file=out)
        return False
    try:
        measures = fetch_measures(fetch, base_url, start)
    except Exception as e:
        print(f"could not fetch measures: {e}", file=out)
        return False
    entries = build_contest_entries(
        index.election.id, index.election.state, measures)
    path = Path(election_dir) / "contests.toml"
    n = append_entries(path, entries)
    print(f"{path}: appended {n} measure(s)", file=out)
    return True


def _fetch_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def _geo_build(data_dir: str, state: str, min_overlap: float,
               tolerance: float, url_overrides: list[str], out,
               fetch=_fetch_bytes) -> bool:
    from .geo.build import BuildError, build
    urls = {}
    for pair in url_overrides:
        name, _, url = pair.partition("=")
        urls[name] = url
    try:
        warnings = build(data_dir, state, fetch, urls=urls,
                         min_overlap=min_overlap, tolerance=tolerance)
    except BuildError as e:
        print(str(e), file=out)
        return False
    for warning in warnings:
        print(f"warning: {warning}", file=out)
    print(f"{Path(data_dir) / 'geo' / state}: built", file=out)
    return True


def _geo_zip(data_dir: str, state: str, zip_code: str, out) -> bool:
    from .geo.lookup import GeoData
    geo_dir = Path(data_dir) / "geo" / state
    geo = GeoData.load(geo_dir)
    result = geo.zip_districts(zip_code)
    if result is None:
        print(f"{zip_code}: no district data for this zip", file=out)
        return False
    for kind, entries in result["kinds"].items():
        for e in entries:
            print(f"{kind}\t{e['ocd_id']}\t{e['name']}", file=out)
    return True


def main(argv: list[str] | None = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="python -m ballotreels")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser(
        "check", help="run the standard's machine checks on contests")
    check.add_argument("contests", nargs="+", metavar="contest-dir")
    narration = sub.add_parser(
        "narration",
        help="write narration.txt: each script line's text, one per line, "
             "in playback order, for `videobuilder say`")
    narration.add_argument("contests", nargs="+", metavar="contest-dir")
    render = sub.add_parser(
        "render", help="render the contest's video with videobuilder")
    render.add_argument("contest", metavar="contest-dir")
    render.add_argument("--format", choices=["9x16", "16x9", "all"],
                        default="all")
    render.add_argument("--out", default="out", metavar="DIR",
                        help="output directory (default: out/)")
    measures = sub.add_parser(
        "measures", help="build or extend a contest index from a source")
    measures_sub = measures.add_subparsers(dest="measures_command",
                                            required=True)
    ca_sos = measures_sub.add_parser(
        "ca-sos",
        help="add California statewide measures from the Secretary of "
             "State's official voter information guide")
    ca_sos.add_argument("election_dir", metavar="election-dir")
    ca_sos.add_argument("--base-url", default=CA_SOS_BASE_URL)
    ca_sos.add_argument("--start", default="1",
                        help="a known proposition number to start from "
                             "(default: 1)")
    geo = sub.add_parser("geo", help="district and zip-code geo data")
    geo_sub = geo.add_subparsers(dest="geo_command", required=True)
    geo_build = geo_sub.add_parser(
        "build", help="download and build geo data under --data-dir")
    geo_build.add_argument("--state", default="ca",
                           help="2-letter state abbreviation (default: ca)")
    geo_build.add_argument("--data-dir", default=str(default_data_dir()),
                           help="default: $BALLOTREELS_DATA_DIR or "
                                "<repo>/var")
    geo_build.add_argument("--min-overlap", type=float, default=0.0,
                           metavar="FRACTION",
                           help="drop a zip/district overlap smaller than "
                                "this fraction of the zip's land area "
                                "(default: 0, keep every sliver)")
    geo_build.add_argument("--tolerance", type=float, default=0.001,
                           metavar="DEGREES",
                           help="Douglas-Peucker simplification tolerance, "
                                "in degrees (default: 0.001)")
    geo_build.add_argument("--url", action="append", default=[],
                           metavar="NAME=URL",
                           help="override one download, e.g. "
                                "cd.zip=https://...")
    geo_zip = geo_sub.add_parser(
        "zip", help="print the candidate districts for a zip code")
    geo_zip.add_argument("zip", metavar="zip-code")
    geo_zip.add_argument("--state", default="ca")
    geo_zip.add_argument("--data-dir", default=str(default_data_dir()))
    args = parser.parse_args(argv)

    if args.command == "narration":
        ok = True
        for path in args.contests:
            ok = _narration_one(path, out) and ok
        return 0 if ok else 1

    if args.command == "render":
        ok = _render_one(args.contest, args.format, Path(args.out), out)
        return 0 if ok else 1

    if args.command == "check":
        standard = load_standard()
        ok = True
        for path in args.contests:
            ok = _check_one(path, standard, out) and ok
        return 0 if ok else 1

    if args.command == "measures":
        ok = _measures_ca_sos(args.election_dir, args.base_url, args.start,
                              out)
        return 0 if ok else 1

    if args.command == "geo":
        if args.geo_command == "build":
            ok = _geo_build(args.data_dir, args.state, args.min_overlap,
                            args.tolerance, args.url, out)
        else:
            ok = _geo_zip(args.data_dir, args.state, args.zip, out)
        return 0 if ok else 1

    raise AssertionError(f"unhandled command {args.command!r}")
