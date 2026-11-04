"""Export a solution to PDF or LaTeX.

PDF is produced without external binaries: the document is written as a minimal
PDF by hand (using the built-in Helvetica core font for ASCII and a Type3-free
fallback for mathematics), which keeps the installer free of ReportLab or a
LaTeX distribution.

Two exporters:

``to_latex``   a self-contained ``.tex`` file, ready for Overleaf or a local
              ``pdflatex`` run. This is what a student hands in.
``to_pdf``     a paginated PDF with the same content, generated here.

Both accept the ``payload`` shape the interface already has:
``{"title": str, "steps": [{"n", "text", "latex"}], "answer": str}``.
"""
from __future__ import annotations

import re
import textwrap
import zlib
from pathlib import Path

MAX_LINE = 92
PAGE_W, PAGE_H = 595, 842          # A4 in points
MARGIN = 56


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


def _pdf_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


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


def _hex_text(text: str, font) -> str:
    """Glyph ids as a PDF hex string, the form Identity-H expects."""
    ids = [font.glyph(ch) for ch in text]
    return "<" + "".join(f"{glyph:04X}" for glyph in ids) + ">"


def _paginate(lines: list[tuple[str, float, bool]], font) -> list[list[tuple]]:
    """Split the flow into pages, wrapping each entry to the text width."""
    usable = PAGE_W - 2 * MARGIN
    pages: list[list[tuple]] = []
    page: list[tuple] = []
    y = PAGE_H - MARGIN

    for text, size, bold in lines:
        for piece in _wrap_width(text, font, size, usable):
            step = size * 1.55
            if y - step < MARGIN:
                pages.append(page)
                page = []
                y = PAGE_H - MARGIN
            page.append((piece, size, bold, y))
            y -= step

    pages.append(page)
    return pages


def _content_stream(page: list[tuple], font) -> str:
    """Page content: every string written as glyph ids."""
    out = []
    for text, size, _bold, y in page:
        if not text:
            continue
        out.append(
            f"BT /F1 {size} Tf 1 0 0 1 {MARGIN} {y:.1f} Tm {_hex_text(text, font)} Tj ET")
    return "\n".join(out)


def to_pdf(payload: dict) -> bytes:
    """A PDF with an embedded Unicode font.

    The core Helvetica font can only represent Latin-1, so a Russian, Chinese or
    Bengali heading raised ``UnicodeEncodeError`` and the export failed. A
    TrueType font is embedded instead and every glyph is addressed by its
    numeric id through a ``Type0`` / ``Identity-H`` font, which needs no
    encoding table at all.
    """
    from .pdf_font import FontError, load_font

    title = _strip_latex(payload.get("title") or "Solution")
    steps = payload.get("steps") or []
    answer = _strip_latex(payload.get("answer") or "")
    heading = ANSWER_TITLES.get(str(payload.get("language", "en"))[:2], "Answer")

    # Collect every glyph first: the font choice depends on the alphabet used
    collected = [title, heading, answer]
    for step in steps:
        collected.append(_strip_latex(step.get("latex") or step.get("text", "")))

    try:
        font = load_font("".join(collected))
    except FontError:
        # Last resort: strip to Latin-1 so the file is still produced
        font = None

    lines: list[tuple[str, float, bool]] = [(title, 16.0, True), ("", 8.0, False)]
    for step in steps:
        body = _strip_latex(step.get("latex") or step.get("text", ""))
        prefix = f"{step.get('n')}. " if step.get("n") else ""
        lines.append((prefix + body, 11.0, False))
        lines.append(("", 5.0, False))

    if answer:
        lines.append(("", 6.0, False))
        lines.append((heading, 13.0, True))
        lines.append((answer, 11.0, False))

    if font is None:
        # Degraded path: no Unicode font found, keep the document Latin-1 only
        lines = [(text.encode("latin-1", "replace").decode("latin-1"), size, bold)
                 for text, size, bold in lines]
        return _pdf_ascii(lines)

    pages = _paginate(lines, font)

    # Glyphs actually used, so the /W array stays small
    used: set[int] = set()
    for page in pages:
        for text, _size, _bold, _y in page:
            used.update(font.glyph(ch) for ch in text)
    used.discard(0)

    widths = " ".join(f"{glyph} [{font.width(glyph)}]" for glyph in sorted(used))

    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    # Reserve object numbers first, then fill them in dependency order.
    # Every number comes from ``len(objects) + 1`` at the moment of the call, so
    # no two objects can ever receive the same id: computing a range in advance
    # and then inserting the ToUnicode map gave the first page the same number
    # as the map, and the page silently disappeared.
    catalog = add(b"")
    pages_obj = add(b"")
    type0 = add(b"")
    cid_font = add(b"")
    descriptor = add(b"")
    font_file = add(b"")
    cmap_object = add(b"")        # reserved here, filled at the end

    page_numbers = []
    content_numbers = []
    for _page in pages:
        page_numbers.append(add(b""))
        content_numbers.append(add(b""))

    objects[catalog - 1] = (
        f"<< /Type /Catalog /Pages {pages_obj} 0 R >>").encode()

    kids = " ".join(f"{number} 0 R" for number in page_numbers)
    objects[pages_obj - 1] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>").encode()

    # Glyph id -> character, so the text stays searchable after export
    glyph_to_char: dict[int, str] = {}
    for page in pages:
        for text, _size, _bold, _y in page:
            for character in text:
                glyph = font.glyph(character)
                if glyph:
                    glyph_to_char.setdefault(glyph, character)

    objects[type0 - 1] = (
        f"<< /Type /Font /Subtype /Type0 /BaseFont /{font.name} "
        f"/Encoding /Identity-H /DescendantFonts [{cid_font} 0 R] "
        f"/ToUnicode {cmap_object} 0 R >>").encode()

    objects[cid_font - 1] = (
        f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{font.name} "
        f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
        f"/FontDescriptor {descriptor} 0 R /DW 1000 /W [{widths}] "
        f"/CIDToGIDMap /Identity >>").encode()

    scale = 1000 / font.units_per_em
    objects[descriptor - 1] = (
        f"<< /Type /FontDescriptor /FontName /{font.name} /Flags 32 "
        f"/FontBBox [0 -300 1000 1000] /ItalicAngle 0 /Ascent {int(900 * 1000 / 1000)} "
        f"/Descent -250 /CapHeight 700 /StemV 80 /FontFile2 {font_file} 0 R >>").encode()

    # Only the glyphs on the page are embedded. A full CJK face is 13 MB; the
    # subset for a page of formulas is a few hundred kilobytes.
    from .pdf_font import subset_font

    subset = subset_font(font, used)
    compressed_font = zlib.compress(subset, 9)
    objects[font_file - 1] = (
        f"<< /Length {len(compressed_font)} /Length1 {len(subset)} "
        f"/Filter /FlateDecode >>\nstream\n".encode()
        + compressed_font + b"\nendstream")

    # Fill the reserved slots; appending here would create fresh object numbers
    # and leave /Kids pointing at empty placeholders.
    for page_index, page in enumerate(pages):
        number = page_numbers[page_index]
        content_number = content_numbers[page_index]

        objects[number - 1] = (
            f"<< /Type /Page /Parent {pages_obj} 0 R "
            f"/MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /F1 {type0} 0 R >> >> "
            f"/Contents {content_number} 0 R >>").encode()

        stream = zlib.compress(_content_stream(page, font).encode("latin-1"), 9)
        objects[content_number - 1] = (
            f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode()
            + stream + b"\nendstream")

    cmap_bytes = _to_unicode_cmap(glyph_to_char)
    stream = zlib.compress(cmap_bytes, 9)
    objects[cmap_object - 1] = (
        f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode()
        + stream + b"\nendstream")

    return _assemble(objects)


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
