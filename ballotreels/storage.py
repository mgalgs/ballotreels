"""Where the worker puts a finished video, behind one interface with two
backends (operator decision 1793069336-01):

- `local` (default, what tests use): PUTs each file to the serve tier's
  worker upload API; the serve tier stores and serves them.
- `s3`: PUTs straight to a DigitalOcean Spaces-compatible bucket, signed
  with `ballotreels.sigv4`; the serve tier never sees the bytes, only the
  object URLs the worker reports back in `complete`.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping, Protocol

from . import sigv4
from .queue import hash_for_key

S3_ENV_VARS = (
    "BALLOTREELS_S3_ENDPOINT",
    "BALLOTREELS_S3_REGION",
    "BALLOTREELS_S3_BUCKET",
    "BALLOTREELS_S3_PUBLIC_BASE",
    "BALLOTREELS_S3_ACCESS_KEY_ID",
    "BALLOTREELS_S3_SECRET_ACCESS_KEY",
)

CONTENT_TYPES = {
    "video.mp4": "video/mp4",
    "poster.jpg": "image/jpeg",
    "script.toml": "application/toml",
    "sources.json": "application/json",
}

# File name -> the name `complete`'s `objects` map uses for it (A25).
OBJECT_NAMES = {"video.mp4": "video", "poster.jpg": "poster",
               "script.toml": "script", "sources.json": "sources"}


class Storage(Protocol):
    def put_all(self, job: dict[str, Any],
               files: dict[str, bytes]) -> dict[str, Any]: ...


class LocalStorage:
    """Uploads through the serve tier's own worker API
    (`PUT /worker/jobs/<id>/files/<name>`)."""

    def __init__(self, client):
        self.client = client

    def put_all(self, job: dict[str, Any],
               files: dict[str, bytes]) -> dict[str, Any]:
        for name, data in files.items():
            self.client.upload(job["id"], job["claim"], name, data)
        return {"storage": "local"}


class S3ConfigError(Exception):
    """One or more BALLOTREELS_S3_* variables are missing."""


class S3Storage:
    """PUTs each file to an S3-compatible bucket (DigitalOcean Spaces),
    path-style (`PUT <endpoint>/<bucket>/<key>`), public-read, with a
    long cache lifetime. The object key is deterministic from the cache
    key (A26), so a retried upload overwrites rather than duplicates."""

    def __init__(self, endpoint: str, region: str, bucket: str,
                public_base: str, access_key_id: str,
                secret_access_key: str, prefix: str = "ballotreels"):
        self.endpoint = endpoint.rstrip("/")
        self.region = region
        self.bucket = bucket
        self.public_base = public_base.rstrip("/")
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.prefix = prefix

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "S3Storage":
        missing = [name for name in S3_ENV_VARS if not env.get(name)]
        if missing:
            raise S3ConfigError(
                "missing required S3 storage variable(s): " +
                ", ".join(missing))
        return cls(
            endpoint=env["BALLOTREELS_S3_ENDPOINT"],
            region=env["BALLOTREELS_S3_REGION"],
            bucket=env["BALLOTREELS_S3_BUCKET"],
            public_base=env["BALLOTREELS_S3_PUBLIC_BASE"],
            access_key_id=env["BALLOTREELS_S3_ACCESS_KEY_ID"],
            secret_access_key=env["BALLOTREELS_S3_SECRET_ACCESS_KEY"],
            prefix=env.get("BALLOTREELS_S3_PREFIX", "ballotreels"))

    def _object_key(self, key_hash: str, name: str) -> str:
        return f"{self.prefix}/{key_hash}/{name}"

    def _put_one(self, key_hash: str, name: str, data: bytes) -> dict[str, str]:
        object_key = self._object_key(key_hash, name)
        parts = urllib.parse.urlsplit(self.endpoint)
        host = parts.netloc
        uri = f"/{self.bucket}/{object_key}"
        url = f"{parts.scheme}://{host}{uri}"
        payload_hash = sigv4.sha256_hex(data)
        amz_date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        headers = {
            "host": host,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "x-amz-acl": "public-read",
            "cache-control": "public, max-age=31536000, immutable",
            "content-type": CONTENT_TYPES.get(name, "application/octet-stream"),
        }
        signed_headers = list(headers.keys())
        signature = sigv4.sign("PUT", uri, "", headers, signed_headers,
                               payload_hash, amz_date, self.region, "s3",
                               self.secret_access_key)
        scope = sigv4.credential_scope(amz_date[:8], self.region, "s3")
        auth = sigv4.authorization_header(self.access_key_id, scope,
                                          signed_headers, signature)
        send_headers = {k: v for k, v in headers.items() if k != "host"}
        send_headers["Authorization"] = auth
        send_headers["Host"] = host
        req = urllib.request.Request(url, data=data, method="PUT",
                                     headers=send_headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            with e:
                body = e.read().decode("utf-8", "replace")
            raise RuntimeError(
                f"S3 PUT {object_key} failed: HTTP {e.code}: {body}") from None
        return {"key": object_key, "url": f"{self.public_base}/{object_key}"}

    def put_all(self, job: dict[str, Any],
               files: dict[str, bytes]) -> dict[str, Any]:
        key = (job["election"], job["division"], job["contest"],
              job["standard_version"], job["template_version"])
        key_hash = hash_for_key(key)
        objects = {}
        for name, data in files.items():
            objects[OBJECT_NAMES.get(name, name)] = self._put_one(
                key_hash, name, data)
        return {"storage": "s3", "objects": objects}
