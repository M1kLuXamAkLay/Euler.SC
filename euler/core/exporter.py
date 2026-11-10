"""Export a solution to PDF or LaTeX.

The solution PDF is laid out with matplotlib, which renders formulas with its
built-in math engine (mathtext), so no LaTeX installation is needed. The graph
PDF is written by hand, which keeps that path free of extra dependencies.

Two exporters:

``to_latex``   a self-contained ``.tex`` file, ready for Overleaf or a local
              ``pdflatex`` run. This is what a student hands in.
``to_pdf``     a paginated PDF with the same content and typeset formulas.

Both accept the ``payload`` shape the interface already has:
``{"title": str, "steps": [{"n", "text", "latex"}], "answer": str}``.
"""
from __future__ import annotations

import base64
import re
import textwrap
import zlib
from pathlib import Path

MAX_LINE = 92
PAGE_W, PAGE_H = 595, 842          # A4 in points
MARGIN = 56


def _use_headless_backend() -> None:
    """Pin matplotlib to a non-interactive backend before any figure exists.

    Export writes files and never shows a window, so Agg is always correct.

    Two things have to happen in this order, and the order is the whole point:

    1. **Repair the environment variable.** ``MPLBACKEND`` inherited from a
       Jupyter session names ``module://matplotlib_inline.backend_inline``. That
       module does not exist outside the notebook, so ``import matplotlib``
       itself raises ``ValueError: Key backend`` — before any of our code gets a
       chance to call ``use()``. The variable is removed first, so the import can
       succeed at all.
    2. **Force Agg.** ``force=True`` also replaces a backend another module
       already selected.

    A failure here is swallowed: if matplotlib is genuinely broken, the export
    reports that later with a clearer message than an import traceback.
    """
    import os

    selected = os.environ.get("MPLBACKEND", "")
    if selected.startswith("module://"):
        # A module backend is only valid inside the environment that provides it
        os.environ.pop("MPLBACKEND", None)

    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
    except Exception:      # pragma: no cover - a broken install fails later anyway
        pass


# --------------------------------------------------------------------- helpers
def _read_group(text: str, start: int) -> tuple[str, int]:
    """Read a ``{...}`` group starting at ``start``; return content and end index.

    Handles nesting, which a regular expression cannot: the numerator of
    ``\\frac{-b \\pm \\sqrt{D}}{2a}`` itself contains braces.
    """
    if start >= len(text) or text[start] != "{":
        # Single token, e.g. ``\\frac12``
        return (text[start] if start < len(text) else ""), start + 1

    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
    return text[start + 1:], len(text)


def _expand_fractions(text: str) -> str:
    """Replace ``\\frac{a}{b}`` with ``(a)/(b)`` innermost-first."""
    marker = "\\frac"
    for _ in range(20):
        index = text.find(marker)
        if index < 0:
            break

        numerator, after = _read_group(text, index + len(marker))
        denominator, final = _read_group(text, after)
        if after > len(text):
            break

        # Recurse so nested fractions collapse too
        numerator = _expand_fractions(numerator)
        denominator = _expand_fractions(denominator)
        text = f"{text[:index]}({numerator})/({denominator}){text[final:]}"
    return text


def _expand_roots(text: str) -> str:
    """Replace ``\\sqrt{a}`` with ``sqrt(a)``, nesting aware."""
    marker = "\\sqrt"
    for _ in range(20):
        index = text.find(marker)
        if index < 0:
            break
        body, final = _read_group(text, index + len(marker))
        text = f"{text[:index]}sqrt({_expand_roots(body)}){text[final:]}"
    return text


def _strip_latex(value: str) -> str:
    """Turn a LaTeX fragment into readable plain text for the PDF page.

    Some producers emit doubled backslashes (``\\frac``) because the string
    travelled through a JSON layer twice. Collapsing them first keeps every
    macro rule below working on one canonical form.
    """
    text = str(value).replace("\\\\", "\\")

    # Structural macros first: they carry braces that would confuse the
    # flat replacements below.
    text = _expand_roots(text)
    text = _expand_fractions(text)

    # Every entry is a literal (str.replace, not regex), so a macro needs a
    # single leading backslash: "\int" is the two-character text "\int".
    simple = [
        ("\\int", "int"), ("\\iint", "iint"), ("\\lim", "lim"),
        ("\\to", "->"), ("\\infty", "inf"), ("\\pi", "pi"),
        ("\\pm", "+-"), ("\\mp", "-+"), ("\\cdot", "*"),
        ("\\times", "*"), ("\\div", "/"), ("\\quad", "   "),
        ("\\qquad", "     "), ("\\,", " "), ("\\;", " "),
        ("\\:", " "), ("\\!", ""), ("\\ ", " "),
        ("\\Rightarrow", "=>"), ("\\Leftrightarrow", "<=>"),
        ("\\rightarrow", "->"), ("\\leq", "<="), ("\\geq", ">="),
        ("\\le", "<="), ("\\ge", ">="), ("\\ne", "!="),
        ("\\neq", "!="), ("\\approx", "~="),
        ("\\sin", "sin"), ("\\cos", "cos"), ("\\tan", "tan"),
        ("\\cot", "cot"), ("\\arcsin", "asin"), ("\\arccos", "acos"),
        ("\\arctan", "atan"), ("\\ln", "ln"), ("\\log", "log"),
        ("\\lg", "lg"), ("\\exp", "exp"),
        ("\\left", ""), ("\\right", ""), ("\\displaystyle", ""),
        ("\\operatorname", ""), ("\\mathrm", ""), ("\\text", ""),
    ]

    for pattern, replacement in simple:
        text = text.replace(pattern, replacement)

    # Remaining groups are plain superscript/subscript arguments
    text = re.sub(r"\^\{([^{}]*)\}", r"^\1", text)
    text = re.sub(r"_\{([^{}]*)\}", r"_\1", text)
    text = text.replace("{", "").replace("}", "")

    # The PDF core font is Latin-1 only: transliterate the rest
    table = {"\u222b": "int", "\u2192": "->", "\u221e": "inf", "\u03c0": "pi",
             "\u00b1": "+-", "\u222a": "U", "\u2200": "for all", "\u2208": "in",
             "\u2264": "<=", "\u2265": ">=", "\u2260": "!=", "\u221a": "sqrt",
             "\u00b7": "*", "\u2212": "-", "\u2261": "=", "\u03bb": "lambda",
             "\u2205": "empty", "\u03b4": "d", "\u03b5": "e"}
    for src, dst in table.items():
        text = text.replace(src, dst)

    text = re.sub(r"\s+", " ", text).strip()

    # No Latin-1 transcoding: the PDF embeds a Unicode font, so Cyrillic, Greek,
    # CJK and Arabic survive. Forcing Latin-1 here turned "Квадратное" into
    # "??????????".
    return text


def _wrap(text: str, width: int = MAX_LINE) -> list[str]:
    return textwrap.wrap(text, width=width) or [""]


# --------------------------------------------------------------------- LaTeX
LATEX_PREAMBLE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb}
\usepackage[margin=2cm]{geometry}
\setlength{\parindent}{0pt}
\begin{document}
"""

LATEX_POSTAMBLE = "\n\\end{document}\n"


ANSWER_TITLES = {
    "ru": "Ответ", "en": "Answer", "zh": "答案", "es": "Respuesta",
    "fr": "Réponse", "bn": "উত্তর", "pt": "Resposta",
}


def to_latex(payload: dict) -> str:
    """A complete ``.tex`` document for the given solution payload.

    ``payload`` keys: ``title``, ``steps`` (list of ``{n, text, latex}``),
    ``answer`` (LaTeX string, already formatted by the engine) and optionally
    ``language`` for the section heading.
    """
    title = payload.get("title") or "Solution"
    steps = payload.get("steps") or []
    answer = payload.get("answer") or ""
    heading = ANSWER_TITLES.get(str(payload.get("language", "en"))[:2], "Answer")

    parts = [LATEX_PREAMBLE]
    parts.append(f"\\section*{{{_escape_latex(title)}}}\n")

    if steps:
        parts.append("\\begin{enumerate}\n")
        for step in steps:
            latex = step.get("latex") or _escape_latex(step.get("text", ""))
            parts.append(f"  \\item ${latex}$\n")
        parts.append("\\end{enumerate}\n")

    if answer:
        parts.append(f"\n\\subsection*{{{heading}}}\n")
        parts.append(f"\\[ {answer} \\]\n")

    parts.append(LATEX_POSTAMBLE)
    return "".join(parts)


def _escape_latex(text: str) -> str:
    """Escape user text, preserving any existing math delimiters."""
    out = str(text)
    for src, dst in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                     ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}")):
        out = out.replace(src, dst)
    return out


# --------------------------------------------------------------------- PDF
def _hex4(value: int) -> str:
    return f"{value:04X}"


def _to_unicode_cmap(mapping: dict[int, str]) -> bytes:
    """A ToUnicode CMap: glyph id -> original character.

    Without it a PDF built from glyph ids is unsearchable and copy-paste yields
    gibberish. With it every viewer extracts the real text.
    """
    entries = sorted(mapping.items())
    chunks = []
    for index in range(0, len(entries), 100):
        block = entries[index:index + 100]
        rows = "\n".join(
            f"<{_hex4(glyph)}> <{''.join(_hex4(ord(ch)) for ch in text)}>"
            for glyph, text in block)
        chunks.append(f"{len(block)} beginbfchar\n{rows}\nendbfchar")

    return (
        "/CIDInit /ProcSet findresource begin\n"
        "12 dict begin\n"
        "begincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Adobe-Identity-UCS def\n"
        "/CMapType 2 def\n"
        "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        + "\n".join(chunks) +
        "\nendcmap\nCMapName currentdict /CMap defineresource pop\n"
        "end\nend\n"
    ).encode("latin-1")


def _escape_literal(text: str) -> str:
    """Escape a PDF literal string, for the parts that stay ASCII."""
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _wrap_width(text: str, font, size: float, limit: float) -> list[str]:
    """Break ``text`` so that every line fits ``limit`` points.

    Widths come from the embedded font, so Cyrillic and CJK wrap at the right
    place instead of running off the page. Words are kept whole; a single word
    longer than the line is broken by characters.
    """
    if not text:
        return [""]

    scale = size / 1000.0

    def measure(piece: str) -> float:
        return sum(font.width(font.glyph(ch)) for ch in piece) * scale

    if measure(text) <= limit:
        return [text]

    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current = ""

        for word in words:
            candidate = word if not current else current + " " + word
            if measure(candidate) <= limit:
                current = candidate
                continue

            if current:
                lines.append(current)
            # A single word that still does not fit: break it by characters
            if measure(word) > limit:
                chunk = ""
                for ch in word:
                    if measure(chunk + ch) > limit and chunk:
                        lines.append(chunk)
                        chunk = ch
                    else:
                        chunk += ch
                current = chunk
            else:
                current = word

        lines.append(current)

    return lines or [""]


STEP_TITLES = {
    "ru": "Шаг", "en": "Step", "zh": "步骤", "es": "Paso",
    "fr": "Étape", "bn": "ধাপ", "pt": "Passo",
}

ACCENT = (0.56, 0.30, 0.34)
PANEL = (0.99, 0.96, 0.97)
INK = (0.18, 0.11, 0.13)
MUTED = (0.43, 0.31, 0.34)
FOOTER_Y = MARGIN - 26
BRAND = "Euler.SC"


def _hex_glyphs(glyphs: list[int]) -> str:
    return "<" + "".join(f"{glyph:04X}" for glyph in glyphs) + ">"


class _Canvas:
    """Page content streams, plus the glyph-to-character map for the ToUnicode table."""

    def __init__(self, font) -> None:
        self.font = font
        self.used: set[int] = set()
        self.chars: dict[int, str] = {}
        self.pages: list[list[str]] = [[]]
        self.y = PAGE_H - MARGIN

    def new_page(self) -> None:
        self.pages.append([])
        self.y = PAGE_H - MARGIN

    def ensure(self, height: float) -> None:
        if self.y - height < MARGIN:
            self.new_page()

    def text(self, x: float, y: float, size: float, value: str,
             bold: bool = False, color: tuple = INK) -> None:
        glyphs = []
        for ch in value:
            glyph = self.font.glyph(ch)
            if glyph:
                self.used.add(glyph)
                self.chars.setdefault(glyph, ch)
            glyphs.append(glyph)
        r, g, b = color
        mode, width = ("2 Tr", 0.35) if bold else ("0 Tr", 0.0)
        self.pages[-1].append(
            f"{r:.3f} {g:.3f} {b:.3f} rg {r:.3f} {g:.3f} {b:.3f} RG {width} w {mode} "
            f"BT /F1 {size} Tf 1 0 0 1 {x:.1f} {y:.1f} Tm {_hex_glyphs(glyphs)} Tj ET 0 Tr")

    def rect(self, x: float, y: float, w: float, h: float,
             fill: tuple | None = None, stroke: tuple | None = None, line: float = 0.8) -> None:
        parts = [f"{line} w"]
        if fill:
            parts.append("%.3f %.3f %.3f rg" % fill)
        if stroke:
            parts.append("%.3f %.3f %.3f RG" % stroke)
        parts.append(f"{x:.1f} {y:.1f} {w:.1f} {h:.1f} re")
        parts.append("B" if fill and stroke else ("f" if fill else "S"))
        self.pages[-1].append(" ".join(parts))

    def rule(self, x1: float, x2: float, y: float, color: tuple, line: float = 1.0) -> None:
        self.pages[-1].append(
            "%.1f w %.3f %.3f %.3f RG %.1f %.1f m %.1f %.1f l S"
            % (line, *color, x1, y, x2, y))

    def paragraph(self, value: str, size: float, bold: bool = False,
                  color: tuple = INK, indent: float = 0.0) -> None:
        leading = size * 1.45
        for piece in _wrap_width(value, self.font, size, PAGE_W - 2 * MARGIN - indent):
            self.ensure(leading)
            self.y -= leading
            self.text(MARGIN + indent, self.y, size, piece, bold, color)


def _footer(canvas: _Canvas, index: int, total: int) -> None:
    canvas.pages[index].append(
        "%.1f w %.3f %.3f %.3f RG %.1f %.1f m %.1f %.1f l S"
        % (0.6, *PANEL, MARGIN, FOOTER_Y + 12, PAGE_W - MARGIN, FOOTER_Y + 12))
    saved = canvas.pages
    canvas.pages = [saved[index]]
    canvas.text(MARGIN, FOOTER_Y, 8, BRAND, color=MUTED)
    number = f"{index + 1} / {total}"
    canvas.text(PAGE_W - MARGIN - 7 * len(number), FOOTER_Y, 8, number, color=MUTED)
    canvas.pages = saved


def _document(pages: list[list[str]], font, canvas: _Canvas,
              image: tuple[int, int, bytes] | None = None) -> bytes:
    """Assemble a PDF with a subset Unicode font and an optional RGB image."""
    from .pdf_font import subset_font

    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")
    pages_obj = add(b"")
    type0 = add(b"")
    cid_font = add(b"")
    descriptor = add(b"")
    font_file = add(b"")
    cmap_object = add(b"")
    image_object = add(b"") if image else 0
    page_numbers = [add(b"") for _ in pages]
    content_numbers = [add(b"") for _ in pages]

    objects[catalog - 1] = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode()
    kids = " ".join(f"{number} 0 R" for number in page_numbers)
    objects[pages_obj - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode()

    objects[type0 - 1] = (
        f"<< /Type /Font /Subtype /Type0 /BaseFont /{font.name} "
        f"/Encoding /Identity-H /DescendantFonts [{cid_font} 0 R] "
        f"/ToUnicode {cmap_object} 0 R >>").encode()

    widths = " ".join(f"{glyph} [{font.width(glyph)}]" for glyph in sorted(canvas.used))
    objects[cid_font - 1] = (
        f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{font.name} "
        f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
        f"/FontDescriptor {descriptor} 0 R /DW 1000 /W [{widths}] "
        f"/CIDToGIDMap /Identity >>").encode()

    objects[descriptor - 1] = (
        f"<< /Type /FontDescriptor /FontName /{font.name} /Flags 32 "
        f"/FontBBox [0 -300 1000 1000] /ItalicAngle 0 /Ascent 900 "
        f"/Descent -250 /CapHeight 700 /StemV 80 /FontFile2 {font_file} 0 R >>").encode()

    subset = subset_font(font, canvas.used)
    compressed_font = zlib.compress(subset, 9)
    objects[font_file - 1] = (
        f"<< /Length {len(compressed_font)} /Length1 {len(subset)} "
        f"/Filter /FlateDecode >>\nstream\n".encode()
        + compressed_font + b"\nendstream")

    xobjects = ""
    if image:
        width, height, raw = image
        packed = zlib.compress(raw, 9)
        objects[image_object - 1] = (
            f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
            f"/Length {len(packed)} >>\nstream\n".encode() + packed + b"\nendstream")
        xobjects = f" /XObject << /Im1 {image_object} 0 R >>"

    for index, page in enumerate(pages):
        objects[page_numbers[index] - 1] = (
            f"<< /Type /Page /Parent {pages_obj} 0 R "
            f"/MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /F1 {type0} 0 R >>{xobjects} >> "
            f"/Contents {content_numbers[index]} 0 R >>").encode()
        stream = zlib.compress("\n".join(page).encode("latin-1"), 9)
        objects[content_numbers[index] - 1] = (
            f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode()
            + stream + b"\nendstream")

    cmap = zlib.compress(_to_unicode_cmap(canvas.chars), 9)
    objects[cmap_object - 1] = (
        f"<< /Length {len(cmap)} /Filter /FlateDecode >>\nstream\n".encode()
        + cmap + b"\nendstream")

    return _assemble(objects)


_LATEX_HINT = re.compile(r"[\\^_{}]")
_LEADING = 1.45
_PAGE_BOTTOM = MARGIN + 40
_USABLE = PAGE_W - 2 * MARGIN


def _formula_latex(value: str) -> str:
    return re.sub(r"\$+|\\\(|\\\)|\\\[|\\\]", "", value or "").strip()


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("$", r"\$")).strip()


def _mathtext_ok(latex: str) -> bool:
    _use_headless_backend()
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties

    try:
        mathtext.MathTextParser("path").parse(f"${latex}$", dpi=72, prop=FontProperties(size=12))
    except Exception:  # the parser raises several exception types for bad input
        return False
    return True


class _Sheet:
    """Top-down page layout on matplotlib figures; text widths are measured, not estimated."""

    def __init__(self) -> None:
        self.figs: list = []
        self._new_page()

    def _new_page(self) -> None:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        fig = Figure(figsize=(PAGE_W / 72, PAGE_H / 72), dpi=72)
        FigureCanvasAgg(fig)
        self.figs.append(fig)
        self.fig = fig
        self.renderer = fig.canvas.get_renderer()
        self.y = PAGE_H - MARGIN

    def ensure(self, height: float) -> None:
        if self.y - height < _PAGE_BOTTOM:
            self._new_page()

    def _text(self, x: float, baseline: float, value: str, size: float,
              bold: bool = False, color: tuple = INK):
        return self.fig.text(x / PAGE_W, baseline / PAGE_H, value, fontsize=size,
                             fontweight="bold" if bold else "normal", color=color,
                             transform=self.fig.transFigure, ha="left", va="baseline")

    def _measure(self, value: str, size: float, bold: bool = False) -> tuple[float, float]:
        artist = self._text(0, 0, value, size, bold)
        box = artist.get_window_extent(self.renderer)
        artist.remove()
        return box.width, box.height

    def _line_height(self, line: str, size: float, bold: bool = False) -> float:
        if line.startswith("$"):
            return self._measure(line, size, bold)[1] * 1.1
        return size * _LEADING

    def _wrap(self, value: str, size: float, bold: bool, width: float) -> list[str]:
        lines, current = [], ""
        for word in value.split():
            candidate = f"{current} {word}".strip()
            if current and self._measure(candidate, size, bold)[0] > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    def _lines(self, value: str, size: float, bold: bool, width: float, latex: bool) -> list[str]:
        if latex:
            formula = _formula_latex(value)
            formula = re.sub(r"\\le(?![a-z])", r"\\leq", formula)
            formula = re.sub(r"\\ge(?![a-z])", r"\\geq", formula)
            formula = formula.replace("\\frac", "\\dfrac")
            if formula and _mathtext_ok(formula):
                markup = f"${formula}$"
                if self._measure(markup, size, bold)[0] <= width:
                    return [markup]
            return self._wrap(_plain(_strip_latex(value)), size, bold, width)
        return self._wrap(_plain(value), size, bold, width)

    def _draw_line(self, x: float, top: float, line: str, size: float,
                   bold: bool = False, color: tuple = INK) -> float:
        if line.startswith("$"):
            height = self._measure(line, size, bold)[1]
            self._text(x, top - height * 0.8, line, size, bold, color)
        else:
            self._text(x, top - size, line, size, bold, color)
        return self._line_height(line, size, bold)

    def rect(self, x: float, y: float, w: float, h: float, *,
             fill: tuple | None = None, stroke: tuple | None = None, line: float = 1.0) -> None:
        from matplotlib.patches import Rectangle

        self.fig.add_artist(Rectangle(
            (x / PAGE_W, y / PAGE_H), w / PAGE_W, h / PAGE_H, transform=self.fig.transFigure,
            facecolor=fill or "none", edgecolor=stroke or "none", linewidth=line))

    def rule(self, y: float, color: tuple, width: float) -> None:
        from matplotlib.lines import Line2D

        self.fig.add_artist(Line2D(
            [MARGIN / PAGE_W, (PAGE_W - MARGIN) / PAGE_W], [y / PAGE_H, y / PAGE_H],
            transform=self.fig.transFigure, color=color, linewidth=width))

    def paragraph(self, value: str, size: float, *, bold: bool = False,
                  color: tuple = INK, latex: bool = False) -> None:
        if not value:
            return
        lines = self._lines(value, size, bold, _USABLE, latex)
        self.ensure(sum(self._line_height(line, size, bold) for line in lines))
        for line in lines:
            self.y -= self._draw_line(MARGIN, self.y, line, size, bold, color)

    def formula(self, latex: str, size: float = 12) -> None:
        lines = self._lines(latex, size, False, _USABLE - 24, latex=True)
        if not lines:
            return
        panel = sum(self._line_height(line, size) for line in lines) + 12
        self.ensure(panel + 8)
        top = self.y - 6
        self.rect(MARGIN, top - panel, _USABLE, panel, fill=PANEL)
        self.rect(MARGIN, top - panel, 3, panel, fill=ACCENT)
        cursor = top - 6
        for line in lines:
            cursor -= self._draw_line(MARGIN + 14, cursor, line, size)
        self.y = top - panel - 8

    def boxed(self, value: str, size: float = 14) -> None:
        lines = self._lines(value, size, True, _USABLE - 24, latex=bool(_LATEX_HINT.search(value)))
        box = sum(self._line_height(line, size, True) for line in lines) + 14
        self.ensure(box + 4)
        top = self.y
        self.rect(MARGIN, top - box, _USABLE, box, stroke=ACCENT, line=1.2)
        cursor = top - 7
        for line in lines:
            cursor -= self._draw_line(MARGIN + 12, cursor, line, size, bold=True)
        self.y = top - box

    def footers(self) -> None:
        total = len(self.figs)
        for index, fig in enumerate(self.figs):
            self.fig = fig
            self.rule(FOOTER_Y + 12, PANEL, 0.6)
            self._text(MARGIN, FOOTER_Y, BRAND, 8, color=MUTED)
            number = f"{index + 1} / {total}"
            self._text(PAGE_W - MARGIN - self._measure(number, 8)[0], FOOTER_Y, number, 8, color=MUTED)


def to_pdf(payload: dict) -> bytes:
    """A solution as a worked answer: title, numbered steps, typeset formulas, boxed answer."""
    import io

    _use_headless_backend()
    import matplotlib as mpl
    from matplotlib.backends.backend_pdf import PdfPages

    lang = str(payload.get("language", "en"))[:2]
    title = _strip_latex(payload.get("title") or "Solution")
    answer = str(payload.get("answer") or "").strip()
    buffer = io.BytesIO()

    with mpl.rc_context({"font.family": "DejaVu Sans", "mathtext.fontset": "dejavusans",
                         "pdf.fonttype": 42}):
        sheet = _Sheet()
        sheet.paragraph(title, 18, bold=True)
        sheet.y -= 6
        sheet.rule(sheet.y, ACCENT, 1.4)
        sheet.y -= 14
        for step in payload.get("steps") or []:
            number = step.get("n")
            name = STEP_TITLES.get(lang, "Step")
            sheet.ensure(30)
            sheet.y -= 6
            sheet.paragraph(f"{name} {number}" if number else name, 9.5, bold=True, color=ACCENT)
            sheet.paragraph(_strip_latex(step.get("text") or ""), 11)
            sheet.formula(step.get("latex") or "")
        if answer:
            sheet.ensure(60)
            sheet.y -= 12
            sheet.paragraph(ANSWER_TITLES.get(lang, "Answer"), 12, bold=True, color=ACCENT)
            sheet.y -= 4
            sheet.boxed(answer)
        sheet.footers()

        with PdfPages(buffer) as pdf:
            pdf.infodict()["Title"] = title
            pdf.infodict()["Creator"] = BRAND
            for fig in sheet.figs:
                pdf.savefig(fig)
    return buffer.getvalue()


def to_graph_pdf(payload: dict) -> bytes:
    """One A4 page: the plotted graph as an image, with its caption above."""
    from .pdf_font import FontError, load_font

    width = int(payload.get("width") or 0)
    height = int(payload.get("height") or 0)
    raw = base64.b64decode(payload.get("rgb") or "")
    if not (16 <= width <= 4000 and 16 <= height <= 4000) or len(raw) != width * height * 3:
        raise ValueError("ExprError.bad_payload")

    caption = _strip_latex(payload.get("title") or "")
    try:
        font = load_font(caption + BRAND + "0123456789")
    except FontError:
        font = None

    if font is None:
        return _pdf_ascii([(BRAND, 12.0, True)])

    canvas = _Canvas(font)
    canvas.y = PAGE_H - MARGIN
    if caption:
        canvas.paragraph(caption, 14, bold=True)
        canvas.y -= 10
    scale = min((PAGE_W - 2 * MARGIN) / width, (PAGE_H - 2 * MARGIN - 60) / height)
    draw_w, draw_h = width * scale, height * scale
    canvas.ensure(draw_h + 10)
    top = canvas.y
    canvas.pages[-1].append(
        f"q {draw_w:.1f} 0 0 {draw_h:.1f} {MARGIN} {top - draw_h:.1f} cm /Im1 Do Q")
    canvas.y = top - draw_h
    total = len(canvas.pages)
    for index in range(total):
        _footer(canvas, index, total)
    return _document(canvas.pages, font, canvas, image=(width, height, raw))


def _pdf_ascii(lines: list[tuple[str, float, bool]]) -> bytes:
    """Fallback writer using the Helvetica core font, Latin-1 only."""
    out = []
    y = PAGE_H - MARGIN
    for text, size, bold in lines:
        for piece in _wrap(text):
            if y < MARGIN:
                break
            font = "F2" if bold else "F1"
            out.append(f"BT /{font} {size} Tf {MARGIN} {y:.1f} Td "
                       f"({_escape_literal(piece)}) Tj ET")
            y -= size * 1.6

    stream = zlib.compress("\n".join(out).encode("latin-1"), 9)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
         f"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>").encode(),
        (f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode()
         + stream + b"\nendstream"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    return _assemble(objects)


def _assemble(objects: list[bytes]) -> bytes:
    """Write the xref table and trailer around the object list."""
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n").encode()
    return bytes(out)


def write(target: Path, data: bytes | str) -> Path:
    """Write text or bytes, creating parent directories."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        target.write_text(data, encoding="utf-8")
    else:
        target.write_bytes(data)
    return target
