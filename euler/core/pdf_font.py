"""TrueType embedding for the hand-written PDF writer.

A PDF built with the Helvetica core font can only carry Latin-1: a Russian or
Chinese heading raised ``UnicodeEncodeError`` and the export failed outright.
The only correct fix is to embed a real Unicode font, which this module does.

What it does:

1.  locates a font that covers the text (a bundled DejaVu is the fallback);
2.  parses ``cmap``, ``hmtx`` and ``head`` to map characters to glyph ids and
    widths;
3.  extracts a single face from a ``.ttc`` collection when needed;
4.  emits the PDF objects for a ``Type0`` / ``Identity-H`` font, so every glyph
    is addressed by its 16-bit id and no encoding table is involved.

Nothing here needs third-party packages: only ``struct`` and ``zlib``.
"""
from __future__ import annotations

import struct
from pathlib import Path

# Candidates in priority order. The bundled font comes first so the output is
# identical on every machine, then platform fonts as a fallback.
# Fonts with ``glyf`` outlines come first: only those can be subset, and a full
# CJK face is 13-18 MB. CFF-based fonts (Noto CJK) are listed last as a
# last resort and are embedded whole.
FONT_CANDIDATES = (
    "assets/fonts/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    # glyf-based CJK faces, checked before the CFF ones on purpose
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    # CFF outlines: cannot be subset, embedded as-is
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


class FontError(RuntimeError):
    """No usable font could be loaded."""


def _read_sfnt(data: bytes, offset: int = 0) -> dict:
    """Table directory of one font face, keyed by 4-character tag."""
    if len(data) < offset + 12:
        raise FontError("truncated font")

    version, count = struct.unpack(">IH", data[offset:offset + 6])
    if version not in (0x00010000, 0x4F54544F, 0x74727565):
        raise FontError("not a TrueType font")

    tables: dict[str, tuple[int, int]] = {}
    for index in range(count):
        base = offset + 12 + index * 16
        tag, _checksum, table_offset, length = struct.unpack(">4sIII", data[base:base + 16])
        tables[tag.decode("latin-1")] = (table_offset, length)
    return tables


def _ttc_face(data: bytes) -> tuple[dict, bytes]:
    """Extract the first face of a ``.ttc`` collection into a standalone sfnt.

    PDF requires a plain font file; a collection cannot be embedded as-is, so
    the shared tables are copied into a fresh table directory.
    """
    if data[:4] != b"ttcf":
        return _read_sfnt(data), data

    count = struct.unpack(">I", data[8:12])[0]
    if not count:
        raise FontError("empty collection")
    face_offset = struct.unpack(">I", data[12:16])[0]
    tables = _read_sfnt(data, face_offset)

    # Build a standalone sfnt: header + directory + padded tables
    tags = sorted(tables)
    header = struct.pack(">IHHHH", 0x00010000, len(tags), 0, 0, 0)
    directory = bytearray()
    body = bytearray()
    base_offset = 12 + len(tags) * 16

    for tag in tags:
        offset, length = tables[tag]
        chunk = data[offset:offset + length]
        directory += struct.pack(">4sIII", tag.encode("latin-1"), 0,
                                 base_offset + len(body), length)
        body += chunk
        while len(body) % 4:
            body.append(0)

    return tables, header + bytes(directory) + bytes(body)


class EmbeddedFont:
    """A parsed TrueType face ready for PDF embedding."""

    def __init__(self, path: Path):
        raw = path.read_bytes()
        tables, standalone = _ttc_face(raw)
        self.name = path.stem.replace(" ", "")
        self.file_bytes = standalone

        for required in ("cmap", "hmtx", "head", "hhea", "maxp"):
            if required not in tables:
                raise FontError(f"{path.name}: missing {required} table")

        head_offset = tables["head"][0]
        self.units_per_em = struct.unpack(">H", raw[head_offset + 18:head_offset + 20])[0]
        self.index_to_loc = struct.unpack(">h", raw[head_offset + 50:head_offset + 52])[0]

        hhea_offset = tables["hhea"][0]
        self.metrics_count = struct.unpack(">H", raw[hhea_offset + 34:hhea_offset + 36])[0]

        maxp_offset = tables["maxp"][0]
        self.glyph_count = struct.unpack(">H", raw[maxp_offset + 4:maxp_offset + 6])[0]

        self._raw = raw
        self._tables = tables
        self.advances = self._read_advances()
        self.cmap = self._read_cmap()

    # ------------------------------------------------------------- font tables
    def _read_advances(self) -> list[int]:
        offset = self._tables["hmtx"][0]
        advances: list[int] = []
        for index in range(min(self.metrics_count, self.glyph_count)):
            advance = struct.unpack(">H", self._raw[offset + index * 4:offset + index * 4 + 2])[0]
            advances.append(advance)
        if advances:
            advances += [advances[-1]] * (self.glyph_count - len(advances))
        return advances

    def _read_cmap(self) -> dict[int, int]:
        """Character code -> glyph id, from the Unicode subtables."""
        base = self._tables["cmap"][0]
        count = struct.unpack(">H", self._raw[base + 2:base + 4])[0]

        best: dict[int, int] = {}
        for index in range(count):
            record = base + 4 + index * 8
            platform, encoding, sub_offset = struct.unpack(
                ">HHI", self._raw[record:record + 8])
            start = base + sub_offset
            fmt = struct.unpack(">H", self._raw[start:start + 2])[0]

            # 3/10 (Windows UCS-4) and 0/x are the widest; prefer them
            if fmt == 12:
                mapping = self._cmap_format12(start)
            elif fmt == 4:
                mapping = self._cmap_format4(start)
            else:
                continue

            if (platform, encoding) in ((3, 10), (0, 4), (0, 6)):
                return mapping
            if len(mapping) > len(best):
                best = mapping

        return best

    def _cmap_format4(self, start: int) -> dict[int, int]:
        raw = self._raw
        seg_count = struct.unpack(">H", raw[start + 6:start + 8])[0] // 2
        ends_at = start + 14
        starts_at = ends_at + seg_count * 2 + 2
        deltas_at = starts_at + seg_count * 2
        ranges_at = deltas_at + seg_count * 2

        mapping: dict[int, int] = {}
        for index in range(seg_count):
            end = struct.unpack(">H", raw[ends_at + index * 2:ends_at + index * 2 + 2])[0]
            begin = struct.unpack(">H", raw[starts_at + index * 2:starts_at + index * 2 + 2])[0]
            delta = struct.unpack(">h", raw[deltas_at + index * 2:deltas_at + index * 2 + 2])[0]
            range_offset = struct.unpack(
                ">H", raw[ranges_at + index * 2:ranges_at + index * 2 + 2])[0]

            if begin == 0xFFFF:
                continue
            for code in range(begin, min(end, 0xFFFE) + 1):
                if range_offset == 0:
                    glyph = (code + delta) & 0xFFFF
                else:
                    address = ranges_at + index * 2 + range_offset + (code - begin) * 2
                    if address + 2 > len(raw):
                        continue
                    glyph = struct.unpack(">H", raw[address:address + 2])[0]
                    if glyph:
                        glyph = (glyph + delta) & 0xFFFF
                if glyph:
                    mapping[code] = glyph
        return mapping

    def _cmap_format12(self, start: int) -> dict[int, int]:
        raw = self._raw
        groups = struct.unpack(">I", raw[start + 12:start + 16])[0]
        mapping: dict[int, int] = {}
        for index in range(min(groups, 40000)):
            at = start + 16 + index * 12
            begin, end, glyph = struct.unpack(">III", raw[at:at + 12])
            for code in range(begin, min(end, begin + 0xFFFF) + 1):
                mapping[code] = glyph + (code - begin)
        return mapping

    # ------------------------------------------------------------------ metrics
    def glyph(self, character: str) -> int:
        return self.cmap.get(ord(character), 0)

    def width(self, glyph_id: int) -> int:
        """Advance width in 1/1000 em, which is what a PDF /W array wants."""
        if 0 <= glyph_id < len(self.advances):
            return round(self.advances[glyph_id] * 1000 / self.units_per_em)
        return 500

    def covers(self, text: str) -> bool:
        """True when every non-space character has a glyph."""
        return all(ord(ch) in self.cmap or ch.isspace() for ch in text)

    def used_widths(self, glyph_ids: set[int]) -> list[int]:
        return [self.width(g) for g in sorted(glyph_ids)]


def load_font(text: str = "") -> EmbeddedFont:
    """First available font; prefer one that covers ``text`` entirely."""
    fallback: EmbeddedFont | None = None

    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent.parent / candidate
        if not path.exists():
            continue
        try:
            font = EmbeddedFont(path)
        except (FontError, struct.error, OSError):
            continue

        if not text or font.covers(text):
            return font
        if fallback is None:
            fallback = font

    if fallback is not None:
        return fallback
    raise FontError("no TrueType font available for PDF export")

# ---------------------------------------------------------------- subsetting
def _loca_offsets(raw: bytes, tables: dict, glyph_count: int, long_format: bool) -> list[int]:
    """Offsets of every glyph inside ``glyf``."""
    start = tables["loca"][0]
    offsets = []
    for index in range(glyph_count + 1):
        if long_format:
            value = struct.unpack(">I", raw[start + index * 4:start + index * 4 + 4])[0]
        else:
            value = struct.unpack(">H", raw[start + index * 2:start + index * 2 + 2])[0] * 2
        offsets.append(value)
    return offsets


def _composite_children(glyph_data: bytes) -> list[int]:
    """Glyph ids referenced by a composite glyph."""
    if len(glyph_data) < 10:
        return []
    contours = struct.unpack(">h", glyph_data[:2])[0]
    if contours >= 0:
        return []

    children: list[int] = []
    position = 10
    while position + 4 <= len(glyph_data):
        flags, child = struct.unpack(">HH", glyph_data[position:position + 4])
        children.append(child)
        position += 4
        position += 4 if flags & 0x0001 else 2      # ARG_1_AND_2_ARE_WORDS
        if flags & 0x0008:                          # WE_HAVE_A_SCALE
            position += 2
        elif flags & 0x0040:                        # WE_HAVE_AN_X_AND_Y_SCALE
            position += 4
        elif flags & 0x0080:                        # WE_HAVE_A_TWO_BY_TWO
            position += 8
        if not flags & 0x0020:                      # MORE_COMPONENTS
            break
    return children


def subset_font(font: EmbeddedFont, used: set[int]) -> bytes:
    """A copy of the font carrying only the glyphs in ``used``.

    Glyph ids are preserved, so ``CIDToGIDMap /Identity`` stays valid and the
    widths table needs no rewriting. Unused glyphs become empty outlines, which
    is what makes a CJK face shrink from 13 MB to a few hundred kilobytes.

    Composite glyphs keep their components: dropping those would blank the
    accented letters and every CJK ideograph built from radicals.
    """
    raw = font._raw
    tables = font._tables
    glyph_count = font.glyph_count
    long_format = font.index_to_loc == 1

    # A CFF face has no outlines this writer can copy: embed it whole.
    if "glyf" not in tables or "loca" not in tables:
        return font.file_bytes

    loca = _loca_offsets(raw, tables, glyph_count, long_format)
    glyf_start = tables["glyf"][0]

    def glyph_bytes(glyph: int) -> bytes:
        if glyph + 1 >= len(loca):
            return b""
        return raw[glyf_start + loca[glyph]:glyf_start + loca[glyph + 1]]

    # Close the set over composite components
    needed = set(used)
    queue = list(used)
    while queue:
        glyph = queue.pop()
        for child in _composite_children(glyph_bytes(glyph)):
            if child not in needed:
                needed.add(child)
                queue.append(child)

    # Rebuild glyf and loca
    new_glyf = bytearray()
    new_loca: list[int] = []

    for glyph in range(glyph_count):
        new_loca.append(len(new_glyf))
        if glyph in needed:
            data = glyph_bytes(glyph)
            new_glyf += data
            while len(new_glyf) % 4:
                new_glyf.append(0)
    new_loca.append(len(new_glyf))

    if long_format:
        loca_bytes = b"".join(struct.pack(">I", value) for value in new_loca)
    else:
        loca_bytes = b"".join(struct.pack(">H", value // 2) for value in new_loca)

    # Tables worth keeping: metrics, hinting and naming. cmap, GSUB and friends
    # are irrelevant once glyph ids are addressed directly.
    keep = ("head", "hhea", "hmtx", "maxp", "cvt ", "fpgm", "prep",
            "name", "OS/2", "post")

    rebuilt: dict[str, bytes] = {}
    for tag in keep:
        if tag in tables:
            offset, length = tables[tag]
            rebuilt[tag] = raw[offset:offset + length]

    rebuilt["glyf"] = bytes(new_glyf)
    rebuilt["loca"] = loca_bytes

    tags = sorted(rebuilt)
    header = struct.pack(">IHHHH", 0x00010000, len(tags), 0, 0, 0)
    directory = bytearray()
    body = bytearray()
    base = 12 + len(tags) * 16

    for tag in tags:
        chunk = rebuilt[tag]
        directory += struct.pack(">4sIII", tag.encode("latin-1"), 0,
                                 base + len(body), len(chunk))
        body += chunk
        while len(body) % 4:
            body.append(0)

    return header + bytes(directory) + bytes(body)

