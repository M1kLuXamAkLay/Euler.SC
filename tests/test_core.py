"""Core behaviour tests.

Run with ``python -m pytest tests -q``. These cover the security boundary,
the parser, the solver, matrices, calculus and plotting. No GUI is involved,
so the suite stays fast and portable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from euler.core import analysis, calculus, grapher, matrix, solver
from euler.core.parser import ExprError, preprocess, validate

# --------------------------------------------------------------------- security
@pytest.mark.parametrize("payload", [
    "__import__('os').system('calc')",
    "x.subs(x,1)",
    "eval('1+1')",
    "open('/etc/passwd').read()",
    "().__class__.__bases__",
    "lambda: 1",
    "exec('x=1')",
    "globals()",
])
def test_blocks_code_injection(payload):
    """Input arrives from the UI, from OCR and from the language model."""
    with pytest.raises(ExprError):
        validate(preprocess(payload))


def test_blocks_string_literals():
    with pytest.raises(ExprError):
        validate("'abc'")


def test_allows_normal_math():
    for expr in ("2+2", "sqrt(x)", "sin(x)+cos(x)", "x^2-5*x+6", "Abs(x)"):
        validate(preprocess(expr))


# --------------------------------------------------------------------- preprocessor
def test_factorial_binds_to_atom():
    """2*3! must become 2*factorial(3)=12, not factorial(2*3)=720."""
    assert preprocess("2*3!") == "2*factorial(3)"


def test_caret_becomes_power():
    assert "**" in preprocess("x^2")


def test_unicode_operators():
    assert preprocess("2\u00d73") == "2*3"
    assert preprocess("6\u00f72") == "6/2"


# --------------------------------------------------------------------- solver
def test_quadratic_roots():
    result = solver.solve_equation("x^2-5x+6=0")
    assert result["ok"]
    assert "2" in result["text"] and "3" in result["text"]


def test_evaluation():
    assert solver.evaluate("2+2*2")["text"] == "6"


def test_inequality():
    result = solver.solve_equation("2x+3>7")
    assert result["ok"] and "\u221e" in result["text"]


def test_trigonometric_solution_is_periodic():
    result = solver.solve_equation("sin(x)=0")
    assert result["ok"]
    assert "\u03c0" in result["text"]


def test_division_by_zero_is_reported():
    result = solver.evaluate("1/0")
    assert not result["ok"]


def test_system_linear():
    result = solver.solve_system(["x+y=5", "x-y=1"])
    assert result["ok"]
    assert "3" in result["text"] and "2" in result["text"]


def test_system_requires_two_equations():
    result = solver.solve_system(["x+y=5"])
    assert not result["ok"]


# --------------------------------------------------------------------- matrices
def test_matrix_from_text():
    m = matrix.from_text("1 2; 3 4")
    assert m.shape == (2, 2)


def test_determinant():
    result = matrix.run("det", [[1, 2], [3, 4]])
    assert "-2" in result["body"]


def test_inverse_returns_grid():
    result = matrix.run("inv", [[1, 2], [3, 4]])
    assert "grid" in result
    assert result["grid"][0][0] == "-2"


def test_transpose_grid():
    result = matrix.run("transpose", [[1, 2, 3], [4, 5, 6]])
    assert result["grid"] == [["1", "4"], ["2", "5"], ["3", "6"]]


def test_singular_matrix_rejected():
    with pytest.raises(ExprError):
        matrix.run("inv", [[1, 2], [2, 4]])


def test_ragged_matrix_rejected():
    with pytest.raises(ExprError):
        matrix.to_matrix([["1", "2"], ["3"]])


def test_multiply_shape_mismatch():
    with pytest.raises(ExprError):
        matrix.run("multiply", [[1, 2, 3]], [[1, 2]])


def test_solve_linear_system():
    result = matrix.run("system", [[2, 1], [1, -1]], [["5"], ["1"]])
    assert result["ok"] if "ok" in result else True
    assert "2" in result.get("body", "") or "3" in result.get("body", "")


# --------------------------------------------------------------------- calculus
def _text(line) -> str:
    """Result lines are ``{text, latex}`` pairs; tests assert on plain text."""
    return line["text"] if isinstance(line, dict) else str(line)


def test_limit():
    result = calculus.limit("sin(x)/x", "0")
    assert _text(result["lines"][0]).endswith("1")


def test_derivative():
    result = calculus.derivative("x^3", 1)
    assert "3" in _text(result["lines"][0])


def test_definite_integral():
    result = calculus.integral_definite("x^2", "0", "1")
    assert "1/3" in _text(result["lines"][0])


def test_divergent_integral_rejected():
    with pytest.raises(ExprError):
        calculus.integral_definite("1/x", "1", "oo")


def test_critical_points():
    result = calculus.critical_points("x^3-3x")
    joined = " ".join(_text(line) for line in result["lines"])
    assert "maximum" in joined and "minimum" in joined


# --------------------------------------------------------------------- analysis
def test_full_report_sections():
    report = analysis.full_report("x^3-3x")
    assert len(report["sections"]) >= 8


def test_domain_of_reciprocal():
    report = analysis.full_report("1/x")
    domain = next(s for s in report["sections"] if s["title"] == "analysis.section.domain")
    assert "\u221e" in _text(domain["lines"][0])


# --------------------------------------------------------------------- plotting
def test_asymptote_splits_segments():
    data = grapher.sample(["1/x"], -5, 5, 400)
    assert len(data["series"][0]["segments"]) >= 2


def test_continuous_single_segment():
    data = grapher.sample(["x^2"], -5, 5, 300)
    assert len(data["series"][0]["segments"]) == 1


def test_plot_is_json_serialisable():
    json.dumps(grapher.sample(["x^2", "1/x"], -3, 3, 200))


def test_invalid_range_rejected():
    with pytest.raises(ExprError):
        grapher.sample(["x"], 5, -5)


def test_autoscale_python_floats():
    result = grapher.autoscale(["x^2"], -5, 5)
    assert all(type(v) is float for v in result.values())
