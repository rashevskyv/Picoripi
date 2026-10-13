"""3DS electronic manual: the line model of the Ukrainian text, ported from the manuals repo's tools/manual.py.

The viewer draws every line of a manual paragraph as its own pane. This module wraps the translation into
lines the same way the build does, so the editor can report a line count, a line width or a word that does not
fit before the owner builds. It has no font file and no repo import: the advances come from widths.json and the
pane geometry from geometry.json (both facts taken from the console dumps).

Two models, as in the gate:
- pane model (small text): each line starts at its own pane x and must end inside its own box.
- column model (large text and the contents): one width per paragraph, the budget from the data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

FONT_EM = 24.0
WIDTH_SLACK = 4.0          # the gate adds this to every column budget
LINE_OFFSET = 8.0          # a line is drawn from pane x + 8
PAGE_EDGE = 310.0          # the text ends by this x in page units
DIGIT_UNITS = 16.3         # measured on the console; the font table says 17
SPACE_UNITS = 8.7          # measured on the console; the font table says 9
SAFETY = 1.0
PANE_PARTS = ("small",)    # the parts laid out with the pane model

MARKER_RE = re.compile(r"\{i(\d+)\}|\{s(\d+)\|([^}]*)\}|(\{br\})")
SPACE_RE = re.compile(r"([ \t\n]+)")
HYPHEN_RE = re.compile(r"(?<=-)(?=.)")
CLOSING = set(".,;:!?)»…")
SHORT_WORDS = set("зуввііййаоокс")
PAGE_WORDS = {"с.", "стор."}
_RUSSIAN_ONLY = set("ыэъёЫЭЪЁ")
_MIXED_WORD = re.compile(r"(?<![\w{}])(?=\w*[A-Za-z])(?=\w*[А-Яа-яІіЇїЄєҐґ])\w+")
_BAD_REFERENCE = re.compile(r"\(\s*с\.\s|стр\.|см\.")
_WORD_APOSTROPHE = re.compile(r"(?<=[^\W\d_])'(?=[^\W\d_])")


class LayoutError(Exception):
    """The text cannot be laid out on the paragraph's lines or panes."""


@dataclass(frozen=True)
class Line:
    x: float      # pane x of the line's first text pane
    box: float    # width of that pane


@dataclass
class Geometry:
    """One paragraph's drawing facts, as geometry.json holds them."""

    part: str
    font_size: float
    char_space: float
    lines: List[Line]
    icon_widths: List[float] = field(default_factory=list)
    fixed: bool = False
    # The column budget the build uses: the widest localisation, recomputed from the dump. None: the JSON width.
    budget: Optional[float] = None
    # Text panes per style, as the build maps them: {0: n} for the paragraph's own style, {1: n} for the next one...
    panes: Dict[int, int] = field(default_factory=dict)

    @property
    def pane_model(self) -> bool:
        return self.part in PANE_PARTS

    def margin(self, line: int) -> float:
        """Where a line starts: the first line may be indented differently."""
        return self.lines[0].x if line == 0 else self.lines[min(1, len(self.lines) - 1)].x


class Widths:
    """Glyph advances (CWDH units at a 24 px em) and the substitutions the build makes before measuring."""

    def __init__(self, data: dict):
        self.advances: Dict[str, float] = {k: float(v) for k, v in data["advances"].items()}
        self.digit = float(data.get("digit", DIGIT_UNITS))
        self.space = float(data.get("space", SPACE_UNITS))
        self.homoglyphs: Dict[str, str] = dict(data.get("homoglyphs", {}))
        self.word_apostrophe = bool(data.get("word_apostrophe", False))

    def glyph(self, ch: str) -> float:
        if ch.isdigit() and ch.isascii():
            return self.digit
        if ch == " ":
            return self.space
        return self.advances.get(ch, 0.0)

    def apply_homoglyphs(self, text: str) -> str:
        if self.homoglyphs:
            text = text.translate(str.maketrans(self.homoglyphs))
        if self.word_apostrophe:
            text = _WORD_APOSTROPHE.sub("ʼ", text)
        return text


def markers(text: str) -> List[str]:
    return sorted(match.group(0).split("|")[0] for match in MARKER_RE.finditer(text))


def text_width(text: str, geo: Geometry, widths: Widths, ignore_char_space: bool) -> float:
    advance = sum(widths.glyph(ch) for ch in text)
    char_space = 0.0 if ignore_char_space else geo.char_space
    return advance * geo.font_size / FONT_EM + char_space * max(len(text) - 1, 0)


@dataclass
class Piece:
    style: int                  # 0 = the paragraph's own style, -1 = an icon, -2 = a hard break
    text: str = ""
    icon: Optional[int] = None  # icon index for style -1
    x: float = 0.0
    width: float = 0.0
    spaced: bool = False


def _atoms(text: str):
    pos = 0
    for match in MARKER_RE.finditer(text):
        if match.start() > pos:
            yield 0, text[pos:match.start()]
        if match.group(1) is not None:
            yield -1, int(match.group(1))
        elif match.group(4):
            yield -2, None
        else:
            yield int(match.group(2)), match.group(3)
        pos = match.end()
    if pos < len(text):
        yield 0, text[pos:]


class _Model:
    """The measuring and wrapping of one paragraph."""

    def __init__(self, geo: Geometry, widths: Widths, ignore_char_space: bool):
        self.geo = geo
        self.widths = widths
        self.ignore = ignore_char_space

    def measure(self, text: str) -> float:
        return text_width(text, self.geo, self.widths, self.ignore) * SAFETY

    def words(self, text: str, limit: float, split_styles: bool) -> List[Tuple[bool, List[Piece]]]:
        icon_widths = self.geo.icon_widths
        words: List[Tuple[bool, List[Piece]]] = [(False, [])]

        def open_word(glue: bool) -> None:
            if words[-1][1]:
                words.append((glue, []))

        for style, payload in _atoms(text):
            if style == -2:
                open_word(False)
                words[-1][1].append(Piece(style=-2))
                open_word(False)
                continue
            if style < 0:
                if payload >= len(icon_widths):
                    raise LayoutError(f"no icon {{i{payload}}} on this paragraph")
                words[-1][1].append(Piece(style=-1, icon=payload, width=icon_widths[payload]))
                continue
            whole = self.measure(payload)
            if split_styles and style:
                open_word(False)
            glued = sum(piece.width for piece in words[-1][1])
            if style and " " in payload.strip() and glued + whole <= limit:
                words[-1][1].append(Piece(style=style, text=payload.strip(), width=whole))
                continue
            chunks = [c for c in re.split(SPACE_RE, payload) if c]
            for index, chunk in enumerate(chunks):
                if SPACE_RE.fullmatch(chunk):
                    last = words[-1][1][-1].text.strip().lower() if words[-1][1] and words[-1][1][-1].icon is None else ""
                    follows = chunks[index + 1] if index + 1 < len(chunks) else ""
                    if last in PAGE_WORDS and follows[:1].isdigit():
                        continue
                    if last in ("(див.", "див.") and follows.strip().lower() in PAGE_WORDS:
                        continue
                    open_word(False)
                    continue
                for part_index, part in enumerate(HYPHEN_RE.split(chunk)):
                    if part_index:
                        open_word(True)
                    words[-1][1].append(Piece(style=style, text=part, width=self.measure(part)))
        return [word for word in words if word[1]]

    def wrap(self, text: str, limit: float, pane: bool, line_count: int) -> List[List[Piece]]:
        geo = self.geo
        space = self.measure(" ")

        def pane_line(index: int) -> Line:
            if index >= len(geo.lines):
                raise LayoutError(f"needs {index + 1} lines, the paragraph has {len(geo.lines)}")
            return geo.lines[index]

        def margin_of(index: int) -> float:
            return pane_line(index).x if pane else geo.margin(index)

        def cap_of(index: int) -> float:
            if not pane:
                return limit
            line = pane_line(index)
            return min(line.box - LINE_OFFSET, PAGE_EDGE - line.x)

        lines: List[List[Piece]] = [[]]
        x = margin_of(0)
        words = self.words(text, max(line.box for line in geo.lines) if pane else limit, split_styles=pane)
        for glue, word in words:
            if word[0].style == -2:
                lines.append([])
                x = margin_of(len(lines) - 1)
                continue
            width = sum(piece.width for piece in word)
            first = word[0]
            closing = first.icon is None and first.text[:1] in CLOSING
            gap = 0.0 if glue or closing or not lines[-1] else space
            if lines[-1] and not closing and x + gap + width > margin_of(len(lines) - 1) + cap_of(len(lines) - 1):
                carried: List[Piece] = []
                current = lines[-1]
                if len(current) > 1 and current[-1].icon is None and current[-1].spaced:
                    tail = current[-1].text.strip().lower()
                    if tail and tail in SHORT_WORDS and current[-1].style == 0:
                        carried = [current.pop()]
                lines.append([])
                x = margin_of(len(lines) - 1)
                gap = 0.0
                for piece in carried:
                    piece.x = x
                    piece.spaced = False
                    lines[-1].append(piece)
                    x += piece.width
                if carried:
                    gap = space
                    x += gap
            x += gap
            for index, piece in enumerate(word):
                piece.x = x
                piece.spaced = index == 0 and gap > 0
                lines[-1].append(piece)
                x += piece.width
            if pane and x > margin_of(len(lines) - 1) + cap_of(len(lines) - 1) + 0.01:
                shown = "".join(p.text for p in word if p.icon is None)
                raise LayoutError(
                    f"word {shown!r} is {x - margin_of(len(lines) - 1):.1f} px, its pane box holds "
                    f"{cap_of(len(lines) - 1):.1f} px"
                )
        if pane and len(lines) > line_count:
            raise LayoutError(f"needs {len(lines)} lines, the paragraph has {line_count}")
        if pane and len(lines) >= 2:
            self._orphan_rule(lines, space, margin_of, cap_of)
        return lines

    def _orphan_rule(self, lines, space, margin_of, cap_of) -> None:
        last_index = len(lines) - 1
        last = lines[last_index]
        if len(last) != 1 or last[0].icon is not None or len(last[0].text.strip()) > 2:
            return
        prev = lines[last_index - 1]
        starts = [i for i, piece in enumerate(prev) if piece.spaced or i == 0]
        if not starts or any(piece.icon is not None for piece in prev[starts[-1]:]):
            return
        tail = prev[starts[-1]:]
        if len(prev) == len(tail):
            return
        width = sum(p.width for p in tail) + space + last[0].width
        if width > cap_of(last_index):
            return
        del prev[starts[-1]:]
        x = margin_of(last_index)
        moved = []
        for piece in tail:
            piece.x = x
            piece.spaced = False
            moved.append(piece)
            x += piece.width
        last[0].x = x + space
        last[0].spaced = True
        lines[last_index] = moved + last


def layout_for(text: str, geo: Geometry, limit: float, widths: Widths, line_count: int
               ) -> Tuple[List[List[Piece]], str, str]:
    """-> (lines, mode, reason). Pane model for small text. A small paragraph the pane model cannot fit falls back
    to the column model, as the gate does: mode "column-fallback" and reason is the pane error. Otherwise mode is
    "pane" or "column" and reason is empty."""
    if geo.pane_model:
        try:
            return _Model(geo, widths, ignore_char_space=True).wrap(text, limit, True, line_count), "pane", ""
        except LayoutError as error:
            lines = _Model(geo, widths, ignore_char_space=False).wrap(text, limit, False, line_count)
            return lines, "column-fallback", str(error)
    return _Model(geo, widths, ignore_char_space=False).wrap(text, limit, False, line_count), "column", ""


def line_overflow(lines: List[List[Piece]], geo: Geometry, limit: float) -> List[float]:
    """How far past the column each laid-out line reaches, in pixels (negative: inside)."""
    out = []
    for index, line in enumerate(lines):
        if not line:
            out.append(float("-inf"))
            continue
        last = line[-1]
        out.append(last.x + last.width - geo.margin(index) - limit)
    return out


def pane_overflow(lines: List[List[Piece]], panes: Dict[int, int]) -> Optional[Tuple[int, int]]:
    """The first style whose pieces need more text panes than the paragraph has: (style, panes), else None.

    The build (manual.to_edits) gives each piece one free pane of its style. Neighbouring pieces of one style on one
    line share a pane, and an icon ends that sharing. Panes are not given back, so a style runs out in order.
    """
    counts: Dict[int, int] = {}
    for line in lines:
        last: Optional[int] = None
        for piece in line:
            if piece.icon is not None:
                last = None
                continue
            if last is not None and piece.style == last:
                continue
            last = piece.style
            counts[piece.style] = counts.get(piece.style, 0) + 1
            if counts[piece.style] > panes.get(piece.style, 0):
                return piece.style, panes.get(piece.style, 0)
    return None


def line_text(line: List[Piece]) -> str:
    return "".join(piece.text if piece.icon is None and piece.style != -2 else "" for piece in line).strip()


def style_problems(ua: str) -> List[str]:
    """Checks on the words, not the layout (the gate's style_problems)."""
    out: List[str] = []
    bare = MARKER_RE.sub(lambda m: m.group(3) or "", ua)
    stray = sorted({ch for ch in bare if ch in _RUSSIAN_ONLY})
    if stray:
        out.append(f"Russian letters {stray} in the Ukrainian text")
    if "  " in ua:
        out.append("double space")
    if ua != ua.strip():
        out.append("leading or trailing space")
    words = _MIXED_WORD.findall(bare)
    if words:
        out.append(f"mixed Latin and Cyrillic in one word {words[:3]}")
    if re.search(r"\bлице\b", bare):
        out.append("«лице» (the manual says «обличчя»)")
    if _BAD_REFERENCE.search(bare):
        out.append("page reference form (use «стор. N»)")
    return out


def missing_glyphs(text: str, widths: Widths) -> List[str]:
    """Characters the font has no advance for (zero width means no glyph in the table)."""
    body = MARKER_RE.sub(lambda m: m.group(3) or "", text)
    return sorted({ch for ch in body if not ch.isspace() and widths.glyph(ch) == 0})


def check_entry(ua: str, ru: str, entry: dict, geo: Optional[Geometry], widths: Widths) -> List[Tuple[str, str]]:
    """Problems of one translated paragraph -> [(problem key, message)]. Empty ua is not checked."""
    if not ua:
        return []
    problems: List[Tuple[str, str]] = []
    if markers(ua) != markers(ru):
        return [("MARKUP", f"markers {markers(ua)} differ from the Russian {markers(ru)}")]
    for text in style_problems(ua):
        problems.append(("STYLE", text))
    glyphs = missing_glyphs(widths.apply_homoglyphs(ua), widths)
    if glyphs:
        problems.append(("GLYPH", f"no glyph for {glyphs}"))
    if geo is None:
        return problems
    rendered = widths.apply_homoglyphs(ua)
    # The build's own budget when the geometry has it: the JSON width is a copy made at extraction time and is stale.
    budget = float(geo.budget if geo.budget is not None else entry.get("width") or 0.0)
    limit = budget + WIDTH_SLACK
    line_count = int(entry.get("lines") or len(geo.lines))
    lines, mode, reason = layout_for(rendered, geo, limit, widths, line_count)
    if mode == "column-fallback":
        # The gate lays such a paragraph out on the column instead and only lists it: here it is a problem.
        problems.append(("WORD", f"does not fit its pane box, shown on the column instead: {reason}"))
    if len(lines) > line_count:
        problems.append(("LINES", f"needs {len(lines)} lines, the paragraph has {line_count}"))
    # The build places the lines on the paragraph's panes; a paragraph it cannot place is not measured for width.
    if not geo.fixed and len(lines) <= len(geo.lines) and geo.panes:
        over = pane_overflow(lines, geo.panes)
        if over:
            problems.append(("PANES", f"out of panes for style {over[0]} (the original has {over[1]})"))
            return problems
    # The gate skips the column check for every small paragraph, the column fallback included.
    if geo.pane_model or not budget:
        return problems
    past = line_overflow(lines, geo, limit)
    worst = max(range(len(past)), key=past.__getitem__)
    if past[worst] > 0:
        problems.append(("WIDTH", f"line {worst + 1} is {past[worst]:.0f} px past the {budget:.0f} px column"))
    return problems
