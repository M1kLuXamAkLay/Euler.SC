"""Function study: domain, range, zeros, monotonicity, asymptotes.

Two design rules drive this module.

**Never iterate an infinite solution set.** ``sp.solveset(sin(x) = 0, x)``
returns an ``ImageSet`` such as ``{2 n pi}``; calling ``list()`` on it loops
forever and froze the whole interface for every trigonometric function. Zeros
are therefore searched inside a finite window, with a numeric bisection
fallback, and the result is capped.

**Every line carries LaTeX.** The interface typesets results, so a domain of
``(-oo, 0) U (0, oo)`` must arrive as ``(-\\infty; 0) \\cup (0; +\\infty)`` and a
zero at ``sqrt(3)`` as ``\\sqrt{3}``. A line is ``{text, latex, math}``:
``math`` tells the front end whether to typeset or print a localised message.
"""
from __future__ import annotations

import math

import sympy as sp

from .parser import ExprError, parse

# A study of a periodic function is only meaningful inside a window
DEFAULT_WINDOW = (-2 * math.pi, 2 * math.pi)
MAX_ZEROS = 8


# --------------------------------------------------------------------- helpers
def _line(text: str, latex: str | None = None) -> dict:
    """A result line.

    ``latex=None`` means "this is a message, translate it". Otherwise ``latex``
    is typeset and ``text`` is just the plain fallback for copying.
    """
    return {"text": text, "latex": latex, "math": latex is not None}


def _msg(key: str) -> dict:
    return {"text": key, "latex": None, "math": False}



BACKSLASH = chr(92)
LOG_MACRO = BACKSLASH + "log"
LN_MACRO = BACKSLASH + "ln"


def ln_latex(value) -> str:
    """LaTeX for a value, with the natural log printed as ``ln``.

    SymPy renders the natural logarithm as ``log``. In school notation a bare
    ``log`` means base 10, so the answer would be misread. A ``log_{...}``
    carries an explicit base and is left alone.
    """
    try:
        text = sp.latex(sp.simplify(value))
    except (ValueError, TypeError):
        try:
            text = sp.latex(value)
        except (ValueError, TypeError):
            return str(value)

    out = []
    index = 0
    while True:
        found = text.find(LOG_MACRO, index)
        if found < 0:
            out.append(text[index:])
            break
        after = text[found + len(LOG_MACRO):found + len(LOG_MACRO) + 1]
        out.append(text[index:found])
        out.append(LOG_MACRO if after == "_" else LN_MACRO)
        index = found + len(LOG_MACRO)
    return "".join(out)


def _tex(value) -> str:
    """LaTeX for a value, with infinities written as proper symbols."""
    if value is sp.oo:
        return "+" + BACKSLASH + "infty"
    if value is -sp.oo:
        return "-" + BACKSLASH + "infty"
    if value is sp.zoo or value is sp.nan:
        return BACKSLASH + "text{—}"
    return ln_latex(value)


def num(value, digits: int = 6) -> str:
    """Plain-text rendering, used in captions and by the calculus module."""
    if value is sp.oo:
        return "+\u221e"
    if value is -sp.oo:
        return "\u2212\u221e"
    if value is sp.zoo or value is sp.nan:
        return "\u2014"

    try:
        value = sp.nsimplify(value)
        if value.is_Integer:
            return str(int(value))
        if value.is_Rational:
            return f"{int(value.p)}/{int(value.q)}"
        if getattr(value, "is_real", None) is False:
            return str(value)

        simplified = sp.simplify(value)
        text = str(simplified).replace("**", "^")
        text = text.replace("sqrt", "\u221a").replace("pi", "\u03c0")
        text = text.replace("oo", "\u221e").replace("*", "\u00b7")
        if len(text) <= 18:
            return text
        return f"\u2248{float(sp.N(value, digits + 2)):.{digits}g}"
    except (TypeError, ValueError, AttributeError):
        return str(value)


def clean_expr(text: str) -> str:
    """Readable plain text instead of SymPy's Python syntax."""
    out = text
    for src, dst in (("**", "^"), ("sqrt", "\u221a"), ("pi", "\u03c0"),
                     ("oo", "\u221e"), ("*", "\u00b7"), ("log", "ln")):
        out = out.replace(src, dst)
    while "\u00b7 " in out:
        out = out.replace("\u00b7 ", "\u00b7")
    return out


def prepare(text: str):
    """Parse an expression and pick its variable."""
    expression = parse(text)
    if not isinstance(expression, sp.Expr):
        raise ExprError("ExprError.not_a_function")
    var = detect_variable(expression)
    return expression, var, var.name


def detect_variable(expression) -> sp.Symbol:
    """The variable in play: ``x`` unless only another letter appears."""
    free = sorted(expression.free_symbols, key=lambda s: s.name)
    for symbol in free:
        if symbol.name == "x":
            return sp.Symbol("x", real=True)
    if free:
        return sp.Symbol(free[0].name, real=True)
    return sp.Symbol("x", real=True)


def _failed(value) -> bool:
    """True for objects that carry no usable limit."""
    return isinstance(value, sp.AccumBounds) or value.has(sp.AccumBounds)


# --------------------------------------------------------------------- interval
def interval_latex(value) -> str | None:
    """LaTeX for a set, or None when the set is not interval-shaped."""
    if value is sp.S.Reals:
        return "\\mathbb{R}"
    if value is sp.S.EmptySet:
        return "\\varnothing"
    if isinstance(value, sp.Interval):
        left = ("-\\infty" if value.left is -sp.oo
                else "+\\infty" if value.left is sp.oo else _tex(value.left))
        right = ("+\\infty" if value.right is sp.oo
                 else "-\\infty" if value.right is -sp.oo else _tex(value.right))
        bracket_l = "(" if value.left_open else "["
        bracket_r = ")" if value.right_open else "]"
        return f"\\left{bracket_l}{left};\\; {right}\\right{bracket_r}"
    if isinstance(value, sp.Union):
        parts = sorted(value.args, key=lambda part: float(getattr(part, "left", 0) or 0))
        return " \\cup ".join(interval_latex(part) for part in parts)
    if isinstance(value, sp.FiniteSet):
        return "\\{" + ",\\; ".join(_tex(item) for item in value.args) + "\\}"
    return None


def interval_text(value) -> str:
    """Plain-text set notation mirroring :func:`interval_latex`."""
    if value is sp.S.Reals:
        return "\u211d"
    if value is sp.S.EmptySet:
        return "\u2205"
    if isinstance(value, sp.Interval):
        left = "\u2212\u221e" if value.left is -sp.oo else num(value.left)
        right = "+\u221e" if value.right is sp.oo else num(value.right)
        return f"{'(' if value.left_open else '['}{left}; {right}{')' if value.right_open else ']'}"
    if isinstance(value, sp.Union):
        parts = sorted(value.args, key=lambda part: float(getattr(part, "left", 0) or 0))
        return " \u222a ".join(interval_text(part) for part in parts)
    return clean_expr(str(value))


# --------------------------------------------------------------------- sections
def domain(expression, var) -> dict:
    try:
        scope = sp.calculus.util.continuous_domain(expression, var, sp.S.Reals)
        latex = interval_latex(scope)
        if latex:
            return _line(interval_text(scope), latex)
    except (NotImplementedError, ValueError, TypeError):
        pass
    return _msg("analysis.undefined")


def value_range(expression, var) -> dict:
    try:
        span = sp.calculus.util.function_range(expression, var, sp.S.Reals)
        latex = interval_latex(span)
        if latex:
            return _line(interval_text(span), latex)
    except (NotImplementedError, ValueError, TypeError, AttributeError):
        pass
    return _msg("analysis.undefined")


def zeros(expression, var, window: tuple[float, float] | None = None) -> dict:
    """Zeros inside a finite window.

    A periodic function has infinitely many; the window keeps the answer
    useful and, more importantly, terminates.
    """
    low, high = window or DEFAULT_WINDOW
    roots = _zeros_in_window(expression, var, low, high)

    if not roots:
        return _msg("analysis.no_zeros")

    parts = [f"{var.name} = {num(r)}" for r in roots]
    tex = ",\\; ".join(f"{var.name} = {_tex(r)}" for r in roots)
    return _line(", ".join(parts), tex)


def _zeros_in_window(expression, var, low: float, high: float) -> list:
    """Roots in ``[low, high]``, exact where possible, numeric otherwise."""
    found: list = []

    try:
        solution = sp.solveset(sp.Eq(expression, 0), var,
                               domain=sp.Interval(low, high))
        if isinstance(solution, sp.FiniteSet):
            found = list(solution.args)
        elif isinstance(solution, sp.Union):
            for part in solution.args:
                if isinstance(part, sp.FiniteSet):
                    found.extend(part.args)
    except (NotImplementedError, ValueError, TypeError):
        found = []

    # exact set may be empty or symbolically unusable: refine numerically
    if not found:
        found = _numeric_zeros(expression, var, low, high)

    cleaned = []
    for root in sorted(found, key=lambda r: float(sp.N(sp.re(r)))):
        try:
            value = float(sp.N(sp.re(root)))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value) or not (low <= value <= high):
            continue
        if cleaned and abs(value - cleaned[-1][0]) < 1e-7:
            continue
        cleaned.append((value, sp.nsimplify(root)))

    return [value for _approx, value in cleaned[:MAX_ZEROS]]


def _numeric_zeros(expression, var, low: float, high: float) -> list:
    """Bisection on sign changes: works for any expression SymPy can evaluate."""
    try:
        function = sp.lambdify(var, expression, "math")
    except (ValueError, TypeError):
        return []

    def evaluate(point: float) -> float:
        try:
            return float(function(point))
        except (TypeError, ValueError, ZeroDivisionError):
            return float("nan")

    steps = 480
    roots = []
    previous_x = low
    previous_y = evaluate(low)
    for index in range(1, steps + 1):
        x = low + (high - low) * index / steps
        y = evaluate(x)
        if math.isfinite(previous_y) and math.isfinite(y):
            if y == 0:
                roots.append(x)
            elif previous_y * y < 0:
                roots.append(_bisect(evaluate, previous_x, x))
        previous_x, previous_y = x, y
    return roots


def _bisect(evaluate, low: float, high: float) -> float:
    """Sixty halvings: far beyond display precision."""
    f_low = evaluate(low)
    for _ in range(60):
        middle = (low + high) / 2
        f_middle = evaluate(middle)
        if not math.isfinite(f_middle):
            break
        if f_low * f_middle <= 0:
            high = middle
        else:
            low, f_low = middle, f_middle
    return (low + high) / 2


def intercept(expression, var) -> dict:
    try:
        value = expression.subs(var, 0)
        if value.is_real is False or _failed(value):
            return _msg("analysis.undefined")
        return _line(f"f(0) = {num(value)}", f"f(0) = {_tex(value)}")
    except (ValueError, TypeError, AttributeError):
        return _msg("analysis.undefined")


def parity(expression, var) -> dict:
    try:
        mirrored = sp.simplify(expression.subs(var, -var))
        if sp.simplify(mirrored - expression) == 0:
            return _msg("analysis.even")
        if sp.simplify(mirrored + expression) == 0:
            return _msg("analysis.odd")
        return _msg("analysis.neither")
    except (ValueError, TypeError):
        return _msg("analysis.undefined")


def periodicity(expression, var) -> dict:
    try:
        period = sp.periodicity(expression, var)
        if period:
            return _line(f"T = {num(period)}", f"T = {_tex(period)}")
        return _msg("analysis.aperiodic")
    except (ValueError, TypeError, NotImplementedError):
        return _msg("analysis.aperiodic")


def monotony(expression, var, window: tuple[float, float] | None = None) -> list[dict]:
    """Increasing and decreasing stretches, bounded to the window.

    Each line carries the key separately from the LaTeX, so the interface can
    translate "increasing" without the formula being swallowed by the lookup.
    """
    low, high = window or DEFAULT_WINDOW
    try:
        derivative = sp.diff(expression, var)
        critical = _zeros_in_window(derivative, var, low, high)
    except (ValueError, TypeError, NotImplementedError):
        return [_msg("analysis.undefined")]

    def entry(key: str, caption: str, latex_range: str) -> dict:
        return {
            "text": f"{key}:{caption}",
            "latex": f"\\text{{{key}}}",
            "math": True,
            "key": key,
            "caption": caption,
            "range_latex": latex_range,
        }

    if not critical:
        sign = _sign_at(derivative, var, (low + high) / 2)
        key = "analysis.increasing" if sign > 0 else "analysis.decreasing"
        return [entry(key, f"({num(low)}; {num(high)})",
                      f"\\left({_tex(low)};\\; {_tex(high)}\\right)")]

    lines: list[dict] = []

    first = critical[0]
    key = "analysis.increasing" if _sign_at(derivative, var, (low + float(first)) / 2) > 0 \
        else "analysis.decreasing"
    lines.append(entry(key, f"{var.name} < {num(first)}", f"{var.name} < {_tex(first)}"))

    for left, right in zip(critical, critical[1:]):
        key = "analysis.increasing" if _sign_at(
            derivative, var, (float(left) + float(right)) / 2) > 0 else "analysis.decreasing"
        lines.append(entry(key, f"({num(left)}; {num(right)})",
                           f"\\left({_tex(left)};\\; {_tex(right)}\\right)"))

    last = critical[-1]
    key = "analysis.increasing" if _sign_at(derivative, var, (float(last) + high) / 2) > 0 \
        else "analysis.decreasing"
    lines.append(entry(key, f"{var.name} > {num(last)}", f"{var.name} > {_tex(last)}"))

    return lines[:8]


def _sign_at(derivative, var, point: float) -> int:
    try:
        return 1 if float(sp.N(derivative.subs(var, point))) > 0 else -1
    except (TypeError, ValueError):
        return 1


def extrema_on(expression, var, low: float, high: float) -> list[dict]:
    """Largest and smallest value on a closed interval."""
    try:
        derivative = sp.diff(expression, var)
        critical = [p for p in _zeros_in_window(derivative, var, low, high)
                    if low <= float(p) <= high]
    except (ValueError, TypeError, NotImplementedError):
        critical = []

    candidates: list[tuple] = [(sp.Integer(int(low)) if float(low).is_integer() else sp.Float(low), "boundary"),
                               (sp.Integer(int(high)) if float(high).is_integer() else sp.Float(high), "boundary")]
    candidates += [(point, "critical") for point in critical]

    values = []
    for point, kind in candidates:
        try:
            height = expression.subs(var, point)
            if _failed(height) or not sp.N(height).is_real:
                continue
            values.append((point, sp.N(height), kind))
        except (TypeError, ValueError):
            continue

    if not values:
        return [_msg("analysis.undefined")]

    maximum = max(values, key=lambda item: float(item[1]))
    minimum = min(values, key=lambda item: float(item[1]))

    lines = [
        _line(f"max f({num(maximum[0])}) = {num(maximum[1])}",
              f"\\max f({_tex(maximum[0])}) = {_tex(expression.subs(var, maximum[0]))}"),
        _line(f"min f({num(minimum[0])}) = {num(minimum[1])}",
              f"\\min f({_tex(minimum[0])}) = {_tex(expression.subs(var, minimum[0]))}"),
    ]
    if critical:
        joined = ",\\; ".join(f"{var.name} = {_tex(p)}" for p in critical[:6])
        lines.append(_line("critical: " + ", ".join(f"{var.name} = {num(p)}" for p in critical[:6]),
                           f"f'(x) = 0:\\; {joined}"))
    return lines


def asymptotes(expression, var) -> list[dict]:
    """Vertical and horizontal asymptotes, skipping oscillating limits."""
    found: list[dict] = []

    # Vertical: where the function leaves its domain
    try:
        scope = sp.calculus.util.continuous_domain(expression, var, sp.S.Reals)
        edges: list = []
        if isinstance(scope, sp.Union):
            for part in scope.args:
                if isinstance(part, sp.Interval):
                    edges.extend([part.left, part.right])
        elif isinstance(scope, sp.Interval):
            edges.extend([scope.left, scope.right])

        for point in edges:
            if point in (sp.oo, -sp.oo) or not getattr(point, "is_real", False):
                continue
            try:
                left = sp.limit(expression, var, point, "-")
                right = sp.limit(expression, var, point, "+")
            except (ValueError, TypeError, NotImplementedError):
                continue
            if _failed(left) or _failed(right):
                continue
            if left in (sp.oo, -sp.oo) or right in (sp.oo, -sp.oo):
                found.append(_line(
                    f"{var.name} = {num(point)} (vertical)",
                    f"{var.name} = {_tex(point)}\\;\\text{{(}}analysis.vertical\\text{{)}}"))
    except (NotImplementedError, ValueError, TypeError):
        pass

    # Horizontal: a finite limit at infinity, not an oscillation
    for target, _label in ((sp.oo, "+\\infty"), (-sp.oo, "-\\infty")):
        try:
            value = sp.limit(expression, var, target)
        except (ValueError, TypeError, NotImplementedError):
            continue
        if _failed(value) or value in (sp.oo, -sp.oo, sp.nan):
            continue
        # Python < 3.12 forbids backslashes inside f-string expressions
        direction = "+\u221e" if target is sp.oo else "\u2212\u221e"
        found.append(_line(
            f"y = {num(value)} (horizontal, {var.name}\u2192{direction})",
            f"y = {_tex(value)}\\;\\text{{(}}analysis.horizontal\\text{{)}}"))

    return found or [_msg("analysis.no_asymptotes")]


def limits_at_infinity(expression, var) -> list[dict]:
    lines: list[dict] = []
    for target, label in ((sp.oo, "+\\infty"), (-sp.oo, "-\\infty")):
        try:
            value = sp.limit(expression, var, target)
        except (ValueError, TypeError, NotImplementedError):
            lines.append(_msg("ExprError.undefined"))
            continue

        if _failed(value):
            lines.append(_line(f"lim({var.name}\u2192{num(target)}) does not exist",
                               f"\\lim_{{{var.name} \\to {label}}} {ln_latex(expression)}"
                               "\\;\\text{—}\\;analysis.oscillates"))
        elif value is sp.oo or value is -sp.oo:
            lines.append(_line(f"lim({var.name}\u2192{num(target)}) = {num(value)}",
                               f"\\lim_{{{var.name} \\to {label}}} {ln_latex(expression)} = {_tex(value)}"))
        else:
            lines.append(_line(f"lim({var.name}\u2192{num(target)}) = {num(value)}",
                               f"\\lim_{{{var.name} \\to {label}}} {ln_latex(expression)} = {_tex(value)}"))
    return lines


def limits_at(expression, var, point) -> list[dict]:
    """Both one-sided limits plus the two-sided verdict."""
    lines: list[dict] = []
    for direction, sign in (("-", "-"), ("+", "+")):
        try:
            value = sp.limit(expression, var, point, direction)
        except (ValueError, TypeError, NotImplementedError):
            continue
        if _failed(value):
            continue
        # Python < 3.12 forbids backslashes inside f-string expressions
        side = "\u2212" if direction == "-" else "+"
        lines.append(_line(
            f"lim({var.name}\u2192{num(point)}{side}) = {num(value)}",
            f"\\lim_{{{var.name} \\to {_tex(point)}^{{{sign}}}}} {ln_latex(expression)} = {_tex(value)}"))

    try:
        left = sp.limit(expression, var, point, "-")
        right = sp.limit(expression, var, point, "+")
        if _failed(left) or _failed(right):
            return lines
        lines.append(_msg("ExprError.limit_mismatch") if left != right
                     else _msg("ExprError.limit_match"))
    except (ValueError, TypeError, NotImplementedError):
        pass
    return lines


# --------------------------------------------------------------------- report
def full_report(text: str, interval: tuple[float, float] | None = None) -> dict:
    """Complete study of a function.

    ``interval`` bounds the extrema search and every place where an unbounded
    scan would otherwise be needed.
    """
    expression, var, name = prepare(text)
    simplified = sp.simplify(expression)
    window = interval or DEFAULT_WINDOW

    sections: list[dict] = []

    def add(title: str, lines) -> None:
        normalised = [ln if isinstance(ln, dict) else _line(str(ln)) for ln in lines]
        sections.append({"title": title, "lines": normalised})

    add("analysis.section.function", [_line(f"f(x) = {clean_expr(str(simplified))}",
                                            f"f({name}) = {ln_latex(simplified)}")])
    add("analysis.section.domain", [domain(expression, var)])
    add("analysis.section.range", [value_range(expression, var)])
    add("analysis.section.zeros", [zeros(expression, var, window)])
    add("analysis.section.intercept", [intercept(expression, var)])
    add("analysis.section.parity", [parity(expression, var)])
    add("analysis.section.periodicity", [periodicity(expression, var)])

    first_derivative = sp.simplify(sp.diff(expression, var))
    add("analysis.section.derivative", [_line(
        clean_expr(str(first_derivative)), f"f'({name}) = {ln_latex(first_derivative)}")])

    add("analysis.section.monotony", monotony(expression, var, window))

    if interval:
        add(f"analysis.section.extrema:{num(interval[0])};{num(interval[1])}",
            extrema_on(expression, var, interval[0], interval[1]))

    add("analysis.section.asymptotes", asymptotes(expression, var))
    add("analysis.section.limits_inf", limits_at_infinity(expression, var))

    # Limits at a few zeros of the denominator, not at every root of f
    try:
        scope = sp.calculus.util.continuous_domain(expression, var, sp.S.Reals)
        breaks = []
        if isinstance(scope, sp.Union):
            for part in scope.args:
                if isinstance(part, sp.Interval):
                    breaks.extend([p for p in (part.left, part.right)
                                   if p not in (sp.oo, -sp.oo) and getattr(p, "is_real", False)])
        for point in breaks[:2]:
            add(f"analysis.section.limit_at:{num(point)}", limits_at(expression, var, point))
    except (NotImplementedError, ValueError, TypeError):
        pass

    try:
        antiderivative = sp.integrate(expression, var)
        if not antiderivative.has(sp.Integral):
            add("analysis.section.integral", [_line(
                f"\u222bf(x)dx = {clean_expr(str(antiderivative))} + C",
                f"\\int f({name})\\,d{name} = {ln_latex(antiderivative)} + C")])
        else:
            add("analysis.section.integral", [_msg("ExprError.no_antiderivative")])
    except (ValueError, TypeError, NotImplementedError):
        add("analysis.section.integral", [_msg("ExprError.no_antiderivative")])

    return {
        "function": f"f({name}) = {clean_expr(str(simplified))}",
        "function_latex": f"f({name}) = {ln_latex(simplified)}",
        "sections": sections,
    }


def limit_at_point(text: str, point_text: str, direction: str = "both") -> dict:
    """Standalone limit query used by the calculus tab."""
    expression, var, name = prepare(text)
    target = parse(point_text, name)

    if direction == "left":
        value = sp.limit(expression, var, target, "-")
        return {"title": ("calculus.title.limit.left", num(target)),
                "lines": [_line(f"lim({name}\u2192{num(target)}\u2212) {clean_expr(str(expression))} = {num(value)}",
                                f"\\lim_{{{name} \\to {_tex(target)}^-}} {ln_latex(expression)} = {_tex(value)}")]}
    if direction == "right":
        value = sp.limit(expression, var, target, "+")
        return {"title": ("calculus.title.limit.right", num(target)),
                "lines": [_line(f"lim({name}\u2192{num(target)}+) {clean_expr(str(expression))} = {num(value)}",
                                f"\\lim_{{{name} \\to {_tex(target)}^+}} {ln_latex(expression)} = {_tex(value)}")]}

    value = sp.limit(expression, var, target)
    lines = [_line(f"lim({name}\u2192{num(target)}) {clean_expr(str(expression))} = {num(value)}",
                   f"\\lim_{{{name} \\to {_tex(target)}}} {ln_latex(expression)} = {_tex(value)}")]
    lines.extend(limits_at(expression, var, target)[2:])
    return {"title": ("calculus.title.limit", num(target)), "lines": lines}


__all__ = [
    "full_report", "limit_at_point", "prepare", "num", "clean_expr",
    "domain", "value_range", "zeros", "intercept", "parity", "periodicity",
    "monotony", "extrema_on", "asymptotes", "limits_at_infinity", "limits_at",
    "interval_text", "interval_latex", "detect_variable",
]
