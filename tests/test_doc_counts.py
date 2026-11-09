"""Documented test and check counts must match the real ones.

The numbers in README, HOW_TO_RUN, CONTRIBUTING and ARCHITECTURE drifted from
the suite several times (40, then 76, then 125, while the real count moved).
Counting here means the document cannot disagree with the tree without a red
test pointing at the exact file.

The unit count is taken from pytest collection in a subprocess so this test
does not count itself.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ["README.md", "HOW_TO_RUN.md", "CONTRIBUTING.md", "ARCHITECTURE.md"]

def _collected_unit_count() -> int:
    """Total tests collected, summed from pytest's per-file ``path: N`` lines."""
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--co", "-q", "-p", "no:cacheprovider",
         "--deselect", "tests/test_doc_counts.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    counts = [int(m.group(1)) for m in re.finditer(r"^tests/\S+\.py: (\d+)$", out, re.M)]
    assert counts, out[-300:]
    return sum(counts)

def _claims(pattern: str) -> set[int]:
    """Every number a document claims via ``pattern`` (first non-empty group).

    Only indented comment tails on lines that START with the command are
    considered. A guard that scanned prose as well flagged its own explanation
    the first time one was written: the sentence "the runner reports 170 passed"
    matched the same pattern as the command line it was describing. The claims
    live in the command comments, so that is what is checked.
    """
    found: set[int] = set()
    for name in DOCS:
        text = (ROOT / name).read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith(("pytest ", "python tests/sweep_full.py")):
                continue
            for match in re.finditer(pattern, line):
                value = next(g for g in match.groups() if g)
                found.add(int(value))
    return found

def test_documented_unit_count_is_current() -> None:
    """Unit-test claims: "N unit tests" and "N passed" in pytest commands only.

    The sweep's ``199/199 passed`` is a different number and is checked below,
    so the pattern requires a pytest context rather than any "passed".
    """
    actual = _collected_unit_count()              # excludes this file by design
    claimed = _claims(r"(?:(\d+) unit tests|pytest[^\n]*?(\d+) passed|must be (\d+) passed)")
    stale = {n for n in claimed if n != actual}
    assert not stale, f"docs claim {sorted(stale)} unit tests, suite has {actual}"

def test_documented_sweep_count_is_current() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "tests" / "sweep_full.py")],
                            capture_output=True, text=True, cwd=ROOT)
    match = re.search(r"(\d+)/(\d+) passed", result.stdout)
    assert match, result.stdout[-300:]
    total = int(match.group(2))
    claimed = _claims(r"(?:(\d+) end-to-end checks|(\d+) functional checks|(\d+)/\d+ passed|must be \d+/(\d+) passed|\d+/(\d+) passed)")
    stale = {n for n in claimed if n != total}
    assert not stale, f"docs claim {sorted(stale)} checks, sweep has {total}"
