"""One Vagrant Story file as Picoripi blocks: which game string each line is, and how to save it.

``parse`` recognises a file by its structure (the plugin gets bytes, not names): an event, a room,
the item names, the item help, the monster book, an area map, a help page, a plain string table,
or -- anything else -- program data, whose tables and loose strings are found by their shape.
Program data is the only kind found by guessing, so the guess is made on the source file and
remembered by the file's layout (``layout_key``): the translation copy, full of Ukrainian, is read
with the source's answer.

Only English lines are shown: strings of the Japanese leftovers (debug events) and empty strings
are skipped, and stay as they are.
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from . import codec, formats, program

# kinds of line: what the AI and the width check are told
DIALOG, ITEM_NAME, ITEM_HELP, MONSTER, MONSTER_HELP, ROOM_NAME, HELP, MENU, NAME, HUD = (
    "dialog", "item_name", "item_help", "monster", "monster_help", "room_name", "help", "menu", "name", "hud")
ITEM_NAME_SIZE = 24


@dataclass
class Line:
    """One English string of a file."""

    raw: bytes                       # without the end byte (0xE7; a HUD word: ASCII ending with 0)
    kind: str
    where: str
    place: int                       # table index, or offset of a string edited in place
    room: int = 0                    # in place: bytes the string may use with its end byte
    box: Optional[formats.Dialog] = None


@dataclass
class Group:
    """Lines that are saved together: one table, one script, or strings edited in place."""

    name: str
    lines: List[Line]
    table: Optional[formats.Table] = None
    script: Optional[formats.Script] = None


@dataclass
class Doc:
    kind: str                        # event, room, items, item_help, monsters, areas, help, table, program
    groups: List[Group] = field(default_factory=list)
    layout: List[Tuple[int, int]] = field(default_factory=list)      # program: text regions

    @property
    def blocks(self) -> List[List[Line]]:
        return [group.lines for group in self.groups]

    @property
    def names(self) -> Dict[str, str]:
        return {str(i): group.name for i, group in enumerate(self.groups)}

    def texts(self, reader: Optional[codec.Reader] = None) -> List[List[str]]:
        return [[text_of(line, reader) for line in group.lines] for group in self.groups]


def text_of(line: Line, reader: Optional[codec.Reader] = None) -> str:
    """Editor text of a line: the game's codec, or plain ASCII for a HUD word."""
    if line.kind == HUD:
        return line.raw.decode("ascii")
    return (reader or codec.decode)(line.raw)


def _shown(raw: bytes) -> bool:
    return bool(raw) and not codec.is_japanese(raw) and any(
        param is None and code <= 0x85 for code, param in codec.tokens(raw))


def _table_lines(data: bytes, table: formats.Table, kind: str, where: str,
                 boxes: Optional[Dict[int, formats.Dialog]] = None) -> List[Line]:
    lines = []
    for index in range(table.count):
        raw = table.string_at(data, index)[:-1]
        if _shown(raw):
            lines.append(Line(raw, kind, f"{where} #{index}", index, box=(boxes or {}).get(index)))
    return lines


def layout_key(data: bytes, regions: Sequence[Tuple[int, int]]) -> str:
    """What a program file and its translation share: everything outside its text."""
    blank = bytearray(data)
    for begin, end in regions:
        blank[begin:end] = bytes(end - begin)
    return hashlib.sha1(bytes(blank)).hexdigest()


def parse(data: bytes, file_name: str = "", known: Optional[Dict[str, List[Tuple[int, int, int]]]] = None) -> Doc:
    """Read a file; ``known`` maps program layout keys to their regions ``(start, end, kind)``
    (kind 1 = table, 0 = string in place)."""
    stem = file_name.rsplit("/", 1)[-1] or "file"
    if formats.is_event(data):
        return _script_doc("event", data, formats.read_script(data, 0, struct.unpack_from("<H", data, 0)[0]),
                           stem, "Event")
    sections = formats.mpd_header(data)
    if sections is not None:
        start, length = sections[2]
        script = formats.read_script(data, start, length) if length else None
        return _script_doc("room", data, script, stem, "Room")
    names = formats.slot_strings(data, ITEM_NAME_SIZE)
    if names is not None:
        lines = [Line(raw, ITEM_NAME, f"{stem} #{i}", i * ITEM_NAME_SIZE, ITEM_NAME_SIZE)
                 for i, raw in enumerate(names) if _shown(raw)]
        return Doc("items", [Group("Item names", lines)])
    if formats.is_monster_file(data):
        return _monster_doc(data, stem)
    rooms = formats.area_rooms(data)
    if rooms is not None:
        lines = []
        for zone, room, at in rooms:
            raw = data[at:codec.string_end(data, at) - 1]
            if _shown(raw):
                lines.append(Line(raw, ROOM_NAME, f"{stem} zone {zone} room {room}", at, formats.ROOM_NAME))
        return Doc("areas", [Group("Room names", lines)])
    table = formats.help_table(data)
    if table is not None:
        return Doc("help", [Group("Help", _table_lines(data, table, HELP, stem), table=table)])
    table = formats.read_table(data, 0, len(data))
    if table is not None and table.used_end(data) > len(data) * 0.5:
        kind = ITEM_HELP if table.count > 500 else MENU
        return Doc("table" if kind == MENU else "item_help",
                   [Group("Item help" if kind == ITEM_HELP else "Strings", _table_lines(data, table, kind, stem),
                          table=table)])
    return _program_doc(data, stem, known)


def _script_doc(kind: str, data: bytes, script: Optional[formats.Script], stem: str, label: str) -> Doc:
    doc = Doc(kind)
    if script is not None and script.table is not None:
        lines = _table_lines(data, script.table, DIALOG, stem, script.dialogs)
        doc.groups.append(Group(f"{label} dialog", lines, table=script.table, script=script))
    return doc


def _monster_doc(data: bytes, stem: str) -> Doc:
    names = []
    for i in range(formats.MONSTER_COUNT):
        at = i * formats.MONSTER_RECORD + formats.MONSTER_NAME
        raw = data[at:codec.string_end(data, at) - 1]
        if _shown(raw):
            names.append(Line(raw, MONSTER, f"{stem} monster {i}", at, formats.MONSTER_RECORD - formats.MONSTER_NAME))
    table = formats.read_table(data, formats.MONSTER_COUNT * formats.MONSTER_RECORD)
    assert table is not None
    return Doc("monsters", [Group("Monster names", names),
                            Group("Monster descriptions", _table_lines(data, table, MONSTER_HELP, stem), table=table)])


def program_regions(data: bytes) -> List[Tuple[int, int, int]]:
    """``(start, end, kind)`` of the tables (1), the strings in place (0) and the ASCII HUD words (2) of
    program data."""
    tables = formats.find_tables(data)
    regions = [(t.start, t.region_end, 1) for t in tables]
    for offset, length in program.scan(data, [(t.start, t.region_end) for t in tables]):
        regions.append((offset, offset + length, 0))
    for offset, length in program.ascii_scan(data, [(s, e) for s, e, _k in regions]):
        regions.append((offset, offset + length, 2))
    return sorted(regions)


def _program_doc(data: bytes, stem: str, known: Optional[Dict[str, List[Tuple[int, int, int]]]]) -> Doc:
    regions = None
    for key_regions in (known or {}).values():
        if all(end <= len(data) for _s, end, _k in key_regions) and \
                layout_key(data, [(s, e) for s, e, _k in key_regions]) in (known or {}):
            regions = key_regions
            break
    if regions is None:
        regions = program_regions(data)
    doc = Doc("program", layout=[(s, e) for s, e, _k in regions])
    loose, hud = [], []
    for start, end, kind in regions:
        if kind == 1:
            table = formats.read_table(data, start, end, min_letters=0)
            if table is None:
                raise formats.FormatError(f"{stem}: the table at {start:#x} is damaged")
            lines = _table_lines(data, table, MENU, f"{stem} {start:#x}")
            if lines:
                doc.groups.append(Group(f"Table {start:#06x}", lines, table=table))
        elif kind == 2:
            hud.append(Line(data[start:end - 1], HUD, f"{stem} {start:#x}", start, end - start))
        else:
            raw = data[start:end - 1]
            loose.append(Line(raw, NAME, f"{stem} {start:#x}", start, end - start))
    if loose:
        doc.groups.append(Group("Strings", loose))
    if hud:
        doc.groups.append(Group("HUD words (ASCII)", hud))
    return doc


def remember(data: bytes, doc: Doc, known: Dict[str, List[Tuple[int, int, int]]]) -> None:
    """Keep a program file's regions under its layout key."""
    if doc.kind != "program":
        return
    regions = []
    for group in doc.groups:
        if group.table is not None:
            regions.append((group.table.start, group.table.region_end, 1))
        else:
            regions += [(line.place, line.place + line.room, 2 if line.kind == HUD else 0) for line in group.lines]
    known.setdefault(layout_key(data, [(s, e) for s, e, _k in regions]), sorted(regions))


# -- saving ----------------------------------------------------------------------------------

def build(source: bytes, doc: Doc, data: List[List[Optional[str]]], char_codes: Optional[Dict[str, int]] = None,
          missing: Optional[Set[str]] = None, stem: str = "file", reader: Optional[codec.Reader] = None) -> bytes:
    """The file with the editor's texts, built from the source file and its parsed ``doc``. A line
    whose text is what the source string reads as keeps its bytes."""
    out = bytearray(source)
    for number, group in enumerate(doc.groups):
        texts = data[number] if number < len(data) else []
        changed: Dict[int, bytes] = {}
        for index, line in enumerate(group.lines):
            text = texts[index] if index < len(texts) else None
            if text is None or str(text) == text_of(line, reader):
                continue
            if line.kind == HUD:
                if any(not 0x20 <= ord(char) < 0x7F for char in str(text)):
                    raise formats.FormatError(f"{stem}: {group.name}: line {index + 1}: the HUD letters are ASCII "
                                              f"only ({str(text)[:40]!r})")
                new = str(text).encode("ascii")
            else:
                new = codec.encode(str(text), char_codes, missing)
            if new != line.raw:
                changed[index] = new
        if not changed:
            continue
        what = f"{stem}: {group.name}"
        if group.table is not None:
            raws = group.table.strings(source)
            for index, new in changed.items():
                raws[group.lines[index].place] = new + bytes((codec.END,))
            if group.script is not None:
                _write_script(out, source, doc, group.script, raws, what)
            else:
                formats.write_table(out, group.table, raws, what)
        else:
            for index, new in changed.items():
                line = group.lines[index]
                raw = new + (b"\0" if line.kind == HUD else bytes((codec.END,)))
                if len(raw) > line.room:
                    raise formats.FormatError(f"{what}: line {index + 1} needs {len(raw)} bytes, its place "
                                              f"has {line.room} ({codec.decode(new)[:40]!r})")
                out[line.place:line.place + len(raw)] = raw
                tail = slice(line.place + len(raw), line.place + line.room)
                if not any(source[line.place + len(line.raw) + 1:line.place + line.room]):
                    out[tail] = bytes(tail.stop - tail.start)      # a field that was zero after its name stays so
    return bytes(out)


def _write_script(out: bytearray, source: bytes, doc: Doc, script: formats.Script, raws: List[bytes],
                  what: str) -> int:
    if doc.kind == "event":
        section, grow = formats.rebuild_script(source, script, raws, formats.EVENT_SIZE, what)
        out[:len(section)] = section
        out[len(section):] = bytes(formats.EVENT_SIZE - len(section))
        return grow
    sections = formats.mpd_header(source)
    assert sections is not None
    sector_end = -(-len(source) // formats.SECTOR) * formats.SECTOR
    limit = script.length + (sector_end - len(source))
    section, grow = formats.rebuild_script(source, script, raws, limit, what)
    tail = source[script.start + script.length:]
    out[:] = source[:script.start] + section + tail
    if grow:
        values = list(struct.unpack_from("<12I", out, 0))
        values[5] += grow                                   # script length
        for i in range(6, 12, 2):                           # sections after it move
            values[i] += grow
        struct.pack_into("<12I", out, 0, *values)
    return grow
