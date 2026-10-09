"""Castlevania: The Dracula X Chronicles (PSP) text bytes <-> editor text, for its three kinds of text files.

- **Remake dialogue** (``stdNN.txt`` from the event packs): one message per ``CR LF`` line, ``\\n`` (backslash,
  n) breaks the line on screen. One byte is one character of the message font: ASCII, the game's accented
  letters on their own codes and the Ukrainian letters on free codes (``translation_map.json``; the workspace
  build points the font's free cells at them). A byte read as Latin-1 is the character, so the translation
  map keeps working; ``\\n`` reads as a new line.
- **Save-data strings** of the program (``BOOT.BIN``, a plain ELF): the English block of UTF-8 strings the PSP
  save screen shows (game title, "Save data", the unlocked games, the description). Each keeps its room: the
  bytes up to the next string.
- **Symphony of the Night strings** in the PSP overlays (``MWo3`` files of ``res/ps/PSPBIN``): found by
  ``units``. Menu, item and enemy names use the 8x8 font cells (``char - 0x20``, ending ``FF 00``);
  descriptions are ASCII / Shift-JIS ending ``00``; dialogue is ASCII between script commands, ``01`` = new
  line. A string keeps its place and room (the code points at it): a shorter text is padded (zeros after a
  ``00``-ended string, spaces in a script), a longer one is cut to the room with a warning.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Set

TAG_RE = re.compile(r"\{([0-9A-F]{2})\}")
NEWLINE = "\\n"

# ---------------------------------------------------------------- remake dialogue (stdNN.txt)

LINE_END = b"\r\n"


def std_lines(data: bytes) -> List[str]:
    """The messages of a dialogue file (the text after the last line end is not a message)."""
    parts = data.split(LINE_END)
    return [p.decode("latin-1").replace(NEWLINE, "\n") for p in parts[:-1]]


def std_encode(text: str, missing: Set[str]) -> bytes:
    out = bytearray()
    for char in str(text).replace("\r", "").replace("\n", NEWLINE):
        code = ord(char)
        if code < 0x100 and char not in "\x00":
            out.append(code)
        else:
            missing.add(char)
            out += b"?"
    return bytes(out)


def std_build(data: bytes, texts: List[Optional[str]], missing: Set[str]) -> bytes:
    parts = data.split(LINE_END)
    for index, text in enumerate(texts):
        if text is not None and index < len(parts) - 1:
            parts[index] = std_encode(text, missing)
    return LINE_END.join(parts)


# ---------------------------------------------------------------- program save-data strings (BOOT.BIN)

def boot_spans(data: bytes) -> List[tuple]:
    """``(start, room)`` of the English save-data strings: from the second game title to the French block."""
    japanese = data.find("セーブデータ".encode("utf-8"))
    start = data.find(b"Castlevania The Dracula X Chronicles\0", japanese if japanese >= 0 else 0)
    end = data.find(b"Sauvegarde\0", start)
    if japanese < 0 or start < 0 or end < 0:
        return []
    spans, at = [], start
    while at < end:
        stop = data.index(b"\0", at)
        if stop > at:
            nxt = stop
            while nxt < end and data[nxt] == 0:
                nxt += 1
            spans.append((at, nxt - at - 1))
            at = nxt
        else:
            at += 1
    return spans


def boot_texts(data: bytes) -> List[str]:
    return [data[s:data.index(b"\0", s)].decode("utf-8", "replace") for s, _room in boot_spans(data)]


def boot_build(data: bytes, texts: List[Optional[str]], too_long: List[str]) -> bytes:
    out = bytearray(data)
    for (start, room), text in zip(boot_spans(data), texts):
        if text is None:
            continue
        raw = str(text).replace("\n", " ").encode("utf-8")
        if len(raw) > room:
            too_long.append(str(text))
            raw = raw[:room].decode("utf-8", "ignore").encode("utf-8")
        out[start:start + room + 1] = raw + bytes(room + 1 - len(raw))
    return bytes(out)


# ---------------------------------------------------------------- Symphony of the Night overlays (MWo3)

OVERLAY_MAGIC = b"MWo3"
HEADER = 0x80                 # the overlay header (name, addresses) holds no text
_SJ = rb"[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]"
_ASCII = re.compile(rb"(?:[\x20-\x7e]|%s)+(?:\x01(?:[\x20-\x7e]|%s)+)*" % (_SJ, _SJ))
_CELL_END = re.compile(rb"\xff\x00")
_BAD = set(rb"^`{}|~<>\@#$_[]")
_WORD = re.compile(rb"[A-Za-z]*[AEIOUaeiou][A-Za-z]*")
_PARAM_FIRST = set(b"0123456789<>=@")


@dataclass
class Unit:
    kind: str       # "cell" (8x8 font name), "string" (00-ended), "script" (dialogue between commands)
    start: int
    length: int     # bytes of the text now
    room: int       # bytes the text may take


def _looks_like_text(raw: bytes) -> bool:
    plain = re.sub(_SJ, b"", raw).replace(b"\x01", b"")
    if not plain or any(b in _BAD for b in plain) or re.search(rb"[a-z][A-Z]", plain):
        return False
    letters = sum(chr(b).isalpha() for b in plain)
    if letters < 3 or letters + plain.count(b" ") < 0.75 * len(plain):
        return False
    words = [w for w in _WORD.findall(raw) if len(w) >= 3]
    return bool(words) and (letters >= 4 or b" " in raw)


def _padding_room(data: bytes, start: int, end: int, keep: int) -> int:
    """The text's room when zeros fill the rest of its 4-byte slot: ``keep`` = terminator bytes."""
    slot = -(-(end + keep) // 4) * 4
    if slot <= len(data) and not any(data[end + keep:slot]):
        return slot - start - keep
    return end - start


def units(data: bytes) -> List[Unit]:
    """The strings of an overlay, in file order."""
    out: List[Unit] = []
    for match in _CELL_END.finditer(data, HEADER):
        end = start = match.start()
        while start > HEADER and data[start - 1] <= 0x5E and not (data[start - 1] == 0 and data[start - 2] == 0):
            start -= 1
        while start < end and data[start] == 0:
            start += 1
        for s in [start] + [p for p in range(start + 1, end) if data[p - 1] == 0 and p % 4 == 0]:
            raw = data[s:end]
            if len(raw) < 2 or data[s - 1] not in (0, 0xFF):
                continue
            if _looks_like_text(bytes(b + 0x20 for b in raw)):
                out.append(Unit("cell", s, end - s, _padding_room(data, s, end, 2)))
                break
    taken = [(u.start, u.start + u.length + 2) for u in out]
    for match in _ASCII.finditer(data, HEADER):
        s, e = match.span()
        if any(a < e and s < b for a, b in taken):
            continue
        raw = match.group()
        if not _looks_like_text(raw):
            continue
        words = [w for w in _WORD.findall(raw) if len(w) >= 3]
        if s % 4 == 0 and data[s - 1] == 0 and data[e:e + 1] == b"\0":
            out.append(Unit("string", s, e - s, _padding_room(data, s, e, 1)))
        elif len(words) >= 2 and b" " in raw and data[s - 1] < 0x20:
            if raw[0] in _PARAM_FIRST and chr(raw[1]).isalpha():
                s += 1          # the last parameter byte of the command before the text
            out.append(Unit("script", s, e - s, e - s))
    return sorted(out, key=lambda u: u.start)


# ponytail: positions are remembered per overlay (name + size) for the session, so an edited string that no
# longer looks like text (e.g. "Hi") keeps its place; a fresh session finds it from the source file again.
_KNOWN: dict = {}


def overlay_units(data: bytes) -> List[Unit]:
    """``units`` of the overlay, merged with the ones found before in another version of the same file."""
    key = (bytes(data[0x20:0x40]), len(data))
    found = {u.start: u for u in units(data)}
    known = _KNOWN.setdefault(key, {})
    for start, unit in found.items():
        known.setdefault(start, unit)
    return [known[s] for s in sorted(known)]


def _current(data: bytes, unit: Unit) -> bytes:
    """The unit's text bytes in ``data`` (its length may differ from the version it was found in)."""
    if unit.kind == "script":
        return data[unit.start:unit.start + unit.room]
    stop = b"\xff" if unit.kind == "cell" else b"\0"
    end = data.find(stop, unit.start, unit.start + unit.room + 1)
    return data[unit.start:end if end >= 0 else unit.start + unit.room]


def unit_text(data: bytes, unit: Unit) -> str:
    raw = _current(data, unit)
    if unit.kind == "cell":
        return "".join(chr(b + 0x20) if b <= 0x5E else "{%02X}" % b for b in raw)
    out, i = [], 0
    while i < len(raw):
        b = raw[i]
        if b == 0x01:
            out.append("\n")
        elif 0x20 <= b < 0x7F:
            out.append(chr(b))
        elif i + 1 < len(raw) and (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF):
            try:
                out.append(raw[i:i + 2].decode("shift_jis"))
            except UnicodeDecodeError:
                out.append("{%02X}{%02X}" % (b, raw[i + 1]))
            i += 1
        else:
            out.append("{%02X}" % b)
        i += 1
    return "".join(out)


def unit_encode(text: str, kind: str, missing: Set[str]) -> bytes:
    out = bytearray()
    for piece in re.split(r"(\{[0-9A-F]{2}\})", str(text).replace("\r", "")):
        tag = TAG_RE.fullmatch(piece)
        if tag:
            out.append(int(tag.group(1), 16))
            continue
        for char in piece:
            if kind == "cell":
                if 0x20 <= ord(char) <= 0x7E:
                    out.append(ord(char) - 0x20)
                else:
                    missing.add(char)
                    out.append(ord("?") - 0x20)
            elif char == "\n":
                out.append(0x01)
            elif 0x20 <= ord(char) < 0x7F:
                out.append(ord(char))
            else:
                try:
                    raw = char.encode("shift_jis")
                except UnicodeEncodeError:
                    raw = b""
                if len(raw) == 2:
                    out += raw
                else:
                    missing.add(char)
                    out += b"?"
    return bytes(out)


def overlay_texts(data: bytes) -> List[str]:
    return [unit_text(data, u) for u in overlay_units(data)]


def overlay_build(data: bytes, texts: List[Optional[str]], missing: Set[str], too_long: List[str]) -> bytes:
    out = bytearray(data)
    for unit, text in zip(overlay_units(data), texts):
        if text is None or text == unit_text(data, unit):
            continue
        raw = unit_encode(text, unit.kind, missing)
        if len(raw) > unit.room:
            too_long.append(str(text))
            raw = raw[:unit.room]
        if unit.kind == "script":
            out[unit.start:unit.start + unit.room] = raw + b" " * (unit.room - len(raw))
        elif unit.kind == "cell":
            out[unit.start:unit.start + unit.room + 2] = raw + b"\xff" + bytes(unit.room + 1 - len(raw))
        else:
            out[unit.start:unit.start + unit.room + 1] = raw + bytes(unit.room + 1 - len(raw))
    return bytes(out)
