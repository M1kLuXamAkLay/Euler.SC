"""Step-by-step solutions.

Two strategies, tried in order:

1. **Rule-based** for the classes of problem a student meets: linear,
   quadratic, separable and linear first-order ODEs, single integrals,
   derivatives, limits. Each step is produced explicitly, so the output reads
   like a worked example rather than a black box.

2. **SymPy helpers** (``manualintegrate``, ``dsolve`` with ``hint``) when the
   rule table has no entry. Their output is unpacked into numbered steps.

Every function returns ``{"ok": True, "title": ..., "steps": [...]}`` where a
step is ``{"n": int, "text": str, "latex": str}``.
"""
from __future__ import annotations

import re

import sympy as sp

from .parser import ExprError, parse
from .analysis import prepare, num, clean_expr

# Kept in sync with solver.SYSTEM_VARIABLES: both walk the same systems.
SYSTEM_VARIABLES = "xyztuvw"


def pretty_number(value) -> str:
    """Plain rendering shared with the solver, imported lazily to avoid a cycle."""
    from .solver import pretty_number as _pretty
    return _pretty(value)

MAX_STEPS = 40


def _step(index: int, text: str, latex: str | None = None) -> dict:
    return {"n": index, "text": text, "latex": latex or text}


def _tex(value) -> str:
    try:
        return sp.latex(value)
    except (ValueError, TypeError):
        return str(value)


def _msg_line(key: str) -> dict:
    """A step that is a message, not a formula."""
    return {"n": 0, "text": key, "latex": None}


def _result(title: str, steps: list[dict],
            plain: str | None = None, latex: str | None = None) -> dict:
    """A worked solution.

    ``plain`` and ``latex`` carry the final answer separately from the step
    list, so the export and the answer line do not have to guess which step
    happens to be the conclusion.
    """
    payload = {"ok": True, "title": title, "steps": steps[:MAX_STEPS]}
    if plain is not None:
        payload["text"] = plain
    if latex is not None:
        payload["latex"] = latex
    return payload


# --------------------------------------------------------------------- algebra
def _linear(left: sp.Expr, right: sp.Expr, var: sp.Symbol) -> list[dict]:
    """a*x + b = c  ->  isolate x."""
    expr = sp.expand(left - right)
    coeff = sp.simplify(sp.diff(expr, var))
    const = sp.simplify(expr.subs(var, 0))

    steps = [
        _step(1, "step.cap.move_one_side",
              f"{_tex(sp.expand(expr))} = 0"),
        _step(2, "step.cap.coefficient",
              f"a = {_tex(coeff)},\\quad b = {_tex(const)}"),
        _step(3, "step.cap.subtract",
              f"{_tex(coeff)}\\,{var.name} = {_tex(-const)}"),
        _step(4, "step.cap.divide",
              f"{var.name} = {_tex(sp.simplify(-const / coeff))}"),
    ]
    return steps


def _quadratic(left: sp.Expr, right: sp.Expr, var: sp.Symbol) -> list[dict]:
    """a*x^2 + b*x + c = 0 through the discriminant."""
    poly = sp.Poly(sp.expand(left - right), var)
    if poly.degree() != 2:
        return []

    a, b, c = (poly.coeff_monomial(var ** 2), poly.coeff_monomial(var), poly.coeff_monomial(1))
    disc = sp.simplify(b ** 2 - 4 * a * c)

    steps = [
        _step(1, "step.cap.standard_form",
              f"{_tex(a)}\\,{var.name}^2 + {_tex(b)}\\,{var.name} + {_tex(c)} = 0"),
        _step(2, "step.cap.coefficients",
              f"a = {_tex(a)},\\quad b = {_tex(b)},\\quad c = {_tex(c)}"),
        _step(3, "step.cap.discriminant",
              f"D = b^2 - 4ac = {_tex(disc)}"),
    ]

    if disc.is_negative:
        steps.append(_step(4, "step.cap.negative_disc",
                           "D < 0 \\Rightarrow x \\in \\varnothing"))
        return steps

    root = sp.sqrt(disc)
    steps.append(_step(4, "step.cap.formula",
                       f"{var.name} = \\frac{{-b \\pm \\sqrt{{D}}}}{{2a}} "
                       f"= \\frac{{{_tex(-b)} \\pm {_tex(root)}}}{{{_tex(2 * a)}}}"))

    first = sp.simplify((-b + root) / (2 * a))
    second = sp.simplify((-b - root) / (2 * a))
    if first == second:
        steps.append(_step(5, "step.cap.repeated_root", f"{var.name} = {_tex(first)}"))
    else:
        steps.append(_step(5, "step.cap.two_roots",
                           f"{var.name}_1 = {_tex(first)},\\quad {var.name}_2 = {_tex(second)}"))
    return steps


# --------------------------------------------------------------------- calculus
def _derivative_steps(expression: str) -> list[dict]:
    expr, var, name = prepare(expression)
    steps = [_step(1, "step.cap.function", f"f({name}) = {_tex(expr)}")]

    if expr.is_Add:
        terms = expr.args
        steps.append(_step(2, "step.cap.term_by_term",
                           f"f' = {' + '.join(f'({_tex(sp.diff(t, var))})' for t in terms[:6])}"))
    elif isinstance(expr, sp.Mul):
        steps.append(_step(2, "step.cap.product_rule",
                           f"(uv)' = u'v + uv'"))
    elif expr.is_Pow:
        base, power = expr.as_base_exp()
        steps.append(_step(2, "step.cap.power_rule",
                           f"\\frac{{d}}{{d{name}}} {_tex(base)}^{{{_tex(power)}}} "
                           f"= {_tex(power)}\\,{_tex(base)}^{{{_tex(power - 1)}}}"))
    elif expr.has(sp.sin) or expr.has(sp.cos):
        steps.append(_step(2, "step.cap.trig_rule",
                           f"\\frac{{d}}{{d{name}}}\\sin({name}) = \\cos({name})"))

    result = sp.simplify(sp.diff(expr, var))
    steps.append(_step(3, "step.cap.simplified", f"f'({name}) = {_tex(result)}"))

    second = sp.simplify(sp.diff(expr, var, 2))
    if second != 0:
        steps.append(_step(4, "step.cap.second_derivative", f"f''({name}) = {_tex(second)}"))
    return steps


def _integral_steps(expression: str) -> list[dict]:
    expr, var, name = prepare(expression)
    steps = [_step(1, "step.cap.integrand", f"\\int {_tex(expr)}\\,d{name}")]

    try:
        parts = sp.integrate(expr, var, meijerg=False, risch=False)
        steps.append(_step(2, "step.cap.basic_rule", f"\\int {_tex(expr)}\\,d{name} = {_tex(parts)} + C"))
    except (ValueError, TypeError, NotImplementedError):
        parts = None

    # manualintegrate shows which substitution was used
    try:
        from sympy.integrals.manualintegrate import manualintegrate

        manual = manualintegrate(expr, var)
        steps.append(_step(3, "step.cap.verified",
                           f"F({name}) = {_tex(manual)} + C"))
    except Exception:                        # noqa: BLE001 - helper is best effort
        pass

    result = sp.integrate(expr, var)
    steps.append(_step(len(steps) + 1, "step.cap.final", f"\\int {_tex(expr)}\\,d{name} = {_tex(result)} + C"))
    return steps


def _limit_steps(expression: str, point: str) -> list[dict]:
    expr, var, name = prepare(expression)
    target = parse(point, name)

    steps = [_step(1, "step.cap.limit",
                   f"\\lim_{{{name} \\to {_tex(target)}}} {_tex(expr)}")]

    direct = expr.subs(var, target)
    if direct not in (sp.zoo, sp.nan) and direct.is_finite is not False:
        steps.append(_step(2, "step.cap.substitute", f"f({_tex(target)}) = {_tex(direct)}"))
        steps.append(_step(3, "step.cap.no_indeterminacy", f"= {_tex(direct)}"))
        return steps

    steps.append(_step(2, "step.cap.indeterminate",
                       "\\frac{0}{0}\\ \\text{or}\\ \\frac{\\infty}{\\infty}"))

    try:
        simplified = sp.simplify(expr)
        if simplified != expr:
            steps.append(_step(3, "step.cap.simplify_first", f"{_tex(simplified)}"))
    except (ValueError, TypeError):
        pass

    try:
        series = sp.series(expr, var, target, 3).removeO()
        steps.append(_step(4, "step.cap.series", f"{_tex(series)}"))
    except (ValueError, TypeError, NotImplementedError):
        pass

    value = sp.limit(expr, var, target)
    steps.append(_step(5, "step.cap.evaluate_limit", f"= {_tex(value)}"))
    return steps


# --------------------------------------------------------------------- dispatch
def _exponential_steps(left, right, var) -> list[dict]:
    """a^x = b: take a logarithm of both sides."""
    steps = [_step(1, "step.cap.equation", f"{_tex(left)} = {_tex(right)}")]

    base = None
    for side, other in ((left, right), (right, left)):
        if isinstance(side, sp.Pow) and side.exp == var and side.base.is_positive:
            base, other = side.base, other
            break

    if base is None:
        return []

    steps.append(_step(2, "The unknown is in the exponent: take the logarithm "
                          "of both sides", f"\\ln\\left({_tex(base)}^{{{var.name}}}\\right) = \\ln\\left({_tex(other)}\\right)"))
    steps.append(_step(3, "step.cap.bring_down",
                       f"{var.name}\\,\\ln\\left({_tex(base)}\\right) = \\ln\\left({_tex(other)}\\right)"))
    value = sp.simplify(sp.log(other) / sp.log(base))
    steps.append(_step(4, "step.cap.divide_log",
                       f"{var.name} = \\frac{{\\ln\\left({_tex(other)}\\right)}}{{\\ln\\left({_tex(base)}\\right)}} = {_tex(value)}"))
    return steps


def _substitution_steps(left, right, var) -> list[dict]:
    """Recognise a quadratic in a function: sin^2 x - 5 sin x + 6 = 0."""
    expression = sp.expand(left - right)

    # find a repeated non-polynomial subexpression
    try:
        candidates = [a for a in expression.atoms(sp.Function) + expression.atoms(sp.Pow)
                      if getattr(a, "has", lambda *_: False)(var)]
    except (AttributeError, TypeError):
        return []
    # Prefer the simplest encapsulating expression: sin(x)^2 must not be tried
    # before sin(x), and a Pow whose base is itself a candidate is skipped.
    candidates.sort(key=lambda a: len(str(a)))

    for candidate in candidates:
        if candidate == var or not candidate.has(var):
            continue
        if isinstance(candidate, sp.Pow) and candidate.base.has(var):
            continue
        try:
            polynomial = sp.Poly(expression, candidate)
        except Exception:                       # noqa: BLE001 - not a polynomial
            continue
        if polynomial.degree() != 2:
            continue

        a = polynomial.coeff_monomial(candidate ** 2)
        b = polynomial.coeff_monomial(candidate)
        c = polynomial.coeff_monomial(1)
        disc = sp.simplify(b ** 2 - 4 * a * c)

        steps = [
            _step(1, "step.cap.substitute_var", f"t = {_tex(candidate)}"),
            _step(2, "step.cap.rewrite",
                  f"{_tex(a)}\\,t^2 + {_tex(b)}\\,t + {_tex(c)} = 0"),
            _step(3, "step.cap.discriminant", f"D = b^2 - 4ac = {_tex(disc)}"),
        ]
        if disc.is_negative:
            steps.append(_step(4, "Discriminant is negative: no real t", "D < 0"))
            return steps

        root = sp.sqrt(disc)
        t1 = sp.simplify((-b + root) / (2 * a))
        t2 = sp.simplify((-b - root) / (2 * a))
        steps.append(_step(4, "step.cap.solve_t",
                           f"t_1 = {_tex(t1)},\\quad t_2 = {_tex(t2)}"))

        for index, (value, label) in enumerate(((t1, "t_1"), (t2, "t_2")), start=5):
            if not (-1 <= float(sp.N(value)) <= 1):
                steps.append(_step(index, f"{label} = {_tex(value)} is outside [-1; 1]",
                                   f"{_tex(candidate)} = {_tex(value)}\\;\\text{{no real solutions}}"))
                continue
            solutions = sp.solve(sp.Eq(candidate, value), var)
            if solutions:
                joined = ",\\quad ".join(f"{var.name} = {_tex(r)}" for r in solutions[:2])
                steps.append(_step(index, f"Back-substitute {label}",
                                   f"{_tex(candidate)} = {_tex(value)} \\Rightarrow {joined}"))
        steps.append(_step(len(steps) + 1, "step.cap.period",
                           f"+ 2\\pi k,\\; k \\in \\mathbb{{Z}}"))
        return steps
    return []


def _row_operation_latex(row_from: int, row_to: int, op: str, factor, matrix) -> str:
    """Caption for one elementary row operation, as LaTeX."""
    r1 = f"R_{{{row_to + 1}}}"
    r2 = f"R_{{{row_from + 1}}}"
    if op == "swap":
        return f"{r1} \\leftrightarrow {r2}"
    if op == "scale":
        return f"{r1} \\to {_tex(factor)}\\,{r1}"
    # add a multiple of another row
    sign = "+" if factor >= 0 else "-"
    mag = _tex(abs(factor)) if abs(factor) != 1 else ""
    return f"{r1} \\to {r1} {sign} {mag}{r2}".replace("  ", " ")


def _gauss_jordan(matrix: sp.Matrix, steps: list, start_index: int):
    """Full Gauss-Jordan elimination, recording every elementary operation.

    Each pivot is normalised to 1 and every other entry of its column is
    cleared, so the result is the reduced row echelon form itself, not an
    intermediate triangular form. Returns the reduced matrix and pivot columns.
    """
    m = matrix.copy()
    rows, cols = m.shape
    pivots: list[int] = []
    pivot_row = 0
    counter = start_index

    # Every column, including the constant one: a pivot there means 0 = c, c != 0
    for col in range(cols):
        if pivot_row >= rows:
            break

        # choose a non-zero pivot; swap it up if needed
        candidates = [r for r in range(pivot_row, rows) if m[r, col] != 0]
        if not candidates:
            continue
        chosen = candidates[0]
        if chosen != pivot_row:
            m.row_swap(pivot_row, chosen)
            counter += 1
            steps.append(_step(counter, "step.cap.row_swap",
                               f"{_row_operation_latex(chosen, pivot_row, 'swap', 0, m)}"
                               f"\\quad{_tex_matrix(m)}"))

        # normalise the pivot to 1
        pivot = sp.simplify(m[pivot_row, col])
        if pivot != 1:
            m.row_op(pivot_row, lambda value, _j, p=pivot: sp.simplify(value / p))
            counter += 1
            # 1/(-2) reads as -1/2 in a textbook, so the sign goes in front
            reciprocal = sp.simplify(1 / pivot)
            steps.append(_step(counter, "step.cap.normalise",
                               f"R_{{{pivot_row + 1}}} \\to {_tex(reciprocal)}\\,R_{{{pivot_row + 1}}}"
                               f"\\quad{_tex_matrix(m)}"))

        # clear the column everywhere else (above and below)
        for other in range(rows):
            if other == pivot_row or m[other, col] == 0:
                continue
            factor = sp.simplify(m[other, col])
            m.zip_row_op(other, pivot_row, lambda a, b, f=factor: sp.simplify(a - f * b))
            counter += 1
            sign = "-" if factor > 0 else "+"
            magnitude = _tex(abs(factor)) if abs(factor) != 1 else ""
            steps.append(_step(counter, "step.cap.eliminate",
                               f"R_{{{other + 1}}} \\to R_{{{other + 1}}} {sign} {magnitude}"
                               f"R_{{{pivot_row + 1}}}\\quad{_tex_matrix(m)}"))

        pivots.append(col)
        pivot_row += 1

    return m, pivots, counter


def _tex_matrix(m: sp.Matrix) -> str:
    """Compact matrix for an inline step caption."""
    return sp.latex(m)


def _expr_latex(expression) -> str:
    return _tex(expression)


def _solve_for(equation, target, symbols):
    """Solve one equation for a variable as a plain expression, or None.

    Returns ``(other_symbol, expression)`` for the first variable that can be
    isolated cleanly. Only equations that are linear in that variable qualify:
    solving ``x^2 + y = 3`` for ``y`` is fine, for ``x`` it produces a root.
    """
    for variable in symbols:
        if variable == target:
            continue
        try:
            solutions = sp.solve(sp.Eq(equation.lhs, equation.rhs), variable)
        except (ValueError, TypeError, NotImplementedError):
            continue
        if len(solutions) != 1:
            continue
        candidate = sp.simplify(solutions[0])
        # must not still contain the variable it was solved for
        if candidate.has(variable):
            continue
        return variable, candidate
    return None, None


def _nonlinear_system_steps(expressions: list, relations: list, symbols: tuple) -> dict:
    """Solve a nonlinear system by substitution, showing each move.

    The walkthrough follows the method a student is taught:

    1. isolate one variable from the simpler equation;
    2. substitute it into the other equation, which becomes one equation in
       one unknown;
    3. solve that equation;
    4. back-substitute each root to recover the paired values.
    """
    steps: list[dict] = []
    counter = 0

    def add(text: str, latex: str | None) -> None:
        nonlocal counter
        counter += 1
        steps.append(_step(counter, text, latex))

    add("step.cap.system_given",
        "\\begin{cases}" + " \\\\ ".join(
            f"{_expr_latex(sp.Eq(rel.lhs, rel.rhs))}" for rel in relations
        ) + " \\end{cases}")

    # Pick the equation that solves cleanly for one variable
    chosen_relation = None
    isolated_variable = None
    isolated_expression = None
    for relation in relations:
        variable, expression = _solve_for(relation, None, symbols)
        if expression is not None:
            chosen_relation = relation
            isolated_variable = variable
            isolated_expression = expression
            break

    if isolated_expression is None:
        # No clean isolation: fall back to stating the answer
        add("step.cap.no_substitution", None)
        return _result("step.title.system_nonlinear", steps, latex=None)

    add("step.cap.isolate",
        f"{isolated_variable.name} = {_expr_latex(isolated_expression)}")

    # Substitute into the remaining equation(s)
    remaining = [rel for rel in relations if rel is not chosen_relation]
    if not remaining:
        return _result("step.title.system_nonlinear", steps, latex=None)

    target = remaining[0]
    substituted = sp.simplify(
        target.lhs.subs(isolated_variable, isolated_expression)
        - target.rhs.subs(isolated_variable, isolated_expression)
    )
    free = [symbol for symbol in symbols if symbol != isolated_variable]
    free_symbol = free[0] if free else symbols[0]

    add("step.cap.substitute_into",
        f"{_expr_latex(sp.Eq(substituted, 0))}")

    # Solve the resulting one-variable equation
    reduced_equation = sp.Eq(substituted, 0)
    try:
        roots = sp.solve(reduced_equation, free_symbol)
    except (ValueError, TypeError, NotImplementedError):
        roots = []

    roots = [sp.simplify(root) for root in roots
             if not isinstance(root, sp.ConditionSet)]

    if not roots:
        add("step.cap.no_roots", None)
        return _result("step.title.system_nonlinear", steps,
                       plain="ExprError.no_solution", latex="\\\\varnothing")

    if len(roots) == 1:
        add("step.cap.one_root", f"{free_symbol.name} = {_tex(roots[0])}")
    else:
        add("step.cap.roots_found",
            ",\\\\quad ".join(f"{free_symbol.name}_{{{i}}} = {_tex(root)}"
                             for i, root in enumerate(roots[:8], 1)))

    # Back-substitute to recover the paired values
    pairs_plain: list[str] = []
    pairs_tex: list[str] = []

    for root in roots[:8]:
        paired = sp.simplify(isolated_expression.subs(free_symbol, root))
        values = {free_symbol: root, isolated_variable: paired}
        ordered_plain = []
        ordered_tex = []
        for symbol in symbols:
            value = values.get(symbol)
            if value is None:
                continue
            ordered_plain.append(f"{symbol.name} = {pretty_number(value)}")
            ordered_tex.append(f"{symbol.name} = {_tex(value)}")
        pairs_plain.append(";  ".join(ordered_plain))
        pairs_tex.append(",\\\\quad ".join(ordered_tex))

    add("step.cap.back_substitute", " \\\\;\\\\text{or}\\\\; ".join(pairs_tex))

    return _result("step.title.system_nonlinear", steps,
                   plain="\n".join(pairs_plain),
                   latex=" \\\\;\\\\text{or}\\\\; ".join(pairs_tex))


def _system_is_linear(expressions: list, symbols: tuple) -> bool:
    for expression in expressions:
        try:
            poly = sp.Poly(expression, *symbols)
            if poly.total_degree() > 1:
                return False
        except Exception:                       # noqa: BLE001 - not polynomial
            return False
    return True


def _system_steps(equations: list[str]) -> dict:
    """Solve a linear system by full Gauss-Jordan elimination.

    Every elementary row operation is shown as its own step. The final matrix
    is the reduced row echelon form; the answer is read from it, so the last
    line and the last matrix can never disagree.

    Outcomes:
      * rank A = rank [A|b] = number of unknowns  -> one solution;
      * rank A = rank [A|b] < number of unknowns  -> free variables;
      * rank A < rank [A|b]                        -> no solution.
    """
    names: list[str] = []
    for equation in equations:
        for name in re.findall(r"[a-z]", equation):
            if name not in names:
                names.append(name)
    names = [n for n in names if n in SYSTEM_VARIABLES][:5] or ["x", "y"]
    symbols = sp.symbols(" ".join(sorted(names)), real=True)
    if not isinstance(symbols, tuple):
        symbols = (symbols,)

    # Split into expressions first: a nonlinear system must not reach the
    # matrix path, where x*y would silently become a linear coefficient.
    parsed_relations = []
    parsed_expressions = []
    for equation in equations:
        parts = _split_relation(equation)
        if parts is None:
            continue
        left, _op, right = parts
        try:
            lhs = parse(left, "x")
            rhs = parse(right, "x")
        except ExprError as exc:
            return _result("step.title.system", [_msg_line(str(exc))])
        parsed_relations.append(sp.Eq(lhs, rhs))
        parsed_expressions.append(sp.expand(lhs - rhs))

    if parsed_expressions and not _system_is_linear(parsed_expressions, symbols):
        return _nonlinear_system_steps(parsed_expressions, parsed_relations, symbols)

    rows: list[list] = []
    for equation in equations:
        parts = _split_relation(equation)
        if parts is None:
            continue
        left, _op, right = parts
        try:
            lhs = parse(left, "x")
            rhs = parse(right, "x")
        except ExprError as exc:
            return _result("step.title.system", [_msg_line(str(exc))])

        expression = sp.expand(lhs - rhs)
        row = [sp.simplify(expression.coeff(symbol)) for symbol in symbols]
        constant = sp.simplify(expression.subs({s: 0 for s in symbols}))
        row.append(sp.simplify(-constant))
        rows.append(row)

    if not rows:
        return _result("step.title.system", [_msg_line("ExprError.need_relation")])

    augmented = sp.Matrix(rows)
    coefficient = augmented[:, :-1]
    unknown_count = len(symbols)

    steps = [_step(1, "step.cap.system_matrix", sp.latex(augmented))]
    reduced, pivots, counter = _gauss_jordan(augmented, steps, 1)

    # Rows that vanished entirely: their equation was a multiple of another
    zero_rows = [r for r in range(reduced.shape[0])
                 if all(reduced[r, c] == 0 for c in range(reduced.shape[1]))]
    if zero_rows:
        counter += 1
        steps.append(_step(counter, "step.cap.redundant",
                           f"R_{{{zero_rows[0] + 1}}} = 0"))

    rank_all = len(pivots)
    rank_coefficient = sum(1 for p in pivots if p < unknown_count)

    # Inconsistent: a pivot in the constant column means 0 = c with c != 0
    if augmented.shape[1] - 1 in pivots:
        steps.append(_step(counter + 1, "step.cap.inconsistent",
                           f"\\operatorname{{rank}} A = {rank_coefficient} < "
                           f"{rank_all} = \\operatorname{{rank}}[A|b] \\Rightarrow \\varnothing"))
        return _result("step.title.system", steps,
                       plain="ExprError.no_solution", latex="\\varnothing")

    # Read the answer from the reduced matrix
    assignments: list[str] = []
    plain_parts: list[str] = []
    free_columns = [c for c in range(unknown_count) if c not in pivots]

    for row_index, pivot_column in enumerate(pivots):
        symbol = symbols[pivot_column]
        expression = sp.simplify(reduced[row_index, -1])
        for column in free_columns:
            coefficient_value = sp.simplify(reduced[row_index, column])
            if coefficient_value != 0:
                expression = sp.simplify(expression - coefficient_value * symbols[column])
        assignments.append(f"{symbol.name} = {_tex(expression)}")
        plain_parts.append(f"{symbol.name} = {pretty_number(expression)}")

    for column in free_columns:
        assignments.append(f"{symbols[column].name}\\;\\text{{free}}")
        plain_parts.append(f"{symbols[column].name} \u2014 free")

    kind = "step.cap.unique_solution" if not free_columns else "step.cap.free_variables"
    joined = ",\\quad ".join(assignments)
    steps.append(_step(counter + 1, kind, joined))

    return _result("step.title.system", steps,
                   plain=";  ".join(plain_parts), latex=joined)



def _split_relation(text: str):
    """Split ``left = right`` on the first relation symbol."""
    for op in ("<=", ">=", "!=", "<", ">", "="):
        if op in text:
            left, right = text.split(op, 1)
            return left.strip(), op, right.strip()
    return None



def steps(expression: str, kind: str = "auto", extra: list[str] | None = None) -> dict:
    """Produce a worked solution for the given expression."""
    if not expression or not expression.strip():
        raise ExprError("ExprError.empty")

    text = expression.strip()

    if kind == "derivative":
        return _result("step.title.derivative", _derivative_steps(text))
    if kind == "integral":
        return _result("step.title.integral", _integral_steps(text))
    if kind == "limit":
        return _result("step.title.limit", _limit_steps(text, "0"))
    if kind == "system" and extra:
        return _system_steps([text, *extra])

    if "=" in text:
        left, right = text.split("=", 1)
        name = "x"
        lhs = parse(left, name)
        rhs = parse(right, name)
        var = sp.Symbol(name, real=True)

        # Exponential: the unknown sits in an exponent
        try:
            exponential = _exponential_steps(lhs, rhs, var)
        except Exception:                       # noqa: BLE001 - optional path
            exponential = []
        if exponential:
            return _result("step.title.exponential", exponential)

        # Quadratic in a function (trigonometric, logarithmic, radical)
        try:
            substituted = _substitution_steps(lhs, rhs, var)
        except Exception:                       # noqa: BLE001 - optional path
            substituted = []
        if substituted:
            return _result("step.title.substitution", substituted)

        try:
            degree = sp.degree(sp.Poly(sp.expand(lhs - rhs), var))
        except Exception:                       # noqa: BLE001 - not a polynomial
            degree = None

        if degree == 1:
            return _result("step.title.linear", _linear(lhs, rhs, var))
        if degree == 2:
            return _result("step.title.quadratic", _quadratic(lhs, rhs, var))

        roots = sp.solve(sp.Eq(lhs, rhs), var)
        return _result("step.title.equation", [
            _step(1, "step.cap.move_one_side", f"{_tex(sp.expand(lhs - rhs))} = 0"),
            _step(2, "Solve for the variable",
                  ",\\quad ".join(f"{var.name} = {_tex(r)}" for r in roots[:6])),
        ])

    if "\u222b" in text or text.lower().startswith("integrate"):
        return _result("step.title.integral", _integral_steps(text))

    if text.lower().startswith("limit"):
        return _result("step.title.limit", _limit_steps(text, "0"))

    return _result("step.title.derivative", _derivative_steps(text))


__all__ = ["steps"]
