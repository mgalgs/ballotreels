"""Command line:

    python -m ballotreels check <contest-dir>...
    python -m ballotreels narration <contest-dir>...
    python -m ballotreels render <contest-dir> [--format 9x16|16x9|all]
    python -m ballotreels render <election-dir>   (its crash course, 9x16)
    python -m ballotreels measures ca-sos <election-dir> [--base-url URL]
    python -m ballotreels geo build [--state ca] [--data-dir DIR]
    python -m ballotreels geo zip <zip> [--state ca] [--data-dir DIR]
    python -m ballotreels serve [--public-port PORT] [--private-port PORT]
    python -m ballotreels worker --server URL [--runner fake|subprocess]
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
from .glance import check_glance
from .index import ContestIndexError, load_index
from .narration import narration_text
from .standard import load_standard, side_order

REPO_ROOT = Path(__file__).resolve().parent.parent
FILM_TEMPLATE = REPO_ROOT / "film" / "measure.py"
CRASH_COURSE_FILM = REPO_ROOT / "film" / "crash_course.py"
CA_SOS_BASE_URL = "https://voterguide.sos.ca.gov"


def default_data_dir() -> Path:
    env = os.environ.get("BALLOTREELS_DATA_DIR")
    return Path(env) if env else REPO_ROOT / "var"


def _default_worker_id() -> str:
    import socket
    return f"{socket.gethostname()}-{os.getpid()}"


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
    if contest.script.template == "measure" and contest.script.choices is None:
        summary += f"; {side_order(contest.id)[0]} plays first"
    print(summary, file=out)
    return not failures


def _check_glance(election_dir: Path, out) -> bool:
    """Check an election's glance.toml (docs/SCRIPT-FORMAT.md); true when
    it passes or the election has none yet."""
    failures = check_glance(election_dir)
    if failures is None:
        return True
    for f in failures:
        print(f"{election_dir}: {f}", file=out)
    name = election_dir.name
    print(f"FAIL glance {name}: {len(failures)} failure"
          f"{'' if len(failures) == 1 else 's'}" if failures
          else f"PASS glance {name}", file=out)
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


def _render_crash_course(path: str, fmt_arg: str, out_dir: Path, out,
                         site_url: str | None = None) -> bool:
    """Render the crash course of the election in `path` (9x16 only)."""
    from .crash_course import CrashCourseError, plan
    try:
        course = plan(path)
    except (CrashCourseError, ContestIndexError) as e:
        print(f"{path}: {e}", file=out)
        print(f"FAIL {path}: could not lay out its crash course", file=out)
        return False
    if fmt_arg not in ("9x16", "all"):
        print(f"{path}: a crash course is 9x16 only", file=out)
        return False
    try:
        import videobuilder as vb
        from videobuilder.render import render
    except ImportError as e:
        print(f"{path}: videobuilder is required to render ({e})", file=out)
        return False
    os.environ["BALLOTREELS_CRASH_COURSE"] = str(Path(path).resolve())
    if site_url:
        os.environ["BALLOTREELS_SITE_URL"] = site_url
    from .pipeline import write_chapters
    module = vb.load_module(str(CRASH_COURSE_FILM))
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{course.entry.id}-9x16.mp4"
    render(module.FILM, str(dest), format="9x16", log=out)
    print(f"wrote {dest}", file=out)
    print(f"wrote {write_chapters(dest, module.CHAPTERS)}", file=out)
    return True


def _render_one(path: str, fmt_arg: str, out_dir: Path, out,
                site_url: str | None = None) -> bool:
    from .crash_course import is_election_dir
    if is_election_dir(path):
        return _render_crash_course(path, fmt_arg, out_dir, out, site_url)
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
    # ...and the site's address, for the link it prints on every frame.
    if site_url:
        os.environ["BALLOTREELS_SITE_URL"] = site_url
    from .pipeline import write_chapters
    module = vb.load_module(str(FILM_TEMPLATE))
    film = module.FILM
    fmts = film.formats if fmt_arg == "all" else [film.format(fmt_arg)]
    out_dir.mkdir(parents=True, exist_ok=True)
    for fmt in fmts:
        dest = out_dir / f"{contest.id}-{fmt.name}.mp4"
        render(film, str(dest), format=fmt, log=out)
        print(f"wrote {dest}", file=out)
        print(f"wrote {write_chapters(dest, module.CHAPTERS)}", file=out)
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


def _serve(args, out, err) -> int:
    from .site.config import load_config
    from .site.server import build_deps, make_servers, run_forever

    config = load_config(args)
    if not config.token:
        print("BALLOTREELS_TOKEN is not set: refusing to start the "
             "private listener", file=err)
        return 2
    from .index import ContestIndexError
    from .site.config import ElectionResolutionError
    try:
        deps = build_deps(config, warn=lambda m: print(m, file=err))
    except (ElectionResolutionError, ContestIndexError) as e:
        print(str(e), file=err)
        return 2
    public, private = make_servers(deps)
    print(f"public listening on http://{public.server_address[0]}:"
         f"{public.server_address[1]}", file=out)
    print(f"private listening on http://{private.server_address[0]}:"
         f"{private.server_address[1]}", file=out)
    run_forever(public, private)
    return 0


def _build_storage(client):
    """The worker's storage backend, or raises S3ConfigError naming
    every missing variable (the caller turns that into exit 2)."""
    storage_name = os.environ.get("BALLOTREELS_STORAGE", "local")
    if storage_name == "local":
        from .storage import LocalStorage
        return LocalStorage(client)
    if storage_name == "s3":
        from .storage import S3Storage
        return S3Storage.from_env(os.environ)
    raise SystemExit(f"unknown BALLOTREELS_STORAGE {storage_name!r}")


def _worker_main(args, out, err) -> int:
    server = args.server or os.environ.get("BALLOTREELS_SERVER")
    token = os.environ.get("BALLOTREELS_TOKEN")
    if token is not None and not token.strip():
        token = None
    if not server:
        print("no server URL: pass --server or set BALLOTREELS_SERVER",
             file=err)
        return 2
    if not token:
        print("BALLOTREELS_TOKEN is not set", file=err)
        return 2
    from .pipeline import FakeRunner, HandWrittenScriptWriter, SubprocessRunner
    from .standard import load_standard
    from .worker import TransportError, Worker, WorkerApiError, WorkerClient

    standard = load_standard()
    ffmpeg = args.ffmpeg or os.environ.get("BALLOTREELS_FFMPEG", "ffmpeg")
    crf = (args.crf if args.crf is not None
          else int(os.environ.get("BALLOTREELS_CRF", "18")))
    maxrate = args.maxrate or os.environ.get("BALLOTREELS_MAXRATE", "1500k")
    masters_dir = Path(args.masters_dir or
                       os.environ.get("BALLOTREELS_MASTERS_DIR",
                                     str(REPO_ROOT / "var" / "masters")))
    if args.runner == "fake":
        runner = FakeRunner()
    else:
        site_url = args.site_url or os.environ.get("BALLOTREELS_SITE_URL")
        runner = SubprocessRunner(args.repo, ffmpeg=ffmpeg, crf=crf,
                                  maxrate=maxrate, site_url=site_url or None)
    client = WorkerClient(server, token)
    from .storage import S3ConfigError
    try:
        storage = _build_storage(client)
    except S3ConfigError as e:
        print(str(e), file=err)
        return 2
    worker = Worker(client=client, worker_id=args.worker_id, repo=args.repo,
                    runner=runner, writer=HandWrittenScriptWriter(),
                    storage=storage, standard=standard,
                    work_dir=Path(args.work_dir),
                    masters_dir=masters_dir,
                    poll_interval=args.poll_interval,
                    heartbeat_interval=args.heartbeat_interval)
    import signal
    # Runner children (narrate.sh's TTS, the render, ffmpeg) run in their
    # own session, so a terminal's Ctrl-C or hang-up no longer reaches
    # them: route those signals through stop(), which kills the child's
    # group and gives the job back, the same as SIGTERM.
    try:
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(signum, lambda *a: worker.stop())
    except ValueError:
        pass  # not the main thread (e.g. under a test runner)
    if args.once:
        try:
            worker.run_once()
        except (TransportError, WorkerApiError) as e:
            print(f"worker: {e}", file=err)
            return 1
    else:
        worker.run_forever()
    return 0


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


def main(argv: list[str] | None = None, out=sys.stdout, err=sys.stderr) -> int:
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
        "render", help="render the contest's video with videobuilder; "
                       "given an election's directory, its crash course")
    render.add_argument("contest", metavar="contest-dir")
    render.add_argument("--format", choices=["9x16", "16x9", "all"],
                        default="all")
    render.add_argument("--out", default="out", metavar="DIR",
                        help="output directory (default: out/)")
    render.add_argument("--site-url", default=None,
                        help="the site's public base URL, for the link to "
                             "the measure's page on every frame (default: "
                             "$BALLOTREELS_SITE_URL or "
                             "https://ballotreels.org)")
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
    serve = sub.add_parser("serve", help="run the serve tier")
    serve.add_argument("--data-dir", default=None,
                       help="default: $BALLOTREELS_DATA_DIR or <repo>/var")
    serve.add_argument("--election", default=None, action="append",
                       help="serve only this election (repeatable, or "
                            "comma-separated); default: "
                            "$BALLOTREELS_ELECTION, or every election "
                            "under data/")
    serve.add_argument("--public-host", default=None)
    serve.add_argument("--public-port", default=None, type=int)
    serve.add_argument("--private-host", default=None)
    serve.add_argument("--private-port", default=None, type=int)
    serve.add_argument("--generate-limit", default=None, type=int,
                       help="max Generate requests per client IP per "
                            "window (default: 5)")
    serve.add_argument("--generate-window", default=None, type=int,
                       help="seconds in the Generate rate-limit window "
                            "(default: 3600)")
    serve.add_argument("--generate-global-limit", default=None, type=int,
                       help="max new public Generate jobs per hour across "
                            "every client (default: 30)")
    serve.add_argument("--require-approval", default=None,
                       action=argparse.BooleanOptionalAction,
                       help="hold each video a visitor requests as pending "
                            "until the operator approves it (default: on; "
                            "--no-require-approval queues them directly)")
    serve.add_argument("--address-limit", default=None, type=int,
                       help="max address lookups per client IP per hour "
                            "(default: 30)")
    serve.add_argument("--trust-forwarded-for", action="store_true",
                       default=None,
                       help="use the rightmost X-Forwarded-For entry as "
                            "the client IP (only behind a trusted proxy)")
    serve.add_argument("--heartbeat-timeout", default=None, type=float,
                       help="seconds without a worker heartbeat before a "
                            "running job is requeued (default: 120)")
    serve.add_argument("--eta-default-minutes", default=None, type=float,
                       help="ETA to show until any job has completed "
                            "(default: 10)")
    serve.add_argument("--max-upload-mb", default=None, type=int,
                       help="largest file a worker may upload (default: "
                            "500)")
    serve.add_argument("--geocoder-url", default=None,
                       help="base URL of the Census Geocoder")
    serve.add_argument("--site-url", default=None,
                       help="the site's public base URL, for the absolute "
                            "URLs in link previews (default: "
                            "https://ballotreels.org)")
    worker = sub.add_parser("worker", help="run a pull worker")
    worker.add_argument("--server", default=None,
                        help="the serve tier's private listener URL; "
                             "default: $BALLOTREELS_SERVER")
    worker.add_argument("--repo", default=str(REPO_ROOT),
                        help="this worker's own checkout (scripts and "
                             "sources come from here); default: this repo")
    worker.add_argument("--worker-id", default=_default_worker_id())
    worker.add_argument("--runner", choices=["subprocess", "fake"],
                        default="subprocess")
    worker.add_argument("--work-dir",
                        default=str(default_data_dir() / "work"),
                        help="default: <data-dir>/work")
    worker.add_argument(
        "--masters-dir", default=None,
        help="default: $BALLOTREELS_MASTERS_DIR or <repo>/var/masters")
    worker.add_argument("--ffmpeg", default=None,
                        help="default: $BALLOTREELS_FFMPEG or 'ffmpeg'")
    worker.add_argument("--crf", type=int, default=None,
                        help="default: $BALLOTREELS_CRF or 18")
    worker.add_argument("--maxrate", default=None,
                        help="default: $BALLOTREELS_MAXRATE or '1500k'")
    worker.add_argument("--site-url", default=None,
                        help="the site's public base URL, for the link "
                             "every video prints (default: "
                             "$BALLOTREELS_SITE_URL or "
                             "https://ballotreels.org)")
    worker.add_argument("--poll-interval", type=float, default=2.0)
    worker.add_argument("--heartbeat-interval", type=float, default=10.0)
    worker.add_argument("--once", action="store_true",
                        help="claim and work at most one job, then exit")
    args = parser.parse_args(argv)

    if args.command == "narration":
        ok = True
        for path in args.contests:
            ok = _narration_one(path, out) and ok
        return 0 if ok else 1

    if args.command == "render":
        ok = _render_one(args.contest, args.format, Path(args.out), out,
                         site_url=args.site_url)
        return 0 if ok else 1

    if args.command == "check":
        standard = load_standard()
        ok = True
        for path in args.contests:
            ok = _check_one(path, standard, out) and ok
        # Each election a checked contest belongs to: its glance.toml, once.
        for election_dir in dict.fromkeys(
                Path(p).resolve().parent for p in args.contests):
            if (election_dir / "contests.toml").is_file():
                ok = _check_glance(election_dir, out) and ok
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

    if args.command == "serve":
        return _serve(args, out, err)

    if args.command == "worker":
        return _worker_main(args, out, err)

    raise AssertionError(f"unhandled command {args.command!r}")
