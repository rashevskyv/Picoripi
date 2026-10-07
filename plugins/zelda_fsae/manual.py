"""The game's electronic manual (``manpages_narc_eu.blz``): pages of UTF-16 text boxes in a BLZ-packed NARC.

The NARC holds, per language (``de en es fr it``), the table of contents ``arc/ntmc/<lang>/manual`` (NTMC),
the pages ``arc/ntpg/<lang>/page_*`` (NTPG), the viewer's own help ``gpArc/ntpg/<lang>/*`` and shared
pictures (``nttf``, no text). The viewer draws the text with the console's shared font (``nand:/<sharedFont>``).

NTMC / NTPG: ``magic, u16 BOM, u16 version, u32 size, u16 header size, u16 block count`` and blocks
``magic, u32 size`` (4-byte aligned). ``txp1`` is the string table: ``u32 n``, ``n + 1`` u32 offsets (from the
offset table), the strings (UTF-16, zero-terminated). ``txt1`` is a text box: ``x, y, w, h, string index,
line count, font size, line height`` (u16), 16 bytes, then per line ``u16 width, u16 height, u16 0,
u16 bytes``: the line breaks are laid out in advance. Inline codes in a string: ``0x01 0x04 N`` picture N,
``0x02 0x04 C`` colour C (BGR555).

Editor form: one string per text, its lines joined with a newline; ``[pic:N]`` and ``[color:N]`` for the
codes (decimal numbers). Writing lays the boxes' lines out from the newlines. A line that did not change
keeps its width; a new line gets a width from the box's average pixels per character.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Optional, Tuple

from core.containers import nitro

LANGUAGE = "en"
_CODE_RE = re.compile(r"\[(pic|color):(\d+)\]")
_BOX = struct.Struct("<8H")


class FormatError(ValueError):
    """Not a manual file this module reads."""


def to_editor(raw: bytes) -> str:
    units = struct.unpack(f"<{len(raw) // 2}H", raw)
    out, at = [], 0
    while at < len(units):
        unit = units[at]
        if unit in (1, 2) and at + 2 < len(units) and units[at + 1] == 4:
            out.append(f"[{'pic' if unit == 1 else 'color'}:{units[at + 2]}]")
            at += 3
            continue
        if unit == 0:
            break
        out.append(chr(unit))
        at += 1
    return "".join(out)


def from_editor(text: str) -> bytes:
    """The UTF-16 units of one line (no terminator)."""
    out = bytearray()
    at = 0
    for match in _CODE_RE.finditer(text):
        out += text[at:match.start()].encode("utf-16-le")
        value = int(match.group(2)) & 0xFFFF
        out += struct.pack("<3H", 1 if match.group(1) == "pic" else 2, 4, value)
        at = match.end()
    out += text[at:].encode("utf-16-le")
    return bytes(out)


class Page:
    """One NTPG / NTMC file: its blocks, strings and text boxes."""

    def __init__(self, data: bytes):
        data = bytes(data)
        if data[:4] not in (b"NTPG", b"NTMC") or len(data) < 16:
            raise FormatError("Not an NTPG / NTMC file")
        header, count = struct.unpack_from("<HH", data, 12)
        self.head = data[:header]
        self.blocks: List[List] = []
        at = header
        for _ in range(count):
            magic, size = data[at:at + 4], struct.unpack_from("<I", data, at + 4)[0]
            self.blocks.append([magic, data[at + 8:at + size]])
            at += size
        self.strings: List[bytes] = []
        for magic, body in self.blocks:
            if magic == b"txp1":
                n = struct.unpack_from("<I", body, 0)[0]
                offsets = struct.unpack_from(f"<{n + 1}I", body, 4)
                self.strings = [body[4 + offsets[i]:4 + offsets[i + 1]] for i in range(n)]
        self.original = data

    def boxes(self) -> Dict[int, Tuple[int, List[Tuple[int, int, int, int]]]]:
        """String index -> (block index of its first text box, lines)."""
        found: Dict[int, Tuple[int, List[Tuple[int, int, int, int]]]] = {}
        for index, (magic, body) in enumerate(self.blocks):
            if magic == b"txt1":
                box = _BOX.unpack_from(body, 0)
                lines = [struct.unpack_from("<4H", body, 32 + 8 * i) for i in range(box[5])]
                found.setdefault(box[4], (index, lines))
        return found

    def texts(self) -> List[str]:
        """The editor form of every string."""
        boxes = self.boxes()
        out = []
        for index, raw in enumerate(self.strings):
            body = raw[:-2] if raw.endswith(b"\0\0") else raw
            lines = boxes.get(index, (0, []))[1]
            if len(lines) > 1:
                parts, at = [], 0
                for line in lines:
                    parts.append(to_editor(body[at:at + line[3]]))
                    at += line[3]
                out.append("\n".join(parts))
            else:
                out.append(to_editor(body))
        return out

    def build(self, texts: List[str]) -> bytes:
        """The file with ``texts`` (editor form, one per string); unchanged texts keep their bytes."""
        old_texts = self.texts()
        boxes = self.boxes()
        strings = list(self.strings)
        new_boxes: Dict[int, bytes] = {}
        for index, text in enumerate(texts):
            if text is None or text == old_texts[index]:
                continue
            lines = [from_editor(line) for line in text.split("\n")]
            strings[index] = b"".join(lines) + b"\0\0"
            if index in boxes:
                block_index, old_lines = boxes[index]
                new_boxes[block_index] = self._box(block_index, old_lines, old_texts[index].split("\n"), lines)
        if strings == self.strings:
            return self.original
        offsets, body = [], bytearray()
        start = 4 * (len(strings) + 1)
        for raw in strings:
            offsets.append(start + len(body))
            body += raw
        offsets.append(start + len(body))
        table = struct.pack(f"<I{len(offsets)}I", len(strings), *offsets) + bytes(body)
        out = bytearray(self.head)
        for index, (magic, block) in enumerate(self.blocks):
            if magic == b"txp1":
                block = table
            block = new_boxes.get(index, block)
            block = bytes(block) + bytes(-len(block) % 4)
            out += magic + struct.pack("<I", 8 + len(block)) + block
        struct.pack_into("<I", out, 8, len(out))
        return bytes(out)

    def _box(self, block_index: int, old_lines, old_text: List[str], lines: List[bytes]) -> bytes:
        body = self.blocks[block_index][1]
        box = list(_BOX.unpack_from(body, 0))
        chars = sum(line[3] for line in old_lines) // 2 or 1
        per_char = sum(line[0] for line in old_lines) / chars
        old_raw = {from_editor(text): line for text, line in zip(old_text, old_lines)}
        height = old_lines[0][1] if old_lines else box[7]
        entries = []
        for raw in lines:
            kept = old_raw.get(raw)
            # ponytail: the console's font is not on disk; a new line's width is the box average per character.
            width = kept[0] if kept else min(box[2], round(len(raw) // 2 * per_char))
            entries.append(struct.pack("<4H", width, height, 0, len(raw)))
        box[5] = len(lines)
        box[3] = max(box[3], height * len(lines))
        return _BOX.pack(*box) + body[16:32] + b"".join(entries)


class Manual:
    """The manual archive: the English pages, in a fixed order."""

    def __init__(self, raw: bytes):
        raw = bytes(raw)
        plain = raw if nitro.NarcContainer.can_handle(raw) else _unpack(raw)
        self.compressed = plain is not raw
        self.archive = nitro.NarcContainer(plain)
        self.original = raw
        names = self.archive.list_files()
        self.members = ([f"arc/ntmc/{LANGUAGE}/manual"]
                        + sorted(n for n in names if n.startswith(f"arc/ntpg/{LANGUAGE}/"))
                        + sorted(n for n in names if n.startswith(f"gpArc/ntpg/{LANGUAGE}/")))
        self.pages = [Page(self.archive.read_file(name)) for name in self.members]

    @staticmethod
    def block_name(member: str) -> str:
        page = member.rsplit("/", 1)[-1]
        if member.startswith("gpArc/"):
            return f"Manual viewer: {page}"
        return "Manual: contents" if page == "manual" else f"Manual: {page}"

    def build(self, data: List[List[Optional[str]]]) -> bytes:
        changed = False
        for name, page, texts in zip(self.members, self.pages, data):
            new = page.build(list(texts) + [None] * (len(page.strings) - len(texts)))
            if new != page.original:
                self.archive.write_file(name, new)
                changed = True
        if not changed:
            return self.original
        plain = self.archive.pack()
        return nitro.blz_compress(plain) if self.compressed else plain


def _unpack(raw: bytes) -> bytes:
    try:
        plain = nitro.blz_decompress(raw)
    except ValueError as error:
        raise FormatError(f"Not a manual archive: {error}") from None
    if not nitro.NarcContainer.can_handle(plain):
        raise FormatError("Not a manual archive (no NARC inside)")
    return plain


def looks_like(raw: bytes) -> bool:
    return raw[:4] == b"NARC"
