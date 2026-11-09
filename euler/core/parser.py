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
    "sqrt", "cbrt", "root", "exp", "log", "ln", "lg", "log10", "Abs", "abs",
    "factorial", "floor", "ceiling", "sign",
    "Min", "Max", "deg", "rad",
})

# Matrix identifiers and operations. Only usable when a registry is present.
_MATRIX_NAMES = frozenset("ABCDEFGH")
_MATRIX_FUNCS = frozenset({"rank", "det", "inv", "trace", "transpose", "T", "rref", "eigenvals", "root"})

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


def _matrix_root_expr(value, degree=2):
    """``sqrt``/``root`` that accept a matrix as well as a scalar.

    For a scalar this is the ordinary root. For a square matrix it is the
    principal root through the eigen-decomposition (see matrix.matrix_root).
    """
    if isinstance(value, sp.MatrixBase):
        from .matrix import matrix_root
        return matrix_root(value, sp.Integer(int(degree)))
    if degree == 2:
        return sp.sqrt(value)
    return sp.Pow(value, sp.Rational(1, int(degree)))


def _matrix_locals(matrices: dict[str, sp.Matrix]) -> dict:
    """Expose matrices plus the matrix operations that may appear in expressions."""
    scope = dict(matrices)
    scope.update({
        "sqrt": _matrix_root_expr,
        "root": lambda m, n=2: _matrix_root_expr(m, n),
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
        "root": lambda v, n=2: sp.Pow(v, sp.Rational(1, 1) / n),
        "exp": sp.exp,
        # "log" is the base-10 key: its inverse on the keypad is 10^x, and a
        # logarithm that ignored the base sat next to "ln" doing the same thing.
        "log": lambda v: sp.log(v, 10), "ln": sp.log,
        "lg": lambda v: sp.log(v, 10), "log10": lambda v: sp.log(v, 10),
        "Abs": sp.Abs, "abs": sp.Abs,
        "factorial": sp.factorial,
        "floor": sp.floor, "ceiling": sp.ceiling, "sign": sp.sign,
        "Min": sp.Min, "Max": sp.Max,
        # deg(v): an angle given in degrees -> radians.  rad(v): an angle given
        # in radians -> degrees.  They were both v*pi/180, so rad(pi/2) became
        # sin(pi^2/360) for a student who meant sin(90 degrees).
        "deg": lambda v: v * sp.pi / 180,
        "rad": lambda v: v * 180 / sp.pi,
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

# Functions whose arguments are comma-separated: inside their brackets a comma
# between digits is a separator, not a decimal mark. "root(27,3)" is the cube
# root of 27; read as a decimal it became root(27.3).
_CALLS_WITH_ARGUMENTS = ("root",)


def _decimal_commas_outside_calls(expr: str) -> str:
    """Turn decimal commas into points, except inside a multi-argument call."""
    out: list[str] = []
    depth_call = 0          # bracket depth inside a call that takes arguments
    stack: list[bool] = []  # for every open bracket: is it such a call?
    index = 0
    while index < len(expr):
        char = expr[index]
        if char == "(":
            name = re.search(r"([A-Za-z_]+)$", "".join(out))
            stack.append(bool(name and name.group(1) in _CALLS_WITH_ARGUMENTS))
            depth_call += stack[-1]
            out.append(char)
        elif char == ")":
            if stack and stack.pop():
                depth_call -= 1
            out.append(char)
        elif char == "," and depth_call == 0:
            # A comma between two digits is a decimal mark
            before = "".join(out)
            after = expr[index + 1:index + 2]
            if before[-1:].isdigit() and after.isdigit() and not re.search(r"[\w.]$", before[:-1] or " "):
                out.append(".")
            else:
                out.append(char)
        else:
            out.append(char)
        index += 1
    return "".join(out)


_DECIMAL_COMMA = re.compile(r"(?<![\w)])(-?\d+),(\d+)")
_MIXED_FRACTION = re.compile(r"(?<![\w.)])(-?\d+)\s+(\d+)/(\d+)")
_FACTORIAL = re.compile(r"(\d+(?:\.\d+)?|[a-zA-Z]\w*|\([^()]*\))!")


_LOG_BASE = re.compile(r"\\?\b(log10|log|lg)\s*_\s*(?:\{([^{}]*)\}|(\d+(?:\.\d+)?))")


def _read_group(text: str, start: int) -> tuple[str, int]:
    """Return the contents of the bracketed group at ``start`` and the end index.

    Bracket counting, not a regular expression: ``log_2(sin(x)+1)`` nests.
    """
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
    return text[start + 1:], len(text)


def _expand_log_bases(expr: str) -> str:
    """Rewrite ``log_b(x)`` as ``log(x)/log(b)``.

    Bases reach the engine in several shapes: ``\\log_{9}(9)`` from a braced
    subscript, ``\\log_9(9)`` from a bare one (MathLive emits this for a single
    digit), and the same after the LaTeX macros have already been stripped.
    Left alone, the subscript turns into the identifier ``log_9``, which is
    rejected as an unknown name.
    """
    while True:
        match = _LOG_BASE.search(expr)
        if not match:
            return expr

        base = match.group(2) if match.group(2) is not None else match.group(3)
        cursor = match.end()
        while cursor < len(expr) and expr[cursor] == " ":
            cursor += 1

        if cursor < len(expr) and expr[cursor] == "(":
            argument, after = _read_group(expr, cursor)
        else:
            token = re.match(r"-?\d+(?:\.\d+)?|[a-zA-Z]+", expr[cursor:])
            if not token:
                return expr
            argument = token.group(0)
            after = cursor + len(argument)

        expr = f"{expr[:match.start()]}(log({argument})/log({base})){expr[after:]}"


def preprocess(raw: str) -> str:
    """Normalise human notation into Python syntax."""
    if not raw:
        return ""
    expr = _expand_log_bases(raw)
    for src, dst in _REPLACEMENTS:
        expr = expr.replace(src, dst)
    expr = re.sub(r"\|([^|]*)\|", r"Abs(\1)", expr)

    # Decimal comma: "1,5" means 1.5 in most of Europe, and OCR returns it that
    # way. A comma between two digits is a decimal separator; a comma after a
    # name or bracket is an argument separator and stays.
    expr = _decimal_commas_outside_calls(expr)

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
