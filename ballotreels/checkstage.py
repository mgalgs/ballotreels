"""Run one of the worker's checking stages as a process of its own:

    python -m ballotreels.checkstage <stage> <dir>

The worker runs these from the job's commit snapshot
(SubprocessRunner.check), so a job is checked by the commit's code
against the commit's standard and film/illustrations/, never by what the
worker imported at startup or what the live checkout holds now. The
stage's PipelineError message is the whole output, exit status 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .pipeline import (PipelineError, run_check, run_crash_check,
                       run_crash_narrate)
from .standard import load_standard

STAGES = {
    "check": run_check,
    "crash-check": run_crash_check,
    "crash-narrate": run_crash_narrate,
}


def main(argv: list[str] | None = None) -> int:
    stage, path = sys.argv[1:] if argv is None else argv
    try:
        STAGES[stage](Path(path), load_standard())
    except PipelineError as e:
        sys.stdout.write(str(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
