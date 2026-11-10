"""Resumable, verified file download with cancellation.

A partial file lives next to the target as ``<name>.part`` and is only renamed
into place after its size and SHA-256 match. A broken or incomplete download
therefore never appears under the final name.
"""
from __future__ import annotations

import hashlib
import http.client
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from collections.abc import Callable

CHUNK = 256 * 1024
RETRIES = 6
TIMEOUT = 30
USER_AGENT = "EulerSC"
RETRYABLE_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})
_NETWORK_ERRORS = (http.client.HTTPException, socket.timeout, ConnectionError,
                   TimeoutError, urllib.error.URLError, OSError)

Progress = Callable[[int, int], None]


class DownloadError(RuntimeError):
    """A download that cannot be completed; the message is a UI key."""


class DownloadCancelled(DownloadError):
    pass


def partial_path(target: Path) -> Path:
    return target.with_name(target.name + ".part")


def discard(target: Path) -> None:
    partial_path(Path(target)).unlink(missing_ok=True)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _check(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise DownloadCancelled("ExprError.cancelled")


def _wait(seconds: float, cancel: threading.Event | None) -> None:
    if cancel is None:
        time.sleep(seconds)
    elif cancel.wait(seconds):
        raise DownloadCancelled("ExprError.cancelled")


def _open(url: str, offset: int, timeout: float):
    headers = {"User-Agent": USER_AGENT}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


def _total(resp, base: int, size: int | None) -> int | None:
    content_range = resp.headers.get("Content-Range", "")
    if "/" in content_range:
        tail = content_range.rsplit("/", 1)[1]
        if tail.isdigit():
            return int(tail)
    length = resp.headers.get("Content-Length", "")
    if length.isdigit():
        return base + int(length)
    return size


def fetch(url: str, target: Path, *, sha256: str | None = None, size: int | None = None,
          cancel: threading.Event | None = None, on_progress: Progress | None = None,
          retries: int = RETRIES, timeout: float = TIMEOUT) -> Path:
    """Download ``url`` to ``target``, resuming after interruptions.

    A network failure keeps the partial file so the next attempt resumes it.
    A size or checksum mismatch removes it, because it is corrupt.
    """
    target = Path(target)
    part = partial_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    failures = 0

    while True:
        _check(cancel)
        offset = part.stat().st_size if part.exists() else 0
        if size is not None and offset > size:
            part.unlink()
            offset = 0

        try:
            with _open(url, offset, timeout) as resp:
                resumed = resp.status == 206
                base = offset if resumed else 0
                total = _total(resp, base, size)
                done = base
                with part.open("ab" if resumed else "wb") as out:
                    while True:
                        _check(cancel)
                        block = resp.read(CHUNK)
                        if not block:
                            break
                        out.write(block)
                        done += len(block)
                        if on_progress is not None:
                            on_progress(done, total or 0)
                if total is not None and done < total:
                    raise http.client.IncompleteRead(b"", total - done)
            break
        except DownloadCancelled:
            raise
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and size is not None and offset == size:
                break
            if exc.code == 416:
                part.unlink(missing_ok=True)
            elif exc.code not in RETRYABLE_CODES:
                raise DownloadError(f"ExprError.http:{exc.code}") from None
            failures += 1
            if failures > retries:
                raise DownloadError(f"ExprError.http:{exc.code}") from None
            _wait(min(2 ** failures, 30), cancel)
        except _NETWORK_ERRORS as exc:
            failures += 1
            if failures > retries:
                raise DownloadError(f"ExprError.download_failed:{exc}") from None
            _wait(min(2 ** failures, 30), cancel)

    actual = part.stat().st_size if part.exists() else 0
    if size is not None and actual != size:
        part.unlink(missing_ok=True)
        raise DownloadError("ExprError.size_mismatch")
    if sha256 is not None and sha256_of(part).lower() != sha256.lower():
        part.unlink(missing_ok=True)
        raise DownloadError("ExprError.checksum_mismatch")

    os.replace(part, target)
    return target
