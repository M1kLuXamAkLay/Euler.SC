"""Per-case timeout for the release sweep.

``signal.alarm`` is POSIX-only. Windows has no ``SIGALRM`` at all, so the guard
used to raise ``AttributeError`` at import time and killed the whole sweep
before its first check -- which is exactly how the Windows CI job failed.

POSIX keeps the real alarm: the expression is interrupted in place. Elsewhere
the call runs on a daemon thread and the sweep stops waiting at the deadline, so
a pathological expression costs one abandoned thread instead of the release gate.
"""
from __future__ import annotations

import signal
import threading

HAS_ALARM = hasattr(signal, "SIGALRM")


class Timeout(Exception):
    """The guarded call did not finish in time."""


def _alarm(_signum, _frame) -> None:
    raise Timeout()


if HAS_ALARM:
    signal.signal(signal.SIGALRM, _alarm)


def run_guarded(fn, seconds: float):
    """Call ``fn``, giving up after ``seconds``."""
    if HAS_ALARM:
        signal.alarm(int(seconds) or 1)
        try:
            return fn()
        finally:
            signal.alarm(0)

    outcome: dict = {}

    def runner() -> None:
        try:
            outcome["value"] = fn()
        except BaseException as exc:          # noqa: BLE001 - re-raised below
            outcome["error"] = exc

    worker = threading.Thread(target=runner, daemon=True)
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        raise Timeout()
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]
