import re
import subprocess
import unittest
import urllib.error
import urllib.request

from ballotreels import sigv4
from ballotreels.queue import hash_for_key
from ballotreels.storage import S3ConfigError, S3Storage

from . import fake_s3
from .helpers import REPO
from .test_worker import WorkerTestCase


class S3WorkerTestCase(WorkerTestCase):
    def setUp(self):
        super().setUp()
        self.s3 = fake_s3.FakeS3Server()
        self.s3.start()
        self.addCleanup(self.s3.stop)
        self.storage = self._make_storage(fake_s3.SECRET_ACCESS_KEY)

    def _make_storage(self, secret_key: str,
                      region: str = fake_s3.REGION) -> S3Storage:
        return S3Storage(
            endpoint=self.s3.base_url, region=region,
            bucket="ballotreels-test",
            public_base=f"{self.s3.base_url}/ballotreels-test",
            access_key_id=fake_s3.ACCESS_KEY_ID, secret_access_key=secret_key,
            prefix="ballotreels")

    def make_worker(self, runner=None, worker_id="w1",
                    heartbeat_interval=0.2, storage=None):
        from ballotreels.pipeline import FakeRunner, HandWrittenScriptWriter
        from ballotreels.worker import Worker

        runner = runner if runner is not None else FakeRunner()
        return Worker(client=self.client, worker_id=worker_id,
                     repo=self.fake_repo, runner=runner,
                     writer=HandWrittenScriptWriter(),
                     storage=storage or self.storage,
                     standard=self.standard,
                     work_dir=self.tmp / "work",
                     masters_dir=self.tmp / "masters",
                     poll_interval=0.05,
                     heartbeat_interval=heartbeat_interval)


class S3EndToEndTest(S3WorkerTestCase):
    def test_worker_uploads_to_s3_end_to_end(self):
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        worker = self.make_worker()
        self.assertTrue(worker.run_once())

        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "done")

        key_hash = hash_for_key(key)
        expected = {f"/ballotreels-test/ballotreels/{key_hash}/{job['id']}/{n}"
                   for n in ("video.mp4", "poster.jpg", "script.toml",
                            "sources.json")}
        self.assertEqual(set(self.s3.objects.keys()), expected)
        self.assertEqual(self.s3.put_count, 4)

        incoming = self.data_dir / "cache" / ".incoming"
        self.assertFalse(incoming.is_dir() and any(incoming.iterdir()))

        video = self.deps.queue.video_for(key)
        self.assertEqual(video.storage, "s3")
        for name in ("video", "poster"):
            self.assertTrue(video.urls[name].startswith(self.s3.base_url))

        with urllib.request.urlopen(video.urls["video"]) as resp:
            data = resp.read()
        self.assertGreater(len(data), 0)


class S3BadSignatureTest(S3WorkerTestCase):
    def test_bad_signature_fails_cache_stage(self):
        bad_storage = self._make_storage("wrong-secret")
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        worker = self.make_worker(storage=bad_storage)
        worker.run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["failed_stage"], "cache")
        self.assertIn("SignatureDoesNotMatch", row["error"])
        self.assertIsNone(self.deps.queue.video_for(key))


    def test_wrong_region_rejected(self):
        storage = self._make_storage(fake_s3.SECRET_ACCESS_KEY,
                                     region="nyc3")
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        self.make_worker(storage=storage).run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["failed_stage"], "cache")
        self.assertIn("SignatureDoesNotMatch", row["error"])


class FakeS3ChecksTest(unittest.TestCase):
    """The fake rejects what a real bucket would, so the S3 tests can
    catch a regression in what the worker signs."""

    def setUp(self):
        self.s3 = fake_s3.FakeS3Server()
        self.s3.start()
        self.addCleanup(self.s3.stop)

    def _put(self, signed: list[str], acl: str = "public-read") -> int:
        body = b"hello"
        host = self.s3.base_url.split("://", 1)[1]
        uri = "/b/k"
        amz_date = "20261026T000000Z"
        sha = sigv4.sha256_hex(body)
        headers = {"host": host, "x-amz-date": amz_date,
                   "x-amz-content-sha256": sha, "x-amz-acl": acl,
                   "cache-control": "public, max-age=31536000, immutable",
                   "content-type": "text/plain"}
        signature = sigv4.sign("PUT", uri, "", headers, signed, sha,
                               amz_date, fake_s3.REGION, "s3",
                               fake_s3.SECRET_ACCESS_KEY)
        scope = sigv4.credential_scope(amz_date[:8], fake_s3.REGION, "s3")
        send = {k: v for k, v in headers.items() if k != "host"}
        send["Authorization"] = sigv4.authorization_header(
            fake_s3.ACCESS_KEY_ID, scope, signed, signature)
        req = urllib.request.Request(self.s3.base_url + uri, data=body,
                                     method="PUT", headers=send)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_all_headers_signed_accepted(self):
        self.assertEqual(self._put(list(fake_s3.REQUIRED_SIGNED)), 200)

    def test_header_left_unsigned_rejected(self):
        self.assertEqual(self._put(["x-amz-date"]), 403)
        for left_out in fake_s3.REQUIRED_SIGNED:
            with self.subTest(unsigned=left_out):
                signed = [h for h in fake_s3.REQUIRED_SIGNED
                          if h != left_out]
                self.assertEqual(self._put(signed), 403)

    def test_acl_must_be_public_read(self):
        self.assertEqual(
            self._put(list(fake_s3.REQUIRED_SIGNED), acl="private"), 400)


class S3ContentHashTest(S3WorkerTestCase):
    def test_content_hash_mismatch_rejected(self):
        self.s3.corrupt_next = True
        key = self.prop2_key()
        job, _ = self.deps.queue.create_job(key)
        worker = self.make_worker()
        worker.run_once()
        row = self.deps.queue.get_job(job["id"])
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["failed_stage"], "cache")
        self.assertIn("XAmzContentSHA256Mismatch", row["error"])


class S3ConfigMissingTest(unittest.TestCase):
    FULL_ENV = {
        "BALLOTREELS_S3_ENDPOINT": "https://x.example.com",
        "BALLOTREELS_S3_REGION": "us-east-1",
        "BALLOTREELS_S3_BUCKET": "bucket",
        "BALLOTREELS_S3_PUBLIC_BASE": "https://cdn.example.com",
        "BALLOTREELS_S3_ACCESS_KEY_ID": "AKIAEXAMPLE",
        "BALLOTREELS_S3_SECRET_ACCESS_KEY": "secret",
    }

    def test_s3_config_missing(self):
        for missing_var in self.FULL_ENV:
            with self.subTest(missing=missing_var):
                env = dict(self.FULL_ENV)
                del env[missing_var]
                with self.assertRaises(S3ConfigError) as cm:
                    S3Storage.from_env(env)
                self.assertIn(missing_var, str(cm.exception))


class S3ReuploadTest(S3WorkerTestCase):
    def test_s3_reupload_same_keys(self):
        key = self.prop2_key()
        job = {"id": 1, "claim": "c", "election": key[0], "division": key[1],
              "contest": key[2], "standard_version": key[3],
              "template_version": key[4]}
        files1 = {"video.mp4": b"first", "poster.jpg": b"p",
                 "script.toml": b"s", "sources.json": b"[]"}
        result1 = self.storage.put_all(job, files1)
        keys1 = {v["key"] for v in result1["objects"].values()}

        files2 = {"video.mp4": b"second-different-bytes", "poster.jpg": b"p",
                 "script.toml": b"s", "sources.json": b"[]"}
        result2 = self.storage.put_all(job, files2)
        keys2 = {v["key"] for v in result2["objects"].values()}

        self.assertEqual(keys1, keys2)
        self.assertEqual(self.s3.put_count, 8)
        self.assertEqual(len(self.s3.objects), 4)

    def test_s3_regenerated_job_gets_new_keys(self):
        # A new job for the same cache key (a regeneration) must not
        # overwrite objects the CDN serves as immutable.
        key = self.prop2_key()
        files = {"video.mp4": b"v", "poster.jpg": b"p",
                 "script.toml": b"s", "sources.json": b"[]"}
        keys = []
        for job_id in (1, 2):
            job = {"id": job_id, "claim": "c", "election": key[0],
                  "division": key[1], "contest": key[2],
                  "standard_version": key[3], "template_version": key[4]}
            result = self.storage.put_all(job, files)
            keys.append({v["key"] for v in result["objects"].values()})
        self.assertEqual(keys[0] & keys[1], set())
        self.assertEqual(len(self.s3.objects), 8)


class NoRealEndpointsTest(unittest.TestCase):
    def test_no_real_endpoints(self):
        result = subprocess.run(["git", "ls-files"], cwd=REPO,
                               capture_output=True, text=True, check=True)
        files = [f for f in result.stdout.splitlines()
                if not f.startswith("tests/")]
        pattern = re.compile(r"[a-z0-9.<>-]*\.digitaloceanspaces\.com")
        violations = []
        for f in files:
            path = REPO / f
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for m in pattern.finditer(text):
                if m.group(0) != "<region>.digitaloceanspaces.com":
                    violations.append((f, m.group(0)))
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
