"""
Solving layer: arithmetic, equations, systems, function analysis.

Every public function returns a dictionary shaped for the JSON bridge:
``{"ok": bool, "text": str, "latex": str | None, "error": str | None}``.

None of them raises: user input must never crash the interface.
Error strings are translation keys such as ``ExprError.div_zero`` so the
frontend can render them in the active language.
"""
from __future__ import annotations

import re

import sympy as sp
from sympy.polys.polyerrors import GeneratorsNeeded

from .parser import ExprError, detect_variable, parse

_RELATIONS = ("<=", ">=", "<", ">", "=")

_SUBSCRIPT = str.maketrans("0123456789", "\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089")

_PRETTY = (
    ("**", "^"),
    ("sqrt", "\u221a"),
    ("pi", "\u03c0"),
    ("oo", "\u221e"),
    ("*", " "),
)


SYSTEM_VARIABLES = "xyztuvw"


def clean(text: str) -> str:
    """Strip Python syntax from a SymPy repr: ``**`` to ``^``, ``*`` to space."""
    out = text
    for src, dst in _PRETTY:
        out = out.replace(src, dst)
    while "  " in out:
        out = out.replace("  ", " ")
    return out.strip()


def ok(text: str, latex: str | None = None, note: str | None = None) -> dict:
    """Success payload.

    ``latex`` is what the interface renders; ``text`` is only for clipboard
    copying. ``forms`` lists the alternative representations the ALT key cycles
    through. ``note`` carries a localisable caveat, such as "roots are complex".
    """
    return {"ok": True, "text": text, "latex": latex, "error": None,
            "forms": [], "note": note, "plain": text}


def ok_value(value) -> dict:
    """Success payload built from an expression, with every display form."""
    from .format import describe

    described = describe(value)
    return {
        "ok": True,
        "text": described["plain"],
        "latex": described["latex"],
        "error": None,
        "form_key": described["key"],
        "forms": described["forms"],
        "plain": described["plain"],
        # "ans" is what the Ans key feeds back: Python/SymPy syntax the parser
        # can read again ("4173/50", "sqrt(5)", "pi"), not display LaTeX.
        "ans": str(value),
    }


def err(key: str) -> dict:
    return {"ok": False, "text": "", "latex": None, "error": key}


def _split_relation(text: str) -> tuple[str, str, str] | None:
    for op in sorted(_RELATIONS, key=len, reverse=True):
        if op in text:
            left, right = text.split(op, 1)
            return left.strip(), op, right.strip()
    return None


def _relation(left: sp.Expr, op: str, right: sp.Expr):
    builders = {
        "<": sp.Lt, ">": sp.Gt, "<=": sp.Le, ">=": sp.Ge, "=": sp.Eq,
    }
    return builders[op](left, right, evaluate=False)


def pretty_number(value, digits: int = 6) -> str:
    """
    Render a number the way a person would write it.

    Integers stay integer, finite rationals become ``3/2`` rather than ``1.5``
    inside exact contexts, and short closed forms such as ``\u221a3`` are kept
    instead of a decimal approximation.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return f"{number:.{digits}g}"

    if not hasattr(value, "is_number"):
        return clean(sp.sstr(value))

    try:
        if value is sp.oo:
            return "+\u221e"
        if value is -sp.oo:
            return "\u2212\u221e"
        if value is sp.zoo or value is sp.nan:
            return "ExprError.undefined"

        value = sp.nsimplify(value)

        if value.is_Integer:
            return str(int(value))
        if value.is_Rational:
            return f"{int(value.p)}/{int(value.q)}"
        if value.is_real is False:
            return clean(str(value))

        simplified = sp.simplify(value)
        text = clean(str(simplified))
        if text in ("e", "\u03c0", "E"):
            return text
        if len(text) <= 18 and ("\u221a" in text or "\u03c0" in text or "/" in text):
            return text

        approx = float(sp.N(value, digits + 2))
        return f"\u2248{approx:.{digits}g}"
    except (TypeError, ValueError, AttributeError):
        return clean(str(value))


def _tex(value) -> str:
    """LaTeX for a value, with infinities and natural log written properly."""
    if value is sp.oo:
        return "+\\infty"
    if value is -sp.oo:
        return "-\\infty"
    if value is sp.zoo or value is sp.nan:
        return "\\text{—}"
    from .analysis import ln_latex
    return ln_latex(value)


def _periodic_latex(solution, var_name: str) -> str:
    """Typeset an arithmetic progression as ``a + Tk, k in Z``.

    An ``ImageSet`` in SymPy is ``{f(n) : n in base}`` where ``f(n) = T*n + a``.
    The offset is therefore ``f(0)`` and the step is ``f(n) - f(n-1)``; reading
    the base set instead gives ``Integers``, not a number.
    """
    try:
        step_symbol = sp.Symbol("n", integer=True)
        lamda = solution.lamda
        offset = sp.simplify(lamda(0))
        period = sp.simplify(lamda(step_symbol) - lamda(step_symbol - 1))
    except (AttributeError, TypeError, ValueError):
        try:
            return f"{var_name} = {sp.latex(solution)}"
        except (ValueError, TypeError):
            return str(solution)

    if period == 0:
        return f"{var_name} = {_tex(offset)}"

    period_text = _tex(period)
    # "1*k" and "-1*k" are noise
    if period_text == "1":
        base = "k"
    elif period_text == "-1":
        base = "-k"
    else:
        # LaTeX macros run until a non-letter: "2 \pi" + "k" would become
        # "2 \pik", an undefined command
        base = f"{period_text}\\,k" if period_text.endswith("}") or "\\" in period_text else f"{period_text}k"

    if offset == 0:
        return f"{var_name} = {base},\\; k \\in \\mathbb{{Z}}"
    if offset.is_negative:
        return f"{var_name} = {base} - {_tex(-offset)},\\; k \\in \\mathbb{{Z}}"
    return f"{var_name} = {_tex(offset)} + {base},\\; k \\in \\mathbb{{Z}}"


def _imaginary_tex(magnitude) -> str:
    """``b\\,i`` with an upright i, and no coefficient for a unit magnitude."""
    body = _tex(magnitude)
    if body in ("1", "+1"):
        return "\\mathrm{i}"
    return f"{body}\\,\\mathrm{{i}}"


def _complex_pairs_latex(values, var_name: str) -> list[str]:
    """Group conjugate roots into ``±a ± bi`` lines.

    ``x^4 + 1 = 0`` gives four roots that SymPy prints as
    ``sqrt(2)(-1 - i)/2``. Written by hand the answer is
    ``x = ±sqrt(2)/2 ± sqrt(2)/2 i``, so the pairs are collected here.
    """
    complex_values = [v for v in values if sp.simplify(sp.im(v)) != 0]
    if len(complex_values) < 4:
        return []

    seen: set = set()
    parts: list[str] = []

    for value in complex_values:
        if value in seen:
            continue
        real = sp.simplify(sp.re(value))
        imaginary = sp.simplify(sp.im(value))
        if imaginary == 0:
            continue

        pair = sp.conjugate(value)
        seen.add(value)
        seen.add(pair)

        real_text = f"{_tex(sp.Abs(real))} " if real != 0 else ""
        imaginary_text = _imaginary_tex(sp.Abs(imaginary))
        parts.append(f"{var_name} = \\pm {real_text}\\pm {imaginary_text}")

    return parts if len(parts) * 2 == len(complex_values) else []


def _format_set_latex(solution, var_name: str) -> str:
    """The same set as :func:`_format_set`, typeset."""
    if solution is sp.S.Reals:
        return f"{var_name} \\in \\mathbb{{R}}"
    if solution is sp.S.EmptySet:
        return "\\varnothing"
    if solution is sp.S.Complexes:
        return f"{var_name} \\in \\mathbb{{C}}"

    if isinstance(solution, sp.FiniteSet):
        values = sorted(solution.args, key=lambda v: (float(sp.re(v) or 0), float(sp.im(v) or 0)))
        if not values:
            return "\\varnothing"
        if len(values) == 1:
            return f"{var_name} = {_tex(values[0])}"

        if len(values) == 2:
            first, second = values
            # Real pair mirrored about zero: x = ±a
            if second == -first and getattr(first, "is_real", False):
                return f"{var_name} = \\pm {_tex(sp.Abs(first))}"

            # Complex conjugate pair: x = a ± bi, which is how the answer is
            # written by hand. Listing "1 - 2i" and "1 + 2i" separately is
            # correct but reads like two unrelated roots.
            if (getattr(first, "is_complex", False)
                    and sp.simplify(second - sp.conjugate(first)) == 0
                    and sp.simplify(sp.im(first)) != 0):
                # \pm already carries both signs, so only the magnitudes are
                # printed: "± -i" and "1 ± -2i" were the result of adding the
                # sign twice.
                real = sp.re(first)
                imaginary = sp.Abs(sp.im(first))
                prefix = f"{_tex(real)} " if real != 0 else ""
                return f"{var_name} = {prefix}\\pm {_imaginary_tex(imaginary)}"
        # General complex set: group conjugates into "±a ± bi" lines.
        lines = _complex_pairs_latex(values, var_name)
        if lines:
            return " \\;\\text{or}\\; ".join(lines)

        joined = ",\\quad ".join(
            f"{var_name}_{{{i}}} = {_tex(v)}" for i, v in enumerate(values[:8], 1))
        return joined

    if isinstance(solution, sp.Interval):
        left = "-\\infty" if solution.left is -sp.oo else _tex(solution.left)
        right = "+\\infty" if solution.right is sp.oo else _tex(solution.right)
        lb = "(" if solution.left_open else "["
        rb = ")" if solution.right_open else "]"
        return f"{var_name} \\in \\left{lb}{left};\\; {right}\\right{rb}"

    if isinstance(solution, sp.Union):
        if all(isinstance(part, sp.Interval) for part in solution.args):
            bodies = [_format_set_latex(part, var_name).split(" \\in ", 1)[-1] for part in solution.args]
            return f"{var_name} \\in " + " \\cup ".join(bodies)
        parts = [_format_set_latex(part, var_name) for part in solution.args]
        # A union of arithmetic progressions reads better one per line than
        # as a single \cup chain a metre long
        if all("k \\in \\mathbb{Z}" in part for part in parts):
            return " \\;\\text{or}\\; ".join(parts)
        return " \\cup ".join(parts)

    if isinstance(solution, sp.Intersection):
        finite = next((a for a in solution.args if isinstance(a, sp.FiniteSet)), None)
        return _format_set_latex(finite, var_name) if finite is not None else sp.latex(solution)

    if isinstance(solution, sp.ImageSet):
        return _periodic_latex(solution, var_name)

    try:
        return sp.latex(solution)
    except (ValueError, TypeError):
        return str(solution)


def _format_set(solution, var_name: str) -> str:
    """Render the result of ``solveset`` in readable mathematical notation."""
    if solution is sp.S.Reals:
        return f"{var_name} \u2208 \u211d"
    if solution is sp.S.EmptySet:
        return "ExprError.no_solution"
    if solution is sp.S.Complexes:
        return f"{var_name} \u2208 \u2102"

    if isinstance(solution, sp.FiniteSet):
        values = sorted(solution.args, key=lambda v: float(sp.re(v) or 0))
        if not values:
            return "ExprError.no_solution"
        if len(values) == 1:
            return f"{var_name} = {pretty_number(values[0])}"
        if len(values) == 2:
            first, second = values
            if second == -first and getattr(first, "is_real", False):
                return f"{var_name} = \u00b1{pretty_number(sp.Abs(first))}"
        lines = [
            f"{var_name}{str(i).translate(_SUBSCRIPT)} = {pretty_number(v)}"
            for i, v in enumerate(values[:8], 1)
        ]
        return "\n".join(lines)

    if isinstance(solution, sp.Interval):
        left = "-\u221e" if solution.left is -sp.oo else pretty_number(solution.left)
        right = "+\u221e" if solution.right is sp.oo else pretty_number(solution.right)
        lb = "(" if solution.left_open else "["
        rb = ")" if solution.right_open else "]"
        return f"{var_name} \u2208 {lb}{left}; {right}{rb}"

    if isinstance(solution, sp.Union):
        if all(isinstance(part, sp.Interval) for part in solution.args):
            bodies = [_format_set(part, var_name).split(" \u2208 ", 1)[-1] for part in solution.args]
            return f"{var_name} \u2208 " + " \u222a ".join(bodies)
        return "\n".join(_format_set(part, var_name) for part in solution.args)

    if isinstance(solution, sp.Intersection):
        finite = next((a for a in solution.args if isinstance(a, sp.FiniteSet)), None)
        return _format_set(finite, var_name) if finite is not None else str(solution)

    if isinstance(solution, sp.ImageSet):
        return f"{var_name} = {_periodic(solution)}, k \u2208 \u2124"

    return clean(str(solution))


def _periodic(image_set) -> str:
    """Convert ``ImageSet`` into ``2\u03c0k`` style notation."""
    from .analysis import clean_expr

    try:
        lam = image_set.args[0]
        variables = lam.variables
        dummy = variables[0] if variables else lam.args[0]
        expr = lam.expr if hasattr(lam, "expr") else lam.args[1]
        k = sp.Symbol("k", integer=True)

        text = str(sp.expand(expr.subs(dummy, k)))
        text = text.replace("pi", "\u03c0").replace("**", "^")
        text = re.sub(r"\s*\*\s*", "", text)

        if "+" in text and "k" in text and "\u03c0" in text:
            terms = [t.strip() for t in text.split("+")]
            const = next((t for t in terms if "k" not in t), None)
            coeff = next((t for t in terms if "k" in t), None)
            if const and coeff:
                text = f"{const} + {coeff}"
        return text
    except (AttributeError, IndexError, TypeError):
        return str(image_set)


def evaluate(text: str, matrices: dict | None = None) -> dict:
    """Compute a numeric, symbolic or matrix expression."""
    try:
        result = parse(text, matrices=matrices)
    except ExprError as exc:
        return err(str(exc))

    try:
        if isinstance(result, sp.MatrixBase):
            return ok(_format_matrix(result))

        # Matrix helpers such as rank() return a plain Python int
        if isinstance(result, bool) or isinstance(result, int):
            return ok_value(sp.Integer(int(result)))
        if isinstance(result, float):
            return ok_value(sp.Rational(str(result)).limit_denominator(10 ** 9))

        # A stray comma parses as a Python tuple, and comparing an unknown name
        # yields a relational object. Neither is a value: report it instead of
        # letting the attribute access below raise AttributeError.
        if isinstance(result, (tuple, list, set, frozenset)):
            raise ExprError("ExprError.comma_outside_call")
        if isinstance(result, sp.logic.boolalg.Boolean) or isinstance(result, sp.Rel):
            return ok(sp.latex(result) and str(result).replace("**", "^"))
        if not isinstance(result, sp.Basic):
            raise ExprError(f"ExprError.generic")

        if result is sp.nan or result is sp.zoo:
            return err("ExprError.div_zero")
        if result.has(sp.oo) and not result.is_number:
            return err("ExprError.infinite")

        simplified = sp.simplify(result)
        return ok_value(simplified)
    except ExprError as exc:
        return err(str(exc))
    except (ZeroDivisionError, ValueError, TypeError):
        return err("ExprError.div_zero")


def _format_matrix(matrix: sp.MatrixBase) -> str:
    """Column-aligned matrix text, as written by hand."""
    if matrix.rows == 0:
        return "(empty)"
    cells = [
        [pretty_number(sp.nsimplify(matrix[i, j])) for j in range(matrix.cols)]
        for i in range(matrix.rows)
    ]
    widths = [max(len(cells[i][j]) for i in range(matrix.rows)) for j in range(matrix.cols)]
    return "\n".join(
        "  ".join(cells[i][j].rjust(widths[j]) for j in range(matrix.cols))
        for i in range(matrix.rows)
    )


def _trig_substitution_solution(expression, var_name: str):
    """Solve ``a*sin^n(x) + … = 0`` by solving for the inner function first.

    ``sin^2(x) - 5sin(x) + 6 = 0`` becomes ``t^2 - 5t + 6 = 0`` with ``t = sin(x)``.
    SymPy's ``solveset`` returns a ``ConditionSet`` for many of these, which used
    to surface as "cannot parse the expression". A root outside [-1; 1] means no
    real solution, not ``asin(2)``.
    """
    inner = sorted(expression.atoms(sp.sin, sp.cos), key=str)
    if len(inner) != 1:
        return None
    function = inner[0]
    symbol = sp.Dummy("t", real=True)
    try:
        polynomial = sp.Poly(sp.expand(expression.subs(function, symbol)), symbol)
    except (sp.PolynomialError, ValueError):
        return None
    if polynomial.degree() < 1:
        return None

    values = [root for root in sp.roots(polynomial, symbol) if root.is_real]
    if not values:
        return None

    x = sp.Symbol(var_name, real=True)
    solved = sp.EmptySet
    for value in values:
        if not (-1 <= value <= 1):
            continue
        solved = sp.Union(solved, sp.solveset(sp.Eq(function, value), x, domain=sp.S.Reals))
    return solved


def solve_equation(text: str, matrices: dict | None = None) -> dict:
    """Solve an equation or inequality with respect to its primary variable."""
    parts = _split_relation(text)
    if parts is None:
        return evaluate(text, matrices)

    left, op, right = parts
    var_name = detect_variable(text)
    var = sp.Symbol(var_name, real=True)

    try:
        lhs = parse(left, var_name, matrices)
        rhs = parse(right, var_name, matrices)
    except ExprError as exc:
        return err(str(exc))

    if isinstance(lhs, sp.MatrixBase) or isinstance(rhs, sp.MatrixBase):
        return err("ExprError.matrix_in_equation")

    try:
        relation = _relation(lhs, op, rhs)

        if op in ("<", ">", "<=", ">="):
            solution = sp.solve_univariate_inequality(relation, var, relational=False)
            return ok(_format_set(solution, var_name), _format_set_latex(solution, var_name))

        try:
            solution = sp.solveset(relation, var, domain=sp.S.Reals)
        except (sp.PolynomialError, ValueError, TypeError, NotImplementedError):
            solution = sp.ConditionSet(var, relation, sp.S.Reals)
        note = None

        if isinstance(solution, sp.ConditionSet) or solution is sp.S.EmptySet:
            substituted = _trig_substitution_solution(sp.expand(lhs - rhs), var_name)
            if substituted is not None:
                solution = substituted
                if substituted is sp.S.EmptySet:
                    return err("ExprError.no_solution")

        if isinstance(solution, sp.ConditionSet) or solution is sp.S.EmptySet:
            # Nothing real. Complex roots still exist for things like x^2+1=0,
            # but a student looking at sin(x)=2 needs to be told the answer is
            # "no real solutions", not handed asin(2) as if it were a number.
            try:
                complex_solution = sp.solveset(relation, var, domain=sp.S.Complexes)
            except (sp.PolynomialError, ValueError, TypeError, NotImplementedError):
                complex_solution = sp.ConditionSet(var, relation, sp.S.Complexes)
            if (not isinstance(complex_solution, sp.ConditionSet)
                    and complex_solution is not sp.S.EmptySet):
                solution = complex_solution
                note = "solution.complex"

        # An empty set is a real answer ("no real solutions"), but it must not
        # arrive as ok=True with the text "ExprError.no_solution": the interface
        # then prints the raw key instead of a message.
        # ``is`` only: sp.EmptySet is an instance, so isinstance() raises
        # TypeError and every equation would report not_solvable.
        if solution is sp.S.EmptySet:
            return err("ExprError.no_solution")

        return ok(_format_set(solution, var_name),
                  _format_set_latex(solution, var_name),
                  note=note)
    except ZeroDivisionError:
        return err("ExprError.div_zero")
    except (ValueError, TypeError, NotImplementedError):
        return err("ExprError.not_solvable")


def _system_symbols(equations: list[str]) -> tuple:
    """Variables mentioned in the system, in a stable order."""
    names: list[str] = []
    for equation in equations:
        for name in re.findall(r"[a-z]", equation):
            if name not in names:
                names.append(name)
    names = [n for n in names if n in SYSTEM_VARIABLES][:5] or ["x", "y"]

    symbols = sp.symbols(" ".join(sorted(names)), real=True)
    if not isinstance(symbols, tuple):
        symbols = (symbols,)
    return symbols


def _parse_system(equations: list[str], symbols: tuple, matrices):
    """Turn each equation into the expression ``left - right``.

    Returns ``(expressions, relations, error)``.
    """
    expressions: list = []
    relations: list = []
    primary = symbols[0].name if symbols else "x"

    for equation in equations:
        parts = _split_relation(equation)
        if parts is None:
            return [], [], "ExprError.need_relation"
        left, op, right = parts
        if op != "=":
            return [], [], "ExprError.need_relation"

        try:
            lhs = parse(left, primary, matrices)
            rhs = parse(right, primary, matrices)
        except ExprError as exc:
            return [], [], str(exc)

        if isinstance(lhs, sp.MatrixBase) or isinstance(rhs, sp.MatrixBase):
            return [], [], "ExprError.matrix_in_equation"

        expression = sp.expand(lhs - rhs)
        expressions.append(expression)
        relations.append(sp.Eq(lhs, rhs))

    return expressions, relations, None


def _is_linear_system(expressions: list, symbols: tuple) -> bool:
    """True when every equation is at most first degree in every variable.

    A product such as ``x*y`` makes the system nonlinear even though each
    variable appears to the first power alone, so the check uses the total
    degree of the multivariate polynomial rather than per-variable degrees.
    """
    for expression in expressions:
        try:
            poly = sp.Poly(expression, *symbols)
        except (sp.PolynomialError, TypeError, ValueError, GeneratorsNeeded):
            return False
        try:
            if poly.total_degree() > 1:
                return False
        except (TypeError, ValueError):
            return False
    return True


def _format_solutions(solutions: list[dict], symbols: tuple) -> tuple[str, str]:
    """Plain text and LaTeX for one or more solution tuples."""
    plain_lines: list[str] = []
    tex_lines: list[str] = []

    for solution in solutions:
        plain_parts, tex_parts = [], []
        for symbol in symbols:
            value = solution.get(symbol)
            if value is None:
                continue
            plain_parts.append(f"{symbol.name} = {pretty_number(value)}")
            tex_parts.append(f"{symbol.name} = {_tex(value)}")
        if plain_parts:
            plain_lines.append(";  ".join(plain_parts))
            tex_lines.append(",\\quad ".join(tex_parts))

    return "\n".join(plain_lines), " \\;\\text{or}\\; ".join(tex_lines)


def _dedupe(solutions: list[dict], symbols: tuple) -> list[dict]:
    """Drop duplicates ``sp.solve`` can emit for equivalent branches."""
    seen: set = set()
    unique: list[dict] = []

    for solution in solutions:
        key = tuple(str(sp.simplify(solution.get(s))) for s in symbols)
        if key in seen:
            continue
        seen.add(key)
        unique.append(solution)

    return unique


def solve_system(equations: list[str], matrices: dict | None = None) -> dict:
    """Solve a system of equations, linear or not.

    Two strategies, chosen from the shape of the system:

    **Linear** (every equation at most first degree) — build ``[A | b]`` and
    take its reduced row echelon form. This makes the three possible outcomes
    explicit: one solution, free variables, or inconsistency, and it matches the
    step-by-step walkthrough, which renders the same matrices.

    **Nonlinear** — hand the relations to SymPy's solver, which handles
    substitution, elimination and trigonometric systems, then format every
    branch. Solutions are deduplicated and capped: a system such as
    ``x*y = 6, x + y = 5`` has two pairs, and both are answers.
    """
    if len(equations) < 2:
        return err("ExprError.need_two_equations")

    symbols = _system_symbols(equations)
    expressions, relations, problem = _parse_system(equations, symbols, matrices)
    if problem:
        return err(problem)

    # ------------------------------------------------------------------ linear
    if _is_linear_system(expressions, symbols):
        rows: list[list] = []
        for expression in expressions:
            row = [sp.simplify(expression.coeff(symbol)) for symbol in symbols]
            row.append(sp.simplify(-expression.subs({symbol: 0 for symbol in symbols})))
            rows.append(row)

        try:
            augmented = sp.Matrix(rows)
            reduced, pivots = augmented.rref()
            rank_all = len(pivots)
            rank_coefficient = augmented[:, :-1].rank()
        except (ValueError, TypeError, IndexError):
            return err("ExprError.not_solvable")

        unknown_count = len(symbols)

        if rank_coefficient < rank_all:
            return ok("ExprError.no_solution", "\\varnothing")

        if rank_coefficient == unknown_count:
            values = [sp.simplify(reduced[index, -1]) for index in range(unknown_count)]
            plain = ";  ".join(f"{symbol.name} = {pretty_number(value)}"
                               for symbol, value in zip(symbols, values))
            tex = ",\\quad ".join(f"{symbol.name} = {_tex(value)}"
                                   for symbol, value in zip(symbols, values))
            return ok(plain, tex)

        free_columns = [c for c in range(unknown_count) if c not in pivots]
        plain_parts, tex_parts = [], []

        for row_index, pivot_column in enumerate(pivots):
            if pivot_column >= unknown_count:
                continue
            symbol = symbols[pivot_column]
            expression = sp.simplify(reduced[row_index, -1])
            for column in free_columns:
                coefficient = sp.simplify(reduced[row_index, column])
                if coefficient != 0:
                    expression -= coefficient * symbols[column]
            plain_parts.append(f"{symbol.name} = {pretty_number(expression)}")
            tex_parts.append(f"{symbol.name} = {_tex(expression)}")

        for column in free_columns:
            name = symbols[column].name
            plain_parts.append(f"{name} \u2014 free")
            tex_parts.append(f"{name}\\;\\text{{free}}")

        return ok(";  ".join(plain_parts), ",\\quad ".join(tex_parts))

    # --------------------------------------------------------------- nonlinear
    solutions: list[dict] = []

    try:
        raw = sp.solve(relations, symbols, dict=True)
        solutions = [item for item in raw if isinstance(item, dict)]
    except (ValueError, TypeError, NotImplementedError, AttributeError):
        solutions = []

    if not solutions:
        # nonlinsolve returns plain tuples; map them back onto the symbols
        try:
            tuples = sp.nonlinsolve(relations, symbols)
        except (ValueError, TypeError, NotImplementedError, AttributeError):
            tuples = set()

        mapped: list[dict] = []
        for item in tuples:
            if isinstance(item, dict):
                mapped.append(item)
            elif isinstance(item, (tuple, list)) and len(item) == len(symbols):
                if any(value is sp.S.NaN for value in item):
                    continue
                mapped.append(dict(zip(symbols, item)))
        solutions = mapped

    # A ConditionSet or an unsolved Integral means SymPy gave up
    solutions = [
        item for item in solutions
        if all(not getattr(value, "has", lambda *_: False)(sp.S.NaN)
               and not isinstance(value, sp.ConditionSet)
               for value in item.values())
    ]

    solutions = _dedupe(solutions, symbols)

    if not solutions:
        return ok("ExprError.no_solution", "\\varnothing")

    if len(solutions) > 12:
        return ok(f"ExprError.too_many:{len(solutions)}", None)

    plain, tex = _format_solutions(solutions, symbols)
    if not plain:
        return ok("ExprError.no_solution", "\\varnothing")

    return ok(plain, tex)


def analyze_function(text: str) -> dict:
    """Derivative, integral and extrema of a single-variable function."""
    from .analysis import full_report

    try:
        report = full_report(text)
    except ExprError as exc:
        return err(str(exc))

    lines = [report["function"]]
    for section in report["sections"]:
        lines.append(f"{section['title']}: " + "; ".join(section["lines"]))
    return ok("\n".join(lines))


__all__ = [
    "evaluate", "solve_equation", "solve_system", "analyze_function",
    "pretty_number", "clean", "ok", "err", "_format_set", "_split_relation",
]
