"""English strings inside program and data files (the executable, ``*.PRG`` overlays, zone files).

These strings have no table the plugin can rewrite safely: they are found by their shape and
edited in place, never longer than the bytes they had. A string is a run of text codes ending
with 0xE7, after a byte that is no text (or four zero bytes: names in records are padded so);
record data glued in front of a name is cut off (``trim``), and the string is kept when it reads
like English words (``looks_like_text``). A run that starts right after another string's 0xE7 is
what an older, longer name left in its field, and is skipped.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple

from . import codec

_TEXT = set(range(0x00, 0x6B)) | set(range(0x8F, 0xAE)) | {codec.NEWLINE, 0xE6, codec.LV}
_TAGS = {0xF8, 0xFA, 0xFB, 0xFD, 0xFE, 0xFF}
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*'?")
_BAD = set("≠≦≧÷„‼·⋯｛｝`\\_@#$<>")
_VOWEL = re.compile(r"[aeiouyAEIOUY]")
_ACCENTS_IN_NAMES = set("áéüÜ")          # accents the English names use (Leá, Müllenkamp)


def _good_word(word: str) -> bool:
    letters = word.replace("'", "")
    return letters.islower() or letters.isupper() or (letters[:1].isupper() and letters[1:].islower())


def looks_like_text(text: str) -> bool:
    plain = codec.TAG_RE.sub(" ", text)
    if any(char in _BAD for char in plain):
        return False
    words = _WORD.findall(plain)
    letters = sum(len(w) for w in words)
    visible = sum(1 for char in plain if not char.isspace())
    if letters < 3 or visible == 0 or letters < 0.7 * visible:
        return False
    if any(not c.isascii() and c not in _ACCENTS_IN_NAMES for w in words for c in w):
        return False                       # accented letters English never uses: data
    if any(len(w) >= 3 and not _VOWEL.search(w) and not w.isupper() for w in words):
        return False
    if not any(len(w) >= 3 and _VOWEL.search(w) and any(c.islower() for c in w) for w in words):
        return False
    if sum(1 for w in words if _good_word(w)) < 0.85 * len(words):
        return False
    if re.search(r"[^\W\d_]\d|\d[^\W\d_]{2}", plain):
        return False                       # letters and digits mixed in one word: data, not text
    first = plain.lstrip()[:1]
    return bool(first) and (first.isalnum() or first in "(\"'-")


def candidates(data: bytes, start: int = 0, end: int = -1) -> Iterable[Tuple[int, int]]:
    """``(offset, length)`` of every E7-terminated text run (length includes the 0xE7)."""
    end = len(data) if end < 0 else end
    i = start
    run = start
    while i < end:
        code = data[i]
        if code == codec.END:
            if i > run:
                yield run, i + 1 - run
            i += 1
            run = i
        elif code in _TAGS and i + 1 < end:
            i += 2
        elif code in _TEXT:
            i += 1
        else:
            i += 1
            run = i


def trim(data: bytes, offset: int, length: int) -> Tuple[int, int]:
    """Drop what comes before the last run of four zero bytes, the zero bytes that lead, and record
    data glued to the name in its first word: digits before a capital (``X10Bloodsuck``) or before
    a tag (``10{regular}``)."""
    body = data[offset:offset + length]
    cut = body.rfind(b"\0\0\0\0")
    if cut >= 0:
        skip = cut + 4
        offset, length, body = offset + skip, length - skip, body[skip:]
    lead = len(body) - len(body.lstrip(b"\0"))
    offset, length, body = offset + lead, length - lead, body[lead:]
    cut = 0
    i = 0
    while i + 1 < len(body):
        code = body[i]
        if code in (codec.SPACE, codec.END, codec.NEWLINE) or (code == 0xFA and body[i + 1] == 6):
            break
        if code >= codec.PARAM_FIRST:
            i += 2
            continue
        following = body[i + 1]
        glue = code <= 0x09 or (0x90 <= code <= 0xAD and code not in (0x96, 0xA0, 0xA7)) or (
            code == 0xA7 and i > 0 and 0x24 <= body[i - 1] <= 0x6A)      # "í-Dark Crusader"
        if glue and (0x0A <= following <= 0x23 or following >= 0xF8):
            cut = i + 1
        i += 1
    return offset + cut, length - cut


_ASCII_WORD = re.compile(rb"[#$]?(?:[A-Z0-9%]|%[0-9]*d)(?:[A-Z0-9 .%/'!&-]|%[0-9]*d){2,}\0")
ASCII_AREA = 0x1200        # the overlays keep these words in the read-only data at their start
_VOWELS = set("AEIOUY")


def _hud_words(text: str) -> bool:
    words = re.findall(r"[A-Z0-9]+", text.replace("%d", " "))
    letters = [w for w in words if w.isalpha()]
    return (len(letters) == len([w for w in words if not w.isdigit()])      # no letters glued to digits
            and any(len(w) >= 3 and _VOWELS & set(w) for w in letters)
            and all(len(w) < 4 or _VOWELS & set(w) for w in letters)
            and all(set(w) - _VOWELS for w in letters if len(w) >= 3)
            and not any(w[k] == w[k + 1] == w[k + 2] for w in letters for k in range(len(w) - 2)))


def ascii_scan(data: bytes, skip: Sequence[Tuple[int, int]] = ()) -> List[Tuple[int, int]]:
    """HUD words in ASCII (``#WEAPON``, ``$TOO   FAST!``, ``$%d CHAINS``): capitals at a 4-byte boundary
    in the first 0x1200 bytes that read as words; drawn with the HUD sheet's letters.
    ``(offset, length with the zero)``; none in an executable (its ASCII strings are the libraries'
    messages)."""
    if data[:8] == b"PS-X EXE":
        return []
    found = []
    for match in _ASCII_WORD.finditer(data[:ASCII_AREA]):
        start = match.start()
        if start % 4 or any(begin <= start < end for begin, end in skip):
            continue
        word = match.group(0)[:-1]
        if sum(1 for byte in word if 0x41 <= byte <= 0x5A) >= 3 and _hud_words(word.decode("ascii")):
            found.append((start, len(word) + 1))
    return found


def scan(data: bytes, skip: Sequence[Tuple[int, int]] = ()) -> List[Tuple[int, int]]:
    """Strings of a program file outside the ``skip`` ranges (tables already handled)."""
    found = []
    pos = 0
    pieces = []
    for begin, stop in sorted(skip):
        if begin > pos:
            pieces.append((pos, begin))
        pos = max(pos, stop)
    pieces.append((pos, len(data)))
    for begin, stop in pieces:
        for offset, length in candidates(data, begin, stop):
            start = offset
            offset, length = trim(data, offset, length)
            if offset == start and offset > 0 and data[offset - 1] == codec.END:
                continue            # what an older, longer name left after a field's string
            if length < 4:
                continue
            raw = data[offset:offset + length - 1]
            if codec.is_japanese(raw):
                continue
            if looks_like_text(codec.decode(raw)):
                found.append((offset, length))
    return found
