"""Result presentation.

A single SymPy expression can be written in several mathematically identical
forms: an exact fraction, a decimal, a mixed fraction, a simplified radical,
or scientific notation. The interface lets the user cycle through them with
the ALT key without recomputing anything.

``forms()`` returns every applicable representation plus LaTeX for typesetting.
LaTeX is the primary output format everywhere in the interface; the plain text
variant exists only for copying to the clipboard.
"""
from __future__ import annotations

import math

import sympy as sp

# Beyond this the LaTeX becomes unreadable in a 40 px display line.
MAX_LATEX = 480
# Values with more digits than this switch to scientific notation by default.
SCIENTIFIC_BIG = 1e7
SCIENTIFIC_SMALL = 1e-4

FORMS = ("auto", "exact", "decimal", "scientific", "mixed", "radical")


# --------------------------------------------------------------------- helpers
def _latex(expr) -> str:
    """LaTeX with unicode-free output that KaTeX/MathLive render correctly."""
    try:
        text = sp.latex(expr)
    except Exception:
        text = str(expr)
    text = text.replace("\\left(", "(").replace("\\right)", ")")
    return text[:MAX_LATEX]


def _plain(expr) -> str:
    """Plain text for the clipboard: no LaTeX markup, no Python syntax."""
    try:
        text = str(expr)
    except Exception:
        return ""
    for src, dst in (("**", "^"), ("sqrt", "\u221a"), ("pi", "\u03c0"),
                     ("oo", "\u221e"), ("*", "\u00b7")):
        text = text.replace(src, dst)
    while "\u00b7 " in text:
        text = text.replace("\u00b7 ", "\u00b7")
    return text


def _is_rational(expr) -> bool:
    return bool(getattr(expr, "is_rational", False)) and getattr(expr, "is_real", False)


def _is_irrational_root(expr) -> bool:
    """True when the simplified value still carries a square root."""
    try:
        atoms = expr.atoms(sp.Pow)
        return any(a.exp == sp.Rational(1, 2) for a in atoms)
    except (AttributeError, TypeError):
        return False


def mixed_latex(value: sp.Rational) -> str | None:
    """``11/2`` becomes ``5\\frac{1}{2}``.

    Only improper fractions with a plain denominator qualify: a mixed form of
    ``7/3`` is readable, while ``101/97`` is not.
    """
    if not _is_rational(value) or value.q == 1 or value.q > 24:
        return None
    if abs(value.p) <= value.q:
        return None

    whole = int(value.p) // int(value.q)
    remainder = abs(int(value.p)) % int(value.q)
    if remainder == 0:
        return None
    return f"{whole}\\frac{{{remainder}}}{{{value.q}}}"


def scientific_latex(value) -> str | None:
    """``1234567`` becomes ``1.234567 \\times 10^{6}``."""
    try:
        number = float(sp.N(value, 12))
    except (TypeError, ValueError):
        return None
    if number == 0 or not math.isfinite(number):
        return None

    exponent = int(math.floor(math.log10(abs(number))))
    mantissa = number / (10 ** exponent)
    mantissa = round(mantissa, 6)
    if mantissa == 10:
        mantissa, exponent = 1.0, exponent + 1

    mantissa_text = ("%f" % mantissa).rstrip("0").rstrip(".")
    if exponent == 0:
        return None
    return f"{mantissa_text} \\times 10^{{{exponent}}}"


def decimal_text(value, digits: int = 12) -> str | None:
    """Decimal expansion, trimmed, with a leading zero kept intact."""
    try:
        number = sp.N(value, digits + 2)
        if not getattr(number, "is_real", False):
            return None
        text = ("%.*f" % (digits, float(number))).rstrip("0").rstrip(".")
        if text in ("", "-0"):
            text = "0"
        return text
    except (TypeError, ValueError):
        return None


def radical_latex(value) -> str | None:
    """Simplified radical: ``\\sqrt{125}`` becomes ``5\\sqrt{5}``."""
    try:
        simplified = sp.radsimp(sp.nsimplify(value))
    except (ValueError, TypeError):
        return None
    if not _is_irrational_root(simplified):
        return None
    text = _latex(simplified)
    return text if len(text) <= MAX_LATEX else None


# --------------------------------------------------------------------- selection
def _auto_key(value) -> str:
    """Pick the form a person would write by hand.

    Priority, in order:

    1. **scientific** for extreme magnitudes — ``1/1234567`` must not print
       seven zeros before the first digit;
    2. **mixed** for improper fractions — ``11/2`` reads better as ``5 1/2``;
    3. **exact** for irrational values — 2π stays 2π, never
       ``6.28318530718``, and a radical stays a radical;
    4. **decimal** for terminating decimals — ``0.25`` beats ``1/4``;
    5. **exact** otherwise, so a recurring fraction stays exact.
    """
    try:
        magnitude = abs(float(sp.N(value, 12)))
    except (TypeError, ValueError):
        magnitude = None

    if magnitude is not None and math.isfinite(magnitude) and magnitude != 0:
        if magnitude >= SCIENTIFIC_BIG or magnitude < SCIENTIFIC_SMALL:
            return "scientific"

    available_forms = forms(value)
    available = {item["key"] for item in available_forms}
    exact_latex = next((item["latex"] for item in available_forms
                        if item["key"] == "exact"), "")

    # pi, e and everything built from them are exact answers
    if _carries_constant(value) and "exact" in available:
        return "exact"

    if "mixed" in available:
        return "mixed"

    if getattr(value, "is_Integer", False):
        return "exact"

    if _is_irrational_root(value):
        # "radical" only exists when it differs from "exact"; sqrt(125) already
        # prints as 5\sqrt{5}, and falling through to "decimal" turned it into
        # 11.180339887499 — the opposite of what a student wants.
        return "radical" if "radical" in available else "exact"

    # Any other irrational value: keep it symbolic when the LaTeX is short
    if not _is_rational(value) and "exact" in available:
        if len(exact_latex) <= 24:
            return "exact"

    if _is_rational(value):
        decimal = decimal_text(value)
        if decimal is not None and len(decimal.replace("-", "").replace(".", "")) <= 10:
            return "decimal"
        return "exact"

    if "decimal" in available:
        return "decimal"

    return "exact"


def _carries_constant(value) -> bool:
    """True when the value contains pi or e as a factor."""
    try:
        symbols = value.atoms(sp.Number)
    except AttributeError:
        return False
    return bool(value.has(sp.pi) or value.has(sp.E))



def forms(value, digits: int = 12) -> list[dict]:
    """Every representation that makes sense for ``value``, in display order."""
    if value is None:
        return []

    try:
        exact = sp.nsimplify(value) if not isinstance(value, sp.Basic) else value
        exact = sp.simplify(exact)
    except (ValueError, TypeError, AttributeError):
        exact = value

    available: list[dict] = []

    def add(key: str, latex: str | None, plain: str | None = None) -> None:
        if not latex:
            return
        available.append({
            "key": key,
            "latex": latex,
            "plain": plain if plain is not None else latex,
        })

    add("exact", _latex(exact), _plain(exact))

    decimal = decimal_text(exact, digits)
    if decimal is not None and not getattr(exact, "is_Integer", False):
        add("decimal", decimal, decimal)

    if _is_rational(exact):
        add("mixed", mixed_latex(sp.Rational(exact)))

    radical = radical_latex(exact)
    if radical and radical != _latex(exact):
        add("radical", radical, _plain(sp.radsimp(sp.nsimplify(exact))))

    add("scientific", scientific_latex(exact))

    return available


def best(value, digits: int = 12) -> dict:
    """Auto-selected representation, always present even for exotic values."""
    available = forms(value, digits)
    if not available:
        text = _plain(value)
        return {"key": "exact", "latex": text, "plain": text}

    preferred = _auto_key(value)
    for item in available:
        if item["key"] == preferred:
            return item
    return available[0]


def cycle(value, current_key: str, digits: int = 12) -> dict:
    """Next representation after ``current_key``, wrapping around."""
    available = forms(value, digits)
    if not available:
        return best(value, digits)

    keys = [item["key"] for item in available]
    try:
        index = keys.index(current_key)
    except ValueError:
        index = -1

    return available[(index + 1) % len(available)]


def describe(value) -> dict:
    """Payload for the bridge: chosen form plus everything it can cycle to."""
    available = forms(value)
    chosen = best(value)
    return {
        "latex": chosen["latex"],
        "plain": chosen["plain"],
        "key": chosen["key"],
        "forms": available,
    }
