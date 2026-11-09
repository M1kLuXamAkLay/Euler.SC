"""Regression tests for the boot document, the engine gate and the sweep guard.

Each case here failed in the 5.1.17 release:

* the Windows job died on ``signal.SIGALRM`` before its first check;
* a SyntaxError in ``analysis.py`` surfaced as ``KeyError: 'solver'``;
* the stored theme was applied only after ``settings_get`` returned, so a user
  who pinned light saw the OS dark scheme for about a second.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from euler import transport  # noqa: E402

DOCUMENT = b'<!DOCTYPE html>\n<html lang="ru" data-booting>\n<head></head>\n</html>\n'


def _serve_with(tmp_path, settings: dict, monkeypatch) -> bytes:
    """Render the document the way the static handler does."""

    from euler.core import settings as settings_module

    monkeypatch.setattr(settings_module, "load", lambda: settings)
    monkeypatch.setattr(transport, "_log", transport._log)
    return transport.boot_document(DOCUMENT)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_document_carries_stored_theme(theme: str, monkeypatch) -> None:
    rendered = _serve_with(None, {"theme": theme, "language": "ru"}, monkeypatch)
    assert f'data-theme="{theme}"'.encode() in rendered


def test_auto_theme_leaves_no_attribute(monkeypatch) -> None:
    """``auto`` must not pin a scheme: the CSS media query then follows the OS."""
    rendered = _serve_with(None, {"theme": "auto", "language": "ru"}, monkeypatch)
    assert b"data-theme" not in rendered


def test_boot_attribute_survives(monkeypatch) -> None:
    """The cloak is removed by app.js, so the server must not drop it."""
    rendered = _serve_with(None, {"theme": "dark", "language": "ru"}, monkeypatch)
    assert b"data-booting" in rendered


def test_language_is_injected(monkeypatch) -> None:
    rendered = _serve_with(None, {"theme": "light", "language": "zh"}, monkeypatch)
    assert b'lang="zh"' in rendered


def test_unreadable_settings_leave_document_untouched(monkeypatch) -> None:
    """A corrupt settings file must never stop the interface from loading."""
    from euler.core import settings as settings_module

    def boom() -> dict:
        raise OSError("settings.json is unreadable")

    monkeypatch.setattr(settings_module, "load", boom)
    assert transport.boot_document(DOCUMENT) == DOCUMENT


def test_engine_failure_is_not_masked(monkeypatch) -> None:
    """``_mod`` used to raise ``KeyError: 'solver'`` and hide the real cause."""
    from euler.bridge import api

    monkeypatch.setattr(api, "_warm_error", SyntaxError("bad f-string"), raising=False)
    monkeypatch.setattr(api, "_core", {}, raising=False)
    api._warm_done.set()
    with pytest.raises(api.EngineUnavailable) as caught:
        api._mod("solver")
    assert "bad f-string" in str(caught.value)
    assert "KeyError" not in str(caught.value)


def test_ready_reports_warm_failure(monkeypatch) -> None:
    """``ready`` returning ``ok: True`` hid a dead engine from the interface."""
    from euler.bridge import api

    monkeypatch.setattr(api, "_warm_error", RuntimeError("numpy missing"), raising=False)
    outcome = api.Api().ready()
    assert outcome["ok"] is False
    assert "numpy missing" in outcome["error"]


def test_sweep_guard_works_without_sigalrm(monkeypatch) -> None:
    """Windows has no SIGALRM: the guard must fall back to a thread."""
    sys.path.insert(0, str(ROOT / "tests"))
    import _guard

    monkeypatch.setattr(_guard, "HAS_ALARM", False)
    assert _guard.run_guarded(lambda: 41 + 1, 5) == 42


def test_sweep_guard_reports_timeout(monkeypatch) -> None:
    import time

    sys.path.insert(0, str(ROOT / "tests"))
    import _guard

    monkeypatch.setattr(_guard, "HAS_ALARM", False)
    with pytest.raises(_guard.Timeout):
        _guard.run_guarded(lambda: time.sleep(5), 0.05)


def test_sweep_guard_propagates_error(monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "tests"))
    import _guard

    monkeypatch.setattr(_guard, "HAS_ALARM", False)

    def explode() -> int:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        _guard.run_guarded(explode, 5)


def test_sweep_imports_cleanly() -> None:
    """The sweep must import on every platform: a Windows run died at line 27."""
    sys.path.insert(0, str(ROOT / "tests"))
    import _guard

    assert hasattr(_guard, "HAS_ALARM")
