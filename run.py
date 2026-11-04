"""Launcher.

Kept as a separate module so PyInstaller has a stable entry point and so that
``python run.py`` behaves identically to the frozen executable.
"""
from __future__ import annotations

import multiprocessing
import sys

from euler.main import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
