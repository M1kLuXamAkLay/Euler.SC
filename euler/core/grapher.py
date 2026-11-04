"""
Sampling for the plot canvas.

Produces polylines broken at discontinuities. Without the split a function
such as ``1/x`` is drawn as a single stroke across the vertical asymptote,
which looks like a bug rather than mathematics.

The interface receives plain Python floats only: NumPy scalars do not survive
JSON serialisation and would break the bridge.
"""
from __future__ import annotations

import math

import numpy as np
import sympy as sp

from .parser import ExprError, parse

MAX_POINTS = 4000
DEFAULT_RANGE = (-10.0, 10.0)


def _split_relation(text: str):
    for op in ("<=", ">=", "<", ">", "="):
        if op in text:
            left, right = text.split(op, 1)
            return left.strip(), op, right.strip()
    return None


def _lambdify(raw: str, var: sp.Symbol):
    """Compile the expression to a fast NumPy callable."""
    relation = _split_relation(raw)
    if relation is None:
        expr = parse(raw, var.name)
    else:
        left, _op, right = relation
        expr = parse(left, var.name) - parse(right, var.name)

    if isinstance(expr, sp.MatrixBase):
        raise ExprError("ExprError.matrix_not_plottable")

    # cse collapses repeated subexpressions and speeds up complex curves
    return sp.lambdify(var, expr, modules="numpy", cse=True)


def sample(equations: list[str], x_min: float, x_max: float,
           points: int = 1200) -> dict:
    """
    Evaluate the equations on a grid.

    :returns: ``{"x_min", "x_max", "series": [{"label", "segments"}], "has_data"}``
              where ``segments`` is a list of polylines, each a list of ``[x, y]``.
    """
    if not equations:
        raise ExprError("ExprError.no_equations")
    if not math.isfinite(x_min) or not math.isfinite(x_max):
        raise ExprError("ExprError.bad_range")
    if x_max <= x_min:
        raise ExprError("ExprError.range_order")
    if x_max - x_min > 1e6:
        raise ExprError("ExprError.range_too_wide")

    points = min(int(points), MAX_POINTS)
    var = sp.Symbol("x", real=True)
    xs = np.linspace(x_min, x_max, points)
    series = []

    for raw in equations:
        function = _lambdify(raw, var)
        try:
            with np.errstate(all="ignore"):
                ys = function(xs)
        except Exception:
            raise ExprError(f"ExprError.plot_failed:{raw}") from None

        ys = np.asarray(ys, dtype=float)
        if ys.ndim == 0:
            ys = np.full_like(xs, float(ys))
        ys = np.broadcast_to(ys, xs.shape).astype(float)
        ys[~np.isfinite(ys)] = np.nan

        # Robust spread from percentiles: min/max are themselves the outliers
        # for functions with asymptotes, so a jump would never be detected.
        finite = ys[np.isfinite(ys)]
        if finite.size:
            low, high = np.percentile(finite, 5), np.percentile(finite, 95)
            spread = float(high - low)
        else:
            spread = 0.0
        jump_limit = spread * 20 if spread > 0 else 1e12

        segments: list[list[list[float]]] = []
        current: list[list[float]] = []
        previous = None

        for x, y in zip(xs, ys):
            if math.isnan(y):
                if len(current) > 1:
                    segments.append(current)
                current, previous = [], None
                continue

            if previous is not None and abs(y - previous) > jump_limit:
                if len(current) > 1:
                    segments.append(current)
                current = []

            current.append([round(float(x), 6), round(float(y), 6)])
            previous = y

        if len(current) > 1:
            segments.append(current)

        series.append({
            "label": raw,
            "segments": [seg for seg in segments if len(seg) > 1],
        })

    return {
        "x_min": float(x_min),
        "x_max": float(x_max),
        "series": series,
        "has_data": any(item["segments"] for item in series),
    }


def autoscale(equations: list[str], x_min: float, x_max: float,
              points: int = 600) -> dict:
    """Pick a vertical range that ignores single-point spikes."""
    data = sample(equations, x_min, x_max, points)
    values = [y for item in data["series"] for seg in item["segments"] for _x, y in seg]

    if not values:
        return {"y_min": -10.0, "y_max": 10.0}

    array = np.array(values, dtype=float)
    low, high = np.percentile(array, 2), np.percentile(array, 98)

    if not math.isfinite(low) or not math.isfinite(high) or high <= low:
        low, high = float(array.min()), float(array.max())

    pad = (high - low) * 0.12 or 1.0
    return {"y_min": round(float(low - pad), 3), "y_max": round(float(high + pad), 3)}


__all__ = ["sample", "autoscale", "MAX_POINTS", "DEFAULT_RANGE"]
