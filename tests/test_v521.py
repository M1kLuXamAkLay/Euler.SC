"""Regression tests for 5.2.1: matrix roots, decimal commas inside calls,
and the graph sampling range."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import sympy as sp

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from euler.core import grapher, matrix, solver  # noqa: E402

A = [["4", "1"], ["2", "3"]]


# ---------------------------------------------------------------- matrix roots
def test_square_root_of_matrix_squares_back() -> None:
    """The defining property: root(A)^2 == A."""
    root = matrix.matrix_root(sp.Matrix([[4, 1], [2, 3]]), sp.Integer(2))
    assert sp.simplify(root * root - sp.Matrix([[4, 1], [2, 3]])) == sp.zeros(2, 2)


def test_cube_root_of_diagonal_matrix() -> None:
    root = matrix.matrix_root(sp.diag(8, 27), sp.Integer(3))
    assert root == sp.diag(2, 3)


def test_defective_matrix_root_is_computed() -> None:
    """A Jordan block has no eigenbasis, but it does have a square root.

    This test used to assert a refusal. That refusal was the bug: routing every
    root through ``P D P^-1`` rejected a whole class of answerable matrices, and
    ``sqrt([[1, 1], [0, 1]])`` came back as an error instead of [[1, 1/2], [0, 1]].
    """
    jordan = sp.Matrix([[1, 1], [0, 1]])
    root = matrix.matrix_root(jordan, sp.Integer(2))
    assert sp.simplify(root * root - jordan) == sp.zeros(2, 2)
    assert root == sp.Matrix([[1, sp.Rational(1, 2)], [0, 1]])


def test_root_operation_through_grid_api() -> None:
    result = matrix.run("root", A, None, "2")
    assert "body" in result and result["body"]


def test_root_degree_out_of_range_is_refused() -> None:
    with pytest.raises(Exception):
        matrix.run("root", A, None, "1")


@pytest.mark.parametrize("expr", ["sqrt(A)*sqrt(A)", "root(A,2)*root(A,2)"])
def test_root_in_expression_squares_back(expr: str) -> None:
    """Round trip: a root multiplied by itself returns the original matrix.

    The text form is a layout for people (spaces, line breaks), so the check
    compares the matrix value, not its string.
    """
    result = solver.evaluate(expr, {"A": A})
    assert result["ok"], result
    expected = sp.Matrix([[4, 1], [2, 3]])
    rows = [[sp.nsimplify(float(v)) for v in line.split()]
            for line in result["text"].strip().splitlines()]
    assert sp.Matrix(rows) == expected


# ------------------------------------------------ decimal commas inside calls
@pytest.mark.parametrize("expr, expected", [
    ("root(27,3)", "3"),
    ("root(16,4)", "2"),
    ("1,5+1,5", "3"),       # decimal comma outside a call is still decimal
    ("2,5*2", "5"),
])
def test_comma_in_call_is_a_separator(expr: str, expected: str) -> None:
    result = solver.evaluate(expr)
    assert result["ok"], result
    assert result["text"] == expected


def test_root_of_scalar_is_exact() -> None:
    assert solver.evaluate("root(27,3)")["text"] == "3"


# ------------------------------------------------------------- graph sampling
@pytest.mark.parametrize("low, high", [(-5, 5), (-40, 40), (60, 90), (-300, -250)])
def test_line_covers_requested_range(low: float, high: float) -> None:
    """The engine must return the whole curve for any window, not stop at a
    fixed span. This is the sampling half of the 'line stops' complaint."""
    segments = grapher.sample(["x"], low, high, 2400)["series"][0]["segments"]
    assert len(segments) == 1
    assert segments[0][0][0] == pytest.approx(low)
    assert segments[0][-1][0] == pytest.approx(high)
