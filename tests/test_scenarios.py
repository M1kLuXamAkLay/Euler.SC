"""Scenario sweep: every tab and every engine entry point.

Drives the public ``Api`` class -- the exact layer the window calls through
``py(...)`` -- so a regression in one tab cannot hide behind a green test in
another. Run: python3 tests/test_scenarios.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from euler.bridge.api import Api

API = Api()
RESULTS: list[tuple[str, str, bool, str]] = []
UNIQUE = {"name": 1_000_000}


def check(area: str, name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((area, name, bool(ok), detail))


def expect(area: str, name: str, fn, *, ok=True, contains=None, error=None):
    """Run one scenario and record whether the answer is what a user expects."""
    if len(name) > 60:
        name = name[:57] + "..."
    try:
        out = fn()
    except Exception as exc:                       # noqa: BLE001 - reported
        check(area, name, False, f"{type(exc).__name__}: {exc}")
        return
    if not isinstance(out, dict):
        check(area, name, False, f"unexpected {type(out).__name__}")
        return
    ok_flag = out.get("ok", True)
    text = str(out.get("text") or out.get("latex") or out.get("body") or "")
    err = out.get("error")
    if ok_flag != ok:
        check(area, name, False, f"ok={ok_flag} err={err} text={text[:36]}")
        return
    if error and err != error:
        check(area, name, False, f"want {error}, got {err}")
        return
    if contains and contains not in text:
        check(area, name, False, f"{contains!r} not in {text[:36]!r}")
        return
    check(area, name, True)


# ---------------------------------------------------------- calculator: numbers
CALC = [
    ("2+2", "4"), ("2+2*2", "6"), ("(2+3)*4", "20"), ("2^10", "1024"),
    ("10%", "0.1"), ("5!", "120"), ("-5+3", "-2"), ("1/3", "1/3"),
    ("0.1+0.2", "0.3"), ("sqrt(16)", "4"), ("cbrt(27)", "3"), ("|(-7)|", "7"),
    ("sin(0)", "0"), ("cos(0)", "1"), ("tan(0)", "0"), ("ln(1)", "0"),
    ("log(100)", "2"), ("exp(0)", "1"), ("pi", "\u03c0"), ("2*pi", "\u03c0"),
    ("5 1/2", "5"), ("1,5+1,5", "3"), ("asin(1)", "\u03c0/2"),
    ("atan(1)", "\u03c0/4"), ("sinh(0)", "0"), ("2^3^2", "512"),
    ("abs(-3)", "3"), ("floor(2.9)", "2"), ("16^(1/2)", "4"), ("0/5", "0"),
    ("sqrt(2)*sqrt(2)", "2"), ("2^0.5", "\u221a(2)"),
]
for _text, _want in CALC:
    expect("калькулятор", _text, lambda t=_text: API.solve(t), contains=_want)

# ------------------------------------------------------- calculator: logarithms
LOGS = [
    ("log_9(9)", "1"), ("log_2(8)", "3"), ("\\log_2(8)", "3"),
    ("log_{2}(8)", "3"), ("log_9 9", "1"), ("log_10(100)", "2"),
    ("log_5(25)", "2"), ("log_2(1/8)", "-3"), ("log_2(0.5)", "-1"),
    ("log_3(9)+log_2(4)", "4"), ("2*log_2(8)", "6"), ("log_2(2^10)", "10"),
    ("lg(100)", "2"), ("ln(e)", "1"), ("log(1000)", "3"),
    ("log_2(sqrt(2))", "0.5"), ("log_2(1024)", "10"), ("log_7(49)", "2"),
]
for _text, _want in LOGS:
    expect("логарифмы", _text, lambda t=_text: API.solve(t), contains=_want)
# A truncated "log_2(8" auto-closes to log_2(8)=3: the field balances
# brackets before sending, so the engine never sees it unbalanced.
expect("логарифмы", "запись обрезана", lambda: API.solve("log_2(8"), contains="3")
expect("логарифмы", "log_2(x) как формула",
       lambda: API.solve("log_2(x)"), contains="log")

# --------------------------------------------------------------- equations tab
EQ = [
    ("x^2-5x+6=0", "2"), ("sin(x)=1/2", "\u03c0/6"),
    ("sin^2(x)-3sin(x)+2=0", "\u03c0/2"), ("cos(x)=0", "\u03c0/2"),
    ("2x+3=7", "2"), ("x/2=5", "10"), ("sqrt(x)=3", "9"),
    ("x^3=27", "3"), ("e^x=1", "0"), ("x^2=4", "2"), ("tan(x)=1", "\u03c0/4"),
    ("log_2(x)=3", "8"),
]
for _text, _want in EQ:
    expect("уравнения", _text, lambda t=_text: API.solve_equation(t),
           contains=_want)
expect("уравнения", "sin(x)=2", lambda: API.solve_equation("sin(x)=2"),
       ok=False, error="ExprError.no_solution")
expect("уравнения", "x+1=x+2", lambda: API.solve_equation("x+1=x+2"),
       ok=False, error="ExprError.no_solution")
expect("уравнения", "x^2<4", lambda: API.solve_equation("x^2<4"))
expect("уравнения", "система 2x2", lambda: API.solve_system(["x+y=3", "x-y=1"]),
       contains="x")
expect("уравнения", "система 3x3",
       lambda: API.solve_system(["x+y+z=6", "x-y=0", "z=2"]), contains="x")
expect("уравнения", "система вырождена",
       lambda: API.solve_system(["x+y=1", "2x+2y=2"]), contains="free")

# ----------------------------------------------------------------- analysis tab
for _text in ["x^2-4", "sin(x)*cos(x)", "1/(x-2)", "exp(-x^2)", "x^3-3x"]:
    expect("анализ", _text, lambda t=_text: API.analyze(t))
expect("анализ", "с интервалом", lambda: API.analyze("x^2-4", [-3, 3]))

# ----------------------------------------------------------------- calculus tab
for _kind, _text in [("derivative", "x^3"), ("derivative", "sin(x)"),
                     ("integral", "x^2"), ("integral", "sin(x)"),
                     ("integral", "exp(-x^2)"), ("derivative", "ln(x)")]:
    expect("исчисление", f"{_kind}: {_text}",
           lambda k=_kind, t=_text: API.calculus(k, t))
expect("исчисление", "предел sin(x)/x", lambda: API.limit("sin(x)/x", "0"))
expect("исчисление", "предел 1/x", lambda: API.limit("1/x", "oo"))

# ------------------------------------------------------------------- graph tab
for _eqs in (["x^2"], ["sin(x)", "cos(x)"], ["1/x"], ["log_2(x)"], ["x^3-3x"]):
    expect("график", " + ".join(_eqs), lambda e=_eqs: API.plot(e, -10, 10, 200))
expect("график", "автоскейл", lambda: API.autoscale(["x^2"], -10, 10))

# ----------------------------------------------------------------- matrix tab
_grid = [["1", "2"], ["3", "4"]]
_inv = [["4", "-2"], ["-3", "1"]]
MATRIX_CASES = [
    ("add", _grid, _grid, "6"),
    ("subtract", _grid, _grid, "0"),
    ("multiply", _grid, _grid, "10"),
    ("determinant", _grid, None, "-2"),
    ("inverse", _grid, None, "-2"),
    ("transpose", _grid, None, "1"),
    ("rank", _grid, None, "2"),
    ("trace", _grid, None, "5"),
    ("power", _grid, None, "7"),
    ("scalar", _grid, None, "2"),
]
for _op, _a, _b, _want in MATRIX_CASES:
    expect("матрицы", _op,
           lambda o=_op, a=_a, b=_b: API.matrix_op(o, a, b, extra="2"),
           contains=_want)


def _roundtrip():
    # "A" is the first free letter and is used by the rank() check below, so the
    # round trip takes the last one instead of racing it.
    name = "H"
    saved = API.matrix_save(name, [["1", "0"], ["0", "1"]])
    got = API.matrix_get(name)
    API.matrix_delete(name)
    return {"ok": saved.get("ok", False) and got.get("ok", False)
            and got.get("grid") == [["1", "0"], ["0", "1"]],
            "text": "" if saved.get("ok") and got.get("ok") else f"{saved} {got}"}


expect("матрицы", "сохранение/чтение/удаление", _roundtrip)
expect("матрицы", "rank(A) в выражении",
       lambda: API.solve("rank(A)", {"A": [["1", "2"], ["2", "4"]]}),
       contains="1")
expect("матрицы", "det(F) в выражении",
       lambda: API.solve("det(F)", {"F": [["2", "0"], ["0", "3"]]}), contains="6")
expect("матрицы", "несовместимые размеры",
       lambda: API.matrix_op("add", _grid, [["1", "2", "3"]]), ok=False)

# ---------------------------------------------------------------- formats / ALT
for _text in ["1/3", "0.5", "sqrt(2)", "pi"]:
    expect("формы ответа", _text, lambda t=_text: API.solve(t))
    expect("формы ответа", f"цикл форм {_text}",
           lambda t=_text: API.cycle_form(t, "auto"))

# ------------------------------------------------------------- steps / reference
for _text in ["x^2-5x+6=0", "2x+3=7", "x^2=9"]:
    expect("шаги решения", _text, lambda t=_text: API.steps(t, "auto"))
expect("справочник", "теорема Виета", lambda: API.reference("\u0412\u0438\u0435\u0442"))

# -------------------------------------------------------------------- guardrails
BAD = ["import os", "__import__('os')", "open('x')", "os.system('dir')",
       "lambda: 1", "x.__class__", "@", "$", "log_9(=", "eval('1')"]
for _text in BAD:
    expect("защита ввода", _text, lambda t=_text: API.solve(t), ok=False)

# ------------------------------------------------------------------------- run
width = max(len(n) for _, n, _, _ in RESULTS) + 1
failed = [r for r in RESULTS if not r[2]]
current = ""
print(f"scenarios: {len(RESULTS)}")
for area, name, ok, detail in RESULTS:
    if area != current:
        print(f"\n== {area}")
        current = area
    if not ok:
        print(f"  FAIL  {name:<{width}}  {detail}")

def test_all_scenarios() -> None:
    """Run the whole sweep as one pytest case.

    The module used to end in ``sys.exit(1)``, which killed the pytest process
    during collection (INTERNALERROR) instead of reporting a failing test.
    Collection stays at module level so ``python tests/test_scenarios.py`` still
    prints the per-area report and exits non-zero.
    """
    assert not failed, "\n".join(
        f"{area}: {name} -> {detail}" for area, name, _, detail in failed)


if __name__ == "__main__":
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("\nfailures by area:")
        for area in dict.fromkeys(a for a, _, ok, _ in failed if not ok):
            names = [n for a, n, ok, _ in failed if a == area and not ok]
            print(f"  {area}: {len(names)} -> {', '.join(names[:6])}")
        sys.exit(1)
