"""Command line:

    python -m ballotreels check <contest-dir>...
    python -m ballotreels narration <contest-dir>...
    python -m ballotreels render <contest-dir> [--format 9x16|16x9|all]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .checks import check_contest, word_count
from .contest import ContestError, load_contest
from .narration import narration_text
from .standard import load_standard, side_order

REPO_ROOT = Path(__file__).resolve().parent.parent
FILM_TEMPLATE = REPO_ROOT / "film" / "measure.py"


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
    words = " ".join(f"{s.id}={word_count(s)}"
                     for s in contest.script.sections)
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
    args = parser.parse_args(argv)

    if args.command == "narration":
        ok = True
        for path in args.contests:
            ok = _narration_one(path, out) and ok
        return 0 if ok else 1

    if args.command == "render":
        ok = _render_one(args.contest, args.format, Path(args.out), out)
        return 0 if ok else 1

    standard = load_standard()
    ok = True
    for path in args.contests:
        ok = _check_one(path, standard, out) and ok
    return 0 if ok else 1
