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


def _evaluate(function, xs: np.ndarray) -> np.ndarray:
    """Call the lambdified function, mapping every non-finite value to NaN."""
    with np.errstate(all="ignore"):
        ys = function(xs)
    ys = np.asarray(ys, dtype=float)
    if ys.ndim == 0:
        ys = np.full(np.shape(xs), float(ys))
    ys = np.broadcast_to(ys, np.shape(xs)).astype(float).copy()
    ys[~np.isfinite(ys)] = np.nan
    return ys


def _adaptive_grid(function, x_min: float, x_max: float,
                   base_points: int, max_points: int) -> tuple[np.ndarray, np.ndarray]:
    """Sample the interval, then refine only where the curve needs it.

    A uniform grid is either too coarse to draw a steep section or far denser
    than a straight line needs. Two passes fix that cheaply:

    1. a uniform pass, which already draws smooth stretches correctly;
    2. each interval whose midpoint sits far off the straight line between its
       ends is split, recursively, up to a budget.

    The midpoint test is what makes this work for a curve such as ``sqrt(x)``
    near zero or ``x^3`` at the edge of the view: those are where a uniform grid
    leaves a visible polygon, and those are exactly where the deviation is
    large. A jump across an asymptote also fails the test, so the two branches
    get sampled densely and the split stays sharp.
    """
    xs = np.linspace(x_min, x_max, base_points)
    ys = _evaluate(function, xs)

    # Per-interval tolerance: a fraction of the vertical spread, so a function
    # that varies between -1e-3 and 1e-3 is refined just as carefully as one
    # between -1000 and 1000.
    finite = ys[np.isfinite(ys)]
    if finite.size > 1:
        low, high = np.percentile(finite, 2), np.percentile(finite, 98)
        scale = float(high - low)
    else:
        scale = 1.0
    if not math.isfinite(scale) or scale <= 0:
        scale = 1.0
    tolerance = scale * 0.004

    points: list[tuple[float, float]] = list(zip(xs.tolist(), ys.tolist()))
    if max_points <= base_points:
        return np.array([p[0] for p in points]), np.array([p[1] for p in points])

    # Iterative refinement: each pass splits every interval that still fails the
    # test. Depth is capped by the budget rather than by a recursion limit.
    budget = max_points - base_points
    for _ in range(6):
        if budget <= 0:
            break
        refined: list[tuple[float, float]] = []
        added = 0
        for index in range(len(points) - 1):
            xa, ya = points[index]
            xb, yb = points[index + 1]
            refined.append(points[index])

            if budget - added <= 0:
                continue

            xm = (xa + xb) / 2
            ym = float(_evaluate(function, np.array([xm], dtype=float))[0])

            # A NaN on either side is already a break; nothing to refine into.
            if math.isnan(ya) or math.isnan(yb):
                continue

            chord = (ya + yb) / 2
            if math.isnan(ym):
                # The function blows up inside the interval: sample it hard so
                # the asymptote is drawn as a near-vertical line, not a gap.
                refined.append((xm, ym))
                added += 1
                continue

            if abs(ym - chord) > tolerance:
                refined.append((xm, ym))
                added += 1

        points = refined + [points[-1]]
        budget -= added
        if added == 0:
            break

    xa = np.array([p[0] for p in points])
    ya = np.array([p[1] for p in points])
    return xa, ya


def _segments(xs: np.ndarray, ys: np.ndarray) -> list[list[list[float]]]:
    """Split the polyline where the curve is genuinely discontinuous.

    A break is inserted when the value is not finite, or when the jump between
    neighbours exceeds the local spread by a wide factor. Comparing against the
    whole-canvas height, as the renderer does, is not possible here (the engine
    does not know the canvas); the percentile spread is the equivalent test that
    survives an asymptote and never fires on a steep-but-continuous curve.
    """
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

    for x, y in zip(xs.tolist(), ys.tolist()):
        if math.isnan(y):
            if len(current) > 1:
                segments.append(current)
            current, previous = [], None
            continue

        if previous is not None and abs(y - previous) > jump_limit:
            if len(current) > 1:
                segments.append(current)
            current = []

        current.append([round(float(x), 9), round(float(y), 9)])
        previous = y

    if len(current) > 1:
        segments.append(current)
    return segments


def sample(equations: list[str], x_min: float, x_max: float,
           points: int = 1200) -> dict:
    """
    Evaluate the equations on an adaptive grid.

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

    # ``points`` is the cost of the uniform pass, not the final count: the
    # refinement may spend up to MAX_POINTS in total on the intervals that need
    # it. A caller that asks for 900 gets 900 on a smooth curve and up to 4000
    # where the curve is steep, instead of 4000 everywhere.
    requested = max(64, min(int(points), MAX_POINTS // 2))
    var = sp.Symbol("x", real=True)
    series = []

    for raw in equations:
        function = _lambdify(raw, var)
        try:
            xs, ys = _adaptive_grid(function, x_min, x_max, requested, MAX_POINTS)
        except Exception:
            raise ExprError(f"ExprError.plot_failed:{raw}") from None

        series.append({
            "label": raw,
            "segments": _segments(xs, ys),
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
