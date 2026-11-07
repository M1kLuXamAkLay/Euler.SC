import base64
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from euler.core import exporter  # noqa: E402

SOLUTION = {
    "title": "Предел \\frac{\\sin x}{x}",
    "language": "ru",
    "steps": [
        {"n": 1, "text": "Первый замечательный предел", "latex": "\\lim_{x\\to 0}\\frac{\\sin x}{x}=1"},
        {"n": 2, "text": "Подстановка", "latex": "$\\int_0^1 x^2\\,dx = \\frac{1}{3}$"},
    ],
    "answer": "\\frac{1}{3}",
}


def test_solution_pdf_is_a_single_valid_document():
    data = exporter.to_pdf(SOLUTION)
    assert data.startswith(b"%PDF-1.4")
    assert data.rstrip().endswith(b"%%EOF")
    assert b"/Type /Page " in data


def test_solution_formulas_are_typeset_by_mathtext():
    for step in SOLUTION["steps"]:
        formula = exporter._formula_latex(step["latex"])
        assert "$" not in formula
        assert exporter._mathtext_ok(formula)
    assert exporter._formula_latex("$\\frac{1}{2}$") == "\\frac{1}{2}"
    assert not exporter._mathtext_ok("\\nosuchcommand{x}")



def test_graph_pdf_embeds_the_image():
    width, height = 40, 20
    rgb = base64.b64encode(bytes([120, 60, 70]) * (width * height)).decode()
    data = exporter.to_graph_pdf({"title": "y = x^3 - 3x", "width": width, "height": height, "rgb": rgb})
    assert data.startswith(b"%PDF-1.4")
    assert b"/Subtype /Image" in data and b"/Width 40" in data


@pytest.mark.parametrize("payload", [
    {"width": 40, "height": 20, "rgb": base64.b64encode(b"short").decode()},
    {"width": 4, "height": 4, "rgb": base64.b64encode(bytes(48)).decode()},
    {"width": 40, "height": 20, "rgb": "!!not-base64!!"},
])
def test_graph_pdf_rejects_bad_payload(payload):
    with pytest.raises(Exception):
        exporter.to_graph_pdf(payload)
