"""3DS electronic manual: the line model of the Ukrainian text, ported from the manuals repo's tools/manual.py.

The viewer draws every line of a manual paragraph as its own pane. This module wraps the translation into
lines the same way the build does (the owner's model, round 19: every glyph at fontSize / 25 with the pane's
charSpace, lines kept inside the card edge and clear of the pictures and frames beside them), then measures
every stored line the way the console draws it (console_render's constants) and reports what the console will
show wrong. It has no font file and no repo import: the advances and the ink overhangs come from widths.json
and the pane geometry from geometry.json (both facts taken from the console dumps).

Two models for the build's placement, as in the gate:
- pane model (small text): each line starts at its own pane x and must end by the card edge of its pane.
- column model (large text and the contents): the lines start at the paragraph margin and end by the card edge.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple

from .console_render import COLUMN_WIDTH, FONT_WIDTH, FRAME_INNER, SUB_PIXEL, WRAP_SLACK

CARD_EDGE = float(COLUMN_WIDTH)   # the build keeps every line inside the card (manual.CARD_EDGE)
BOX_PADDING = WRAP_SLACK + 0.5    # the build widens a pane to its text plus this (manual.to_edits)
SAFETY = 1.0
PANE_PARTS = ("small",)           # the parts laid out with the pane model
PANE_MARGIN = 0.0                 # extra safety the pane model keeps (manual.PANE_MARGIN)
ICON_GAP = 1.5                    # a line keeps this clear of an inline icon that follows it
SPLIT_STYLES = True               # a highlighted run starts a new word in the pane model
# Pictures and frames beside a line (manual.right_limit): a picture counts when it is at least this big, the
# line stops this far short of its left edge; a frame is a box only when big enough, and the text stops at its
# inner edge (its right edge less the frame texture's width, or FRAME_MARGIN when the width is not known).
OCC_START = 0.0            # where a line's ink starts, relative to its pane x (calibration; 0 on the console)
OCC_MARGIN = 4.0
OCC_BOX_MIN_W = 200.0
OCC_BOX_MIN_H = 40.0
FRAME_MARGIN = 12.0

MARKER_RE = re.compile(r"\{i(\d+)\}|\{s(\d+)\|([^}]*)\}|(\{br\})")
SPACE_RE = re.compile(r"([ \t\n]+)")
HYPHEN_RE = re.compile(r"(?<=-)(?=.)")
CLOSING = set(".,;:!?)»…")
SHORT_WORDS = set("зуввііййаоокс")
PAGE_WORDS = {"с.", "стор."}
_RUSSIAN_ONLY = set("ыэъёЫЭЪЁ")
_MIXED_WORD = re.compile(r"(?<![\w{}])(?=\w*[A-Za-z])(?=\w*[А-Яа-яІіЇїЄєҐґ])\w+")
_BAD_REFERENCE = re.compile(r"\(\s*с\.\s|\bстр\.|\bсм\.")  # \b: "стр." and "см." as words, not "Настр." or "просм."
_WORD_APOSTROPHE = re.compile(r"(?<=[^\W\d_])'(?=[^\W\d_])")


class LayoutError(Exception):
    """The text cannot be laid out on the paragraph's lines or panes."""


def fingerprint(keys: List[str]) -> str:
    """Which manual a file is: a hash of its keys in order (the keys come from the console's own document)."""
    return hashlib.sha1("\n".join(keys).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Line:
    """One text pane of a paragraph line, as geometry.json holds it (the first pane of a line is the line)."""

    x: float      # pane x (local to its group)
    box: float    # width of the pane
    # The pane's page position (its groups added) and the line step: Geometry.right_limit().
    abs_x: float = 0.0
    abs_y: float = 0.0
    step: float = 20.0
    char_space: float = 0.0
    style: int = 0          # 0 = the paragraph's own style, 1.. the highlighted ones in order of appearance
    origin: int = 0         # the 3 x 3 origin grid of the pane (0: placed by its top-left corner)
    text_pos: int = 0       # the text block's place in the box (3 x 3 grid), and the line alignment
    text_align: int = 0
    mark: str = ""          # a button glyph or sign pane: its text (it stays in its pane when the translation drops it)


@dataclass(frozen=True)
class Occluder:
    """A picture (pic1) or a window (wnd1) of the page, in page coordinates (BCLYT y: 0 at the top, down is negative)."""

    kind: str
    abs_x: float
    abs_y: float
    width: float
    height: float
    frame_width: Optional[float] = None   # wnd1: the width of its right frame texture, when the dump has it


@dataclass
class Geometry:
    """One paragraph's drawing facts, as geometry.json holds them."""

    part: str
    font_size: float
    char_space: float
    # The text panes of each line: a list of Line (one pane per line) or a list of lists of Line.
    lines: List[Any]
    icon_widths: List[float] = field(default_factory=list)
    fixed: bool = False
    # The column budget the build uses: the widest localisation, recomputed from the dump. None: the JSON width.
    budget: Optional[float] = None
    # Pictures and frames of the paragraph's page that a line can run into.
    occluders: List[Occluder] = field(default_factory=list)
    # Glyph and sign panes the translation leaves in their own pane (marks_out()).
    kept_marks: str = ""

    def __post_init__(self) -> None:
        self.rows: List[List[Line]] = [[row] if isinstance(row, Line) else list(row) for row in self.lines]
        self.lines = [row[0] for row in self.rows]

    @property
    def pane_model(self) -> bool:
        return self.part in PANE_PARTS

    @property
    def pools(self) -> Dict[int, List[Line]]:
        """The text panes by style, in page order: the panes the build gives the pieces of that style."""
        out: Dict[int, List[Line]] = {}
        for row in self.rows:
            for pane in row:
                out.setdefault(pane.style, []).append(pane)
        return out

    @property
    def pane_counts(self) -> Dict[int, int]:
        return {style: len(panes) for style, panes in self.pools.items()}

    def marks_out(self, ua: str) -> "Geometry":
        """The paragraph without the glyph and sign panes the translation leaves out (manual.mark_panes_out).

        Such a pane stays where Nintendo drew it: it is no line and no pane of the layout. Only the paragraph's own
        style counts, and a paragraph with no pane left is left whole.
        """
        marks: List[str] = []
        rows: List[List[Line]] = []
        for row in self.rows:
            keep: List[Line] = []
            for pane in row:
                if pane.style == 0 and pane.mark and pane.mark not in ua:
                    marks.append(pane.mark)
                else:
                    keep.append(pane)
            if keep:
                rows.append(keep)
        if not marks or not rows:
            return self
        return replace(self, lines=rows, char_space=rows[0][0].char_space, kept_marks="".join(marks))

    def margin(self, line: int) -> float:
        """Where a line starts: the first line may be indented differently."""
        return self.lines[0].x if line == 0 else self.lines[min(1, len(self.lines) - 1)].x

    def abs_margin(self, line: int) -> float:
        """Page position of the margin() that line `line` reads."""
        return self.lines[0].abs_x if line == 0 else self.lines[min(1, len(self.lines) - 1)].abs_x

    def pane_x(self, line: int) -> float:
        """Pane model: line `line` starts at the x of its own pane."""
        if line >= len(self.lines):
            raise LayoutError(f"needs {line + 1} lines, the paragraph has {len(self.lines)}")
        return self.lines[line].x

    def right_limit(self, line: int, picture_margin: float = OCC_MARGIN, frame_margin: float = FRAME_MARGIN) -> float:
        """Absolute x a line must end before, because a picture or frame sits beside it (inf: none).

        A line is in the way of an occluder when their vertical extents overlap. A picture to the right of the
        line's start ends the line before its left edge; a frame the line starts inside ends it at its inner edge
        (the right edge less the frame texture's width, never less than FRAME_INNER; `frame_margin` when the
        width is not known). A line past the paragraph's own lines continues below the last one.
        """
        last = len(self.lines) - 1
        pane = self.lines[min(line, last)]
        top = pane.abs_y - max(line - last, 0) * pane.step
        bottom = top - pane.step
        left = pane.abs_x + OCC_START
        limit = float("inf")
        for occluder in self.occluders:
            occ_top = occluder.abs_y
            occ_bottom = occ_top - occluder.height
            # A picture that only touches the line's band (within a pixel) is not in the way of it.
            if not (occ_bottom < top - 1.0 and occ_top > bottom + 1.0):
                continue
            right = occluder.abs_x + occluder.width
            if occluder.kind == "pic1" and occluder.abs_x > left:
                limit = min(limit, occluder.abs_x - picture_margin)
            elif (occluder.kind == "wnd1" and occluder.abs_x <= left < right
                  and occluder.width >= OCC_BOX_MIN_W and occluder.height >= OCC_BOX_MIN_H):
                frame = occluder.frame_width
                limit = min(limit, right - (frame_margin if frame is None else max(frame, FRAME_INNER)))
        return limit

    def room(self, line: int, pane: bool) -> float:
        """Width line `line` may take before the nearest picture or frame beside it, measured from its start (inf: none).

        The start is the line's pane x (pane model) or the paragraph margin (column model), both in page coordinates.
        """
        start = (self.lines[line].abs_x if pane else self.abs_margin(line)) + OCC_START
        limit = self.right_limit(line)
        if limit == float("inf"):
            return limit
        return limit - start

    def edge_width(self, pane: Line) -> float:
        """Most a line of `pane` may be wide and still end by CARD_EDGE, from where the viewer starts it.

        The viewer starts a line at the pane's origin corner, moved by its alignment within the box
        (text_pos % 3 when text_align is 0): start = left + (box - width) * align / 2.
        """
        origin = (pane.origin % 3) * 0.5
        align = (pane.text_pos % 3 if pane.text_align == 0 else pane.text_align - 1) * 0.5
        room = CARD_EDGE - pane.abs_x + origin * pane.box - pane.box * align
        if align >= 1.0:
            return float("inf") if room >= 0 else 0.0
        return room / (1.0 - align)


class Widths:
    """Glyph advances and ink overhangs (CWDH units at the console's 25-unit em) and the build's substitutions."""

    def __init__(self, data: dict):
        self.advances: Dict[str, float] = {k: float(v) for k, v in data["advances"].items()}
        # Units between a glyph's ink and the end of its advance (negative: the ink runs past the advance).
        self.overhangs: Dict[str, float] = {k: float(v) for k, v in data.get("overhangs", {}).items()}
        self.homoglyphs: Dict[str, str] = dict(data.get("homoglyphs", {}))
        self.word_apostrophe = bool(data.get("word_apostrophe", False))

    def glyph(self, ch: str) -> float:
        return self.advances.get(ch, 0.0)

    def overhang(self, ch: str, font_size: float) -> float:
        """Pixels between the right edge of a glyph's ink and the end of its advance (0 for a space or an unknown glyph)."""
        if ch.isspace():
            return 0.0
        return self.overhangs.get(ch, 0.0) * font_size / FONT_WIDTH

    def apply_homoglyphs(self, text: str) -> str:
        if self.homoglyphs:
            text = text.translate(str.maketrans(self.homoglyphs))
        if self.word_apostrophe:
            text = _WORD_APOSTROPHE.sub("ʼ", text)
        return text


def markers(text: str) -> List[str]:
    return sorted(match.group(0).split("|")[0] for match in MARKER_RE.finditer(text))


def text_width(text: str, geo: Geometry, widths: Widths, char_space: Optional[float] = None) -> float:
    """The advance the console draws `text` with: each glyph at fontSize / FONT_WIDTH, charSpace between glyphs."""
    advance = sum(widths.glyph(ch) for ch in text)
    cs = geo.char_space if char_space is None else char_space
    return advance * geo.font_size / FONT_WIDTH + cs * max(len(text) - 1, 0)


def measure(text: str, geo: Geometry, widths: Widths, char_space: Optional[float] = None) -> float:
    return text_width(text, geo, widths, char_space) * SAFETY


@dataclass
class Piece:
    style: int                  # 0 = the paragraph's own style, -1 = an icon, -2 = a hard break
    text: str = ""
    icon: Optional[int] = None  # icon index for style -1
    x: float = 0.0
    width: float = 0.0
    spaced: bool = False


def tail_overhang(pieces: List[Piece], geo: Geometry, widths: Widths) -> float:
    """The overhang of the last glyph of a run of pieces (icons have none): how far its ink ends before its advance."""
    for piece in reversed(pieces):
        if piece.icon is None:
            text = piece.text.rstrip()
            return widths.overhang(text[-1], geo.font_size) if text else 0.0
        return 0.0
    return 0.0


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


def _words(text: str, geo: Geometry, widths: Widths, limit: float, split_styles: bool
           ) -> List[Tuple[bool, List[Piece]]]:
    """Break the markup into words -> [(glued to the previous word, pieces), ...] (manual._words)."""
    icon_widths = geo.icon_widths
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
        # A highlighted run is one pane: it stays whole while it fits a line.
        whole = measure(payload, geo, widths)
        if style:
            open_word(False)
        if style and " " in payload.strip() and whole <= limit:
            words[-1][1].append(Piece(style=style, text=payload.strip(), width=whole))
            continue
        chunks = [c for c in re.split(SPACE_RE, payload) if c]
        for index, chunk in enumerate(chunks):
            if SPACE_RE.fullmatch(chunk):
                # "с. 4" / "стор. 6": the page word and its number stay on one row.
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
                words[-1][1].append(Piece(style=style, text=part, width=measure(part, geo, widths)))
    return [word for word in words if word[1]]


def layout(text: str, geo: Geometry, widths: Widths, pane: bool) -> List[List[Piece]]:
    """Wrap the marked-up translation into lines of pieces, greedily (manual.layout).

    Each text piece is priced with the charSpace of the pane it will be drawn in (per style, in order; a run of
    one style on one line shares its pane). A closing mark stays with the word before it; a one-letter word at
    the end of a line moves down with the next word. `pane`: the pane model, where line i starts at its own
    pane's x and must end by the card edge; a word that cannot is an error (the viewer would break it).
    """
    pools = geo.pools
    lines: List[List[Piece]] = [[]]

    def cs_of(text_pane: Optional[Line]) -> float:
        return geo.char_space if text_pane is None else text_pane.char_space

    def place(pieces: List[Piece], state):
        """Widths and panes of `pieces` placed after `state` = (panes taken per style, last text style, its pane)."""
        taken, last_style, last_pane = state
        taken = dict(taken)
        out: List[float] = []
        panes_out: List[Optional[Line]] = []
        for piece in pieces:
            if piece.icon is not None:
                out.append(piece.width)
                panes_out.append(None)
                last_style, last_pane = None, None
                continue
            if piece.style == last_style and last_pane is not None:
                target: Optional[Line] = last_pane
            else:
                index = taken.get(piece.style, 0)
                pool = pools.get(piece.style, [])
                target = pool[index] if index < len(pool) else None
                taken[piece.style] = index + 1
                last_style, last_pane = piece.style, target
            out.append(measure(piece.text, geo, widths, cs_of(target)))
            panes_out.append(target)
        return (out, panes_out), (taken, last_style, last_pane)

    def gap_on(state) -> float:
        cs = cs_of(state[2])
        # A space is one glyph with a charSpace on each side of it (text_width counts the one in between).
        return measure(" ", geo, widths, cs) + 2 * cs

    def margin_of(index: int) -> float:
        return geo.pane_x(index) if pane else geo.margin(index)

    def cap_of(index: int) -> float:
        if not pane:
            # Column model: up to the card edge, never past a picture or frame the line runs beside.
            # 0.5 px of rounding room: a word-by-word sum and the merged line differ by a tenth of a pixel.
            return min(CARD_EDGE, geo.room(index, pane=False), CARD_EDGE - geo.abs_margin(index)) - 0.5
        # The box is not a limit (the build widens it to the line): only the card edge and what is beside the line.
        return min(geo.edge_width(geo.lines[index]), geo.room(index, pane=True)) - PANE_MARGIN

    state = ({}, None, None)
    x = margin_of(0)
    words = _words(text, geo, widths, max(cap_of(i) for i in range(len(geo.lines))), split_styles=pane and SPLIT_STYLES)
    next_word = 0
    while next_word < len(words):
        glue, word = words[next_word]
        next_word += 1
        if word[0].style == -2:
            lines.append([])
            state = (state[0], None, None)
            x = margin_of(len(lines) - 1)
            continue
        first = word[0]
        closing = first.icon is None and first.text[:1] in CLOSING
        gap = 0.0 if glue or closing or not lines[-1] else gap_on(state)
        (widths_now, panes_now), after = place(word, state)
        if (not lines[-1] and len(word) == 1 and word[0].style > 0 and word[0].icon is None
                and " " in word[0].text.strip() and sum(widths_now) > cap_of(len(lines) - 1)):
            # A highlighted run wider than the line it starts is broken into its words, which take the panes of
            # that style one after another.
            chunks = [c for c in re.split(SPACE_RE, word[0].text.strip()) if c and not SPACE_RE.fullmatch(c)]
            words[next_word:next_word] = [(glue if n == 0 else False, [Piece(style=word[0].style, text=c)])
                                          for n, c in enumerate(chunks)]
            continue
        # Pieces that join without a space (a hyphen, a glued run) carry the charSpace of the pane between them.
        width = sum(widths_now) + sum(
            cs_of(pane_i) for index, (piece, pane_i) in enumerate(zip(word, panes_now))
            if index and piece.icon is None and word[index - 1].icon is None and pane_i is not None
        )
        if not gap and lines[-1] and lines[-1][-1].icon is None and word[0].icon is None and panes_now[0] is not None:
            width += cs_of(panes_now[0])  # glued to the word before it: that join carries a charSpace too
        if any(piece.icon is not None for piece in word):
            width += ICON_GAP
        # A closing mark stays with the word before it, unless the pane model has no room for the pair.
        if (lines[-1] and (not closing or pane)
                and x + gap + width - tail_overhang(word, geo, widths) > margin_of(len(lines) - 1) + cap_of(len(lines) - 1)):
            carried: List[Piece] = []
            current = lines[-1]
            if len(current) > 1 and current[-1].icon is None and current[-1].spaced:
                tail = current[-1].text.strip().lower()
                if tail and tail in SHORT_WORDS and current[-1].style == 0:
                    carried = [current.pop()]
            lines.append([])
            state = (state[0], None, None)
            x = margin_of(len(lines) - 1)
            gap = 0.0
            (carried_widths, _carried_panes), state = place(carried, state)
            for piece, piece_width in zip(carried, carried_widths):
                piece.width = piece_width
                piece.x = x
                piece.spaced = False
                lines[-1].append(piece)
                x += piece_width
            if carried:
                gap = gap_on(state)
                x += gap
            (widths_now, panes_now), after = place(word, state)
        x += gap
        state = after
        for index, (piece, piece_width, pane_i) in enumerate(zip(word, widths_now, panes_now)):
            spaced_now = index == 0 and gap > 0
            if piece.icon is not None and lines[-1] and lines[-1][-1].icon is None:
                x += ICON_GAP  # an icon after text keeps the clearance a picture gets
            elif piece.icon is None and lines[-1] and lines[-1][-1].icon is None and not spaced_now and pane_i is not None:
                x += cs_of(pane_i)  # a join without a space: the charSpace between the two runs
            piece.width = piece_width
            piece.x = x
            piece.spaced = spaced_now
            lines[-1].append(piece)
            x += piece_width
        if pane and x - tail_overhang(word, geo, widths) > margin_of(len(lines) - 1) + cap_of(len(lines) - 1) + 0.01:
            shown = "".join(p.text for p in word if p.icon is None)
            raise LayoutError(f"{shown!r} does not fit its pane box ({x - margin_of(len(lines) - 1):.1f}px "
                              f"in {cap_of(len(lines) - 1):.1f}px)")

    if pane and len(lines) > len(geo.lines):
        raise LayoutError(f"needs {len(lines)} lines, the paragraph has {len(geo.lines)}")
    if pane and len(lines) >= 2:
        _orphan_rule(lines, gap_on(({}, None, None)), margin_of, cap_of)
    return lines


def _orphan_rule(lines, space, margin_of, cap_of) -> None:
    """Pane model: a last row of one or two characters moves its neighbour word down, if that fits the last pane."""
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


def layout_for(text: str, geo: Geometry, widths: Widths) -> Tuple[List[List[Piece]], str, str]:
    """-> (lines, mode, reason). Pane model for small text. A small paragraph the pane model cannot fit (a word
    too wide, too many lines, out of panes) falls back to the column model, as the build does: mode
    "column-fallback" and reason is the pane error. Otherwise mode is "pane" or "column" and reason is empty."""
    if geo.fixed:
        # A contents entry is one line: the list widget truncates it with an ellipsis and never wraps it.
        return [[Piece(style=0, text=text, width=measure(text, geo, widths))]], "column", ""
    if not geo.pane_model:
        return layout(text, geo, widths, pane=False), "column", ""
    try:
        lines = layout(text, geo, widths, pane=True)
        over = pane_overflow(lines, geo.pane_counts)  # the build also needs a pane for every piece of every style
        if over:
            raise LayoutError(f"out of panes for style {over[0]} (the original has {over[1]})")
        return lines, "pane", ""
    except LayoutError as error:
        return layout(text, geo, widths, pane=False), "column-fallback", str(error)


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
    """Characters outside the font's charset (the gate's check: ord(ch) not in the charset file, plus the patched letters)."""
    body = MARKER_RE.sub(lambda m: m.group(3) or "", text)
    return sorted({ch for ch in body if not ch.isspace() and ch not in widths.advances})


def pua_counts(text: str) -> Counter:
    """Private-use code points (the console's button glyphs) of a string, with their counts."""
    return Counter(ch for ch in text if 0xE000 <= ord(ch) <= 0xF8FF)


def _codepoints(counts: Counter) -> str:
    return " ".join(f"U+{ord(ch):04X}x{n}" if n > 1 else f"U+{ord(ch):04X}" for ch, n in sorted(counts.items())) or "none"


def icon_problems(ua: str, source: str, kept: str = "") -> str:
    """The button glyphs of the source must all come back in the translation, the same count of each.

    A dropped glyph shows as a gap where the button name was, so this is a gate. A glyph in a pane of its own
    (`kept`) stays there untouched: the translation must not repeat it, and need not carry it. "" when they match.
    """
    want, have = pua_counts(source), pua_counts(ua)
    kept_counts = pua_counts(kept)
    repeated = [ch for ch in kept_counts if ch in have]
    if repeated:
        return f"button glyph {_codepoints(Counter(repeated))} is drawn in its own pane and must not be in the translation"
    want = want - kept_counts
    if want == have:
        return ""
    return f"button glyphs {_codepoints(have)} in the translation, {_codepoints(want)} in the source"


def console_width(text: str, geo: Geometry, widths: Widths, char_space: Optional[float] = None) -> float:
    """The advance the console gives a stored line: glyph advances at fontSize / FONT_WIDTH plus charSpace."""
    return text_width(text, geo, widths, char_space)


def _stored_line(line: List[Piece]) -> Tuple[str, float]:
    """The text the build writes for a laid-out line and the icons' width on it (icons are picture panes)."""
    text = ""
    icons = 0.0
    for piece in line:
        if piece.icon is not None:
            icons += piece.width
        elif piece.style != -2:
            text += (" " if piece.spaced and text else "") + piece.text
    return text, icons


def console_problems(lines: List[List[Piece]], geo: Geometry, widths: Widths, pane: bool) -> List[Tuple[str, str]]:
    """What the console shows wrong on the lines the build writes (console_render's constants).

    - WRAP: the line is wider than its pane box less WRAP_SLACK, so the viewer breaks it inside the pane and
      its end lands on the next line (the pane box is the stored one, widened by the build to the text it measured);
    - WIDTH: the line's ink runs past the card's right edge (COLUMN_WIDTH) onto the scroll track;
    - BESIDE: the line's ink runs past a picture's left edge or past a box frame's inner edge.
    Overruns under SUB_PIXEL are not reported: the console rounds them away.
    """
    out: List[Tuple[str, str]] = []
    last = len(geo.lines) - 1
    for index, line in enumerate(lines):
        if not line:
            continue
        text, icons = _stored_line(line)
        first = geo.lines[min(index, last)]
        width = console_width(text, geo, widths, first.char_space) + icons
        tail = text.rstrip()
        ink = width - (widths.overhang(tail[-1], geo.font_size) if tail else 0.0)
        if pane:
            local, start = first.x, first.abs_x
        else:
            local, start = geo.margin(index), geo.abs_margin(index)
        owner_width = line[-1].x + line[-1].width - local
        box = max(first.box, owner_width + BOX_PADDING)
        if width > box - WRAP_SLACK + 0.01:
            out.append(("WRAP", f"line {index + 1} is {width:.0f} px in a {box:.0f} px pane; the console breaks it inside"))
        if start + ink > COLUMN_WIDTH + SUB_PIXEL:
            out.append(("WIDTH", f"line {index + 1} runs {start + ink - COLUMN_WIDTH:.0f} px past the card edge"))
        edge = geo.right_limit(index, 0.0, FRAME_INNER)
        if edge != float("inf") and start + ink > edge + SUB_PIXEL:
            out.append(("BESIDE", f"line {index + 1} runs {start + ink - edge:.0f} px into the picture or frame"))
    return out


def check_entry(ua: str, ru: str, entry: dict, geo: Optional[Geometry], widths: Widths) -> List[Tuple[str, str]]:
    """Problems of one translated paragraph -> [(problem key, message)]. Empty ua is not checked.

    The build's placement (the owner's model) decides the lines; the console's measure (console_problems)
    decides what is wrong with them, so the problems agree with the simulator's render."""
    if not ua:
        return []
    if markers(ua) != markers(ru):
        return [("MARKUP", f"markers {markers(ua)} differ from the Russian {markers(ru)}")]
    problems: List[Tuple[str, str]] = []
    if geo is not None:
        geo = geo.marks_out(ua)
    icons = icon_problems(ua, ru or entry.get("en", ""), geo.kept_marks if geo is not None else "")
    if icons:
        problems.append(("ICON", icons))
    for text in style_problems(ua):
        problems.append(("STYLE", text))
    glyphs = missing_glyphs(widths.apply_homoglyphs(ua), widths)
    if glyphs:
        problems.append(("GLYPH", f"no glyph for {glyphs}"))
    if geo is None:
        return problems
    rendered = widths.apply_homoglyphs(ua)
    lines, mode, reason = layout_for(rendered, geo, widths)
    if mode == "column-fallback":
        # The build lays such a paragraph out on the column instead and only lists it: here it is a problem.
        problems.append(("WORD", f"does not fit its pane box, shown on the column instead: {reason}"))
    # A paragraph the build cannot place (the gate's "needs N lines", "out of panes") is not measured for width.
    if len(lines) > len(geo.lines):
        problems.append(("LINES", f"needs {len(lines)} lines, the paragraph has {len(geo.lines)}"))
        return problems
    if not geo.fixed:
        over = pane_overflow(lines, geo.pane_counts)
        if over:
            problems.append(("PANES", f"out of panes for style {over[0]} (the original has {over[1]})"))
            return problems
    problems.extend(console_problems(lines, geo, widths, mode == "pane"))
    return problems
