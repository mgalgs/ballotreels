"""The pull worker: claims a job from the serve tier's private API, runs
the stages in `ballotreels.pipeline` in a scratch copy of the contest,
and uploads the result. The worker pulls so the home cluster it runs on
never needs inbound access (the brief).

A job renders from the repo's committed HEAD as it is at claim time
(ballotreels.snapshot), never from the live checkout, which may be
mid-merge.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .contest import load_contest
from . import crash_course
# What the stages import lazily, imported now, while the checkout is
# whole: an import made mid-job would read whatever the working tree
# holds then, conflict markers and all.
from . import ballots, checks, index, narration, storyboard  # noqa: F401
from .geo import states  # noqa: F401
from .pipeline import (PipelineError, Runner, ScriptWriter, read_chapters,
                       run_check, run_crash_check, run_crash_narrate,
                       run_crash_script, run_crash_sources, run_encode,
                       run_narrate, run_render, run_script, run_sources)
from .narration_store import TakeCache, TakeError, materialize
from .queue import hash_for_key
from .snapshot import Snapshots, export, kind
from .standard import Standard

MAX_FAIL_OUTPUT = 256 * 1024

# Longest pause between claim attempts while the serve tier is unreachable.
MAX_BACKOFF = 60.0


class WorkerApiError(Exception):
    def __init__(self, status: int, body: Any):
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


class TransportError(Exception):
    """The serve tier could not be reached (connection refused, a timeout,
    a tunnel blip), even after retrying."""


class ClaimConflict(Exception):
    """A worker-API call 409'd: this worker's claim on the job is gone
    (requeued by a heartbeat timeout, or cancelled/requeued by an
    admin)."""


class WorkerClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0,
                 retry_delays: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0)):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        # Pauses between attempts when the serve tier can't be reached.
        # Every worker call is safe to repeat: a repeated upload overwrites,
        # and a repeated call whose first attempt landed gets a 409.
        self.retry_delays = retry_delays

    def _request(self, method: str, path: str, json_body: Any = None,
                 data: bytes | None = None,
                 raw: bool = False) -> tuple[int, Any]:
        for delay in (*self.retry_delays, None):
            try:
                return self._request_once(method, path, json_body, data,
                                          raw)
            except TransportError:
                if delay is None:
                    raise
                time.sleep(delay)
        raise AssertionError("unreachable")

    def _request_once(self, method: str, path: str, json_body: Any,
                      data: bytes | None,
                      raw: bool = False) -> tuple[int, Any]:
        """(status, the body parsed as JSON); with `raw`, a 200's body is
        returned as bytes instead."""
        url = self.base_url + path
        headers = {"Authorization": f"Bearer {self.token}"}
        body = data
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, method=method,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
                if raw:
                    return resp.status, body
                return resp.status, (json.loads(body) if body else None)
        except urllib.error.HTTPError as e:
            with e:
                raw = e.read()
            try:
                parsed = json.loads(raw) if raw else None
            except ValueError:
                parsed = None
            return e.code, parsed
        except (urllib.error.URLError, OSError) as e:
            raise TransportError(f"{method} {url}: {e}") from None

    def claim(self, worker_id: str) -> dict[str, Any] | None:
        status, body = self._request("POST", "/worker/claim",
                                     json_body={"worker": worker_id})
        if status == 204:
            return None
        if status != 200:
            raise WorkerApiError(status, body)
        return body["job"]

    def heartbeat(self, job_id: int, claim: str, stage: str | None) -> None:
        # One attempt: the heartbeat loop simply tries again next beat.
        status, body = self._request_once(
            "POST", f"/worker/jobs/{job_id}/heartbeat",
            {"claim": claim, "stage": stage}, None)
        if status == 409:
            raise ClaimConflict(body)
        if status != 200:
            raise WorkerApiError(status, body)

    def stage_event(self, job_id: int, claim: str, stage: str,
                    event: str) -> None:
        status, body = self._request(
            "POST", f"/worker/jobs/{job_id}/stage",
            json_body={"claim": claim, "stage": stage, "event": event})
        if status == 409:
            raise ClaimConflict(body)
        if status != 200:
            raise WorkerApiError(status, body)

    def upload(self, job_id: int, claim: str, name: str, data: bytes) -> None:
        status, body = self._request(
            "PUT", f"/worker/jobs/{job_id}/files/{name}?claim={claim}",
            data=data)
        if status != 200:
            raise WorkerApiError(status, body)

    def complete(self, job_id: int, claim: str, storage: str,
                sources: list[dict[str, Any]],
                objects: dict[str, Any] | None = None,
                chapters: list[dict[str, Any]] | None = None) -> None:
        payload: dict[str, Any] = {"claim": claim, "storage": storage,
                                   "sources": sources}
        if objects is not None:
            payload["objects"] = objects
        if chapters is not None:
            payload["chapters"] = chapters
        status, body = self._request(
            "POST", f"/worker/jobs/{job_id}/complete", json_body=payload)
        if status == 409:
            raise ClaimConflict(body)
        if status != 200:
            raise WorkerApiError(status, body)

    def fail(self, job_id: int, claim: str, stage: str, output: str) -> None:
        # Keep the tail of very long output, inside the private listener's
        # request size limit.
        if len(output) > MAX_FAIL_OUTPUT:
            output = "[...]\n" + output[-MAX_FAIL_OUTPUT:]
        self._request("POST", f"/worker/jobs/{job_id}/fail",
                      json_body={"claim": claim, "stage": stage,
                                "output": output})

    def release(self, job_id: int, claim: str) -> None:
        self._request("POST", f"/worker/jobs/{job_id}/release",
                      json_body={"claim": claim})

    # The narration store (ballotreels.narration_store): takes by SHA-256.

    def narration_has(self, sha: str) -> bool:
        status, body = self._request("HEAD", f"/worker/narration/{sha}")
        if status == 404:
            return False
        if status != 200:
            raise WorkerApiError(status, body)
        return True

    def narration_get(self, sha: str) -> bytes | None:
        """The take's audio, or None when the server has no such take."""
        status, body = self._request("GET", f"/worker/narration/{sha}",
                                     raw=True)
        if status == 404:
            return None
        if status != 200:
            raise WorkerApiError(status, body)
        return body

    def narration_put(self, sha: str, data: bytes) -> bool:
        """Upload a take; True when the server stored it, False when it
        already had it."""
        status, body = self._request("PUT", f"/worker/narration/{sha}",
                                     data=data)
        if status != 200:
            raise WorkerApiError(status, body)
        return bool(body.get("stored"))


def _source_dicts(contest) -> list[dict[str, Any]]:
    return [{"id": s.id, "kind": s.kind, "publisher": s.publisher,
            "url": s.url, "retrieved": s.retrieved,
            "credit": s.credit} for s in contest.sources]


class Worker:
    def __init__(self, client: WorkerClient, worker_id: str, repo: str | Path,
                runner: Runner, writer: ScriptWriter, storage,
                standard: Standard, work_dir: str | Path,
                masters_dir: str | Path, poll_interval: float = 2.0,
                heartbeat_interval: float = 10.0,
                narration_cache: str | Path | None = None):
        self.client = client
        self.worker_id = worker_id
        self.repo = Path(repo)
        self.runner = runner
        self.writer = writer
        self.storage = storage
        self.standard = standard
        self.work_dir = Path(work_dir)
        self.masters_dir = Path(masters_dir)
        # Narration takes, by hash: the audio is not in the commit.
        self.takes = TakeCache(narration_cache if narration_cache is not None
                               else self.work_dir / "narration")
        self.poll_interval = poll_interval
        self.heartbeat_interval = heartbeat_interval
        self._stop = threading.Event()
        self._current = None  # (job_id, claim)
        self._current_stage = None
        self._cancelled = False
        self._hb_thread = None
        self._hb_stop = None
        # Job directories are named by job id, so this never meets one.
        self.snapshots = Snapshots(self.repo, self.work_dir / "snapshots")

    def run_once(self) -> bool:
        job = self.client.claim(self.worker_id)
        if job is None:
            return False
        self._work(job)
        return True

    def run_forever(self) -> None:
        backoff = self.poll_interval
        while not self._stop.is_set():
            try:
                worked = self.run_once()
            except (TransportError, WorkerApiError) as e:
                # The serve tier is down or restarting, or the tunnel is
                # out: wait and try again rather than exit.
                print(f"worker: {e}; retrying in {backoff:.0f}s",
                      file=sys.stderr, flush=True)
                self._stop.wait(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
                continue
            backoff = self.poll_interval
            if not worked:
                self._stop.wait(self.poll_interval)

    def stop(self) -> None:
        self._stop.set()
        current = self._current
        if current is not None:
            job_id, claim = current
            self._cancelled = True
            if hasattr(self.runner, "kill"):
                self.runner.kill()
            try:
                self.client.release(job_id, claim)
            except Exception:
                pass

    # -- internal ---------------------------------------------------

    def _job_work_dir(self, job_id: int) -> Path:
        return self.work_dir / str(job_id)

    def _master_path(self, job: dict[str, Any]) -> Path:
        key = (job["election"], job["division"], job["contest"],
              job["standard_version"], job["template_version"])
        return self.masters_dir / hash_for_key(key) / "master.mp4"

    def _export_dir(self, sha: str, path: str, dest: Path) -> bool:
        """Write the directory at repo-relative `path` in commit `sha` to
        `dest`; False, writing nothing, when the commit has none."""
        if kind(self.repo, sha, path) != "tree":
            return False
        stage = dest.parent / f".{dest.name}.export"
        export(self.repo, sha, [path], stage)
        os.rename(stage / path, dest)
        shutil.rmtree(stage)
        return True

    def _prepare_scratch(self, job: dict[str, Any], wd: Path,
                         sha: str) -> Path:
        election = job["election"]
        contest_id = job["contest"]
        prefix = f"{election}-"
        dir_name = (contest_id[len(prefix):]
                   if contest_id.startswith(prefix) else contest_id)
        dest = wd / dir_name
        wd.mkdir(parents=True, exist_ok=True)
        # With its committed narration sidecars: the narrate stage
        # reuses them (run_narrate), and `say` needs narration.json's
        # phrase_cache beside narration.wav to keep unchanged phrases.
        if not self._export_dir(sha, f"data/{election}/{dir_name}", dest):
            dest.mkdir(parents=True, exist_ok=True)
        self._materialize(dest, contest_id)
        return dest

    def _materialize(self, contest_dir: Path, contest_id: str) -> None:
        """Put the take the commit's narration.json records at
        narration.wav (narration_store), or fail the job naming it: a
        take that cannot be had is never re-narrated here."""
        try:
            materialize(contest_dir, self.takes, self.client,
                        where=contest_id)
        except TakeError as e:
            raise PipelineError(str(e)) from None

    def _prepare_election_scratch(self, job: dict[str, Any], wd: Path,
                                  sha: str) -> Path:
        """A crash course's scratch copy: the election's contests.toml and
        each member's directory, committed narration and all."""
        from .index import load_index
        election = job["election"]
        src = crash_course.election_dir_for(Path(), election).as_posix()
        dest = wd / election
        dest.mkdir(parents=True, exist_ok=True)
        if kind(self.repo, sha, f"{src}/contests.toml") != "blob":
            return dest  # the script stage reports it
        stage = wd / f".{election}.export"
        export(self.repo, sha, [f"{src}/contests.toml"], stage)
        os.rename(stage / src / "contests.toml", dest / "contests.toml")
        shutil.rmtree(stage)
        entry = load_index(dest).crash_course
        for cid in (entry.members if entry is not None else ()):
            member = crash_course.member_dir(dest, election, cid)
            if self._export_dir(sha, f"{src}/{member.name}", member):
                self._materialize(member, cid)
        return dest

    def _checking(self, stage: str, path: Path, func):
        """A checking stage's work: in the commit snapshot's own process
        when the runner has one, so the commit's code and assets
        (film/illustrations/, standard/) judge it, not this process's."""
        if hasattr(self.runner, "check"):
            return lambda: self.runner.check(stage, path)
        return lambda: func(path, self.standard)

    def _heartbeat_loop(self, job_id: int, claim: str) -> None:
        while not self._hb_stop.is_set():
            if self._hb_stop.wait(self.heartbeat_interval):
                break
            try:
                self.client.heartbeat(job_id, claim, self._current_stage)
            except ClaimConflict:
                self._cancelled = True
                if hasattr(self.runner, "kill"):
                    self.runner.kill()
                break
            except Exception:
                pass  # a transient network error; try again next beat

    def _heartbeat_start(self, job_id: int, claim: str) -> None:
        self._cancelled = False
        self._hb_stop = threading.Event()
        self._hb_thread = threading.Thread(
            target=self._heartbeat_loop, args=(job_id, claim), daemon=True)
        self._hb_thread.start()

    def _heartbeat_stop(self) -> None:
        if self._hb_stop is not None:
            self._hb_stop.set()
        if self._hb_thread is not None:
            self._hb_thread.join(timeout=5)

    def _run_stage(self, job_id: int, claim: str, stage: str, func) -> Any:
        self._current_stage = stage
        self.client.stage_event(job_id, claim, stage, "start")
        result = func()
        self.client.stage_event(job_id, claim, stage, "finish")
        return result

    def _upload_and_complete(self, job: dict[str, Any], contest_dir: Path,
                             web: Path, poster: Path,
                             chapters: list[dict[str, Any]] | None = None
                             ) -> None:
        if crash_course.is_crash_course(job["contest"]):
            # what the reused lines cite, and a record of what it says
            course = crash_course.plan(contest_dir)
            sources = crash_course.sources(course)
            script = crash_course.script_toml(course).encode("utf-8")
        else:
            contest = load_contest(contest_dir)
            sources = _source_dicts(contest)
            script = (Path(contest_dir) / "script.toml").read_bytes()
        files = {
            "video.mp4": Path(web).read_bytes(),
            "poster.jpg": Path(poster).read_bytes(),
            "script.toml": script,
            "sources.json": json.dumps(sources).encode("utf-8"),
        }
        published = self.storage.put_all(job, files)
        if published["storage"] == "local":
            self.client.complete(job["id"], job["claim"], "local", sources,
                                 chapters=chapters)
        else:
            self.client.complete(job["id"], job["claim"], "s3", sources,
                                 objects=published["objects"],
                                 chapters=chapters)

    def _work(self, job: dict[str, Any]) -> None:
        job_id, claim = job["id"], job["claim"]
        self._current = (job_id, claim)
        self._current_stage = None
        if self._stop.is_set():
            # stop() ran between the claim and the line above, saw no
            # current job, and gave nothing back: give this one back now.
            # (stop() sets the flag before it reads _current, so one of the
            # two always sees the other; a second release just 409s.)
            # No lock: stop() also runs as a signal handler on this thread.
            self._current = None
            try:
                self.client.release(job_id, claim)
            except Exception:
                pass
            return
        wd = self._job_work_dir(job_id)
        succeeded = False
        master_path = None
        lease = None
        try:
            self._heartbeat_start(job_id, claim)
            # Everything the stages read comes from this commit: the
            # contest's files below, and the code and assets the runner
            # runs (the snapshot).
            sha = self.snapshots.head()
            print(f"worker: job {job_id}: {job['contest']} from commit "
                  f"{sha}", file=sys.stderr, flush=True)
            lease = self.snapshots.acquire(sha)
            self.snapshots.prune(keep=sha)
            if hasattr(self.runner, "use_tree"):
                self.runner.use_tree(lease.tree)
            if crash_course.is_crash_course(job["contest"]):
                # The same stages over an election's statewide measures:
                # nothing to write, and nothing ever narrated.
                contest_dir = self._prepare_election_scratch(job, wd, sha)
                stages = (
                    ("sources", lambda: run_crash_sources(contest_dir)),
                    ("script", lambda: run_crash_script(
                        contest_dir, job, self.standard)),
                    ("check", self._checking(
                        "crash-check", contest_dir, run_crash_check)),
                    ("narrate", self._checking(
                        "crash-narrate", contest_dir, run_crash_narrate)),
                )
            else:
                contest_dir = self._prepare_scratch(job, wd, sha)
                stages = (
                    ("sources", lambda: run_sources(contest_dir)),
                    ("script", lambda: run_script(
                        contest_dir, self.writer, job, self.standard)),
                    ("check", self._checking(
                        "check", contest_dir, run_check)),
                    ("narrate", lambda: run_narrate(
                        contest_dir, self.runner, self.standard)),
                )
            for stage, func in stages:
                self._run_stage(job_id, claim, stage, func)
            out_dir = wd / "out"
            rendered = self._run_stage(
                job_id, claim, "render",
                lambda: run_render(contest_dir, self.runner, out_dir))
            # Each section's start, written beside the render.
            chapters = read_chapters(rendered)
            master_path = self._master_path(job)
            master_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(rendered, master_path)
            web, poster = wd / "web.mp4", wd / "poster.jpg"
            self._run_stage(
                job_id, claim, "encode",
                lambda: run_encode(master_path, web, poster, self.runner))
            self._current_stage = "cache"
            self.client.stage_event(job_id, claim, "cache", "start")
            try:
                self._upload_and_complete(job, contest_dir, web, poster,
                                          chapters)
            except ClaimConflict:
                raise
            except Exception as e:
                raise PipelineError(str(e)) from e
            succeeded = True
        except PipelineError as e:
            if not self._cancelled:
                try:
                    # (no stage yet: the scratch copy's narration take)
                    self.client.fail(job_id, claim,
                                     self._current_stage or "sources",
                                     str(e))
                except Exception:
                    pass
        except ClaimConflict:
            pass
        except (TransportError, WorkerApiError) as e:
            # Lost the serve tier mid-job. Give the job back if we can;
            # otherwise the heartbeat timeout requeues it.
            print(f"worker: job {job_id}: {e}; giving it back",
                  file=sys.stderr, flush=True)
            try:
                self.client.release(job_id, claim)
            except Exception:
                pass
        except Exception as e:
            # Anything else a stage raised (a script.toml that won't load,
            # a missing ffmpeg) fails the job with its error, rather than
            # leaving it running for the heartbeat timeout to requeue to
            # the next worker, which would crash the same way.
            if not self._cancelled:
                try:
                    self.client.fail(job_id, claim,
                                     self._current_stage or "sources",
                                     f"{type(e).__name__}: {e}")
                except Exception:
                    pass
        finally:
            self._heartbeat_stop()
            self._current = None
            if lease is not None:
                lease.release()
            if not succeeded and master_path is not None:
                shutil.rmtree(master_path.parent, ignore_errors=True)
            shutil.rmtree(wd, ignore_errors=True)
