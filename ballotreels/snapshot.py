"""A commit's files, read out of git for the worker to render from.

The worker renders from the repo's committed HEAD as it is when a job is
claimed, never the live checkout: an operator mid-merge leaves conflict
markers in data/ and code there, and every render started in that window
used to fail on them. Everything here only reads git's objects (rev-parse,
ls-tree, cat-file, archive, with GIT_OPTIONAL_LOCKS=0), so the live repo's
.git, index and working tree are never written.

The code and shared assets (every top-level path but data/, which is
almost all of the tree and mostly other contests) are extracted once per
commit, under the worker's own directory, and shared by every job on that
commit; a job takes its own contest's files from the same commit
(`export`). A snapshot is a complete tree of the commit's code, so a path
missing from it fails the render rather than being read from anywhere
else.
"""

from __future__ import annotations

import fcntl
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

# The top-level paths a snapshot leaves out: contest data, which a job
# exports for its own contest alone.
DATA = "data"


class SnapshotError(Exception):
    """git could not read the commit (not a repo, no such path, ...)."""


def _env() -> dict[str, str]:
    # Without this, even a read-only command such as `git status` may
    # refresh and rewrite the index.
    return {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, env=_env())
    if proc.returncode != 0:
        raise SnapshotError(f"git {' '.join(args)}: "
                            f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout.decode("utf-8")


def head(repo: str | Path) -> str:
    """The full sha of the commit HEAD names."""
    return _git(Path(repo), "rev-parse", "--verify", "HEAD^{commit}").strip()


def kind(repo: str | Path, sha: str, path: str) -> str | None:
    """"tree" or "blob" for repo-relative `path` at commit `sha`, or None
    when the commit has no such path."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-t", f"{sha}:{path}"],
        capture_output=True, env=_env())
    return proc.stdout.decode("utf-8").strip() if proc.returncode == 0 \
        else None


def export(repo: str | Path, sha: str, paths: list[str],
           dest: str | Path) -> None:
    """Write repo-relative `paths` as commit `sha` has them under `dest`,
    in the repo's layout: what a clean checkout of `sha` would hold, since
    `git archive` applies the commit's .gitattributes as checkout does."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        ["git", "-C", str(repo), "archive", "--format=tar", sha, "--",
         *paths], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=_env())
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            tar.extractall(dest, filter="data")
    except tarfile.TarError as e:
        proc.kill()
        proc.wait()
        err = proc.stderr.read().decode("utf-8", "replace").strip()
        raise SnapshotError(f"git archive {sha} {' '.join(paths)}: "
                            f"{err or e}") from None
    finally:
        proc.stdout.close()
    err = proc.stderr.read().decode("utf-8", "replace").strip()
    proc.stderr.close()
    if proc.wait() != 0:
        raise SnapshotError(f"git archive {sha} {' '.join(paths)}: {err}")


class Lease:
    """A snapshot held in use: pruning skips it until `release`."""

    def __init__(self, sha: str, tree: Path, lock):
        self.sha = sha
        self.tree = tree
        self._lock = lock

    def release(self) -> None:
        if self._lock is not None:
            self._lock.close()
            self._lock = None


class Snapshots:
    """The snapshots of `repo`'s commits kept under `root`, one directory
    per sha. Workers sharing `root` share them: each holds a shared lock on
    `<sha>.lock` while a job uses the snapshot, and pruning takes the
    exclusive lock first, so it never removes one in use."""

    def __init__(self, repo: str | Path, root: str | Path):
        self.repo = Path(repo)
        self.root = Path(root)

    def head(self) -> str:
        return head(self.repo)

    def acquire(self, sha: str) -> Lease:
        """The snapshot of commit `sha`, made if there is none yet, and
        held until the lease is released."""
        self.root.mkdir(parents=True, exist_ok=True)
        lock = open(self.root / f"{sha}.lock", "a")
        try:
            fcntl.flock(lock, fcntl.LOCK_SH)
            return Lease(sha, self._tree(sha), lock)
        except BaseException:
            lock.close()
            raise

    def _tree(self, sha: str) -> Path:
        dest = self.root / sha
        if dest.is_dir():
            return dest
        names = [n for n in _git(self.repo, "ls-tree", "--name-only", "-z",
                                 sha).split("\0") if n and n != DATA]
        tmp = Path(tempfile.mkdtemp(prefix=f".{sha}-", dir=self.root))
        try:
            export(self.repo, sha, names, tmp)
            # The environment the scripts run in (scripts/narrate.sh finds
            # its interpreter at the repo's .venv), not part of the tree.
            venv = self.repo / ".venv"
            if venv.is_dir():
                (tmp / ".venv").symlink_to(venv.resolve())
            os.rename(tmp, dest)
        except OSError:
            shutil.rmtree(tmp, ignore_errors=True)
            if not dest.is_dir():
                raise
            # another worker sharing root made it first
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return dest

    def prune(self, keep: str) -> None:
        """Remove every snapshot but `keep`'s and those in use, and what a
        worker killed mid-extraction left behind."""
        if not self.root.is_dir():
            return
        shas = {p.name.lstrip(".").split("-", 1)[0]
                for p in self.root.iterdir() if p.is_dir()}
        for sha in shas - {keep}:
            with open(self.root / f"{sha}.lock", "a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue  # a running job's
                # The lock file stays: removing it would let a worker that
                # opened it a moment ago lock a file no one else sees.
                for p in self.root.glob(f".{sha}-*"):
                    shutil.rmtree(p, ignore_errors=True)
                shutil.rmtree(self.root / sha, ignore_errors=True)
