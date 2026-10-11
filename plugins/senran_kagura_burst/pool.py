"""Text compiled into Senran Kagura Burst's executable (``exefs/code.bin``, decompressed).

The menus, mission briefings, item and music descriptions and the battle lines are NUL-terminated UTF-16LE strings
that lie back to back in the read-only data. They are written back in place: a text may not be longer than the
original string plus the NUL padding after it (a shorter text is padded with NUL units, the terminator stays).

Finding the strings: a run of units that are ASCII text, a line feed, Latin-1 and Latin Extended letters, Cyrillic
(a translation) or one of the few symbols the game's font draws (circled digits, the music note ...), at least
three long, after a NUL unit and ended by a NUL unit, with two letters in a row and not a file name or an
identifier. Areas are clusters of such runs (gap below 2 KiB) with at least 20 strings; the file names of the game
(``rom:/...``) lie between the texts and are not text. A translated file is read with the strings found in the
original (``reference``), so a text that no longer looks like one is still found.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Optional, Tuple

GAP = 2048
MIN_AREA = 20
BLOCK = 200   # strings per block in the editor
_UNIT = rb"(?:[\x20-\x7e\n\xa0-\xff]\x00|[\x00-\xff][\x01\x02\x04\x20-\x30])"
_RUN = re.compile(rb"(?<=\x00\x00)(" + _UNIT + rb"{3,})\x00\x00")
_IDENT = re.compile(r"^[A-Za-z0-9_.\\/:%\-]+$")
_ALLOWED_HIGH = re.compile("[Ā-ɏЀ-ӿ‐-‧①-⑳■-◿★☆♪　]")
_LETTERS = re.compile(r"[^\W\d_]{2}")


class PoolError(ValueError):
    pass


def is_text(text: str) -> bool:
    if not _LETTERS.search(text):
        return False
    if any(ord(c) > 0xFF and not _ALLOWED_HIGH.match(c) for c in text):
        return False
    if any(ord(c) < 0x20 and c != "\n" for c in text):
        return False
    if text.startswith(("rom:", "data:", "/", ".")) or "::" in text or ".cpp" in text or "()" in text:
        return False
    if not re.search(r"\s", text) and (
            any(c in text for c in "/\\_:") or re.search(r"[A-Za-z0-9]\.[A-Za-z0-9]{1,4}$", text)
            or re.fullmatch(r"%\w{1,3}", text)):
        return False        # a file name or an identifier
    if len(text) > 12 and " " not in text and re.search(r"[a-z][A-Z]", text):
        return False
    letters = sum(c.isalpha() or c.isspace() for c in text)
    return letters * 2 >= len(text)


class Item:
    __slots__ = ("start", "room", "area")

    def __init__(self, start: int, room: int, area: int) -> None:
        self.start, self.room, self.area = start, room, area


def _find(raw: bytes) -> List[Item]:
    found: List[Tuple[int, int, bool]] = []
    for m in _RUN.finditer(raw):
        if m.start() % 2:
            continue
        try:
            text = m.group(1).decode("utf-16-le")
        except UnicodeDecodeError:
            continue
        found.append((m.start(), len(text), is_text(text)))
    areas: List[List[Tuple[int, int, bool]]] = []
    for entry in found:
        if areas and entry[0] - (areas[-1][-1][0] + areas[-1][-1][1] * 2) <= GAP:
            areas[-1].append(entry)
        else:
            areas.append([entry])
    items: List[Item] = []
    number = 0
    for area in areas:
        if sum(1 for e in area if e[2]) < MIN_AREA:
            continue
        number += 1
        for start, units, text_like in area:
            if not text_like:
                continue
            end = start + units * 2
            zeros = 0
            while end + zeros * 2 + 2 <= len(raw) and raw[end + zeros * 2:end + zeros * 2 + 2] == b"\0\0":
                zeros += 1
            items.append(Item(start, units + max(0, zeros - 1), number))
    return items


class Pool:
    """The editable strings of the executable and the way to write them back.

    ``reference``: the game's original executable; the strings are found in it and read from ``raw`` (the same
    positions), so a file whose texts were already translated keeps its strings.
    """

    def __init__(self, raw: bytes, reference: Optional[bytes] = None) -> None:
        raw = bytes(raw)
        if len(raw) < 0x10000 or raw[:4] == b"TAMS":
            raise PoolError("not an executable")
        self.raw = raw
        base = bytes(reference) if reference is not None and len(reference) == len(raw) else raw
        self.items = _find(base)

    def _read(self, item: Item) -> str:
        if item.start + item.room * 2 > len(self.raw):
            return ""
        units = struct.unpack_from(f"<{item.room}H", self.raw, item.start)
        out = []
        for u in units:
            if u == 0:
                break
            out.append(chr(u))
        return "".join(out)

    def _flat(self) -> List[Item]:
        return sorted(self.items, key=lambda i: (i.area, i.start))

    def texts(self) -> List[List[str]]:
        """The strings in file order, ``BLOCK`` strings to a list."""
        flat = [self._read(i) for i in self._flat()]
        return [flat[k:k + BLOCK] for k in range(0, len(flat), BLOCK)]

    def capacities(self) -> List[List[int]]:
        flat = [i.room for i in self._flat()]
        return [flat[k:k + BLOCK] for k in range(0, len(flat), BLOCK)]

    def rebuild(self, texts: List[List[str]]) -> bytes:
        flat = [t for block in texts for t in block]
        if len(flat) != len(self.items):
            raise PoolError(f"{len(flat)} strings for {len(self.items)} in the executable")
        out = bytearray(self.raw)
        for item, text in zip(self._flat(), flat):
            try:
                blob = str(text).encode("utf-16-le")
            except UnicodeEncodeError:
                raise PoolError(f"the string at {item.start:#x} has a character outside UTF-16") from None
            if any(blob[i:i + 2] == b"\0\0" for i in range(0, len(blob), 2)):
                raise PoolError(f"the string at {item.start:#x} contains a NUL character")
            if len(blob) // 2 > item.room:
                raise PoolError(f"the string at {item.start:#x} is {len(blob) // 2 - item.room} characters too long "
                                f"(room {item.room} characters): {str(text)[:40]!r}")
            end = item.start + item.room * 2
            out[item.start:end] = blob + b"\0" * (end - item.start - len(blob))
        return bytes(out) if out != self.raw else self.raw


def check(raw: bytes) -> Dict[str, int]:
    """Counts for a quick look: ``{"strings": n, "blocks": m}``."""
    p = Pool(raw)
    return {"strings": len(p.items), "blocks": len(p.texts())}
