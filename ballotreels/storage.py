"""Where the worker puts a finished video, behind one interface
(operator decision 1793069336-01):

- `local` (default, what tests use): PUTs each file to the serve tier's
  worker upload API; the serve tier stores and serves them.
"""

from __future__ import annotations

from typing import Any, Protocol


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
