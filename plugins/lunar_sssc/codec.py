"""Text of Lunar: Silver Star Story Complete (PlayStation) as editable strings with readable tags.

The game's decoder (SLUS_006.28 0x8005A884) reads two modes:

- raw: 0x0E starts a compressed run, 0xFF ends the string, a byte from 0xD6 up starts a two-byte control
  (``{FA:39}``: window, colour, name, pause...), any other byte is one table glyph (``{raw:11}``);
- compressed (after 0x0E, until 0x00): 0x01-0x5B is the ASCII character ``byte + 0x1F``, except six
  controls; 0x5C-0xFC, 0xFD xx and 0xFE xx are words of the dictionary (``dictionary.json``, the 512
  words at SLUS_006.28 0xA306C).

Compressed controls: 0x05 ends a message (wait for a button, close), 0x06 ``{wait}``, 0x0B ``{page}``
(wait, new page), 0x21 a new line, 0x3D ``{close}``, 0x3F ``{clear}``. A message that ends with 0xFF
instead of 0x05 (no wait) shows ``{end}`` at its end.

``encode`` writes characters in compressed runs and uses the longest dictionary word that saves bytes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

START, STOP, END_RAW, END_MESSAGE = 0x0E, 0x00, 0xFF, 0x05
NEWLINE = 0x21
CONTROLS = {0x06: "{wait}", 0x0B: "{page}", 0x3D: "{close}", 0x3F: "{clear}"}
CODES = {tag: code for code, tag in CONTROLS.items()}
END_TAG = "{end}"
TAG_RE = re.compile(r"\{(?:wait|page|close|clear|end|raw:[0-9A-F]{2}|[0-9A-F]{2}:[0-9A-F]{2})\}")
_TOKEN = re.compile(r"\{[^{}]*\}|\n|.", re.S)
_TEXT_CHARS = {chr(code + 0x1F) for code in range(0x01, 0x5C) if code not in CONTROLS and code not in (0x05, 0x21)}
WORDS: List[str] = json.loads((Path(__file__).resolve().parent / "dictionary.json").read_text(encoding="ascii"))


def _word_index(byte: int, data: bytes, p: int) -> Tuple[int, int]:
    if byte == 0xFD:
        return 0xA1 + data[p], p + 1
    if byte == 0xFE:
        return 0x19E + data[p], p + 1
    return byte - 0x5C, p


def decode(data: bytes, start: int, end: int, words: Optional[List[str]] = None) -> str:
    """The text of ``data[start:end]`` (end just after the terminator)."""
    words = WORDS if words is None else words
    out: List[str] = []
    p = start
    while p < end:
        b = data[p]
        p += 1
        if b == END_RAW:
            break
        if b == START:
            while p < end:
                c = data[p]
                p += 1
                if c == STOP:
                    break
                if c == END_MESSAGE:
                    return "".join(out)
                if c < 0x5C:
                    out.append("\n" if c == NEWLINE else CONTROLS.get(c) or chr(c + 0x1F))
                else:
                    index, p = _word_index(c, data, p)
                    out.append(words[index] if index < len(words) else f"{{word:{index}}}")
            continue
        if b >= 0xD6:
            out.append(f"{{{b:02X}:{data[p]:02X}}}")
            p += 1
        else:
            out.append(f"{{raw:{b:02X}}}")
    return "".join(out)


def decode_message(data: bytes, start: int, end: int, words: Optional[List[str]] = None) -> str:
    """A message: ``{end}`` marks the ones that end with 0xFF (no wait for a button)."""
    text = decode(data, start, end, words)
    return text + END_TAG if data[end - 1] == END_RAW else text


class Encoder:
    """Text to bytes with one dictionary; characters the game cannot write go to ``missing``."""

    def __init__(self, words: Optional[List[str]] = None):
        self.words = WORDS if words is None else words
        self.by_first: Dict[str, List[Tuple[str, int]]] = {}
        for index, word in enumerate(self.words):
            if word and index <= 0x29D:
                self.by_first.setdefault(word[0], []).append((word, index))
        for entries in self.by_first.values():
            entries.sort(key=lambda item: -len(item[0]))
        self.missing: Set[str] = set()

    @staticmethod
    def _word_bytes(index: int) -> bytes:
        if index <= 0xA0:
            return bytes([0x5C + index])
        if index <= 0x1A0:
            return bytes([0xFD, index - 0xA1])
        return bytes([0xFE, index - 0x19E])

    def _run(self, text: str) -> bytes:
        out = bytearray()
        i = 0
        while i < len(text):
            best: Optional[Tuple[str, int]] = None
            for word, index in self.by_first.get(text[i], ()):
                if text.startswith(word, i) and len(word) > len(self._word_bytes(index)):
                    if best is None or len(word) - len(self._word_bytes(index)) > len(best[0]) - len(self._word_bytes(best[1])):
                        best = (word, index)
            if best is not None:
                out += self._word_bytes(best[1])
                i += len(best[0])
            else:
                out.append(ord(text[i]) - 0x1F)
                i += 1
        return bytes(out)

    def encode(self, text: str) -> Tuple[bytes, bool]:
        """The bytes of ``text`` without a terminator, and whether they end inside a compressed run."""
        out = bytearray()
        compressed = False
        run: List[str] = []

        def flush():
            nonlocal compressed
            if run:
                if not compressed:
                    out.append(START)
                    compressed = True
                out.extend(self._run("".join(run)))
                run.clear()

        def need(mode: bool):
            nonlocal compressed
            flush()
            if mode and not compressed:
                out.append(START)
            elif not mode and compressed:
                out.append(STOP)
            compressed = mode

        for token in _TOKEN.findall(text):
            if token in _TEXT_CHARS:
                run.append(token)
            elif token == "\n":
                need(True)
                out.append(NEWLINE)
            elif token in CODES:
                need(True)
                out.append(CODES[token])
            elif TAG_RE.fullmatch(token) and token != END_TAG:
                need(False)
                if token.startswith("{raw:"):
                    out.append(int(token[5:7], 16))
                else:
                    high, low = int(token[1:3], 16), int(token[4:6], 16)
                    if high < 0xD6:
                        raise ValueError(f"{token}: a two-byte code starts at D6")
                    out += bytes((high, low))
            else:
                self.missing.add(token)
                run.append("?")
        flush()
        return bytes(out), compressed

    def message(self, text: str) -> bytes:
        """A message body with its terminator: 0x05 inside a run, or 0xFF after ``{end}``."""
        raw_end = END_TAG in text                      # wherever it was typed, it is the end
        body, compressed = self.encode(text.replace(END_TAG, ""))
        if raw_end:
            return body + (bytes((STOP,)) if compressed else b"") + bytes((END_RAW,))
        return body + (b"" if compressed else bytes((START,))) + bytes((END_MESSAGE,))

    def string(self, text: str) -> bytes:
        """A 0xFF-ended string (choices, item and menu tables)."""
        body, compressed = self.encode(text)
        return body + (bytes((STOP,)) if compressed else b"") + bytes((END_RAW,))


def filler(terminator: int) -> bytes:
    """Two bytes the game skips, put before ``terminator`` to pad a text: leave the compressed run and
    start it again before 0x05, an empty run before 0xFF."""
    return bytes((STOP, START)) if terminator == END_MESSAGE else bytes((START, STOP))
