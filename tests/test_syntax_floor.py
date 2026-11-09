"""Guard the minimum supported Python version.

CI runs on 3.10, but a developer on 3.12 can write syntax that only 3.12
accepts (PEP 701 f-strings with backslashes). This test parses every source
file with ``feature_version=(3, 10)`` so such code fails locally, not in CI.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCES = sorted(
    p for pattern in ("euler/**/*.py", "tests/**/*.py", "run.py")
    for p in ROOT.glob(pattern)
)


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_parses_on_python_310(path: Path) -> None:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path),
              feature_version=(3, 10))
