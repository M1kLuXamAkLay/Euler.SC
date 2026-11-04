"""
Persisted user preferences.

Stored as a single JSON file under the OS application-data directory:
``%APPDATA%\\EulerSC`` on Windows, ``~/.local/share/EulerSC`` on Linux and
``~/Library/Application Support/EulerSC`` on macOS.

Writes are atomic: content goes to a temporary file which then replaces the
target, so a crash mid-write never leaves a half-written configuration.
"""
from __future__ import annotations

import json
import os
import sys
import shutil
import threading
from pathlib import Path
from typing import Any

# Every key the interface may persist. Unknown keys are dropped on load so a
# stale or hand-edited file cannot inject unexpected state.
DEFAULTS: dict[str, Any] = {
    "language": "ru",
    "model": "",
    "temperature": 0.3,
    "angle_unit": "deg",
    "theme": "auto",
    "points": 1200,
    "models_dir": "",
    "hardware": None,
    "onboarding_done": False,
    # Matrices survive restarts: losing an entered matrix is unacceptable.
    # Registry stores name -> grid of strings, e.g. {"F": [["1","2"],["3","4"]]}
    "matrices": {},
    "matrix_order": [],
    # Interface state restored on next launch.
    "active_tab": "calc",
    "calculus": {"fn": "x^2-1", "point": "1", "lower": "0", "upper": "1"},
    "analysis": {"fn": "x^3-3x", "interval": "-2; 2"},
    "graph": {"x_min": -5, "x_max": 5, "y_min": -10, "y_max": 10},
    "equations": ["x^2-5x+6=0"],
}

_lock = threading.Lock()


def _base_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base)


def data_dir() -> Path:
    """Application data directory, created on demand.

    The application was called differently before version 5, and its data lived
    in a directory of that name. Renaming the program would have silently
    orphaned every saved setting, so the old directory is moved on first launch.
    The move happens once: afterwards there is nothing left to migrate.
    """
    path = _base_dir() / "EulerSC"

    if not path.exists():
        legacy = _base_dir() / "SulerSC"
        if legacy.is_dir():
            try:
                legacy.rename(path)
            except OSError:
                # Crossing filesystems, or an open handle. Copy what matters
                # rather than starting the user from defaults.
                shutil.copytree(legacy, path, dirs_exist_ok=True)

    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return data_dir() / "settings.json"


def load() -> dict:
    """Read settings, falling back to defaults on any problem."""
    path = settings_path()
    if not path.exists():
        return dict(DEFAULTS)

    try:
        with path.open(encoding="utf-8") as handle:
            stored = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULTS)

    if not isinstance(stored, dict):
        return dict(DEFAULTS)

    merged = dict(DEFAULTS)
    merged.update({key: value for key, value in stored.items() if key in DEFAULTS})
    return merged


def save(patch: dict) -> dict:
    """
    Merge ``patch`` into the stored settings and write atomically.

    :returns: ``{"ok": bool, "settings": dict}`` or ``{"ok": False, "error": str}``
    """
    if not isinstance(patch, dict):
        return {"ok": False, "error": "ExprError.bad_payload"}

    with _lock:
        current = load()
        current.update({key: value for key, value in patch.items() if key in DEFAULTS})

        path = settings_path()
        try:
            temporary = path.with_suffix(".tmp")
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(current, handle, ensure_ascii=False, indent=2)
            os.replace(temporary, path)
        except OSError as exc:
            return {"ok": False, "error": str(exc), "settings": current}

    return {"ok": True, "settings": current}


__all__ = ["load", "save", "data_dir", "settings_path", "DEFAULTS"]
