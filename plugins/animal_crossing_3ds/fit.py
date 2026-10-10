"""How text fits the 3DS Animal Crossing message windows: which window a file's text shows in, the width of a line in
the game font, and re-wrapping a translation with the game's own break codes.

``window_layouts.json`` (measured from the games' BCLYT layouts and fonts, see its ``source`` notes) gives each window
kind its line width in pixels of the message font at its own size, its lines per page and the preview geometry;
``files`` maps a script file (by path glob) to its kind. A line is measured in the font's advances (``font_map``):
``{size:N}`` scales what follows by N/100 (also on later lines, as the game does), a tag that inserts a name or a
number counts as ``insert_width`` pixels (the longest the game allows, e.g. an 8-letter player name), every other
tag draws nothing. A letter the font does not have yet is measured as its look-alike (``і`` as ``i``, ``є`` as
``е``), so Ukrainian text is measured before the font editor adds those letters.

Breaks: a line ends with U+000A (the MSBT newline); ``{pageBreak}`` (tag 0:4) closes the window page and waits for A.
Lines after a question / menu tag (``ask*``, ``menu*``, ``systemMenu*``) are its answers, one per line: they are
never wrapped or joined.
"""
from __future__ import annotations

import fnmatch
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .tags import TAG_RE

PAGE_BREAK = "{pageBreak}"
_PAGE_RE = re.compile(r"\{(?:pageBreak|PageBreak|G0_4)\}")
_CHOICE_RE = re.compile(r"\{(?:ask|menu|systemMenu)\d+(?::[^{}]*)?\}")
_SIZE_RE = re.compile(r"\{(?:size|Size|G0_2):(\d+)\}")
LOOK_ALIKES = {"і": "i", "ї": "ï", "є": "е", "ґ": "г", "І": "I", "Ї": "Ï", "Є": "Е", "Ґ": "Г", "’": "'", "ʼ": "'"}
_PUNCT_START = set(",.!?:;…)]»”’")


@lru_cache(maxsize=1)
def layouts() -> Dict[str, Any]:
    return json.loads(Path(__file__).with_name("window_layouts.json").read_text(encoding="utf-8"))


def kind_for_path(rel_path: str, doc: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """The window kind of a script file (``romfs/Script/Talk/x.umsbt`` -> ``dialogue``), or None."""
    doc = doc or layouts()
    path = str(rel_path).replace("\\", "/")
    for pattern, kind in doc.get("files", {}).items():
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, "*/" + pattern):
            return kind
    return None


def split_choice(text: str) -> Tuple[str, List[str]]:
    """``(the text up to and including the question tag, the answer lines)``; no answers without a question tag."""
    last = None
    for last in _CHOICE_RE.finditer(text):
        pass
    if last is None or "\n" not in text[last.end():]:
        return text, []
    head, _, answers = text[last.end():].partition("\n")
    return text[:last.end()] + head, answers.split("\n")


class Measure:
    """Line widths in the message font's pixels at its own size."""

    def __init__(self, font_map: Dict[str, Any], insert_widths: Dict[str, int], default_width: int = 10):
        self.font_map = font_map or {}
        self.inserts = insert_widths
        self.default = default_width

    def char(self, char: str) -> int:
        entry = self.font_map.get(char)
        if entry is None and char in LOOK_ALIKES:
            entry = self.font_map.get(LOOK_ALIKES[char]) or self.font_map.get(LOOK_ALIKES[char][0])
        if isinstance(entry, dict):
            return int(entry.get("width", self.default))
        return self.default if char.strip() or char == "　" else int((self.font_map.get(" ") or {}).get("width", 6))

    def lines(self, text: str, scale: float = 1.0) -> List[float]:
        """The width of every line of ``text`` up to its last visible character (a ``{size}`` carries on to the
        next lines; trailing spaces draw nothing)."""
        widths, total, visible, position = [], 0.0, 0.0, 0
        for match in list(TAG_RE.finditer(text)) + [None]:
            end = match.start() if match else len(text)
            for char in text[position:end]:
                if char == "\n":
                    widths.append(visible)
                    total = visible = 0.0
                else:
                    total += self.char(char) * scale
                    if not char.isspace():
                        visible = total
            if match is None:
                break
            tag = match.group(0)
            size = _SIZE_RE.fullmatch(tag)
            if size:
                scale = int(size.group(1)) / 100
            elif _PAGE_RE.fullmatch(tag):
                widths.append(visible)      # a page break ends the line as a newline does
                total = visible = 0.0
            else:
                name = tag[1:-1].split(":")[0].lstrip("/")
                if self.inserts.get(name):
                    total += self.inserts[name] * scale
                    visible = total
            position = match.end()
        widths.append(visible)
        return widths

    def width(self, line: str) -> int:
        return math.ceil(max(self.lines(line)) - 1e-9)


def pages(text: str) -> List[List[str]]:
    """The lines of each window page (``{pageBreak}`` splits pages; the break tag stays at the end of its page)."""
    out, start = [], 0
    for match in _PAGE_RE.finditer(text):
        out.append(text[start:match.end()].split("\n"))
        start = match.end()
    out.append(text[start:].split("\n"))
    return out


def _words(text: str) -> List[str]:
    """Words with their tags glued on; a run of spaces is its own item."""
    return re.findall(rf"(?:{TAG_RE.pattern}|[^\s{{}}]|\{{)+|\s+", text)


def _wrap_paragraph(text: str, measure: Measure, width: int) -> List[str]:
    lines: List[str] = []
    current = ""
    for word in _words(text):
        if word.isspace():
            if current:
                current += " "
            continue
        trial = current + word
        if current and measure.width(trial.rstrip()) > width and not word[0] in _PUNCT_START:
            lines.append(current.rstrip())
            current = word
        else:
            current = trial
    if current.strip() or not lines:
        lines.append(current.rstrip())
    return lines


def fit(text: str, measure: Measure, width: int, lines_per_page: int, auto_pages: bool = False) -> str:
    """``text`` re-wrapped to ``width`` with the game's breaks: a page whose lines are all narrow enough and that has
    no more than ``lines_per_page`` lines (any number in a window that goes on by itself every ``lines_per_page``
    lines, ``auto_pages``) keeps its breaks; any other page is wrapped again as one paragraph and cut
    into pages of ``lines_per_page`` lines with ``{pageBreak}`` (after the line that ends a sentence when it can).
    The answers of a question stay as they are."""
    body, answers = split_choice(text)
    out_pages: List[str] = []
    for page in pages(body):
        joined = "\n".join(page)
        tail = ""
        match = _PAGE_RE.search(joined)
        if match:
            joined, tail = joined[:match.start()], joined[match.start():]
        lines = joined.split("\n")
        if (auto_pages or len(lines) <= lines_per_page) and all(measure.width(line) <= width for line in lines):
            out_pages.append(joined + tail)
            continue
        wrapped = _wrap_paragraph(" ".join(part.strip() for part in lines if part.strip()), measure, width)
        chunks = []
        while len(wrapped) > lines_per_page:
            cut = lines_per_page
            for index in range(lines_per_page, 0, -1):
                if re.search(r"[.!?…](?:\{[^{}]*\})*$", wrapped[index - 1]):
                    cut = index
                    break
            chunks.append("\n".join(wrapped[:cut]))
            wrapped = wrapped[cut:]
        chunks.append("\n".join(wrapped))
        out_pages.append(PAGE_BREAK.join(chunks) + tail)
    result = "".join(out_pages)
    return result + ("\n" + "\n".join(answers) if answers else "")
