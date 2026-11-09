"""docs/API.md must match the exported Api surface.

The file is generated (tools/gen_api_doc.py). If this fails, run the generator
and commit the result: a method added to Api._exported without a regenerated
document is a documentation bug that would otherwise ship silently.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import gen_api_doc  # noqa: E402

COMMITTED = ROOT / "docs" / "API.md"


def test_api_doc_is_current() -> None:
    assert COMMITTED.read_text(encoding="utf-8") == gen_api_doc.render(), (
        "docs/API.md is stale: run `python tools/gen_api_doc.py`")


def test_every_exported_method_is_documented() -> None:
    from euler.bridge.api import Api

    text = COMMITTED.read_text(encoding="utf-8")
    missing = [name for name in Api._exported if f"| `{name}` |" not in text]
    assert not missing, f"undocumented methods: {missing}"


def test_no_private_method_leaks_into_docs() -> None:
    text = COMMITTED.read_text(encoding="utf-8")
    assert "| `_" not in text
