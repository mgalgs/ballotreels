import http.client
import io
import re
import shutil
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path

import ballotreels.site.config as site_config
from ballotreels.cli import main
from ballotreels.contest import load_contest
from ballotreels.index import key_for
from ballotreels.narration import CURRENT, narration_state
from ballotreels.pipeline import (STAGES, FakeRunner, HandWrittenScriptWriter,
                                  PipelineError, SubprocessRunner, run_check)
from ballotreels.queue import hash_for_key
from ballotreels.site.server import build_deps, make_servers
from ballotreels.standard import Risk
from ballotreels.storage import LocalStorage
from ballotreels.worker import Worker, WorkerClient

from .helpers import (NARRATION_SIDECARS, PROP_2, REPO,
                      write_committed_narration)
from .test_serve_public import _make_config

WORKER_FIXTURE_ELECTION = REPO / "tests" / "fixtures" / "worker_election"


class WorkerTestCase(unittest.TestCase):
    config_overrides: dict = {}

    def setUp(self):
        self._old_root = site_config.DATA_ROOT
        site_config.DATA_ROOT = WORKER_FIXTURE_ELECTION
        self.addCleanup(self._restore_root)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.data_dir = self.tmp / "var"
        self.fake_repo = self.tmp / "repo"
        dest = self.fake_repo / "data" / "ca-2026-11-03" / "prop-2"
        shutil.copytree(PROP_2, dest,
                       ignore=shutil.ignore_patterns(*NARRATION_SIDECARS))
        (self.fake_repo / "scripts").mkdir(parents=True, exist_ok=True)
        (self.fake_repo / "scripts" / "narrate.sh").write_text(
            "#!/bin/sh\nexit 0\n", encoding="utf-8")

        self.config = _make_config(self.data_dir, election="ca-2026-11-03",
                                   **self.config_overrides)
        self.deps = build_deps(self.config)
        self.public, self.private = make_servers(self.deps)
        self.addCleanup(self.deps.queue.close)
        for srv in (self.public, self.private):
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
        self.addCleanup(self._shutdown)

        self.client = WorkerClient(
            f"http://127.0.0.1:{self.private.server_address[1]}",
            "test-token")

    def _restore_root(self):
        site_config.DATA_ROOT = self._old_root

    def _shutdown(self):
        self.public.shutdown()
        self.private.shutdown()
        self.public.server_close()
        self.private.server_close()

    def make_worker(self, runner=None, worker_id="w1",
                    heartbeat_interval=0.2, standard=None):
        runner = runner if runner is not None else FakeRunner()
        return Worker(client=self.client, worker_id=worker_id,
                     repo=self.fake_repo, runner=runner,
                     writer=HandWrittenScriptWriter(),
                     storage=LocalStorage(self.client),
                     standard=standard or self.deps.standard,
                     work_dir=self.tmp / "work",
                     masters_dir=self.tmp / "masters",
                     poll_interval=0.05,
                     heartbeat_interval=heartbeat_interval)

    def prop2_key(self):
        entry = self.deps.states["ca"].index.get("ca-2026-11-03-prop-2")
        return key_for(self.deps.states["ca"].index.election.id, entry, self.deps.standard)

    def get_public(self, path, headers=None):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.public.server_address[1], timeout=5)
        conn.request("GET", path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp, body


class EndToEndTest(WorkerTestCase):
    def test_end_to_end_fake_runner(self):
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        worker = self.make_worker()
        self.assertTrue(worker.run_once())

        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "done")
        events = self.deps.queue.stage_events_for(job["id"])
        finished = {e["stage"] for e in events if e["event"] == "finish"}
        self.assertEqual(finished, set(STAGES) | {"cache"})

        video = self.deps.queue.video_for(key)
        self.assertIsNotNone(video)
        key_hash = hash_for_key(key)

        resp, body = self.get_public(f"/v/{key_hash}/{job['id']}/video.mp4",
                                     {"Range": "bytes=0-9"})
        self.assertEqual(resp.status, 206)
        self.assertEqual(len(body), 10)

        resp, body = self.get_public(f"/v/{key_hash}/{job['id']}/poster.jpg")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "image/jpeg")


class RegenerateTest(WorkerTestCase):
    def test_regenerated_video_gets_a_new_url(self):
        key = self.prop2_key()
        key_hash = hash_for_key(key)
        job, _ = self.deps.queue.create_job(key)
        worker = self.make_worker()
        self.assertTrue(worker.run_once())
        old_url = self.deps.queue.video_for(key).urls["video"]
        self.assertEqual(old_url, f"/v/{key_hash}/{job['id']}/video.mp4")

        ok, message = self.deps.queue.transition(job["id"], "regenerate")
        self.assertTrue(ok, message)
        # While the new job waits, the old video still serves.
        resp, _ = self.get_public(old_url)
        self.assertEqual(resp.status, 200)

        self.assertTrue(worker.run_once())
        new_url = self.deps.queue.video_for(key).urls["video"]
        self.assertNotEqual(new_url, old_url)
        resp, _ = self.get_public(new_url, {"Range": "bytes=0-9"})
        self.assertEqual(resp.status, 206)
        resp, _ = self.get_public(old_url)
        self.assertEqual(resp.status, 404)
        new_job_id = new_url.split("/")[3]
        self.assertEqual(
            [p.name for p in (self.data_dir / "cache" / key_hash).iterdir()],
            [new_job_id])


class FailsWithoutSourcesTest(WorkerTestCase):
    def test_fails_without_sources(self):
        shutil.rmtree(self.fake_repo / "data" / "ca-2026-11-03" / "prop-2")
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        self.make_worker().run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["failed_stage"], "sources")
        self.assertIn("haven't been archived yet", row["error"])


class FailsWithoutScriptTest(WorkerTestCase):
    def test_fails_without_script(self):
        (self.fake_repo / "data" / "ca-2026-11-03" / "prop-2" /
         "script.toml").unlink()
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        self.make_worker().run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["failed_stage"], "script")
        self.assertEqual(row["error"], "automatic script writing isn't built yet")

    def test_unloadable_script_fails_the_job(self):
        # An unexpected exception from a stage fails the job with its
        # error rather than crashing the worker and leaving it running.
        (self.fake_repo / "data" / "ca-2026-11-03" / "prop-2" /
         "script.toml").write_text("this is = = not toml\n", encoding="utf-8")
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        self.make_worker().run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["failed_stage"], "script")
        self.assertIn("script.toml", row["error"])


class FailsCheckTest(WorkerTestCase):
    def test_fails_check_with_output(self):
        script_path = (self.fake_repo / "data" / "ca-2026-11-03" / "prop-2" /
                      "script.toml")
        text = script_path.read_text(encoding="utf-8")
        text = text.replace("The Legislature put it",
                            "The bold Legislature put it", 1)
        script_path.write_text(text, encoding="utf-8")
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        self.make_worker().run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["failed_stage"], "check")
        self.assertIn("[judgment-word]", row["error"])


class CheckRunsWithoutSidecarsTest(WorkerTestCase):
    def test_check_runs_on_copy_without_sidecars(self):
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        worker = self.make_worker()
        contest_dir = worker._prepare_scratch(job, worker._job_work_dir(job["id"]))
        self.assertFalse((contest_dir / "narration.json").exists())
        run_check(contest_dir, self.deps.standard)  # must not raise


class NarrateRechecksAirtimeTest(WorkerTestCase):
    def test_narrate_rechecks_airtime(self):
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        worker = self.make_worker(runner=FakeRunner(stretch={"yes": 4.0}))
        worker.run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["failed_stage"], "narrate")
        self.assertIn("airtime", row["error"])


class VersionMismatchTest(WorkerTestCase):
    def test_version_mismatch(self):
        election, division, contest, std_v, tmpl_v = self.prop2_key()
        bad_key = (election, division, contest, std_v, tmpl_v + 1)
        job, _ = self.deps.queue.create_job(bad_key)
        self.make_worker().run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["failed_stage"], "script")
        self.assertIn("worker has standard", row["error"])


class CancelWhileRunningTest(WorkerTestCase):
    def test_cancel_while_running(self):
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        block_event = threading.Event()
        runner = FakeRunner(block_stage="narrate", block_event=block_event)
        worker = self.make_worker(runner=runner, heartbeat_interval=0.1)
        t = threading.Thread(target=worker.run_once)
        t.start()
        for _ in range(100):
            row = self.deps.queue.get_job(job["id"])
            if row["state"] == "running" and row["stage"] == "narrate":
                break
            time.sleep(0.05)
        else:
            self.fail("worker never reached the narrate stage")

        ok, _ = self.deps.queue.transition(job["id"], "cancel")
        self.assertTrue(ok)
        t.join(timeout=5)
        self.assertFalse(t.is_alive())

        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "cancelled")
        self.assertFalse((worker.work_dir / str(job["id"])).exists())
        self.assertIsNone(self.deps.queue.claim("someone-else"))


class StopReleasesJobTest(WorkerTestCase):
    def test_stop_releases_job(self):
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        block_event = threading.Event()
        runner = FakeRunner(block_stage="narrate", block_event=block_event)
        worker = self.make_worker(runner=runner, heartbeat_interval=5.0)
        t = threading.Thread(target=worker.run_once)
        t.start()
        for _ in range(100):
            row = self.deps.queue.get_job(job["id"])
            if row["state"] == "running":
                break
            time.sleep(0.05)
        else:
            self.fail("worker never claimed the job")

        worker.stop()
        t.join(timeout=5)

        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "queued")
        self.assertFalse((worker.work_dir / str(job["id"])).exists())

        worker2 = self.make_worker(worker_id="w2")
        self.assertTrue(worker2.run_once())
        self.assertEqual(self.deps.queue.get_job(job["id"])["state"], "done")


class DeadWorkerTest(WorkerTestCase):
    config_overrides = {"heartbeat_timeout": 0.2}

    def test_dead_worker_job_completed_by_another(self):
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        claimed = self.client.claim("dead-worker")
        self.assertIsNotNone(claimed)
        time.sleep(0.4)
        worker2 = self.make_worker(worker_id="w2")
        self.assertTrue(worker2.run_once())
        self.assertEqual(self.deps.queue.get_job(job["id"])["state"], "done")


class EncodeOutputsTest(WorkerTestCase):
    def test_encode_stage_outputs_and_master_kept(self):
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        worker = self.make_worker()
        self.assertTrue(worker.run_once())
        key_hash = hash_for_key(key)
        master_path = worker.masters_dir / key_hash / "master.mp4"
        self.assertTrue(master_path.is_file())

        resp, served = self.get_public(f"/v/{key_hash}/{job['id']}/video.mp4")
        self.assertEqual(resp.status, 200)
        self.assertNotEqual(served, master_path.read_bytes())

        resp, poster_bytes = self.get_public(f"/v/{key_hash}/{job['id']}/poster.jpg")
        self.assertEqual(resp.getheader("Content-Type"), "image/jpeg")
        self.assertTrue(poster_bytes.startswith(b"\xff\xd8"))


class MasterRemovedOnFailureTest(WorkerTestCase):
    def test_master_removed_on_failure(self):
        class BoomRunner(FakeRunner):
            def encode(self, master, web, poster):
                raise PipelineError("boom")

        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        worker = self.make_worker(runner=BoomRunner())
        worker.run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "failed")
        key_hash = hash_for_key(key)
        self.assertFalse((worker.masters_dir / key_hash).exists())


class FakePopenProcess:
    def __init__(self, argv, **kwargs):
        self.argv = argv
        self.kwargs = kwargs
        self.returncode = 0

    def communicate(self):
        return b"", None

    def kill(self):
        self.returncode = -9


class BlockingFakeProcess:
    def __init__(self, argv, **kwargs):
        self.argv = argv
        self.returncode = None
        self._event = threading.Event()

    def communicate(self):
        self._event.wait()
        self.returncode = -9
        return b"killed", None

    def kill(self):
        self._event.set()


class SubprocessRunnerArgvTest(unittest.TestCase):
    def test_subprocess_runner_argv(self):
        calls = []

        def fake_popen(argv, **kwargs):
            calls.append(argv)
            return FakePopenProcess(argv)

        runner = SubprocessRunner("/repo", popen=fake_popen)
        runner.narrate(Path("/repo/data/e/c"))
        self.assertEqual(calls[-1], ["/repo/scripts/narrate.sh",
                                     "/repo/data/e/c"])

        out_dir = Path("/tmp/does-not-need-to-exist-for-this-test")
        result = runner.render(PROP_2, out_dir)
        self.assertEqual(calls[-1], [
            sys.executable, "-m", "ballotreels", "render", str(PROP_2),
            "--format", "9x16", "--out", str(out_dir)])
        self.assertEqual(result, out_dir / "ca-2026-11-03-prop-2-9x16.mp4")

    def test_render_passes_the_site_url_on(self):
        calls = []

        def fake_popen(argv, **kwargs):
            calls.append(argv)
            return FakePopenProcess(argv)

        runner = SubprocessRunner("/repo", popen=fake_popen,
                                  site_url="https://staging.example.org")
        out_dir = Path("/tmp/does-not-need-to-exist-for-this-test")
        runner.render(PROP_2, out_dir)
        self.assertEqual(calls[-1][-2:],
                         ["--site-url", "https://staging.example.org"])

    def test_encode_argv(self):
        calls = []

        def fake_popen(argv, **kwargs):
            calls.append(argv)
            return FakePopenProcess(argv)

        runner = SubprocessRunner("/repo", ffmpeg="ffmpeg", crf=28,
                                  maxrate="1500k", bufsize="3000k",
                                  popen=fake_popen)
        runner.encode(Path("/m.mp4"), Path("/w.mp4"), Path("/p.jpg"))
        self.assertEqual(len(calls), 2)
        video_argv, poster_argv = calls
        self.assertIn("libx264", video_argv)
        self.assertIn("yuv420p", video_argv)
        self.assertIn("aac", video_argv)
        self.assertIn("+faststart", video_argv)
        self.assertEqual(video_argv[video_argv.index("-crf") + 1], "28")
        self.assertEqual(video_argv[video_argv.index("-maxrate") + 1],
                         "1500k")
        self.assertIn("-frames:v", poster_argv)
        self.assertIn(str(Path("/p.jpg")), poster_argv)

    def test_subprocess_runner_kill(self):
        def fake_popen(argv, **kwargs):
            return BlockingFakeProcess(argv)

        runner = SubprocessRunner("/repo", popen=fake_popen)
        result = {}

        def go():
            try:
                runner.narrate(Path("/x"))
            except PipelineError as e:
                result["error"] = e

        t = threading.Thread(target=go)
        t.start()
        time.sleep(0.1)
        runner.kill()
        t.join(timeout=5)
        self.assertFalse(t.is_alive())
        self.assertIn("error", result)

    def test_subprocess_runner_kill_reaches_grandchild(self):
        # narrate.sh runs the TTS as a child of the shell, not via exec;
        # a kill must stop that grandchild too, or communicate() waits
        # for it while it holds the output pipe.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "scripts" / "narrate.sh"
            script.parent.mkdir()
            script.write_text("#!/bin/sh\nsleep 30\ntrue\n")
            script.chmod(0o755)
            runner = SubprocessRunner(tmp)
            result = {}

            def go():
                try:
                    runner.narrate(Path(tmp))
                except PipelineError as e:
                    result["error"] = e

            t = threading.Thread(target=go)
            start = time.monotonic()
            t.start()
            time.sleep(0.3)
            runner.kill()
            t.join(timeout=10)
            self.assertFalse(t.is_alive())
            self.assertLess(time.monotonic() - start, 5)
            self.assertIn("error", result)

    def test_interrupt_kills_child_group(self):
        # Children run in their own session, so a terminal's Ctrl-C reaches
        # only the worker; an interrupted wait must take the child's whole
        # group down rather than leave the TTS running as an orphan.
        import os
        import signal
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "grandchild.pid"
            script = Path(tmp) / "scripts" / "narrate.sh"
            script.parent.mkdir()
            script.write_text(
                f"#!/bin/sh\nsh -c 'echo $$ > {pidfile}; exec sleep 30'\n"
                "true\n")
            script.chmod(0o755)
            driver = subprocess.Popen(
                [sys.executable, "-c",
                 "import sys; from pathlib import Path; "
                 "from ballotreels.pipeline import SubprocessRunner; "
                 "SubprocessRunner(sys.argv[1]).narrate(Path(sys.argv[1]))",
                 tmp], cwd=str(REPO), stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 10
            while not pidfile.exists() or not pidfile.read_text().strip():
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.05)
            grandchild = int(pidfile.read_text())
            driver.send_signal(signal.SIGINT)
            driver.wait(timeout=10)

            def alive(pid):
                try:
                    stat = Path(f"/proc/{pid}/stat").read_text()
                except FileNotFoundError:
                    return False
                return stat.rsplit(")", 1)[1].split()[0] != "Z"

            deadline = time.monotonic() + 3
            while alive(grandchild) and time.monotonic() < deadline:
                time.sleep(0.05)
            if alive(grandchild):
                os.kill(grandchild, signal.SIGKILL)
                self.fail("the narrate grandchild outlived the interrupt")



class WorkerCliTest(unittest.TestCase):
    def test_worker_cli_requires_server_and_token(self):
        import os

        cases = [
            (["worker"], {"BALLOTREELS_SERVER": None, "BALLOTREELS_TOKEN": None},
             "no server URL"),
            (["worker", "--server", "http://x"],
             {"BALLOTREELS_SERVER": None, "BALLOTREELS_TOKEN": None},
             "BALLOTREELS_TOKEN is not set"),
        ]
        for argv, env, expect in cases:
            with self.subTest(argv=argv):
                saved = {k: os.environ.pop(k, None) for k in env}
                for k, v in env.items():
                    if v is not None:
                        os.environ[k] = v
                try:
                    out, err = io.StringIO(), io.StringIO()
                    code = main(argv, out=out, err=err)
                    self.assertEqual(code, 2)
                    self.assertIn(expect, err.getvalue())
                finally:
                    for k, v in saved.items():
                        if v is None:
                            os.environ.pop(k, None)
                        else:
                            os.environ[k] = v

    def test_worker_cli_routes_interrupt_and_hangup_to_stop(self):
        # SIGINT and SIGHUP must stop the worker the way SIGTERM does
        # (kill the runner's group, release the job), not raise
        # KeyboardInterrupt past a child running in its own session.
        import http.server
        import os
        import signal
        from unittest import mock

        class NoJobs(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(204)
                self.end_headers()

            def log_message(self, *a):
                pass

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), NoJobs)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        saved = {s: signal.getsignal(s) for s in
                 (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)}
        for s, h in saved.items():
            self.addCleanup(signal.signal, s, h)
        tmp = self.enterContext(tempfile.TemporaryDirectory())
        stops = []
        with mock.patch.dict(os.environ, {"BALLOTREELS_TOKEN": "t"}), \
                mock.patch.object(Worker, "stop",
                                  lambda self: stops.append(True)):
            code = main(["worker", "--server",
                         f"http://127.0.0.1:{srv.server_address[1]}",
                         "--runner", "fake", "--once",
                         "--work-dir", str(Path(tmp) / "work"),
                         "--masters-dir", str(Path(tmp) / "masters")],
                        out=io.StringIO(), err=io.StringIO())
            self.assertEqual(code, 0)
            for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                with self.subTest(signal=s.name):
                    handler = signal.getsignal(s)
                    self.assertTrue(callable(handler))
                    self.assertIsNot(handler, saved[s])
                    before = len(stops)
                    handler(s, None)
                    self.assertEqual(len(stops), before + 1)



class UnreachableServerTest(unittest.TestCase):
    def test_run_forever_survives_unreachable_server(self):
        import socket
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()  # nothing listens here now
        client = WorkerClient(f"http://127.0.0.1:{port}", "t",
                              timeout=1, retry_delays=())
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        worker = Worker(client=client, worker_id="w1", repo=tmp,
                        runner=FakeRunner(), writer=HandWrittenScriptWriter(),
                        storage=LocalStorage(client), standard=None,
                        work_dir=tmp / "work", masters_dir=tmp / "masters",
                        poll_interval=0.01)
        errors = []

        def run():
            try:
                worker.run_forever()
            except BaseException as e:  # what the fix prevents
                errors.append(e)

        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(0.3)
        self.assertTrue(t.is_alive(), errors)
        worker.stop()
        t.join(timeout=5)
        self.assertFalse(t.is_alive())
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()


class NoTTSRunner(FakeRunner):
    """A FakeRunner whose narrate must not be called: standing in for the
    real TTS, which a committed, current narration never needs."""

    def __init__(self):
        super().__init__()
        self.narrated = []

    def narrate(self, contest_dir):
        self.narrated.append(Path(contest_dir))
        raise AssertionError("TTS called for a contest whose committed "
                             "narration matches its script")


class CommittedNarrationReusedTest(WorkerTestCase):
    """Arizona Proposition 141's render re-synthesised a narration already
    narrated, transcript-checked and committed on the host, and the new take
    failed the transcript check: the scratch copy dropped the sidecars, so
    `say` had no phrase_cache to reuse. A committed narration that matches
    the script is reused byte for byte, with no TTS call."""

    def setUp(self):
        super().setUp()
        dest = self.fake_repo / "data" / "ca-2026-11-03" / "prop-2"
        for name in NARRATION_SIDECARS + ("narration.txt",):
            shutil.copy2(PROP_2 / name, dest / name)
        self.dest = dest

    def test_scratch_copy_keeps_the_sidecars(self):
        job, _ = self.deps.queue.create_job(self.prop2_key())
        worker = self.make_worker()
        contest_dir = worker._prepare_scratch(
            job, worker._job_work_dir(job["id"]))
        for name in NARRATION_SIDECARS:
            self.assertEqual((contest_dir / name).read_bytes(),
                             (self.dest / name).read_bytes(), name)

    def test_current_narration_never_calls_tts(self):
        job, _ = self.deps.queue.create_job(self.prop2_key())
        runner = NoTTSRunner()
        self.make_worker(runner=runner).run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "done", row["error"])
        self.assertEqual(runner.narrated, [])

    def test_visual_only_edit_never_calls_tts(self):
        # Montana CI-132's render re-synthesised its yes side after an edit
        # to an illustration only: what is on screen is not spoken, so the
        # committed narration stays current and is reused as it is.
        script = self.dest / "script.toml"
        script.write_text(script.read_text(encoding="utf-8").replace(
            'title = "Where General Fund money goes (approximate)"',
            'title = "Where the General Fund goes (approximate)"'),
            encoding="utf-8")
        self.assertIn("Where the General Fund goes",
                      script.read_text(encoding="utf-8"))
        self.assertEqual(narration_state(load_contest(self.dest)), CURRENT)
        job, _ = self.deps.queue.create_job(self.prop2_key())
        runner = NoTTSRunner()
        self.make_worker(runner=runner).run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "done", row["error"])
        self.assertEqual(runner.narrated, [])

    def test_stale_narration_fails_fast(self):
        # An edited script's committed narration is not re-made on the
        # worker: `say` would re-speak the edited line and the unchanged
        # line after it, and either new take can fail its transcript check.
        script = self.dest / "script.toml"
        script.write_text(script.read_text(encoding="utf-8").replace(
            "A no vote means the current rules would not change.",
            "A no vote means the current rules would stay the same."),
            encoding="utf-8")
        job, _ = self.deps.queue.create_job(self.prop2_key())
        runner = NoTTSRunner()
        self.make_worker(runner=runner).run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["failed_stage"], "narrate")
        self.assertIn("scripts/narrate.sh", row["error"])
        self.assertEqual(runner.narrated, [])


class CheckJudgesFreshnessTest(WorkerTestCase):
    """The check stage runs on the scratch copy, which carries the
    contest's committed sidecars, so it judges a phrase fresh exactly as
    `python -m ballotreels check` does in the repo: a narration current for
    its script is never linted, and an edited line is."""

    def setUp(self):
        super().setUp()
        self.dest = self.fake_repo / "data" / "ca-2026-11-03" / "prop-2"
        write_committed_narration(self.dest)

    def run_job(self, standard=None):
        job, _ = self.deps.queue.create_job(self.prop2_key())
        runner = NoTTSRunner()
        self.make_worker(runner=runner, standard=standard).run_once()
        return self.deps.queue.get_job(job["id"]), runner

    def test_current_narration_passes_whatever_the_list(self):
        every_word = replace(self.deps.standard, speakability=(
            Risk(re.compile(r"\w+"), "test reason", "test suggestion"),))
        row, runner = self.run_job(every_word)
        self.assertEqual(row["state"], "done", row["error"])
        self.assertEqual(runner.narrated, [])

    def test_fresh_line_fails_check(self):
        script = self.dest / "script.toml"
        script.write_text(script.read_text(encoding="utf-8").replace(
            "A no vote means the current rules would not change.",
            "A no vote means the rules stay, unless a driver consents."),
            encoding="utf-8")
        row, runner = self.run_job()
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["failed_stage"], "check")
        self.assertIn("[speakability] vote.line[1]: 'consents'", row["error"])
        # The committed narration still covers every other phrase.
        self.assertNotIn("1980 to 2014", row["error"])
        self.assertEqual(runner.narrated, [])
