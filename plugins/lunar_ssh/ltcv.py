"""Lunar: Silver Star Harmony event scripts (``LTCV``, ``ScriptPack/TEXT*.dat``): find the text, put it back.

Layout (little endian): ``"LTCV"``, u32 code size, u32 label count, u32 code start (16 + 8 * count); a
label table of ``u16 id, u16 length, u32 offset`` (bytes into the code; the labels follow each other with
no gap); the code, 16-bit words. Text is UTF-16 inside the code:

- a message: opcode ``0x0002``, then text up to ``0x0416`` (end) or ``0x0417`` (end, window stays);
- a choice: opcode ``0x0007``, one word, then two or more strings each ended by ``0xFFFF``.

Inside a message ``0x04xx`` words are control codes (so Cyrillic, U+0400-04FF, cannot be stored as it is):
``0x0401`` new line, ``0x0414`` wait for a button, ``0x0419`` new page, ``0x042E n`` / ``0x044E n``
speaker, ``0x042A n``, ``0x0411 n`` pause, ``0x0413 n``. No jump in the code points into text, so a
longer or shorter text only moves the labels: their offsets and lengths are counted again on save.
Text is told from other code by its shape (every word a character or one of these codes); a saved
text keeps to the characters that pass that test, so the translated file reads back the same way.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

MAGIC = b"LTCV"
MESSAGE, CHOICE = 0x0002, 0x0007
END = (0x0416, 0x0417)
NEWLINE = 0x0401
SEPARATOR = 0xFFFF
TAGS = {0x0414: "wait", 0x0419: "page"}                       # no argument
ARG_TAGS = {0x042E: "speaker", 0x044E: "speaker2", 0x042A: "voice", 0x0411: "pause", 0x0413: "face"}
CODES = {name: code for code, name in {**TAGS, **ARG_TAGS}.items()}
TAG_RE = re.compile(r"\{([a-z0-9]+)(?::(\d+))?\}")


def is_char(word: int) -> bool:
    """A character the game's text uses (ASCII, Latin-1, punctuation, a few symbols)."""
    return 0x20 <= word < 0x7F or 0xA0 <= word < 0x100 or 0x2000 <= word < 0x2100 or word in (0x2605, 0x2665, 0x266A, 0x3000)


@dataclass
class Span:
    """Words ``start:end`` of the code are one editable string (``kind``: "message" or "choice")."""

    kind: str
    start: int
    end: int


@dataclass
class Script:
    labels: List[Tuple[int, int, int]]
    code: List[int]
    spans: List[Span]


def _message(code: List[int], at: int) -> Optional[int]:
    """End (index of the end code) of a message whose text starts at ``at``, or None."""
    chars = 0
    j = at
    while j < len(code) and code[j] not in END:
        word = code[j]
        if word in ARG_TAGS:
            j += 2
        elif word in TAGS or word == NEWLINE:
            j += 1
        elif is_char(word):
            j += 1
            chars += 1
        else:
            return None
    return j if j < len(code) and chars else None


def _choice(code: List[int], at: int) -> List[Tuple[int, int]]:
    items = []
    j = at
    while j < len(code) and is_char(code[j]):
        start = j
        while j < len(code) and is_char(code[j]):
            j += 1
        if j >= len(code) or code[j] != SEPARATOR:
            break
        items.append((start, j))
        j += 1
    return items if len(items) >= 2 else []


def find_spans(code: List[int]) -> List[Span]:
    spans: List[Span] = []
    i = 0
    while i < len(code):
        if code[i] == MESSAGE and i + 1 < len(code):
            end = _message(code, i + 1)
            if end is not None:
                spans.append(Span("message", i + 1, end))
                i = end + 1
                continue
        if code[i] == CHOICE and i + 2 < len(code):
            items = _choice(code, i + 2)
            if items:
                spans += [Span("choice", s, e) for s, e in items]
                i = items[-1][1] + 1
                continue
        i += 1
    return spans


def parse(data: bytes) -> Script:
    if data[:4] != MAGIC:
        raise ValueError("not an LTCV script")
    size, count, start = struct.unpack_from("<III", data, 4)
    if start != 16 + 8 * count or start + size != len(data) or size % 2:
        raise ValueError("LTCV header does not match the file")
    labels = [struct.unpack_from("<HHI", data, 16 + 8 * i) for i in range(count)]
    code = list(struct.unpack_from(f"<{size // 2}H", data, start))
    return Script(labels, code, find_spans(code))


def render(words: List[int]) -> str:
    """Words of a span as editor text: characters, ``\\n`` and ``{tag}`` / ``{tag:n}``."""
    out = []
    i = 0
    while i < len(words):
        word = words[i]
        if word == NEWLINE:
            out.append("\n")
        elif word in TAGS:
            out.append("{" + TAGS[word] + "}")
        elif word in ARG_TAGS and i + 1 < len(words):
            out.append("{%s:%d}" % (ARG_TAGS[word], words[i + 1]))
            i += 1
        else:
            out.append(chr(word))
        i += 1
    return "".join(out)


def encode(text: str, kind: str, missing: Optional[Set[str]] = None) -> List[int]:
    """Editor text back to words. A character the game cannot store becomes ``?`` (and goes into
    ``missing``); a choice has no codes and no new lines; a string never ends up empty."""
    words: List[int] = []
    at = 0
    for match in TAG_RE.finditer(text):
        words += _chars(text[at:match.start()], kind, missing)
        name, value = match.group(1), match.group(2)
        code = CODES.get(name)
        if code is None or kind != "message" or (value is None) != (code in TAGS):
            words += _chars(match.group(0), kind, missing)
        else:
            words += [code] if value is None else [code, int(value) & 0xFFFF]
        at = match.end()
    words += _chars(text[at:], kind, missing)
    if not any(is_char(w) for w in words):
        words = [0x20] + words
    return words


def _chars(text: str, kind: str, missing: Optional[Set[str]]) -> List[int]:
    out = []
    for char in text:
        if char == "\n" and kind == "message":
            out.append(NEWLINE)
        elif len(char) == 1 and is_char(ord(char)):
            out.append(ord(char))
        else:
            if missing is not None and char != "\n":
                missing.add(char)
            out.append(0x3F if char != "\n" else 0x20)
    return out


def texts(script: Script) -> List[str]:
    return [render(script.code[s.start:s.end]) for s in script.spans]


def build(data: bytes, new_texts: List[Optional[str]], missing: Optional[Set[str]] = None) -> bytes:
    """The script with its strings replaced (None or the same text keeps the original words)."""
    script = parse(data)
    code = script.code
    out: List[int] = []
    shift: List[Tuple[int, int]] = []        # (old index from which, delta)
    at = 0
    delta = 0
    for span, text in zip(script.spans, new_texts):
        old = code[span.start:span.end]
        if text is None or text == render(old):
            continue
        words = encode(text, span.kind, missing)
        out += code[at:span.start] + words
        at = span.end
        delta += len(words) - len(old)
        shift.append((span.end, delta))
    if not shift:
        return data
    out += code[at:]

    def moved(index: int) -> int:
        d = 0
        for frm, dd in shift:
            if index >= frm:
                d = dd
        return index + d

    head = bytearray(data[:16 + 8 * len(script.labels)])
    struct.pack_into("<I", head, 4, 2 * len(out))
    for number, (ident, length, offset) in enumerate(script.labels):
        start, end = moved(offset // 2), moved((offset + length) // 2)
        if 2 * (end - start) > 0xFFFF:
            raise ValueError(f"LTCV label {ident}: more than 64 KB of code and text")
        struct.pack_into("<HHI", head, 16 + 8 * number, ident, 2 * (end - start), 2 * start)
    return bytes(head) + struct.pack(f"<{len(out)}H", *out)
