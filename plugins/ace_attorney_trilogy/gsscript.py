"""Ace Attorney Trilogy script blobs (3DS ``pack.dat`` members, Switch ``*.mdt``): 16-bit words, English text as
game character codes.

A script file (an English member of ``pack.dat`` entry "scripts", decompressed) is ``u32 n`` followed by ``n``
u32 words: the first ``n - 2`` are the offsets of the sections (dialogue or investigation scenes; the section
table is the only place that names where a section starts), the last two are flags the game keeps. The
sections are streams of u16 words: a word below 0x80 is a command followed by a fixed number of argument words;
a word from 0x80 up is a character of the message being shown.

Characters: 0x80-0x89 digits, 0x8A-0xA3 A-Z, 0xA4-0xBD a-z, 0xBE ``!``, 0xBF ``?``, and the punctuation of
``CHARS`` (0x161-0x18A). A character this table does not know stays as ``{xNNN}`` and writes back unchanged.

A message is a run of characters with the commands that sit inside a sentence: ``\\n`` (command 1, a line break),
``{page}`` (command 2 when text follows at once) and ``{wait:N}`` (command 0xC with one argument, a pause of
N frames). Every other command ends the message and stays as it was. Messages are found again from the
section words on save, so a changed text can be longer or shorter: the section offsets that follow move.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Optional, Tuple

# number of argument words of every command word, learned from the 18 English scripts by minimising the characters
# that fall outside the character set (2338 of 2339 sections parse to their exact end, 46 of 704 712 characters
# stay outside it). Commands that no message needs are left at 0 arguments: the parser only has to find where
# the text is, and a command's arguments below 0x80 are never mistaken for text.
ARGC: Dict[int, int] = {
    0x1e: 3, 0x0c: 1, 0x0e: 1, 0x0b: 1, 0x12: 1, 0x1b: 1, 0x05: 2, 0x27: 1, 0x06: 2, 0x0f: 1, 0x10: 1, 0x31: 1,
    0x1a: 4, 0x07: 5, 0x0a: 1, 0x19: 2, 0x69: 2, 0x29: 4, 0x3c: 1, 0x22: 2, 0x78: 1, 0x13: 1, 0x35: 2, 0x17: 1,
    0x2c: 1, 0x48: 2, 0x1d: 1, 0x37: 1, 0x33: 5, 0x2a: 3, 0x3d: 1, 0x4e: 1, 0x39: 5, 0x36: 1, 0x47: 1, 0x3b: 2,
}
NEWLINE, PAGE, WAIT = 0x01, 0x02, 0x0C

CHARS: Dict[int, str] = {0xBE: "!", 0xBF: "?", 0x161: ".", 0x16D: ":", 0x16F: ",", 0x173: "'", 0x17F: " ",
                         0x180: "-", 0x181: '"', 0x165: "(", 0x166: ")", 0x172: "*", 0x17C: "&", 0x184: "$",
                         0x185: "#", 0x18A: "é", 0x177: "%", 0x171: "/", 0x18C: ";"}
for _i in range(10):
    CHARS[0x80 + _i] = str(_i)
for _i in range(26):
    CHARS[0x8A + _i] = chr(65 + _i)
    CHARS[0xA4 + _i] = chr(97 + _i)
CODES = {char: code for code, char in CHARS.items()}

# The Switch (Unity) version writes the same scripts with the codes of its own font: digits 0xFF90.., A-Z 0xFFA1..,
# a-z 0xFFC1.., the space 0x3080 and the punctuation below (found by comparing the Switch and 3DS scripts message by
# message).
SWITCH_CHARS: Dict[int, str] = {0xFF81: "!", 0xFF9F: "?", 0xFF8E: ".", 0xFF9A: ":", 0xFF8C: ",", 0xFF87: "'",
                                0x3080: " ", 0x2095: "-", 0xFF82: '"', 0xFF88: "(", 0xFF89: ")", 0xFF8A: "*"}
for _i in range(10):
    SWITCH_CHARS[0xFF90 + _i] = str(_i)
for _i in range(26):
    SWITCH_CHARS[0xFFA1 + _i] = chr(65 + _i)
    SWITCH_CHARS[0xFFC1 + _i] = chr(97 + _i)
SWITCH_CODES = {char: code for code, char in SWITCH_CHARS.items()}


def detect_chars(sections) -> Dict[int, str]:
    """The character table (3DS or Switch) a script's words belong to."""
    switch = three = 0
    for words in sections:
        for w in words:
            if 0xFFA1 <= w <= 0xFFDA:
                switch += 1
            elif 0xA4 <= w <= 0xBD:
                three += 1
    return SWITCH_CHARS if switch > three else CHARS
_TAG = re.compile(r"\{(x[0-9a-fA-F]{1,4}|page|wait:\d+)\}")


class ScriptError(ValueError):
    pass


def is_script(raw: bytes) -> bool:
    if len(raw) < 12:
        return False
    n = struct.unpack_from("<I", raw, 0)[0]
    return 2 < n < 4096 and 4 + 4 * n <= len(raw) and struct.unpack_from("<I", raw, 4)[0] == 4 + 4 * n


def _is_text(word: int) -> bool:
    return word >= 0x80


def encode(text: str, codes: Optional[Dict[str, int]] = None) -> List[int]:
    """The words of a message text (``ScriptError`` on a character the game has no code for)."""
    codes = CODES if codes is None else codes
    words: List[int] = []
    pos = 0
    while pos < len(text):
        m = _TAG.match(text, pos)
        if m:
            tag = m.group(1)
            if tag == "page":
                words.append(PAGE)
            elif tag.startswith("wait:"):
                words += [WAIT, int(tag[5:])]
            else:
                words.append(int(tag[1:], 16))
            pos = m.end()
            continue
        char = text[pos]
        if char == "\n":
            words.append(NEWLINE)
        elif char in codes:
            words.append(codes[char])
        else:
            raise ScriptError(f"no game code for {char!r}")
        pos += 1
    return words


def decode(words: List[int], chars: Optional[Dict[int, str]] = None) -> str:
    chars = CHARS if chars is None else chars
    out = []
    i = 0
    while i < len(words):
        w = words[i]
        if w == NEWLINE:
            out.append("\n")
        elif w == PAGE:
            out.append("{page}")
        elif w == WAIT:
            out.append("{wait:%d}" % words[i + 1])
            i += 1
        elif w in chars:
            out.append(chars[w])
        else:
            out.append("{x%x}" % w)
        i += 1
    return "".join(out)


class Script:
    """The sections of one script file and the messages found in them."""

    def __init__(self, raw: bytes) -> None:
        if not is_script(raw):
            raise ScriptError("not an Ace Attorney script")
        self.raw = bytes(raw)
        self.n = struct.unpack_from("<I", raw, 0)[0]
        table = list(struct.unpack_from(f"<{self.n}I", raw, 4))
        self.header = 4 + 4 * self.n
        # table slots that are section offsets (the last two are flags)
        self.slots = [i for i, v in enumerate(table) if self.header <= v < len(raw) and i < self.n - 2]
        self.table = table
        starts = sorted(set(table[i] for i in self.slots))
        self.bounds = list(zip(starts, starts[1:] + [len(raw)]))
        self.words = [struct.unpack_from(f"<{(end - start) // 2}H", raw, start) for start, end in self.bounds]
        self.chars = detect_chars(self.words)
        self.codes = {char: code for code, char in self.chars.items()}
        self.messages: List[Tuple[int, int, int]] = []     # (section, first word, end word)
        for sec, words in enumerate(self.words):
            self.messages += [(sec, a, b) for a, b in _runs(words)]

    def texts(self) -> List[str]:
        return [decode(list(self.words[s][a:b]), self.chars) for s, a, b in self.messages]

    def rebuild(self, texts: List[str]) -> bytes:
        if len(texts) != len(self.messages):
            raise ScriptError(f"{len(texts)} texts for {len(self.messages)} messages")
        by_section: Dict[int, List[Tuple[int, int, List[int]]]] = {}
        for (sec, a, b), text in zip(self.messages, texts):
            by_section.setdefault(sec, []).append((a, b, encode(text, self.codes)))
        parts: List[bytes] = []
        new_start: Dict[int, int] = {}
        pos = self.header
        for sec, (start, _end) in enumerate(self.bounds):
            words = list(self.words[sec])
            for a, b, new in sorted(by_section.get(sec, []), reverse=True):
                words[a:b] = new
            blob = struct.pack(f"<{len(words)}H", *words)
            new_start[start] = pos
            parts.append(blob)
            pos += len(blob)
        head = bytearray(self.raw[:self.header])
        for slot in self.slots:
            struct.pack_into("<I", head, 4 + 4 * slot, new_start[self.table[slot]])
        return bytes(head) + b"".join(parts)


def _runs(words) -> List[Tuple[int, int]]:
    """``[(first, end)]`` of the messages of one section (see the module doc)."""
    out: List[Tuple[int, int]] = []
    n, p = len(words), 0
    first: Optional[int] = None
    last_text: Optional[int] = None
    while p < n:
        w = words[p]
        if _is_text(w):
            if first is None:
                first = p
            last_text = p
            p += 1
            continue
        step = 1 + ARGC.get(w, 0)
        inline = w == NEWLINE or (w == WAIT and p + 1 < n) or (w == PAGE and p + 1 < n and _is_text(words[p + 1]))
        if first is not None and inline and _continues(words, p + step):
            p += step
            continue
        if first is not None:
            if last_text is not None:
                out.append((first, last_text + 1))
            first = None
        p += step
    if first is not None and last_text is not None:
        out.append((first, last_text + 1))
    return out


def _continues(words, p: int) -> bool:
    """Text follows at ``p`` (after an inline command): the message goes on."""
    n = len(words)
    while p < n:
        w = words[p]
        if _is_text(w):
            return True
        if w == NEWLINE or (w == WAIT and p + 1 < n):
            p += 1 + ARGC.get(w, 0)
            continue
        if w == PAGE:
            p += 1
            continue
        return False
    return False
