"""The pull worker: claims a job from the serve tier's private API, runs
the stages in `ballotreels.pipeline` in a scratch copy of the contest,
and uploads the result. The worker pulls so the home cluster it runs on
never needs inbound access (the brief).
"""

from __future__ import annotations

import json
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .contest import load_contest
from .pipeline import (PipelineError, Runner, ScriptWriter, read_chapters,
                       run_check, run_encode, run_narrate, run_render,
                       run_script, run_sources)
from .queue import hash_for_key
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
                 data: bytes | None = None) -> tuple[int, Any]:
        for delay in (*self.retry_delays, None):
            try:
                return self._request_once(method, path, json_body, data)
            except TransportError:
                if delay is None:
                    raise
                time.sleep(delay)
        raise AssertionError("unreachable")

    def _request_once(self, method: str, path: str, json_body: Any,
                      data: bytes | None) -> tuple[int, Any]:
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
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else None)
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


def _source_dicts(contest) -> list[dict[str, Any]]:
    return [{"id": s.id, "kind": s.kind, "publisher": s.publisher,
            "url": s.url, "retrieved": s.retrieved,
            "credit": s.credit} for s in contest.sources]


class Worker:
    def __init__(self, client: WorkerClient, worker_id: str, repo: str | Path,
                runner: Runner, writer: ScriptWriter, storage,
                standard: Standard, work_dir: str | Path,
                masters_dir: str | Path, poll_interval: float = 2.0,
                heartbeat_interval: float = 10.0):
        self.client = client
        self.worker_id = worker_id
        self.repo = Path(repo)
        self.runner = runner
        self.writer = writer
        self.storage = storage
        self.standard = standard
        self.work_dir = Path(work_dir)
        self.masters_dir = Path(masters_dir)
        self.poll_interval = poll_interval
        self.heartbeat_interval = heartbeat_interval
        self._stop = threading.Event()
        self._current = None  # (job_id, claim)
        self._current_stage = None
        self._cancelled = False
        self._hb_thread = None
        self._hb_stop = None

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

    def _prepare_scratch(self, job: dict[str, Any], wd: Path) -> Path:
        election = job["election"]
        contest_id = job["contest"]
        prefix = f"{election}-"
        dir_name = (contest_id[len(prefix):]
                   if contest_id.startswith(prefix) else contest_id)
        src = self.repo / "data" / election / dir_name
        dest = wd / dir_name
        wd.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            # With its committed narration sidecars: the narrate stage
            # reuses them (run_narrate), and `say` needs narration.json's
            # phrase_cache beside narration.wav to keep unchanged phrases.
            shutil.copytree(src, dest)
        else:
            dest.mkdir(parents=True, exist_ok=True)
        return dest

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
        contest = load_contest(contest_dir)
        sources = _source_dicts(contest)
        files = {
            "video.mp4": Path(web).read_bytes(),
            "poster.jpg": Path(poster).read_bytes(),
            "script.toml": (Path(contest_dir) / "script.toml").read_bytes(),
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
        wd = self._job_work_dir(job_id)
        succeeded = False
        master_path = None
        try:
            self._heartbeat_start(job_id, claim)
            contest_dir = self._prepare_scratch(job, wd)
            self._run_stage(job_id, claim, "sources",
                           lambda: run_sources(contest_dir))
            self._run_stage(
                job_id, claim, "script",
                lambda: run_script(contest_dir, self.writer, job,
                                   self.standard))
            self._run_stage(job_id, claim, "check",
                           lambda: run_check(contest_dir, self.standard))
            self._run_stage(
                job_id, claim, "narrate",
                lambda: run_narrate(contest_dir, self.runner, self.standard))
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
                    self.client.fail(job_id, claim, self._current_stage,
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
            if not succeeded and master_path is not None:
                shutil.rmtree(master_path.parent, ignore_errors=True)
            shutil.rmtree(wd, ignore_errors=True)
