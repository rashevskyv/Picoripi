"""One Vagrant Story file as Picoripi blocks: which game string each line is, and how to save it.

``parse`` recognises a file by its structure (the plugin gets bytes, not names): an event, a room
(its script, its door scripts and the name of the weapon in its chest), the item names, the item
help, the monster book, an area map, a help page, a plain string table, the staff roll, or --
anything else -- program data, whose tables and loose strings are found by their shape.
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
DIALOG, ITEM_NAME, ITEM_HELP, MONSTER, MONSTER_HELP, ROOM_NAME, HELP, MENU, NAME, HUD, CREDITS = (
    "dialog", "item_name", "item_help", "monster", "monster_help", "room_name", "help", "menu", "name", "hud",
    "credits")
NOTHING = bytes.fromhex("3132372b2c312afa06")     # "nothing ": an empty weapon slot of a room's treasure
ITEM_NAME_SIZE = 24


@dataclass
class Line:
    """One English string of a file."""

    raw: bytes                       # without the end byte (0xE7; a HUD word: ASCII ending with 0; a
                                     # staff-roll line: its ASCII text, no end byte)
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
    if line.kind == CREDITS:
        return "".join(chr(c) if 0x20 <= c < 0x7F else f"{{x{c:02X}}}" for c in line.raw)
    return (reader or codec.decode)(line.raw)


def credits_bytes(text: str) -> bytes:
    """A staff-roll line from its editor text: ASCII, any other byte as ``{xNN}``."""
    out, at = bytearray(), 0
    for match in codec.TAG_RE.finditer(text):
        out += text[at:match.start()].encode("ascii")
        tag = match.group(0)
        if not (len(tag) == 5 and tag[1] == "x"):
            raise ValueError(f"unknown tag {tag}")
        out.append(int(tag[2:4], 16))
        at = match.end()
    out += text[at:].encode("ascii")
    return bytes(out)


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
        return _room_doc(data, sections, stem)
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
    credits = formats.credit_lines(data)
    if credits is not None:
        return Doc("credits", [Group("Staff roll", [Line(data[at:at + size], CREDITS, f"{stem} {at:#x}", at, size)
                                                    for at, size in credits])])
    return _program_doc(data, stem, known)


def _script_doc(kind: str, data: bytes, script: Optional[formats.Script], stem: str, label: str) -> Doc:
    doc = Doc(kind)
    if script is not None and script.table is not None:
        lines = _table_lines(data, script.table, DIALOG, stem, script.dialogs)
        doc.groups.append(Group(f"{label} dialog", lines, table=script.table, script=script))
    return doc


def _room_doc(data: bytes, sections: List[Tuple[int, int]], stem: str) -> Doc:
    """A room: its script's dialog (the first group, as before door scripts were read), the dialog of
    every door script, the name of the weapon in its chest."""
    start, length = sections[2]
    doc = _script_doc("room", data, formats.read_script(data, start, length) if length else None, stem, "Room")
    for slot, script in formats.door_scripts(data, sections):
        assert script.table is not None
        lines = _table_lines(data, script.table, DIALOG, f"{stem} door {slot}", script.dialogs)
        if lines:
            doc.groups.append(Group(f"Door {slot} dialog", lines, table=script.table, script=script))
    at = formats.treasure_name(data, sections)
    if at is not None:
        raw = data[at:codec.string_end(data, at) - 1]
        if _shown(raw) and raw != NOTHING:
            doc.groups.append(Group("Treasure", [Line(raw, NAME, f"{stem} treasure", at,
                                                      formats.TREASURE_NAME_SIZE)]))
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
    scripts: List[Tuple[Group, List[bytes], str]] = []
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
            elif line.kind == CREDITS:
                try:
                    new = credits_bytes(str(text))
                except ValueError as error:
                    raise formats.FormatError(f"{stem}: {group.name}: line {index + 1}: the staff roll is ASCII "
                                              f"only ({error})") from None
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
                scripts.append((group, raws, what))
            else:
                formats.write_table(out, group.table, raws, what)
        else:
            for index, new in changed.items():
                line = group.lines[index]
                if line.kind == CREDITS:
                    if len(new) > line.room:
                        raise formats.FormatError(f"{what}: line {index + 1} needs {len(new)} bytes, its place "
                                                  f"has {line.room}")
                    out[line.place:line.place + line.room] = new + b" " * (line.room - len(new))
                    continue
                raw = new + (b"\0" if line.kind == HUD else bytes((codec.END,)))
                if len(raw) > line.room:
                    raise formats.FormatError(f"{what}: line {index + 1} needs {len(raw)} bytes, its place "
                                              f"has {line.room} ({codec.decode(new)[:40]!r})")
                out[line.place:line.place + len(raw)] = raw
                tail = slice(line.place + len(raw), line.place + line.room)
                if not any(source[line.place + len(line.raw) + 1:line.place + line.room]):
                    out[tail] = bytes(tail.stop - tail.start)      # a field that was zero after its name stays so
    # Scripts last, the one furthest into the file first: a script that grows moves only what follows it.
    for group, raws, what in sorted(scripts, key=lambda item: -item[0].script.start):
        _write_script(out, len(source), doc, group.script, raws, what)
    return bytes(out)


def _write_script(out: bytearray, source_size: int, doc: Doc, script: formats.Script, raws: List[bytes],
                  what: str) -> int:
    """Put a script with a new dialog table into ``out``. In a room, a script that grows moves the
    rest of the file: the room header follows, and after a door script the door section's offsets."""
    if doc.kind == "event":
        section, grow = formats.rebuild_script(bytes(out), script, raws, formats.EVENT_SIZE, what)
        out[:len(section)] = section
        out[len(section):] = bytes(formats.EVENT_SIZE - len(section))
        return grow
    sections = formats.mpd_header(bytes(out))
    assert sections is not None
    sector_end = -(-source_size // formats.SECTOR) * formats.SECTOR
    limit = script.length + (sector_end - len(out))
    section, grow = formats.rebuild_script(bytes(out), script, raws, limit, what)
    out[script.start:script.start + script.length] = section
    if grow:
        number = next(i for i, (start, length) in enumerate(sections) if start <= script.start < start + length)
        values = list(struct.unpack_from("<12I", out, 0))
        values[number * 2 + 1] += grow                      # the section's length
        for i in range(number * 2 + 2, 12, 2):              # sections after it move
            values[i] += grow
        struct.pack_into("<12I", out, 0, *values)
        if number == formats.DOOR_SECTION:                  # door scripts after this one move
            start = sections[number][0]
            mine = script.start - start
            offsets = [o + grow if o > mine else o for o in struct.unpack_from(f"<{formats.DOOR_SLOTS}H", out, start)]
            struct.pack_into(f"<{formats.DOOR_SLOTS}H", out, start, *offsets)
    return grow
