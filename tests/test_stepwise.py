import sympy as sp

from euler.core import stepwise


def _latex(expression: str) -> str:
    return " ".join(step["latex"] or "" for step in stepwise.steps(expression)["steps"])


def test_polynomial_hides_unit_coefficients_and_fixes_signs():
    x = sp.Symbol("x")
    assert stepwise._polynomial_tex([(sp.Integer(1), "x^{2}"), (sp.Integer(-5), "x"), (sp.Integer(6), "")]) \
        == "x^{2} - 5\\,x + 6"
    assert stepwise._polynomial_tex([(sp.Integer(-1), "x^{2}"), (sp.Integer(0), "x"), (sp.Integer(-1), "")]) \
        == "-x^{2} - 1"
    assert stepwise._polynomial_tex([(sp.Integer(-1), "x")]) == "-x"


def test_quadratic_steps_have_no_unit_coefficient_or_double_sign():
    steps = stepwise.steps("x^2-5x+6=0")["steps"]
    assert steps[0]["latex"] == "x^{2} - 5\\,x + 6 = 0"
    for step in steps:
        assert "+ -" not in step["latex"]


def test_inequality_has_sign_table_and_union_answer():
    result = stepwise.steps("(x-1)/(x+2)>=0")
    assert result["title"] == "step.title.inequality"
    captions = [step["text"] for step in result["steps"]]
    assert captions.count("step.cap.sign_on_interval") == 3
    assert result["latex"] == "x \\in \\left(-\\infty;\\; -2\\right) \\cup \\left[1;\\; +\\infty\\right)"


def test_inequality_without_real_roots_is_all_reals():
    assert stepwise.steps("x^2+1>0")["latex"] == "x \\in \\mathbb{R}"


def test_equation_without_real_roots_shows_empty_set_and_no_key_as_formula():
    steps = stepwise.steps("sin(x)=2")["steps"]
    assert steps[-1]["latex"] == "\\varnothing"


def test_several_roots_are_numbered():
    steps = stepwise.steps("x^3-6x^2+11x-6=0")["steps"]
    assert steps[-1]["latex"] == "x_{1} = 1,\\quad x_{2} = 2,\\quad x_{3} = 3"


def test_exported_inequality_formulas_are_typeset():
    from euler.core import exporter
    for expression in ("(x-1)/(x+2)>=0", "x^2-4<=0", "x^2-5x+6>0"):
        for step in stepwise.steps(expression)["steps"]:
            formula = exporter._formula_latex(step["latex"])
            formula = exporter.re.sub(r"\\le(?![a-z])", r"\\leq", formula)
            formula = exporter.re.sub(r"\\ge(?![a-z])", r"\\geq", formula)
            formula = formula.replace("\\frac", "\\dfrac")
            assert exporter._mathtext_ok(formula), formula
