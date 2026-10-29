"""The acceptance walk: a real serve-tier subprocess and a real
fake-runner worker subprocess, talking over real HTTP sockets, exactly
as the operator would run them (docs/ARCHITECTURE.md end to end)."""

from __future__ import annotations

import http.client
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from pathlib import Path

from . import geo_fixtures
from .helpers import REPO, copy_contest, git_commit_all

TOKEN = "e2e-test-token"


def _line_reader(stream, out_queue: queue.Queue) -> None:
    for line in stream:
        out_queue.put(line)


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = Path(tmp.name) / "var"
        geo_fixtures.build_fixture_geo(self.data_dir)
        self.procs: list[subprocess.Popen] = []
        self.addCleanup(self._kill_all)

    def _kill_all(self):
        for proc in self.procs:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            if proc.stdout is not None:
                proc.stdout.close()

    def _env(self):
        env = dict(os.environ)
        env["BALLOTREELS_TOKEN"] = TOKEN
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _start_serve(self):
        proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "ballotreels", "serve",
             "--data-dir", str(self.data_dir), "--election", "ca-2026-11-03",
             "--public-port", "0", "--private-port", "0"],
            cwd=REPO, env=self._env(), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.procs.append(proc)
        lines: queue.Queue = queue.Queue()
        reader = threading.Thread(target=_line_reader, args=(proc.stdout, lines),
                                  daemon=True)
        reader.start()
        public_port = private_port = None
        for _ in range(2):
            try:
                line = lines.get(timeout=20)
            except queue.Empty:
                self.fail("serve did not print its listening lines in time")
            m = re.search(r"(public|private) listening on http://[^:]+:(\d+)",
                         line)
            if not m:
                self.fail(f"unexpected serve output: {line!r}")
            if m.group(1) == "public":
                public_port = int(m.group(2))
            else:
                private_port = int(m.group(2))
        self.assertIsNotNone(public_port)
        self.assertIsNotNone(private_port)
        return proc, public_port, private_port

    def _worker_repo(self, private_port):
        """The worker's checkout: Prop 2 as committed, with a stand-in for
        its take (the real audio is not in git), which the operator
        pushes to the store as they would the real one."""
        repo = self.data_dir.parent / "repo"
        prop_2 = copy_contest(REPO / "data" / "ca-2026-11-03" / "prop-2",
                              repo / "data" / "ca-2026-11-03" / "prop-2")
        git_commit_all(repo)
        proc = subprocess.run(
            [sys.executable, "-u", "-m", "ballotreels", "narration", "push",
             str(prop_2), "--server", f"http://127.0.0.1:{private_port}",
             "--narration-cache", str(self.data_dir / "push-cache")],
            cwd=REPO, env=self._env(), capture_output=True, text=True,
            timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return repo

    def _run_worker_once(self, private_port):
        proc = subprocess.run(
            [sys.executable, "-u", "-m", "ballotreels", "worker",
             "--server", f"http://127.0.0.1:{private_port}",
             "--runner", "fake", "--once",
             "--repo", str(self._worker_repo(private_port)),
             "--work-dir", str(self.data_dir / "work"),
             "--masters-dir", str(self.data_dir / "masters"),
             "--narration-cache", str(self.data_dir / "worker-cache")],
            cwd=REPO, env=self._env(), capture_output=True, text=True,
            timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def _get(self, port, path):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp, body

    def _post(self, port, path, data, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("POST", path, body=json.dumps(data).encode("utf-8"),
                     headers={"Content-Type": "application/json",
                              **(headers or {})})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp, body

    def test_whole_flow_over_http(self):
        _, public_port, private_port = self._start_serve()

        resp, body = self._get(public_port, "/api/zip/99902")
        self.assertEqual(resp.status, 200)
        doc = json.loads(body)
        self.assertIn("cd", doc["ambiguous"])
        self.assertEqual(len(doc["kinds"]["cd"]), 2)

        resp, body = self._get(public_port, "/api/zip/99902/shapes?kind=cd")
        self.assertEqual(resp.status, 200)
        shapes = json.loads(body)
        roles = [f["properties"].get("role") for f in shapes["features"]]
        self.assertEqual(roles.count("zip"), 1)
        self.assertEqual(roles.count("district"), 2)

        chosen_cd = doc["kinds"]["cd"][0]["ocd_id"]
        divisions = [chosen_cd] + [e["ocd_id"] for k, v in doc["kinds"].items()
                                   if k != "cd" for e in v]
        query = "&".join(f"d={urllib.parse.quote(d)}" for d in divisions)
        resp, body = self._get(public_port, f"/api/ballot?{query}")
        self.assertEqual(resp.status, 200)
        ballot = json.loads(body)
        all_ids = [c["id"] for lvl in ballot["levels"] for c in lvl["contests"]]
        self.assertIn("ca-2026-11-03-prop-2", all_ids)

        resp, body = self._post(public_port, "/api/generate",
                                {"contest": "ca-2026-11-03-prop-2"})
        self.assertIn(resp.status, (200, 201))
        job_doc = json.loads(body)
        self.assertIsNotNone(job_doc["job"])
        # A visitor's request waits for the operator's approval.
        self.assertEqual(job_doc["job"]["state"], "pending")
        job_id = job_doc["job"]["id"]
        resp, _ = self._post(private_port, f"/admin/api/jobs/{job_id}/approve",
                             {}, headers={"Authorization": f"Bearer {TOKEN}"})
        self.assertEqual(resp.status, 200)
        resp, body = self._get(public_port, f"/api/jobs/{job_id}")
        job_doc = json.loads(body)
        self.assertEqual(job_doc["state"], "queued")
        self.assertIn("position", job_doc)
        self.assertIn("eta_minutes", job_doc)

        self._run_worker_once(private_port)

        deadline = time.monotonic() + 30
        state = None
        video_url = None
        while time.monotonic() < deadline:
            resp, body = self._get(public_port, f"/api/jobs/{job_id}")
            doc = json.loads(body)
            state = doc["state"]
            video_url = doc.get("video_url")
            if state in ("done", "failed"):
                break
            time.sleep(1)
        self.assertEqual(state, "done")
        self.assertIsNotNone(video_url)

        conn = http.client.HTTPConnection("127.0.0.1", public_port, timeout=10)
        conn.request("GET", video_url, headers={"Range": "bytes=0-9"})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        self.assertEqual(resp.status, 206)
        self.assertEqual(len(data), 10)


if __name__ == "__main__":
    unittest.main()
