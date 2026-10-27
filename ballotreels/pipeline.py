"""The worker's stages: sources, script, check, narrate, render, encode
(docs/ARCHITECTURE.md's pipeline, minus the two ends the serve tier owns:
divisions-to-contests, and cache). Each stage function raises
PipelineError with a plain, publishable message on failure.

`ScriptWriter` and `Runner` are the pluggable pieces: today's only
`ScriptWriter` returns a contest's hand-written script.toml; the only
`Runner`s are a real one (shells out to narrate.sh, the renderer and
ffmpeg) and a fake one (for tests, and CI, where none of those exist).
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Protocol

from .standard import TEMPLATES, Standard

STAGES = ("sources", "script", "check", "narrate", "render", "encode")


class PipelineError(Exception):
    """A stage failed; the message is what the public job status and the
    queue monitor both show (the monitor also gets the full output)."""


class ScriptWriter(Protocol):
    def write_script(self, contest_dir: Path) -> None: ...


class HandWrittenScriptWriter:
    """The only script writer today: the contest's own script.toml, or a
    failure, since automatic script writing isn't built yet."""

    def write_script(self, contest_dir: Path) -> None:
        if not (Path(contest_dir) / "script.toml").is_file():
            raise PipelineError("automatic script writing isn't built yet")


class Runner(Protocol):
    def narrate(self, contest_dir: Path) -> None: ...
    def render(self, contest_dir: Path, out_dir: Path) -> Path: ...
    def encode(self, master: Path, web: Path, poster: Path) -> None: ...
    def kill(self) -> None: ...


def run_sources(contest_dir: Path) -> None:
    contest_dir = Path(contest_dir)
    if not (contest_dir / "sources.toml").is_file() or \
       not (contest_dir / "sources").is_dir():
        raise PipelineError("Sources for this contest haven't been "
                            "archived yet.")


def run_script(contest_dir: Path, writer: ScriptWriter, job: dict[str, Any],
               standard: Standard) -> None:
    writer.write_script(contest_dir)
    from .contest import load_contest
    contest = load_contest(contest_dir)
    worker_template_version = max(TEMPLATES[contest.script.template])
    if (standard.version != job["standard_version"] or
            worker_template_version != job["template_version"]):
        raise PipelineError(
            f"worker has standard {standard.version} / template "
            f"{worker_template_version}, job wants standard "
            f"{job['standard_version']} / template {job['template_version']}")


def _check_or_raise(contest_dir: Path, standard: Standard) -> None:
    from .checks import check_contest
    from .contest import ContestError, load_contest
    try:
        contest = load_contest(contest_dir)
    except ContestError as e:
        raise PipelineError(str(e)) from None
    failures = check_contest(contest, standard)
    if failures:
        raise PipelineError("\n".join(str(f) for f in failures))


def run_check(contest_dir: Path, standard: Standard) -> None:
    _check_or_raise(contest_dir, standard)


def run_narrate(contest_dir: Path, runner: Runner, standard: Standard) -> None:
    runner.narrate(contest_dir)
    # STANDARD.md rule 7 ("A video that fails any rule is not published"):
    # re-check now that the sidecars exist, since airtime can only be
    # measured once they do.
    _check_or_raise(contest_dir, standard)


def run_render(contest_dir: Path, runner: Runner, out_dir: Path) -> Path:
    return runner.render(contest_dir, out_dir)


def run_encode(master: Path, web: Path, poster: Path, runner: Runner) -> None:
    runner.encode(master, web, poster)


class SubprocessRunner:
    """Shells out to the real tools: scripts/narrate.sh (Chatterbox), the
    videobuilder renderer, and ffmpeg for the web encode (operator
    decision 1793069336-01: H.264/yuv420p/AAC, +faststart, a poster from
    an early frame)."""

    def __init__(self, repo: str | Path, ffmpeg: str = "ffmpeg",
                crf: int = 18, maxrate: str = "1500k",
                bufsize: str = "3000k",
                popen: Callable[..., Any] = subprocess.Popen):
        self.repo = Path(repo)
        self.ffmpeg = ffmpeg
        self.crf = crf
        self.maxrate = maxrate
        self.bufsize = bufsize
        self._popen = popen
        self._lock = threading.Lock()
        self._current = None

    def narrate(self, contest_dir: Path) -> None:
        self._run([str(self.repo / "scripts" / "narrate.sh"),
                   str(contest_dir)])

    def render(self, contest_dir: Path, out_dir: Path) -> Path:
        from .contest import load_contest
        contest = load_contest(contest_dir)
        self._run([sys.executable, "-m", "ballotreels", "render",
                   str(contest_dir), "--format", "9x16", "--out",
                   str(out_dir)])
        return out_dir / f"{contest.id}-9x16.mp4"

    def encode(self, master: Path, web: Path, poster: Path) -> None:
        self._run([
            self.ffmpeg, "-nostdin", "-y", "-i", str(master),
            "-c:v", "libx264", "-preset", "slow", "-crf", str(self.crf),
            "-maxrate", self.maxrate, "-bufsize", self.bufsize,
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart", str(web),
        ])
        self._run([
            self.ffmpeg, "-nostdin", "-y", "-ss", "1", "-i", str(master),
            "-frames:v", "1", "-q:v", "3", str(poster),
        ])

    def _run(self, argv: list[str]) -> None:
        with self._lock:
            proc = self._popen(argv, cwd=str(self.repo),
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               start_new_session=True)
            self._current = proc
        try:
            out, _ = proc.communicate()
        except BaseException:
            # Interrupted (KeyboardInterrupt, say): the child is in its own
            # session and would outlive us, so take its group down too.
            self.kill()
            raise
        finally:
            with self._lock:
                self._current = None
        if proc.returncode != 0:
            raise PipelineError((out or b"").decode("utf-8", "replace"))

    def kill(self) -> None:
        with self._lock:
            proc = self._current
        if proc is None:
            return
        # narrate.sh runs the TTS as its own child, which would outlive a
        # kill of the shell and hold the output pipe open; each child is
        # started in its own session, so kill the whole process group.
        pid = getattr(proc, "pid", None)
        if isinstance(pid, int):
            try:
                os.killpg(pid, signal.SIGKILL)
                return
            except (ProcessLookupError, PermissionError):
                pass
        proc.kill()


class FakeRunner:
    """A runner that needs none of the real tools: `videobuilder.speech`
    (text splitting only, no TTS) lays out fake phrase timings the same
    way `videobuilder say` would; render and encode write small
    placeholder files. Nothing playable is produced or committed (A17).
    """

    def __init__(self, stretch: dict[str, float] | None = None,
                block_stage: str | None = None,
                block_event: threading.Event | None = None):
        self.stretch = stretch or {}
        self.block_stage = block_stage
        self.block_event = block_event
        self._killed = threading.Event()

    def kill(self) -> None:
        self._killed.set()
        if self.block_event is not None:
            self.block_event.set()

    def _maybe_block(self, stage: str) -> None:
        if stage == self.block_stage and self.block_event is not None:
            self.block_event.wait()
            if self._killed.is_set():
                raise PipelineError("killed")

    def narrate(self, contest_dir: Path) -> None:
        self._maybe_block("narrate")
        contest_dir = Path(contest_dir)
        from .contest import load_contest
        from .narration import narration_lines

        contest = load_contest(contest_dir)
        try:
            from videobuilder import speech
            split = speech.phrases
        except ImportError:
            def split(text):
                return [text]

        phrases = []
        t = 0.0
        for line in narration_lines(contest):
            factor = self.stretch.get(line.section, 1.0)
            for text in split(line.text):
                end = t + 0.4 * len(text.split()) * factor
                phrases.append({"text": text, "start": round(t, 2),
                               "end": round(end, 2)})
                t = end + 0.25
        doc = {"phrases": phrases, "seconds": round(t, 2)}
        (contest_dir / "narration.json").write_text(
            json.dumps(doc) + "\n", encoding="utf-8")

    def render(self, contest_dir: Path, out_dir: Path) -> Path:
        self._maybe_block("render")
        from .contest import load_contest
        contest = load_contest(contest_dir)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f"{contest.id}-9x16.mp4"
        # A placeholder, not a real MP4 (A17): starts with an ftyp box so
        # it is at least recognizable, 64 KiB of deterministic bytes.
        body = (b"\x00\x00\x00\x18ftypisom" +
               bytes((i % 256 for i in range(64 * 1024 - 16))))
        dest.write_bytes(body)
        return dest

    def encode(self, master: Path, web: Path, poster: Path) -> None:
        self._maybe_block("encode")
        master = Path(master)
        data = bytearray(master.read_bytes())
        if data:
            data[-1] ^= 0xFF  # so a test can tell web.mp4 from the master
        Path(web).write_bytes(bytes(data))
        Path(poster).write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 16 +
                                 b"\xff\xd9")
