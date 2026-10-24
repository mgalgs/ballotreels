"""Command line: python -m ballotreels check <contest-dir>..."""

from __future__ import annotations

import argparse
import sys

from .checks import check_contest, word_count
from .contest import ContestError, load_contest
from .standard import load_standard, side_order


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


def main(argv: list[str] | None = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="python -m ballotreels")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser(
        "check", help="run the standard's machine checks on contests")
    check.add_argument("contests", nargs="+", metavar="contest-dir")
    args = parser.parse_args(argv)

    standard = load_standard()
    ok = True
    for path in args.contests:
        ok = _check_one(path, standard, out) and ok
    return 0 if ok else 1
