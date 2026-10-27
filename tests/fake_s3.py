"""An in-process fake S3-compatible server, for testing `S3Storage`
without a real DigitalOcean Spaces bucket (A28).

Not circular: it re-derives the expected signature with the same
`ballotreels.sigv4` module the signer uses, which is pinned against
AWS's own published vectors in tests/test_sigv4.py. This fake only
checks what actually reached the wire, so it can catch a wrong secret
or a body corrupted in transit the same way a real bucket would.
"""

from __future__ import annotations

import hmac
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ballotreels import sigv4

ACCESS_KEY_ID = "fake-access-key-id"
SECRET_ACCESS_KEY = "fake-secret-access-key"
REGION = "us-east-1"

# Headers a PUT must sign (plan A26); a real bucket rejects a request
# that leaves host or an x-amz-* header it sent out of SignedHeaders.
REQUIRED_SIGNED = ("host", "x-amz-date", "x-amz-content-sha256",
                   "x-amz-acl", "cache-control", "content-type")


class _Handler(BaseHTTPRequestHandler):
    server: "FakeS3Server"

    def log_message(self, *a):
        pass

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        if self.server.corrupt_next:
            body = bytearray(body)
            body[0] ^= 0xFF
            body = bytes(body)
            self.server.corrupt_next = False
        ok, code, reason = self._check(body)
        if not ok:
            return self._error(code, reason)
        self.server.objects[self.path] = body
        self.server.put_count += 1
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        body = self.server.objects.get(self.path)
        if body is None:
            return self._error(404, "NoSuchKey")
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, reason: str) -> None:
        body = f"<Error><Code>{reason}</Code></Error>".encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check(self, body: bytes) -> tuple[bool, int, str]:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("AWS4-HMAC-SHA256 "):
            return False, 403, "SignatureDoesNotMatch"
        parts = {}
        for item in auth[len("AWS4-HMAC-SHA256 "):].split(", "):
            k, _, v = item.partition("=")
            parts[k.strip()] = v.strip()
        credential = parts.get("Credential", "")
        signed_headers_str = parts.get("SignedHeaders", "")
        signature = parts.get("Signature", "")
        try:
            access_key, date_stamp, region, service, _ = credential.split("/")
        except ValueError:
            return False, 403, "SignatureDoesNotMatch"

        content_sha = self.headers.get("x-amz-content-sha256", "")
        if content_sha != sigv4.sha256_hex(body):
            return False, 400, "XAmzContentSHA256Mismatch"
        if self.headers.get("x-amz-acl") != "public-read":
            return False, 400, "MissingHeader:x-amz-acl=public-read"
        if not self.headers.get("Cache-Control"):
            return False, 400, "MissingHeader:Cache-Control"

        signed_names = signed_headers_str.split(";")
        unsigned = [h for h in REQUIRED_SIGNED if h not in signed_names]
        if unsigned:
            return False, 403, ("SignatureDoesNotMatch:unsigned "
                                + ",".join(unsigned))
        amz_date = self.headers.get("x-amz-date", "")
        if region != self.server.region or service != "s3" or \
                date_stamp != amz_date[:8]:
            return False, 403, "SignatureDoesNotMatch:credential scope"
        headers_for_sig = {name: self.headers.get(name, "")
                          for name in signed_names}
        # Signed with the server's own region and service, not the
        # client's claim of them.
        expected = sigv4.sign(
            "PUT", self.path, "", headers_for_sig, signed_names,
            content_sha, amz_date, self.server.region, "s3",
            self.server.secret_key)
        if (access_key != self.server.access_key or
                not hmac.compare_digest(expected, signature)):
            return False, 403, "SignatureDoesNotMatch"
        return True, 200, ""


class FakeS3Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address=("127.0.0.1", 0), access_key=ACCESS_KEY_ID,
                secret_key=SECRET_ACCESS_KEY, region=REGION):
        super().__init__(address, _Handler)
        self.objects: dict[str, bytes] = {}
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.put_count = 0
        self.corrupt_next = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.shutdown()
        self.server_close()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"
