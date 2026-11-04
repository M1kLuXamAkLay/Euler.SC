"""
Named matrix registry and operations.

The interface keeps a set of matrices addressed by uppercase letters ``A``..``H``.
This module converts between the grid representation used by the UI and SymPy
objects, and implements every operation exposed as a button.

Results that are themselves matrices carry an ``grid`` field so the interface
can feed them back into the registry and continue a calculation chain.
"""
from __future__ import annotations

import re

import sympy as sp

from .parser import ExprError, parse

MAX_SIZE = 8
LETTERS = "ABCDEFGH"


def _scalar(token: str) -> sp.Expr:
    token = str(token).strip()
    if not token:
        raise ExprError("ExprError.empty_cell")
    return parse(token)


def to_matrix(grid: list[list[str]]) -> sp.Matrix:
    """Convert a rectangular grid of strings into a SymPy matrix."""
    if not grid or not grid[0]:
        raise ExprError("ExprError.empty_matrix")

    width = len(grid[0])
    for row in grid:
        if len(row) != width:
            raise ExprError("ExprError.ragged_matrix")

    if len(grid) > MAX_SIZE or width > MAX_SIZE:
        raise ExprError(f"ExprError.matrix_too_big:{MAX_SIZE}")

    return sp.Matrix([[_scalar(cell) for cell in row] for row in grid])


def from_text(text: str) -> sp.Matrix:
    """Parse ``"1 2; 3 4"`` notation into a matrix."""
    if not text or not text.strip():
        raise ExprError("ExprError.empty_matrix")

    rows = [r for r in re.split(r"[;\n]", text.strip()) if r.strip()]
    grid = [[c for c in re.split(r"[,\t ]+", row.strip()) if c] for row in rows]
    return to_matrix(grid)


def to_grid(matrix: sp.MatrixBase) -> list[list[str]]:
    """Matrix into the string grid the UI fills its cells with."""
    return [[_cell(matrix[i, j]) for j in range(matrix.cols)]
            for i in range(matrix.rows)]


def to_text(matrix: sp.MatrixBase) -> str:
    """Column-aligned text representation."""
    if matrix.rows == 0:
        return "(empty)"

    cells = [[_cell(matrix[i, j]) for j in range(matrix.cols)]
             for i in range(matrix.rows)]
    widths = [max(len(cells[i][j]) for i in range(matrix.rows))
              for j in range(matrix.cols)]

    return "\n".join(
        "  ".join(cells[i][j].rjust(widths[j]) for j in range(matrix.cols))
        for i in range(matrix.rows)
    )


def _cell(value) -> str:
    """Exact fractions inside matrices: ``3/2`` reads better than ``1.5``."""
    value = sp.nsimplify(value)
    if value.is_Integer:
        return str(int(value))
    if value.is_Rational and not value.is_Integer:
        return f"{int(value.p)}/{int(value.q)}"
    if value.is_real is False:
        return str(value)
    return (str(value).replace("**", "^")
            .replace("sqrt", "\u221a").replace("pi", "\u03c0"))


def _result(title_key: str, matrix: sp.MatrixBase | None = None,
            text: str | None = None, with_grid: bool = True) -> dict:
    payload = {"title": title_key, "body": text if text is not None else to_text(matrix)}
    if matrix is not None and with_grid:
        payload["grid"] = to_grid(matrix)
    return payload


def _require_square(matrix: sp.MatrixBase) -> None:
    if matrix.rows != matrix.cols:
        raise ExprError("ExprError.matrix_not_square")


def _require_same_shape(left: sp.MatrixBase, right: sp.MatrixBase) -> None:
    if left.shape != right.shape:
        raise ExprError(
            f"ExprError.shape_mismatch:{left.rows}x{left.cols}:{right.rows}x{right.cols}")


# ------------------------------------------------------------------ operations
def determinant(grid: list[list[str]]) -> dict:
    matrix = to_matrix(grid)
    _require_square(matrix)
    return _result("matrix.op.det", text=f"det = {_cell(sp.simplify(matrix.det()))}",
                   with_grid=False)


def inverse(grid: list[list[str]]) -> dict:
    matrix = to_matrix(grid)
    _require_square(matrix)
    if sp.simplify(matrix.det()) == 0:
        raise ExprError("ExprError.singular")
    return _result("matrix.op.inv", matrix.inv())


def rank(grid: list[list[str]]) -> dict:
    matrix = to_matrix(grid)
    reduced, pivots = matrix.rref()
    columns = ", ".join(str(p + 1) for p in pivots) or "\u2014"
    return _result(
        "matrix.op.rank",
        text=f"rank = {matrix.rank()}\n\n{to_text(reduced)}\n\npivot columns: {columns}",
        with_grid=False)


def transpose(grid: list[list[str]]) -> dict:
    return _result("matrix.op.transpose", to_matrix(grid).T)


def trace(grid: list[list[str]]) -> dict:
    matrix = to_matrix(grid)
    _require_square(matrix)
    return _result("matrix.op.trace", text=f"tr = {_cell(matrix.trace())}", with_grid=False)


def eigenvalues(grid: list[list[str]]) -> dict:
    matrix = to_matrix(grid)
    _require_square(matrix)

    lines = []
    for value, multiplicity in matrix.eigenvals().items():
        suffix = f"  (mult {multiplicity})" if multiplicity > 1 else ""
        lines.append(f"\u03bb = {_cell(sp.simplify(value))}{suffix}")

    body = "\n".join(lines)
    try:
        polynomial = str(matrix.charpoly().as_expr())
        polynomial = (polynomial.replace("lambda", "\u03bb")
                      .replace("**", "^").replace("*", " "))
        body += f"\n\ncharacteristic polynomial:\n{polynomial}"
    except (ValueError, TypeError):
        pass
    return _result("matrix.op.eigen", text=body, with_grid=False)


def eigenvectors(grid: list[list[str]]) -> dict:
    matrix = to_matrix(grid)
    _require_square(matrix)

    parts = []
    # eigenvects() yields (eigenvalue, multiplicity, [vectors]); unpacking four
    # values raised ValueError and broke the whole operation.
    for value, _multiplicity, vectors in matrix.eigenvects():
        rendered = ",  ".join(
            "(" + ", ".join(_cell(v) for v in vector) + ")" for vector in vectors)
        parts.append(f"\u03bb = {_cell(sp.simplify(value))}:  {rendered}")

    return _result("matrix.op.eigenvec",
                   text="\n".join(parts) if parts else "ExprError.no_solution",
                   with_grid=False)


def lu(grid: list[list[str]]) -> dict:
    lower, upper, _ = to_matrix(grid).LUdecomposition()
    return _result("matrix.op.lu",
                   text=f"L =\n{to_text(lower)}\n\nU =\n{to_text(upper)}",
                   with_grid=False)


def multiply(left_grid: list[list[str]], right_grid: list[list[str]]) -> dict:
    left, right = to_matrix(left_grid), to_matrix(right_grid)
    if left.cols != right.rows:
        raise ExprError(f"ExprError.multiply_shape:{left.cols}:{right.rows}")
    return _result("matrix.op.multiply", left * right)


def add(left_grid: list[list[str]], right_grid: list[list[str]], sign: int = 1) -> dict:
    left, right = to_matrix(left_grid), to_matrix(right_grid)
    _require_same_shape(left, right)
    key = "matrix.op.add" if sign > 0 else "matrix.op.subtract"
    return _result(key, left + right if sign > 0 else left - right)


def scalar(grid: list[list[str]], factor_text: str) -> dict:
    matrix = to_matrix(grid)
    return _result("matrix.op.scalar", matrix * _scalar(factor_text or "1"))


def power(grid: list[list[str]], exponent_text: str) -> dict:
    matrix = to_matrix(grid)
    _require_square(matrix)
    try:
        exponent = int(_scalar(exponent_text))
    except (TypeError, ValueError):
        raise ExprError("ExprError.integer_required") from None
    if not -8 <= exponent <= 8:
        raise ExprError("ExprError.power_range")
    return _result("matrix.op.power", matrix ** exponent)


def solve_linear(left_grid: list[list[str]], right_grid: list[list[str]]) -> dict:
    """Solve ``A x = B`` including degenerate cases."""
    matrix = to_matrix(left_grid)
    rhs = to_matrix(right_grid)

    _require_square(matrix)
    if rhs.rows != matrix.rows:
        raise ExprError(f"ExprError.rhs_shape:{rhs.rows}:{matrix.rows}")
    if rhs.cols != 1:
        raise ExprError("ExprError.rhs_not_column")

    det = sp.simplify(matrix.det())
    if det == 0:
        augmented = matrix.row_join(rhs)
        if augmented.rank() == matrix.rank():
            return _result("ExprError.infinite_solutions",
                           text=to_text(matrix.gauss_jordan_solve(rhs)[0]),
                           with_grid=False)
        raise ExprError("ExprError.inconsistent_system")

    solution = matrix.inv() * rhs
    lines = [to_text(solution), f"\ndet = {_cell(det)}"]

    if matrix.rows <= 4:
        cramer = []
        for column in range(matrix.cols):
            swapped = matrix.copy()
            swapped[:, column] = rhs
            name = "\u0394" if column == 0 else f"\u0394{column + 1}"
            cramer.append(f"{name} = {_cell(swapped.det())}")
        lines.append("\ncramer: " + ",  ".join(cramer))

    return _result("matrix.op.system", text="\n".join(lines), with_grid=False)


OPERATIONS = {
    "det": determinant,
    "inv": inverse,
    "rank": rank,
    "transpose": transpose,
    "trace": trace,
    "eigen": eigenvalues,
    "eigenvec": eigenvectors,
    "lu": lu,
}


def run(operation: str, first: list[list[str]],
        second: list[list[str]] | None = None,
        extra: str = "") -> dict:
    """
    Dispatch a matrix operation.

    :param operation: one of the keys in ``OPERATIONS`` plus multiply/add/
                      subtract/scalar/power/system
    :param first: grid of the left operand
    :param second: grid of the right operand where the operation needs two
    :param extra: scalar or exponent as text
    """
    if operation == "multiply":
        if second is None:
            raise ExprError("ExprError.need_second_matrix")
        return multiply(first, second)

    if operation in ("add", "subtract"):
        if second is None:
            raise ExprError("ExprError.need_second_matrix")
        return add(first, second, 1 if operation == "add" else -1)

    if operation == "scalar":
        return scalar(first, extra)

    if operation == "power":
        return power(first, extra)

    if operation == "system":
        if second is None:
            raise ExprError("ExprError.need_second_matrix")
        return solve_linear(first, second)

    if operation in OPERATIONS:
        return OPERATIONS[operation](first)

    raise ExprError(f"ExprError.unknown_operation:{operation}")


__all__ = [
    "to_matrix", "from_text", "to_grid", "to_text", "run", "OPERATIONS",
    "solve_linear", "LETTERS", "MAX_SIZE",
]
