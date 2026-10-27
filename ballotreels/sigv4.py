"""AWS Signature Version 4, implemented from the published spec with the
stdlib's hmac/hashlib only (no boto3 or other SDK):
docs.aws.amazon.com/general/latest/gr/signature-version-4.html

Used to sign uploads to a DigitalOcean Spaces bucket (S3-compatible), by
`ballotreels.storage.S3Storage`. Tested against AWS's own published
worked examples (A27 in the plan): the IAM docs' derived-signing-key
example, the sigv4 test suite's `get-vanilla`, and the S3 developer
guide's GetObject example.
"""

from __future__ import annotations

import hashlib
import hmac
import urllib.parse

ALGORITHM = "AWS4-HMAC-SHA256"


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _hmac_hex(key: bytes, msg: str) -> str:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).hexdigest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def signing_key(secret_key: str, date_stamp: str, region: str,
                service: str) -> bytes:
    k_date = _hmac(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    return _hmac(k_service, "aws4_request")


def _uri_encode(segment: str) -> str:
    # S3 canonical URIs are not double-encoded: each segment is encoded
    # once, '/' is the path separator (kept, never itself encoded).
    return urllib.parse.quote(segment, safe="-_.~")


def canonical_uri(path: str) -> str:
    if not path:
        return "/"
    return "/".join(_uri_encode(seg) for seg in path.split("/"))


def canonical_query_string(query: str) -> str:
    if not query:
        return ""
    pairs = []
    for part in query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
        else:
            k, v = part, ""
        pairs.append((urllib.parse.quote(k, safe="-_.~"),
                     urllib.parse.quote(v, safe="-_.~")))
    pairs.sort()
    return "&".join(f"{k}={v}" for k, v in pairs)


def canonical_request(method: str, uri: str, query_string: str,
                      headers: dict[str, str], signed_headers: list[str],
                      payload_hash: str) -> str:
    ordered = sorted(signed_headers, key=str.lower)
    canon_headers = "".join(f"{h.lower()}:{headers[h].strip()}\n"
                            for h in ordered)
    signed = ";".join(h.lower() for h in ordered)
    return "\n".join([
        method, canonical_uri(uri), canonical_query_string(query_string),
        canon_headers, signed, payload_hash])


def string_to_sign(amz_date: str, credential_scope: str,
                   canonical_req: str) -> str:
    return "\n".join([
        ALGORITHM, amz_date, credential_scope,
        sha256_hex(canonical_req.encode("utf-8"))])


def credential_scope(date_stamp: str, region: str, service: str) -> str:
    return f"{date_stamp}/{region}/{service}/aws4_request"


def authorization_header(access_key: str, scope: str,
                         signed_headers: list[str], signature: str) -> str:
    signed = ";".join(sorted((h.lower() for h in signed_headers)))
    return (f"{ALGORITHM} Credential={access_key}/{scope}, "
           f"SignedHeaders={signed}, Signature={signature}")


def sign(method: str, uri: str, query_string: str, headers: dict[str, str],
        signed_headers: list[str], payload_hash: str, amz_date: str,
        region: str, service: str, secret_key: str) -> str:
    """The hex signature for one request."""
    date_stamp = amz_date[:8]
    creq = canonical_request(method, uri, query_string, headers,
                             signed_headers, payload_hash)
    sts = string_to_sign(amz_date, credential_scope(date_stamp, region, service),
                         creq)
    key = signing_key(secret_key, date_stamp, region, service)
    return _hmac_hex(key, sts)
