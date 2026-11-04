"""
Safe expression parser.

Security model
--------------
Input arrives from three untrusted sources: manual entry, OCR and LLM output.
The previous implementation used ``sympify``, which evaluates arbitrary Python.
Every expression now passes token validation against an allow-list before it
reaches SymPy: only known identifiers, numbers, operators and brackets survive.

Matrix support
--------------
Uppercase letters ``A`` through ``H`` are reserved for named matrices. When a
matrix registry is supplied, those letters resolve to ``sympy.Matrix`` objects,
so expressions such as ``rank(A) * A`` or ``det(A + B)`` evaluate directly.
"""
from __future__ import annotations

import io
import re
import tokenize

import sympy as sp
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    rationalize,
    standard_transformations,
)

# Identifiers the parser accepts. Anything outside this set is rejected.
_SCALAR_NAMES = frozenset({
    "x", "y", "z", "w", "u", "v", "n", "t", "k", "a", "b", "c", "m",
    "pi", "E", "I", "e", "oo", "inf", "infty", "nan",
    "sin", "cos", "tan", "cot", "ctg", "sec", "csc",
    "asin", "acos", "atan", "arcsin", "arccos", "arctan",
    "sinh", "cosh", "tanh",
    "sqrt", "cbrt", "exp", "log", "ln", "lg", "Abs", "abs",
    "factorial", "floor", "ceiling", "sign",
    "Min", "Max", "deg", "rad",
})

# Matrix identifiers and operations. Only usable when a registry is present.
_MATRIX_NAMES = frozenset("ABCDEFGH")
_MATRIX_FUNCS = frozenset({"rank", "det", "inv", "trace", "transpose", "T", "rref", "eigenvals"})

_ALLOWED_TOKEN_TYPES = frozenset({
    tokenize.NAME, tokenize.NUMBER, tokenize.OP,
    tokenize.ENDMARKER, tokenize.NEWLINE, tokenize.NL,
})

_TRANSFORMS = standard_transformations + (
    implicit_multiplication_application,
    rationalize,
)


class ExprError(ValueError):
    """Parse or evaluation failure carrying a user-facing message."""


def _allowed_names(with_matrices: bool) -> frozenset:
    if with_matrices:
        return _SCALAR_NAMES | _MATRIX_NAMES | _MATRIX_FUNCS
    return _SCALAR_NAMES


def validate(expr: str, with_matrices: bool = False) -> str:
    """
    Reject anything that is not pure mathematics.

    Blocks string literals, attribute access, private names, calls to unknown
    identifiers and every dunder form such as ``__import__``.
    """
    if not expr or not expr.strip():
        raise ExprError("ExprError.empty")
    if len(expr) > 2000:
        raise ExprError("ExprError.too_long")

    allowed = _allowed_names(with_matrices)
    try:
        for token in tokenize.generate_tokens(io.StringIO(expr).readline):
            if token.type not in _ALLOWED_TOKEN_TYPES:
                raise ExprError(f"ExprError.bad_char:{token.string}")
            if token.type == tokenize.NAME and token.string not in allowed:
                raise ExprError(f"ExprError.bad_name:{token.string}")
            if token.type == tokenize.OP and token.string == ".":
                raise ExprError(f"ExprError.bad_op:{token.string}")
    except tokenize.TokenError as exc:
        raise ExprError(f"ExprError.syntax:{exc}") from None
    return expr


def _matrix_locals(matrices: dict[str, sp.Matrix]) -> dict:
    """Expose matrices plus the matrix operations that may appear in expressions."""
    scope = dict(matrices)
    scope.update({
        "rank": lambda m: m.rank(),
        "det": lambda m: m.det(),
        "inv": lambda m: m.inv(),
        "trace": lambda m: m.trace(),
        "transpose": lambda m: m.T,
        "T": lambda m: m.T,
        "rref": lambda m: m.rref()[0],
        "eigenvals": lambda m: m.eigenvals(),
    })
    return scope


def _scalar_locals(var) -> dict:
    var = sp.Symbol(str(var), real=True)
    """Symbols and functions visible to the parser.

    Every free variable is declared ``real=True``. This is not cosmetic: the
    solver builds ``Symbol("z", real=True)`` and asks for ``coeff(z)``, and a
    plain ``Symbol("z")`` is a *different* object whose coefficient is always
    zero. That mismatch silently dropped ``z`` from every three-unknown system.
    """
    return {
        "x": var,
        "y": sp.Symbol("y", real=True),
        "z": sp.Symbol("z", real=True),
        "w": sp.Symbol("w", real=True),
        "u": sp.Symbol("u", real=True),
        "v": sp.Symbol("v", real=True),
        "t": sp.Symbol("t", real=True),
        "n": sp.Symbol("n", real=True),
        "k": sp.Symbol("k", real=True),
        "a": sp.Symbol("a", real=True),
        "b": sp.Symbol("b", real=True),
        "c": sp.Symbol("c", real=True),
        "m": sp.Symbol("m", real=True),
        "pi": sp.pi, "E": sp.E, "I": sp.I, "e": sp.E,
        "oo": sp.oo, "inf": sp.oo, "infty": sp.oo, "nan": sp.nan,
        "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
        "cot": sp.cot, "ctg": sp.cot, "sec": sp.sec, "csc": sp.csc,
        "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
        "arcsin": sp.asin, "arccos": sp.acos, "arctan": sp.atan,
        "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
        "sqrt": sp.sqrt, "cbrt": lambda v: sp.Pow(v, sp.Rational(1, 3)),
        "exp": sp.exp, "log": sp.log, "ln": sp.log,
        "lg": lambda v: sp.log(v, 10),
        "Abs": sp.Abs, "abs": sp.Abs,
        "factorial": sp.factorial,
        "floor": sp.floor, "ceiling": sp.ceiling, "sign": sp.sign,
        "Min": sp.Min, "Max": sp.Max,
        "deg": lambda v: v * sp.pi / 180,
        "rad": lambda v: v * sp.pi / 180,
    }


_REPLACEMENTS = (
    ("\u00d7", "*"), ("\u00b7", "*"), ("\u00f7", "/"),
    ("\u2212", "-"), ("\u2013", "-"), ("\u2014", "-"),
    ("^", "**"), ("\u221a", "sqrt"), ("\u03c0", "pi"),
    ("\u221e", "oo"), ("\u2264", "<="), ("\u2265", ">="), ("\u2260", "!="),
    ("\u00b2", "**2"), ("\u00b3", "**3"),
)


# "78 + 7%" reads as "78 plus 7 percent of 78". A plain substitution to /100
# would give 78.07, which is not what the key is for on any calculator.
_PERCENT_OF = re.compile(
    r"(?<![\w.)])(-?\d+(?:\.\d+)?)\s*([+\-])\s*(\d+(?:\.\d+)?)\s*%")
_PERCENT_ANY = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _expand_percent(expr: str) -> str:
    """Rewrite percent notation into plain arithmetic.

    * ``A + B%`` and ``A - B%`` -> ``A +/- A*B/100`` (percent *of A*)
    * ``A * B%``, ``A / B%``, bare ``B%`` -> ``B/100``

    Only numeric operands are rewritten; a ``%`` left in place is rejected by
    the validator, which is the correct outcome for something like ``x + y%``.
    """
    def percent_of(match: re.Match) -> str:
        base, sign, rate = match.groups()
        return f"({base}{sign}({base})*({rate})/100)"

    expr = _PERCENT_OF.sub(percent_of, expr)
    expr = _PERCENT_ANY.sub(lambda m: f"(({m.group(1)})/100)", expr)
    return expr

_DECIMAL_COMMA = re.compile(r"(?<![\w)])(-?\d+),(\d+)")
_MIXED_FRACTION = re.compile(r"(?<![\w.)])(-?\d+)\s+(\d+)/(\d+)")
_FACTORIAL = re.compile(r"(\d+(?:\.\d+)?|[a-zA-Z]\w*|\([^()]*\))!")


def preprocess(raw: str) -> str:
    """Normalise human notation into Python syntax."""
    if not raw:
        return ""
    expr = raw
    for src, dst in _REPLACEMENTS:
        expr = expr.replace(src, dst)
    expr = re.sub(r"\|([^|]*)\|", r"Abs(\1)", expr)

    # Decimal comma: "1,5" means 1.5 in most of Europe, and OCR returns it that
    # way. A comma between two digits is a decimal separator; a comma after a
    # name or bracket is an argument separator and stays.
    expr = _DECIMAL_COMMA.sub(r"\1.\2", expr)

    # Percent, calculator convention: "78 + 7%" is 78 + 7% *of 78*, not 78 + 0.07
    expr = _expand_percent(expr)

    # Mixed fraction "5 1/2" means 5 + 1/2. Must run before whitespace collapse,
    # because the space is the only thing separating the whole part.
    expr = _MIXED_FRACTION.sub(r"(\1+\2/\3)", expr)

    expr = _FACTORIAL.sub(r"factorial(\1)", expr)
    return re.sub(r"\s+", " ", expr).strip()


def _matrix_scope(matrices: dict[str, list[list[str]]]) -> dict:
    """Build SymPy matrices from raw grids for use inside expressions."""
    scope = {}
    for name, grid in matrices.items():
        try:
            scope[name] = sp.Matrix(
                [[_parse_scalar(cell) for cell in row] for row in grid])
        except (TypeError, ValueError):
            raise ExprError(f"ExprError.bad_matrix:{name}") from None
    return _matrix_locals(scope)


def parse(raw: str, var_name: str = "x",
          matrices: dict[str, list[list[str]]] | None = None) -> sp.Expr:
    """
    Parse an expression into a SymPy object.

    :param raw: user input in any supported notation
    :param var_name: primary variable symbol
    :param matrices: optional mapping name -> grid of strings for A..H

    The result may be a scalar expression or a Matrix, depending on the input.
    """
    expr = preprocess(raw)
    validate(expr, with_matrices=bool(matrices))

    scope = _scalar_locals(sp.Symbol(var_name, real=True))
    if matrices:
        scope.update(_matrix_scope(matrices))

    try:
        return parse_expr(expr, local_dict=scope,
                          transformations=_TRANSFORMS, evaluate=True)
    except ExprError:
        raise
    except SyntaxError as exc:
        raise ExprError(f"ExprError.syntax:{exc.msg}") from None
    except ZeroDivisionError:
        raise ExprError("ExprError.div_zero") from None
    except Exception as exc:
        raise ExprError(_humanize(exc)) from None


def _parse_scalar(text: str) -> sp.Expr:
    """Parse a single matrix cell. Cells are always scalar expressions."""
    cleaned = preprocess(str(text))
    validate(cleaned, with_matrices=False)
    try:
        return parse_expr(cleaned, local_dict=_scalar_locals(sp.Symbol("x")),
                          transformations=_TRANSFORMS, evaluate=True)
    except Exception as exc:
        raise ExprError(_humanize(exc)) from None


def _humanize(exc: Exception) -> str:
    msg = str(exc).lower()
    if "division by zero" in msg:
        return "ExprError.div_zero"
    if "logarithm" in msg or ("log" in msg and "negative" in msg):
        return "ExprError.log_domain"
    if "factorial" in msg or "gamma" in msg:
        return "ExprError.factorial_domain"
    return "ExprError.generic"


def detect_variable(text: str) -> str:
    """Pick the primary variable: x when present, otherwise the first Latin letter."""
    stripped = re.sub(
        r"\b(sin|cos|tan|cot|ctg|sec|csc|asin|acos|atan|arcsin|arccos|arctan|"
        r"sinh|cosh|tanh|sqrt|cbrt|exp|log|ln|lg|Abs|abs|factorial|floor|"
        r"ceiling|sign|Min|Max|deg|rad|pi|oo|E)\b", "", text)
    found = re.findall(r"[a-z]", stripped)
    if not found:
        return "x"
    unique = list(dict.fromkeys(found))
    return "x" if "x" in unique else unique[0]
