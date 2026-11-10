"""Limits, derivatives and integrals.

Every result line carries two fields:

``text``  plain string for the clipboard;
``latex`` the same statement typeset for the display.

The interface renders the LaTeX, so a limit arrives as a real
``\\lim_{x\\to 0}`` fraction rather than an ASCII approximation.
"""
from __future__ import annotations

import sympy as sp

from .analysis import clean_expr, latex_value, num, prepare, result_line
from .parser import ExprError, parse


def limit(expression: str, point: str, direction: str = "both") -> dict:
    """Limit at a point or at infinity."""
    function, var, _name = prepare(expression)

    try:
        target = parse(point, var.name)
    except ExprError:
        raise ExprError("ExprError.bad_point") from None

    lines: list[dict] = []
    try:
        if direction == "left":
            value = sp.limit(function, var, target, "-")
            lines.append(result_line(
                f"lim({var.name}\u2192{num(target)}\u2212) {clean_expr(str(function))} = {num(value)}",
                f"\\lim_{{{var.name} \\to {latex_value(target)}^-}} {latex_value(function)} = {latex_value(value)}"))
        elif direction == "right":
            value = sp.limit(function, var, target, "+")
            lines.append(result_line(
                f"lim({var.name}\u2192{num(target)}+) {clean_expr(str(function))} = {num(value)}",
                f"\\lim_{{{var.name} \\to {latex_value(target)}^+}} {latex_value(function)} = {latex_value(value)}"))
        else:
            value = sp.limit(function, var, target)
            lines.append(result_line(
                f"lim({var.name}\u2192{num(target)}) {clean_expr(str(function))} = {num(value)}",
                f"\\lim_{{{var.name} \\to {latex_value(target)}}} {latex_value(function)} = {latex_value(value)}"))
            try:
                left = sp.limit(function, var, target, "-")
                right = sp.limit(function, var, target, "+")
                if left != right:
                    lines.append(result_line(
                        f"left = {num(left)},  right = {num(right)}",
                        f"\\text{{left}} = {latex_value(left)},\\quad \\text{{right}} = {latex_value(right)}"))
                    lines.append(result_line("ExprError.limit_mismatch"))
                else:
                    lines.append(result_line("ExprError.limit_match"))
            except (ValueError, TypeError, NotImplementedError):
                pass
    except (ValueError, TypeError, NotImplementedError):
        raise ExprError("ExprError.limit_failed") from None

    return {"title": ("calculus.title.limit", num(target)), "lines": lines}


def derivative(expression: str, order: int = 1) -> dict:
    """N-th order derivative, 1 <= order <= 10."""
    if not 1 <= order <= 10:
        raise ExprError("ExprError.order_range")

    function, var, _name = prepare(expression)
    try:
        result = sp.simplify(sp.diff(function, var, order))
    except (ValueError, TypeError, NotImplementedError):
        raise ExprError("ExprError.not_solvable") from None

    prime = "'" * order if order <= 3 else ""
    superscript = f"^{{({order})}}" if order > 3 else ""
    return {
        "title": ("calculus.title.derivative", str(order)),
        "lines": [result_line(
            f"f{prime}{('(' + str(order) + ')') if order > 3 else ''}({var.name}) = {clean_expr(str(result))}",
            f"f{superscript}({var.name}) = {latex_value(result)}")],
    }


def critical_points(expression: str) -> dict:
    """Stationary points classified by the second derivative."""
    function, var, _name = prepare(expression)
    try:
        first = sp.diff(function, var)
        second = sp.diff(first, var)
        points = sp.solve(sp.Eq(first, 0), var)
    except (ValueError, TypeError, NotImplementedError):
        raise ExprError("ExprError.not_solvable") from None

    if not points:
        return {"title": ("calculus.title.critical", ""),
                "lines": [result_line("ExprError.no_critical_points")]}

    lines = []
    for point in points[:10]:
        try:
            curvature = complex(second.subs(var, point))
            if abs(curvature.imag) > 1e-12:
                kind, kind_tex = "complex", "\\text{complex}"
            elif curvature.real > 0:
                kind, kind_tex = "minimum", "\\min"
            elif curvature.real < 0:
                kind, kind_tex = "maximum", "\\max"
            else:
                kind, kind_tex = "ExprError.inconclusive", "\\text{?}"

            height = function.subs(var, point)
            lines.append(result_line(
                f"{var.name} = {num(point)}  \u2192  {kind},  f = {num(height)}",
                f"{var.name} = {latex_value(point)},\\quad f = {latex_value(height)}\\;({kind_tex})"))
        except (TypeError, ValueError):
            lines.append(result_line(f"{var.name} = {num(point)}", f"{var.name} = {latex_value(point)}"))

    return {"title": ("calculus.title.critical", ""), "lines": lines}


def integral_indefinite(expression: str) -> dict:
    function, var, name = prepare(expression)
    try:
        result = sp.integrate(function, var)
    except (ValueError, TypeError, NotImplementedError):
        raise ExprError("ExprError.no_antiderivative") from None

    return {
        "title": ("calculus.title.integral", ""),
        "lines": [result_line(
            f"\u222b{clean_expr(str(function))} d{name} = {clean_expr(str(result))} + C",
            f"\\int {latex_value(function)}\\,d{name} = {latex_value(result)} + C")],
    }


def integral_definite(expression: str, lower: str, upper: str) -> dict:
    """Definite integral with the antiderivative shown for reference."""
    function, var, name = prepare(expression)

    try:
        low = parse(lower, var.name)
        high = parse(upper, var.name)
    except ExprError:
        raise ExprError("ExprError.bad_bounds") from None

    if low == high:
        raise ExprError("ExprError.empty_interval")

    try:
        exact = sp.integrate(function, (var, low, high))
    except (ValueError, TypeError, NotImplementedError):
        try:
            numeric = sp.N(sp.Integral(function, (var, low, high)).doit())
            return {
                "title": ("calculus.title.definite_numeric", ""),
                "lines": [
                    result_line(f"\u222b from {num(low)} to {num(high)} {clean_expr(str(function))} d{name} \u2248 {num(numeric)}",
                          f"\\int_{{{latex_value(low)}}}^{{{latex_value(high)}}} {latex_value(function)}\\,d{name} \\approx {latex_value(numeric)}"),
                    result_line("ExprError.numeric_only"),
                ],
            }
        except (ValueError, TypeError, NotImplementedError):
            raise ExprError("ExprError.integral_failed") from None

    if exact in (sp.oo, -sp.oo) or exact is sp.zoo or exact is sp.nan:
        raise ExprError("ExprError.divergent_integral")

    lines = [result_line(
        f"\u222b from {num(low)} to {num(high)} {clean_expr(str(function))} d{name} = {num(exact)}",
        f"\\int_{{{latex_value(low)}}}^{{{latex_value(high)}}} {latex_value(function)}\\,d{name} = {latex_value(exact)}")]

    try:
        antiderivative = sp.integrate(function, var)
        lines.append(result_line(f"F({name}) = {clean_expr(str(antiderivative))} + C",
                           f"F({name}) = {latex_value(antiderivative)} + C"))
        substituted = sp.simplify(
            antiderivative.subs(var, high) - antiderivative.subs(var, low))
        lines.append(result_line(
            f"F({num(high)}) \u2212 F({num(low)}) = {num(substituted)}",
            f"F({latex_value(high)}) - F({latex_value(low)}) = {latex_value(substituted)}"))
    except (ValueError, TypeError, NotImplementedError):
        pass

    return {"title": ("calculus.title.definite", ""), "lines": lines}


def run(kind: str, expression: str, a: str = "", b: str = "",
        direction: str = "both") -> dict:
    """Single entry point for the bridge."""
    if kind == "limit":
        return limit(expression, a or "0", direction)

    if kind == "derivative":
        try:
            order = int(a) if a else 1
        except ValueError:
            raise ExprError("ExprError.integer_required") from None
        return derivative(expression, order)

    if kind == "integral":
        return integral_indefinite(expression)

    if kind == "definite":
        if not a or not b:
            raise ExprError("ExprError.need_bounds")
        return integral_definite(expression, a, b)

    if kind == "critical":
        return critical_points(expression)

    raise ExprError(f"ExprError.unknown_operation:{kind}")


__all__ = ["limit", "derivative", "critical_points", "integral_indefinite",
           "integral_definite", "run"]
