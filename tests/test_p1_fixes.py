"""Regression tests for the P1 fixes: angle functions and 0^0 caveat."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from euler.core import solver  # noqa: E402


def _text(expr: str) -> str:
    result = solver.evaluate(expr)
    assert result["ok"], result
    return result["text"]


@pytest.mark.parametrize("expr, expected", [
    ("deg(180)", "\u03c0"),       # 180 degrees is pi radians
    ("rad(pi)", "180"),           # pi radians is 180 degrees
    ("rad(pi/2)", "90"),          # the case that used to give sin(pi^2/360)
])
def test_angle_conversions(expr: str, expected: str) -> None:
    assert _text(expr) == expected


def test_rad_and_deg_are_inverses() -> None:
    assert _text("rad(deg(90))") == "90"


def test_sin_of_degrees_is_one() -> None:
    assert _text("sin(deg(90))") == "1"


def test_zero_power_is_flagged() -> None:
    result = solver.evaluate("0^0")
    assert result["ok"]
    assert result["note"] == "ExprError.zero_power_convention"


@pytest.mark.parametrize("expr", ["2^0", "0^2", "10^0"])
def test_ordinary_powers_are_not_flagged(expr: str) -> None:
    assert solver.evaluate(expr).get("note") is None


def test_known_gap_decimal_zero_power() -> None:
    """Documented gap: the source-text check does not match ``0.0^0``.

    Kept as an explicit test so that closing the gap later is a deliberate
    change, not an accident.
    """
    assert solver.evaluate("0.0^0").get("note") is None
