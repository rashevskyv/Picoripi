"""One Hyrule Warriors DE text file: twelve language sections, the English one exposed for editing.

Layout: an offset container of 12 language sections (0 JA, 1 EN-US, 2 FR, 3 DE, 4 IT, 5 ES,
6 EN-EU, 7 FR-CA, 8 ES-LA, 9 KO, 10 ZH-CN, 11 ZH-TW); each section is XL tables, sometimes nested in
another container. The English section is edited; on save every changed cell is also copied into the
mirror sections (EN-EU) where the table has the same shape there.

Which cells are strings to translate is decided so that the source and the saved translation give
the same list: a cell is exposed when it holds text and is not a Japanese leftover (byte-identical to
the Japanese section's cell and Japanese). A translated cell is never written empty, so it stays
exposed after a reload.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

from . import ktbin, tags

LANGUAGES = ("JA", "EN-US", "FR", "DE", "IT", "ES", "EN-EU", "FR-CA", "ES-LA", "KO", "ZH-CN", "ZH-TW")
SECTION_JA = 0
SECTION_EN = 1
MIRROR_SECTIONS = (6,)

Node = Union[ktbin.XlTable, list, bytes]

_ROLES = {
    (3, 3, 3, 0): "Messages",
    (0,) * 9: "Place names (forms)",
    (0,) * 8: "Names (forms)",
    (2, 2, 2, 2, 2, 0): "Subtitles",
    (1, 0): "Voice lines",
    (1, 2, 2, 2, 3, 3, 3, 3, 0): "Voice lines (variants)",
    (0,): "Text",
}


def table_role(table: ktbin.XlTable) -> str:
    return _ROLES.get(tuple(table.types), "Table")


SUBTITLE_SPEAKER_ROW = 8  # column 4 of a subtitle row: 0 a line, 8 the name shown with it


def subtitle_speaker_rows(table: ktbin.XlTable) -> Dict[int, int]:
    """Subtitle row -> the row that names its speaker (same start and end frame, column 4 == 8)."""
    if table_role(table) != "Subtitles":
        return {}
    names = {(r[2], r[3]): i for i, r in enumerate(table.rows) if r[4] == SUBTITLE_SPEAKER_ROW}
    return {i: names[(r[2], r[3])] for i, r in enumerate(table.rows)
            if r[4] != SUBTITLE_SPEAKER_ROW and (r[2], r[3]) in names}


def parse_tree(data: bytes) -> Node:
    if data[:2] == b"XL":
        return ktbin.parse_xl(data)
    if ktbin.looks_like_container(data):
        payloads, _gaps = ktbin.split_container(data)
        return [parse_tree(p) for p in payloads]
    return data


def build_tree(node: Node) -> bytes:
    if isinstance(node, ktbin.XlTable):
        return ktbin.build_xl(node)
    if isinstance(node, list):
        return ktbin.build_container([build_tree(n) for n in node])
    return node


def leaves(node: Node) -> List[ktbin.XlTable]:
    if isinstance(node, ktbin.XlTable):
        return [node]
    if isinstance(node, list):
        return [t for n in node for t in leaves(n)]
    return []


def english_tables(data: bytes) -> List[ktbin.XlTable]:
    """The English section's tables (``TextFile(data).tables``) without parsing the other 11 languages."""
    if not ktbin.looks_like_container(data):
        raise FormatError("not a 12-language text file")
    payloads, _gaps = ktbin.split_container(data)
    if len(payloads) != len(LANGUAGES):
        raise FormatError("not a 12-language text file")
    return leaves(parse_tree(payloads[SECTION_EN]))


def is_japanese(raw: bytes) -> bool:
    s = re.sub(rb"\x1b.[0-9]?|%[0-9]?[sd]", b"", raw.split(b"\0", 1)[0])
    if not s or sum(ch >= 0x80 for ch in s) / len(s) < 0.2:
        return False
    try:
        s.decode("cp932")
    except UnicodeDecodeError:
        return False
    return True


def is_wide(table: ktbin.XlTable) -> bool:
    """UTF-16 table: its cells look like ``X\\0Y\\0...`` (msgdata title table)."""
    for row in table.rows:
        for c in table.string_columns:
            cell = row[c]
            if len(cell) >= 4 and cell[0] and not cell[1]:
                return True
    return False


def split_cell(cell: bytes, wide: bool) -> Tuple[bytes, bytes]:
    """(text bytes, terminator and anything after it)."""
    if wide:
        for i in range(0, len(cell) - 1, 2):
            if cell[i] == 0 and cell[i + 1] == 0:
                return cell[:i], cell[i:]
        return cell, b""
    end = cell.find(b"\0")
    return (cell, b"") if end < 0 else (cell[:end], cell[end:])


def decode_cell(cell: bytes, wide: bool) -> str:
    text, _tail = split_cell(cell, wide)
    return tags.to_editor(tags.units_from_wide(text) if wide else list(text))


def encode_cell(text: str, original: bytes, wide: bool) -> Tuple[bytes, List[str]]:
    """New cell bytes for ``text``, keeping the original terminator; and characters that had no byte."""
    _old, tail = split_cell(original, wide)
    units = tags.from_editor(text)
    if wide:
        return tags.wide_from_units(units) + (tail or b"\0\0"), []
    missing = sorted({u for u in units if isinstance(u, str)})
    body = bytes(u if isinstance(u, int) else 0x3F for u in units)
    return body + (tail or b"\0"), missing


@dataclass
class Block:
    table: int  # index into the English section's tables
    cells: List[Tuple[int, int]]  # (row, column) of every exposed string
    wide: bool
    name: str


class FormatError(ValueError):
    pass


class TextFile:
    def __init__(self, data: bytes, verify: bool = False):
        """``verify``: also check that the file rebuilds byte-exact (before a save writes it back)."""
        tree = parse_tree(data)
        if not isinstance(tree, list) or len(tree) != len(LANGUAGES):
            raise FormatError("not a 12-language text file")
        if verify and build_tree(tree) != data:
            raise FormatError("the file does not rebuild byte-exact")
        self.tree = tree
        self.sections = [leaves(s) for s in tree]
        self.tables = self.sections[SECTION_EN]
        if not any(t.string_columns for t in self.tables):
            raise FormatError("no text in the English section")
        ja = self.sections[SECTION_JA]
        same_shape = _shape(ja) == _shape(self.tables)
        self.blocks: List[Block] = []
        for ti, table in enumerate(self.tables):
            wide = is_wide(table)
            cells = []
            for r, row in enumerate(table.rows):
                for c in table.string_columns:
                    cell = row[c]
                    if not split_cell(cell, wide)[0]:
                        continue
                    if same_shape and cell == ja[ti].rows[r][c] and is_japanese(cell):
                        continue
                    cells.append((r, c))
            if cells:
                self.blocks.append(Block(ti, cells, wide, self._name(ti, table)))

    @staticmethod
    def _name(ti: int, table: ktbin.XlTable) -> str:
        role = table_role(table)
        if role == "Subtitles" and table.rows:
            return f"{ti:03d} Subtitles (scene {table.rows[0][0]})"
        return f"{ti:03d} {role}"

    def texts(self) -> List[List[str]]:
        return [[decode_cell(self.tables[b.table].rows[r][c], b.wide) for r, c in b.cells] for b in self.blocks]

    def names(self) -> Dict[str, str]:
        return {str(i): b.name for i, b in enumerate(self.blocks)}

    def cell(self, block: int, string: int) -> Tuple[ktbin.XlTable, int, int]:
        b = self.blocks[block]
        r, c = b.cells[string]
        return self.tables[b.table], r, c

    def build(self, texts: List[List[Optional[str]]], missing: Optional[set] = None) -> bytes:
        """The file with ``texts`` written into the English section (and its mirrors).

        A text equal to what the original decodes to keeps the original bytes; an empty text keeps
        the original too (an empty cell would stop being a string to translate).
        """
        for bi, block in enumerate(self.blocks):
            block_texts = texts[bi] if bi < len(texts) else []
            table = self.tables[block.table]
            for si, (r, c) in enumerate(block.cells):
                text = block_texts[si] if si < len(block_texts) else None
                original = table.rows[r][c]
                if not text or text == decode_cell(original, block.wide):
                    continue
                new, lost = encode_cell(text, original, block.wide)
                if missing is not None:
                    missing.update(lost)
                table.rows[r][c] = new
                for m in MIRROR_SECTIONS:
                    mirror = self.sections[m]
                    if block.table < len(mirror) and _shape([mirror[block.table]]) == _shape([table]):
                        mirror[block.table].rows[r][c] = new
        return build_tree(self.tree)


def _shape(tables: List[ktbin.XlTable]) -> List[Tuple[int, Tuple[int, ...]]]:
    return [(len(t.rows), tuple(t.types)) for t in tables]
