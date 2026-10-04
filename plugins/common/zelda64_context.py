"""Offline OoT/MM translation context from a zeldaret decomp and a ROM: speakers, scenes and glossary seeds per message id.

Run once per game; the plugin ships the JSON and only reads it.  Everything here is
evidence, not truth: see ``scan_text_ids`` for the heuristics and their limits.

    python -m plugins.common.zelda64_context --game mm --decomp <mm> --rom <rom.z64> --out context.json

Sources (paths relative to the decomp root):
- ``src/overlays/**`` and ``src/code``: text-id literals in talk code -> who uses a message;
  the file header `` * Description:`` -> a human name for the actor.
- ``include/tables/actor_table.h`` / ``scene_table.h``: actor and scene ids, scene names
  (MM: the comment above each entry and the title-card message id).
- ``baseroms/<version>/segments.csv``: dmadata file names in ROM order, used to find
  the scene and room files; their actor lists say which actor stands in which scene.
- ``ovl_player_actor``'s ``GET_ITEM`` table: item -> get-item message (item names).
- MM ``include/tables/notebook_table.h``: Bombers' Notebook people and their messages.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

GAMES = {
    "mm": {"segments": "baseroms/n64-us/segments.csv", "text_file": "message_data_static",
           "table": 0x1210D8, "actor_mask": 0x1FFF, "red": 0x01, "item_descriptions": 0x1700,
           "enemy_note": ("TATL_HINT_ID_", 0x1900, "Tatl")},
    "oot": {"segments": "baseroms/ntsc-1.0/segments.csv", "text_file": "nes_message_data_static",
            "table": 0xFD9EC, "actor_mask": 0xFFFF, "red": 0x41, "item_descriptions": 0,
            "enemy_note": ("NAVI_ENEMY_", 0x600, "Navi")},
}

# Actors whose message comes from their placement params, not from code
# (read off each actor's init/talk code in the decomp).  Exact per scene.
PLACEMENT_TEXT: Dict[str, Dict[str, Callable[[int], int]]] = {
    "oot": {
        "En_Kanban": lambda p: p | 0x300,                   # signpost
        "Elf_Msg": lambda p: (p & 0xFF) + 0x100,            # Navi call spot
        "Elf_Msg2": lambda p: (p & 0xFF) + 0x100,           # Navi check spot
        "En_Wonder_Talk2": lambda p: 0x200 | ((p >> 6) & 0xFF),
        "En_Gs": lambda p: (p & 0xFF) + 0x400,              # Gossip Stone hint
    },
    "mm": {
        "En_Kanban": lambda p: p | 0x300,                   # signpost
        "Elf_Msg": lambda p: (p & 0xFF) + 0x200,            # Tatl hint spots
        "Elf_Msg2": lambda p: (p & 0xFF) + 0x200,
        "Elf_Msg3": lambda p: (p & 0xFF) + 0x200,
        "Elf_Msg4": lambda p: (p & 0xFF) + 0x200,
    },
}

MAX_SCENES = 6        # an actor placed in more scenes than this is too generic to say "where"
MAX_GLOSSARY_IDS = 12

# ---------------------------------------------------------------- C source scan

_COMMENT_RE = re.compile(r'"(?:\\.|[^"\\\n])*"|/\*.*?\*/|//[^\n]*', re.S)
_HEX = r"0x[0-9A-Fa-f]{1,4}\b"
_HEX_RE = re.compile(_HEX)
_TEXT_NAME = re.compile(r"(?i)text|msg|message")
_NOT_TEXT = re.compile(r"(?i)textur|sfx|sched|state|advance|close|choice|switch_flag|ocarina|load|draw|"
                       r"font|timer|rupee|digit|color|face|queue|decode|setup|grow|highlight")
_TEXT_VAR = r"[A-Za-z_]\w*(?:->|\.)?\w*(?:[Tt]ext[Ii][Dd]|[Mm]sg[Ii][Dd]|TEXTID|MSGID)\w*"
_ASSIGN_RE = re.compile(_TEXT_VAR + r"\s*(?:\[[^\]]*\])?\s*=(?!=)\s*([^;]*)")
_COMPARE_RE = re.compile(_TEXT_VAR + r"\s*[!=]=\s*(" + _HEX + ")|(" + _HEX + r")\s*[!=]=\s*" + _TEXT_VAR)
_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_SWITCH_RE = re.compile(r"\bswitch\s*\(")
_CASE_RE = re.compile(r"\bcase\s+(" + _HEX + r")\s*:")
_FUNC_RE = re.compile(r"^[A-Za-z_][\w \t\*]*?\b([A-Za-z_]\w*)\s*\([^;{)]*\)\s*\{", re.M)
_RETURN_RE = re.compile(r"\breturn\b([^;]*);")
_ARRAY_RE = re.compile(r"\b([A-Za-z_]\w*)\s*(?:\[[^\]]*\])+\s*=\s*\{")
_INDEXED_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\[")
_DEFINE_RE = re.compile(r"^[ \t]*#[ \t]*define[ \t]+(\w+)(?:\([^)]*\))?[ \t]+(.*)$", re.M)


def _strip_comments(src: str) -> str:
    def repl(m: re.Match) -> str:
        s = m.group(0)
        return s if s.startswith('"') else "\n" * s.count("\n") + " "
    return _COMMENT_RE.sub(repl, src)


def _balanced(src: str, open_index: int) -> int:
    """Index just past the bracket that closes the one at ``open_index``."""
    pairs = {"(": ")", "{": "}", "[": "]"}
    opener = src[open_index]
    closer = pairs[opener]
    depth = 0
    for i in range(open_index, len(src)):
        if src[i] == opener:
            depth += 1
        elif src[i] == closer:
            depth -= 1
            if depth == 0:
                return i + 1
    return len(src)


_TYPEDEF_RE = re.compile(r"typedef\s+struct\s*\w*\s*\{([^{}]*)\}\s*(\w+)\s*;")


def _hexes(text: str) -> Set[int]:
    return {int(h, 16) for h in _HEX_RE.findall(text)}


def _split_top(text: str) -> List[str]:
    """Split on commas that are not inside brackets."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


def _struct_table_ids(src: str) -> Set[int]:
    """Literals in the ``*TextId`` columns of arrays of structs (shop item tables and the like)."""
    found: Set[int] = set()
    for body, type_name in _TYPEDEF_RE.findall(src):
        names = []
        for decl in body.split(";"):
            m = re.search(r"\(\s*\*\s*(\w+)\s*\)", decl) or re.search(r"(\w+)\s*(?:\[[^\]]*\])*\s*$", decl)
            if decl.strip():
                names.append(m.group(1) if m else "")
        columns = [i for i, n in enumerate(names) if re.search(r"(?i)textid|msgid", n)]
        if not columns:
            continue
        for m in re.finditer(r"\b" + type_name + r"\s+\w+\s*(?:\[[^\]]*\])+\s*=\s*\{", src):
            for row in _split_top(src[m.end():_balanced(src, m.end() - 1) - 1]):
                cells = _split_top(row[1:-1]) if row.startswith("{") else []
                for column in columns:
                    if column < len(cells):
                        found |= _hexes(cells[column])
    return found


def _is_text_name(name: str) -> bool:
    return bool(_TEXT_NAME.search(name)) and not _NOT_TEXT.search(name)


def scan_text_ids(src: str) -> Set[int]:
    """Hex literals that this C source uses as message ids.  Heuristic; callers filter by the real id set.

    Accepted contexts: ``xTextId = <expr>`` (all literals of the expression, so ternaries
    count), ``textId ==/!= 0x..``, arguments of calls whose name says text/msg/message
    (``Message_StartTextbox``, ``MSCRIPT_CMD_BEGIN_TEXT`` ...; texture/sfx/state helpers are
    excluded by name), ``case`` labels of a ``switch`` on a text-id variable, ``return``
    values of functions named ``*Text*``/``*Msg*``, initialisers of arrays named that way or
    indexed in one of those contexts, ``*TextId`` columns of struct tables, and
    ``#define *TEXT*/*MSG*`` values.
    Ids below 0x100 (item messages in both games) are kept only when passed straight to
    ``Message_StartTextbox``/``Message_ContinueTextbox`` or in a ``*TextId`` struct column: elsewhere small literals are mostly
    state numbers in fields the decomp happens to call ``textId``.
    Missed: ids held in unnamed locals/fields (``this->unk_1E0 = 0x1234``) and ids built by
    arithmetic on variables.
    """
    src = _strip_comments(src)
    found: Set[int] = set()
    text_arrays: Set[str] = set()
    direct = _struct_table_ids(src)
    for name, value in _DEFINE_RE.findall(src):
        if _is_text_name(name):
            found |= _hexes(value)
    for m in _ASSIGN_RE.finditer(src):
        found |= _hexes(m.group(1))
        text_arrays.update(_INDEXED_RE.findall(m.group(1)))
    for m in _COMPARE_RE.finditer(src):
        found |= _hexes(m.group(1) or m.group(2))
    for m in _CALL_RE.finditer(src):
        if _is_text_name(m.group(1)):
            args = src[m.end() - 1:_balanced(src, m.end() - 1)]
            found |= _hexes(args)
            text_arrays.update(_INDEXED_RE.findall(args))
            if m.group(1) in ("Message_StartTextbox", "Message_ContinueTextbox"):
                direct |= _hexes(args)
    for m in _SWITCH_RE.finditer(src):
        expr_end = _balanced(src, m.end() - 1)
        if not re.search(r"(?i)textid|msgid", src[m.end():expr_end]):
            continue
        brace = src.find("{", expr_end)
        if brace >= 0:
            found |= {int(h, 16) for h in _CASE_RE.findall(src[brace:_balanced(src, brace)])}
    for m in _FUNC_RE.finditer(src):
        if _is_text_name(m.group(1)):
            body = src[m.end() - 1:_balanced(src, m.end() - 1)]
            for ret in _RETURN_RE.findall(body):
                found |= _hexes(ret)
                text_arrays.update(_INDEXED_RE.findall(ret))
    for m in _ARRAY_RE.finditer(src):
        name = m.group(1)
        if (_is_text_name(name) and "script" not in name.lower()) or name in text_arrays:  # MsgScript: see calls
            found |= _hexes(src[m.end() - 1:_balanced(src, m.end() - 1)])
    return ({v for v in found if v >= 0x100} | direct) - {0, 0xFFFF}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


_ENEMY_NOTE_RE = re.compile(r"\b(?:hintId|naviEnemyId)\s*=\s*([A-Z][A-Z0-9_]+)")


def actor_sources(decomp: Path) -> Dict[str, Tuple[str, Set[int], Set[str]]]:
    """Overlay (``En_Ma4``, ``code/z_message``) -> (description, message ids its code uses, enemy-note enums)."""
    out: Dict[str, Tuple[str, Set[int], Set[str]]] = {}
    overlays = decomp / "src" / "overlays"
    for directory in sorted(p for p in overlays.glob("*/*") if p.is_dir()):
        name = directory.name[4:] if directory.name.startswith("ovl_") else directory.name
        files = [p for p in sorted(directory.rglob("*")) if p.suffix in (".c", ".h") and "_JPN" not in p.name]
        src = "\n".join(_read(p) for p in sorted(files, key=lambda p: p.suffix != ".h"))
        m = re.search(r"^ \* Description:[ \t]*(.*\S)", src, re.M)
        out[name] = (m.group(1) if m else "", scan_text_ids(src), set(_ENEMY_NOTE_RE.findall(src)))
    for path in sorted((decomp / "src" / "code").glob("*.c")):
        if "_JPN" not in path.name:
            out[f"code/{path.stem}"] = ("", scan_text_ids(_read(path)), set())
    return out


# ---------------------------------------------------------------- tables

def _indexed_defines(path: Path, macro: str) -> List[Tuple[int, List[str], str]]:
    """(index, arguments, comment line above) for each ``/* 0xNN */ MACRO(...)`` line."""
    rows = []
    comment = ""
    for line in _read(path).splitlines():
        stripped = line.strip()
        if stripped.startswith("//"):
            comment = stripped[2:].strip()
            continue
        m = re.match(r"/\*\s*(0x[0-9A-Fa-f]+)\s*\*/\s*" + macro + r"\((.*)\)\s*$", stripped)
        if m:
            rows.append((int(m.group(1), 16), [a.strip() for a in m.group(2).split(",")], comment))
            comment = ""
    return rows


def actor_table(decomp: Path) -> Dict[int, str]:
    """Actor id -> overlay name (``En_Ma4``)."""
    return {index: args[0] for index, args, _ in
            _indexed_defines(decomp / "include/tables/actor_table.h", r"DEFINE_ACTOR(?:_INTERNAL)?")}


def _pretty_enum(enum: str) -> str:
    words = re.sub(r"^SCENE_", "", enum).split("_")
    return " ".join(w.capitalize() if w.isalpha() else w for w in words)


def scene_table(decomp: Path, game: str) -> Dict[int, dict]:
    """Scene id -> {segment, enum, name, title_text_id (MM)}."""
    scenes = {}
    for index, args, comment in _indexed_defines(decomp / "include/tables/scene_table.h", "DEFINE_SCENE"):
        if game == "mm":
            segment, enum, title = args[0], args[1], int(args[2], 0)
            name = comment or _pretty_enum(enum)
        else:
            segment, enum, title = args[0], args[2], 0
            name = _pretty_enum(enum)
        scenes[index] = {"segment": segment, "enum": enum, "name": name, "title_text_id": title}
    return scenes


def get_item_table(decomp: Path) -> List[Tuple[str, int]]:
    """(``ITEM_*``, get-item message id) from Player's ``GET_ITEM`` table."""
    src = _read(decomp / "src/overlays/actors/ovl_player_actor/z_player.c")
    return [(item, int(text_id, 16)) for item, text_id in
            re.findall(r"^\s*GET_ITEM\((ITEM_\w+),\s*\w+,\s*\w+,\s*(0x[0-9A-Fa-f]+)", src, re.M)]


def notebook_table(decomp: Path) -> List[Tuple[str, str, List[int]]]:
    """MM Bombers' Notebook: (kind ``person``/``event``, name from the enum, its message ids)."""
    path = decomp / "include/tables/notebook_table.h"
    rows: List[Tuple[str, str, List[int]]] = []
    if not path.exists():
        return rows
    for _index, args, _ in _indexed_defines(path, "DEFINE_PERSON"):
        name = _pretty_enum(args[0].replace("BOMBERS_NOTEBOOK_PERSON_", ""))
        rows.append(("person", name, [int(args[2], 16), int(args[4], 16)]))
    for _index, args, _ in _indexed_defines(path, "DEFINE_EVENT"):
        name = _pretty_enum(args[0].replace("BOMBERS_NOTEBOOK_EVENT_", ""))
        rows.append(("event", name, [int(args[3], 16), int(args[4], 16)]))
    return rows


def enum_values(decomp: Path, prefix: str) -> Dict[str, int]:
    """``/* 0xNN */ PREFIX_NAME`` enum members anywhere under ``include/``."""
    values: Dict[str, int] = {}
    pattern = re.compile(r"/\*\s*(0x[0-9A-Fa-f]+)\s*\*/\s*(" + prefix + r"\w+)")
    for path in sorted((decomp / "include").rglob("*.h")):
        for value, name in pattern.findall(_read(path)):
            values.setdefault(name, int(value, 16))
    return values


# ---------------------------------------------------------------- ROM: messages

class Message:
    """One message: plain text, highlighted ``(colour, text)`` spans and the ids it links to."""

    def __init__(self, text: str, spans: List[Tuple[int, str]], links: List[int]):
        self.text, self.spans, self.links = text, spans, links


_OOT_ARGS = {0x05: 1, 0x06: 1, 0x07: 2, 0x0C: 1, 0x0E: 1, 0x11: 2, 0x12: 2, 0x13: 1, 0x14: 1,
             0x15: 3, 0x1E: 1}
_MM_ARGS = {0x14: 1, 0x1B: 2, 0x1C: 2, 0x1D: 2, 0x1E: 2, 0x1F: 2}


def decode_message(game: str, raw: bytes) -> Message:
    """Plain text of a raw message (OoT: body; MM: 11-byte header + body)."""
    links: List[int] = []
    if game == "mm":
        next_id = struct.unpack_from(">H", raw, 3)[0] if len(raw) >= 5 else 0xFFFF
        if next_id != 0xFFFF:
            links.append(next_id)
        body, args, end, default_color = raw[11:], _MM_ARGS, 0xBF, 0
    else:
        body, args, end, default_color = raw, _OOT_ARGS, 0x02, 0x40
    text: List[str] = []
    spans: List[Tuple[int, str]] = []
    span: List[str] = []
    color = default_color

    def close_span() -> None:
        term = " ".join("".join(span).split()).strip(" .,!?:;\"")
        if term:
            spans.append((color, term))
        span.clear()

    i = 0
    while i < len(body):
        c = body[i]
        if c == end:
            break
        argc = args.get(c, 0)
        arg = body[i + 1:i + 1 + argc]
        i += 1 + argc
        is_color = (game == "mm" and c <= 0x08) or (game == "oot" and c == 0x05)
        if is_color:
            close_span()
            color = c if game == "mm" else (arg[0] if arg else default_color)
            continue
        if game == "oot" and c == 0x07 and len(arg) == 2:
            links.append(struct.unpack(">H", arg)[0])
        if 0x20 <= c <= 0x7E:
            ch = chr(c)
        elif (game == "mm" and c == 0x11) or (game == "oot" and c == 0x01):
            ch = " "
        else:
            if c in ((0x10, 0x12, 0x1B) if game == "mm" else (0x04, 0x0C)):
                close_span()
                color = default_color
            ch = " " if c < 0x20 else ""
        text.append(ch)
        if color != default_color:
            span.append(ch)
    close_span()
    return Message(" ".join("".join(text).split()), spans, links)


def read_message_table(code: bytes, table_offset: int, data: bytes) -> Dict[int, bytes]:
    """Message id -> raw bytes, from the table in ``code`` (u16 id, u8, u8, u32 segment address)."""
    entries = []
    offset = table_offset
    while offset + 8 <= len(code):
        message_id, _info, _pad, address = struct.unpack_from(">HBBI", code, offset)
        entries.append((message_id, address & 0xFFFFFF))
        offset += 8
        if message_id == 0xFFFF:
            break
    out = {}
    for (message_id, start), (_next, stop) in zip(entries, entries[1:]):
        if message_id < 0xFFFC:
            out[message_id] = data[start:stop if stop > start else len(data)]
    return out


# ---------------------------------------------------------------- ROM: scenes

def _commands(blob: bytes, offset: int) -> Iterable[Tuple[int, int, int]]:
    for _ in range(64):
        if offset + 8 > len(blob):
            return
        cmd, data1, _pad, data2 = struct.unpack_from(">BBHI", blob, offset)
        if cmd == 0x14:
            return
        yield cmd, data1, data2
        offset += 8


def _headers(blob: bytes, segment: int) -> List[int]:
    """Offsets of the main header and its alternates (command 0x18) in a scene/room file."""
    offsets = [0]
    for cmd, _d1, d2 in _commands(blob, 0):
        if cmd != 0x18 or d2 >> 24 != segment:
            continue
        pos = d2 & 0xFFFFFF
        while pos + 4 <= len(blob):
            pointer = struct.unpack_from(">I", blob, pos)[0]
            if pointer and (pointer >> 24 != segment or (pointer & 0xFFFFFF) >= len(blob)
                            or blob[pointer & 0xFFFFFF] > 0x1E):
                break
            if pointer:
                offsets.append(pointer & 0xFFFFFF)
            pos += 4
    return offsets


def scene_placements(rom, segments: List[str], scenes: Dict[int, dict], actor_mask: int
                     ) -> Dict[int, List[Tuple[int, int]]]:
    """Scene id -> [(actor id, params)] over all rooms and alternate headers (cutscene/age/day setups)."""
    index_by_name = {name: i for i, name in enumerate(segments)}
    index_by_vrom = {entry[0]: i for i, entry in enumerate(rom.files)}
    out: Dict[int, List[Tuple[int, int]]] = {}
    for scene_id, scene in scenes.items():
        file_index = index_by_name.get(scene["segment"])
        if file_index is None:
            continue
        blob = rom.read_file(file_index)
        rooms: Set[int] = set()
        placed: List[Tuple[int, int]] = []
        for header in _headers(blob, 0x02):
            for cmd, count, d2 in _commands(blob, header):
                if cmd == 0x04 and d2 >> 24 == 0x02:
                    for k in range(count):
                        vstart = struct.unpack_from(">I", blob, (d2 & 0xFFFFFF) + 8 * k)[0]
                        if vstart in index_by_vrom:
                            rooms.add(index_by_vrom[vstart])
                elif cmd == 0x0E and d2 >> 24 == 0x02:   # doors and other transition actors
                    for k in range(count):
                        base = (d2 & 0xFFFFFF) + 16 * k
                        placed.append((struct.unpack_from(">H", blob, base + 4)[0] & actor_mask,
                                       struct.unpack_from(">H", blob, base + 14)[0]))
        for room_index in sorted(rooms):
            room = rom.read_file(room_index)
            for header in _headers(room, 0x03):
                for cmd, count, d2 in _commands(room, header):
                    if cmd == 0x01 and d2 >> 24 == 0x03:
                        for k in range(count):
                            base = (d2 & 0xFFFFFF) + 16 * k
                            if base + 16 <= len(room):
                                actor_id = struct.unpack_from(">H", room, base)[0] & actor_mask
                                placed.append((actor_id, struct.unpack_from(">H", room, base + 14)[0]))
        out[scene_id] = placed
    return out


# ---------------------------------------------------------------- assembly

def _git_commit(root: Path) -> str:
    head = root / ".git" / "HEAD"
    if not head.exists():
        return ""
    ref = head.read_text().strip()
    if not ref.startswith("ref:"):
        return ref
    ref = ref[4:].strip()
    loose = root / ".git" / ref
    if loose.exists():
        return loose.read_text().strip()
    packed = root / ".git" / "packed-refs"
    if packed.exists():
        for line in packed.read_text().splitlines():
            if line.endswith(" " + ref):
                return line.split()[0]
    return ""


def _contains(text: str, term: str) -> bool:
    return re.search(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", text) is not None


def _name_candidates(description: str) -> List[str]:
    """``Blacksmith - Gabora`` -> [``Gabora``]: the part after `` - `` (before it is usually a place),
    split on ``/``, ``,`` and ``and``; parentheticals and long phrases dropped."""
    names = []
    description = re.sub(r"\s*[(\[].*", "", description).split(" - ")[-1]
    for part in re.split(r"\s*/\s*|,\s*|\s+and\s+", description):
        part = part.strip(" ?")
        if len(part) >= 3 and part[0].isupper() and len(part.split()) <= 3:
            names.append(part)
    return names


def build_context(game: str, decomp: Path, rom_path: Optional[Path] = None) -> dict:
    """The whole context document for one game (see the module docstring)."""
    from plugins.common.n64_rom import N64Rom  # Yaz0 lives in core; only needed with a ROM

    config = GAMES[game]
    sources = actor_sources(decomp)
    actors = actor_table(decomp)
    scenes = scene_table(decomp, game)
    messages: Dict[int, Message] = {}
    placements: Dict[int, List[Tuple[int, int]]] = {}
    rom_sha1 = ""
    if rom_path:
        raw_rom = rom_path.read_bytes()
        rom_sha1 = hashlib.sha1(raw_rom).hexdigest()
        rom = N64Rom(raw_rom)
        segments = [row[0] for row in csv.reader((decomp / config["segments"]).open())][1:]
        if len(segments) != len(rom.files):
            raise ValueError(f"{config['segments']} lists {len(segments)} files, the ROM has {len(rom.files)}")
        code = rom.read_file(segments.index("code"))
        text = rom.read_file(segments.index(config["text_file"]))
        messages = {i: decode_message(game, raw)
                    for i, raw in read_message_table(code, config["table"], text).items()}
        placements = scene_placements(rom, segments, scenes, config["actor_mask"])
        all_text = "\n".join(m.text for m in messages.values())
        for scene in scenes.values():  # OoT enum names lost their apostrophes: "Midos House"
            possessive = re.sub(r"\b(\w{3,})s\b(?= )", r"\1's", scene["name"])
            if possessive != scene["name"] and possessive in all_text and scene["name"] not in all_text:
                scene["name"] = possessive

    def valid(message_id: int) -> bool:
        return message_id in messages if messages else 0 < message_id < 0xFFFC

    # actor -> scenes it stands in; message -> exact scenes from placement params
    actor_scenes: Dict[str, Set[int]] = defaultdict(set)
    exact: Dict[int, Dict[str, Set[int]]] = defaultdict(lambda: defaultdict(set))
    rules = PLACEMENT_TEXT[game]
    for scene_id, placed in placements.items():
        for actor_id, params in placed:
            overlay = actors.get(actor_id)
            if not overlay:
                continue
            actor_scenes[overlay].add(scene_id)
            if overlay in rules:
                text_id = rules[overlay](params) & 0xFFFF
                if valid(text_id):
                    exact[text_id][overlay].add(scene_id)

    entries: Dict[int, dict] = {}
    used_by: Counter = Counter()

    def entry(message_id: int) -> dict:
        return entries.setdefault(message_id, {"speakers": [], "actors": [], "scenes": []})

    def add(message_id: int, overlay: str, speaker: str, scene_ids: Set[int]) -> None:
        e = entry(message_id)
        if overlay not in e["actors"]:
            e["actors"].append(overlay)
            used_by[message_id] += 1
        if speaker and speaker not in e["speakers"]:
            e["speakers"].append(speaker)
        if len(scene_ids) <= MAX_SCENES:
            for name in sorted(scenes[s]["name"] for s in scene_ids):
                if name not in e["scenes"]:
                    e["scenes"].append(name)

    for overlay, (description, ids, _notes) in sources.items():
        speaker = description or ("" if overlay.startswith("code/") else overlay)
        for message_id in sorted(ids):
            if valid(message_id) and message_id not in exact:
                add(message_id, overlay, speaker, actor_scenes.get(overlay, set()))
    for message_id, by_overlay in exact.items():
        for overlay, scene_ids in by_overlay.items():
            add(message_id, overlay, sources.get(overlay, ("",))[0], scene_ids)
    # Tatl/Navi notes on enemies: the actor sets an enum, Player adds a base.
    prefix, base, narrator = config["enemy_note"]
    note_ids = enum_values(decomp, prefix)
    for overlay, (description, _ids, notes) in sources.items():
        for note in notes:
            message_id = note_ids.get(note, -1) + base
            if note in note_ids and valid(message_id):
                add(message_id, overlay, narrator, actor_scenes.get(overlay, set()))
                entry(message_id).setdefault("about", description or overlay)
    direct = set(entries)

    # follow "next message" links (MM header, OoT goto) into ids nobody claims directly
    inherited = 0
    queue = sorted(direct)
    while queue and messages:
        parent = queue.pop(0)
        for child in messages[parent].links if parent in messages else []:
            if child in messages and child not in entries:
                entry(child).update({k: list(entries[parent][k]) for k in ("speakers", "actors", "scenes")})
                entries[child]["chain_from"] = f"0x{parent:04X}"
                inherited += 1
                queue.append(child)

    # glossary seeds
    all_text = "\n".join(m.text for m in messages.values())
    glossary: Dict[Tuple[str, str], dict] = {}

    def gloss(term: str, section: str, ids: Iterable[int], note: str) -> None:
        g = glossary.setdefault((section, term.lower()),
                                {"term": term, "section": section, "message_ids": [], "note": note})
        if g["term"][0].islower() and term[0].isupper():
            g["term"] = term  # "bug" and "Bug" are one entry; prefer the capitalised spelling
        for i in ids:
            hex_id = f"0x{i:04X}"
            if hex_id not in g["message_ids"] and len(g["message_ids"]) < MAX_GLOSSARY_IDS:
                g["message_ids"].append(hex_id)

    def mentions(term: str) -> List[int]:
        return [i for i, m in sorted(messages.items()) if _contains(m.text, term)]

    def proper_noun(term: str) -> bool:
        """In the game's text and never written in lower case there (so not a common noun)."""
        return _contains(all_text, term) and not _contains(all_text, term.lower())

    def first_span(message_id: int) -> str:
        m = messages.get(message_id)
        return m.spans[0][1] if m and m.spans else ""

    for item, text_id in get_item_table(decomp):
        term = first_span(text_id)
        if term:
            gloss(term, "Items", [text_id], f"get-item text of {item}")
            entry(text_id).setdefault("item", term)
    if config["item_descriptions"]:
        for item, value in enum_values(decomp, "ITEM_").items():
            message_id = config["item_descriptions"] + value
            term = first_span(message_id)
            if term and value < 0x100:
                gloss(term, "Items", [message_id], f"pause-menu description of {item}")
                entry(message_id).setdefault("item", term)
    places = set()
    for scene in scenes.values():
        title = scene["title_text_id"]
        if title and title in messages and messages[title].text:
            places.add(messages[title].text)
            gloss(messages[title].text, "Places", [title], f"title card of {scene['enum']}")
            entry(title).setdefault("place", messages[title].text)
        elif not title and messages and _contains(all_text, scene["name"]):
            places.add(scene["name"])
            gloss(scene["name"], "Places", mentions(scene["name"]), f"decomp scene name {scene['enum']}, found in text")
    for kind, name, ids in notebook_table(decomp):
        ids = [i for i in ids if i]  # 0 = no message
        if kind == "person" and ids:
            gloss(first_span(ids[0]) or name, "Characters", ids, "Bombers' Notebook person")
        for message_id in ids:
            if valid(message_id):
                entry(message_id).setdefault("notebook", f"{kind}: {name}")
    for overlay, (description, ids, _notes) in sources.items():
        if not messages or not any(valid(i) for i in ids):
            continue
        for name in _name_candidates(description):
            if name not in places and proper_noun(name):
                gloss(name, "Characters", mentions(name), f"actor {overlay}: {description}")
    known = {term.lower() for _section, term in glossary}
    span_ids: Dict[str, List[int]] = defaultdict(list)
    for message_id, m in sorted(messages.items()):
        for color, span in set(m.spans):
            if (color == config["red"] and re.fullmatch(r"[A-Z][A-Za-z'\-]*(?: [A-Za-z'\-]+){0,3}", span)
                    and span.lower() not in known):
                span_ids[span].append(message_id)
    for span, ids in span_ids.items():
        if len(ids) >= 3 and proper_noun(span):
            gloss(span, "Terms", ids, f"highlighted in red in {len(ids)} messages")

    for e in entries.values():
        if not e["actors"]:
            del e["speakers"], e["actors"], e["scenes"]
    stats = {
        "messages_in_rom": len(messages),
        "messages_with_actor": len(direct),
        "messages_with_one_actor": sum(1 for i in direct if used_by[i] == 1),
        "messages_with_named_speaker": sum(1 for i in direct if entries[i]["speakers"]),
        "messages_with_scene": sum(1 for e in entries.values() if e.get("scenes")),
        "messages_via_chain": inherited,
        "messages_exact_placement": len(exact),
        "messages_with_any_context": len(entries),
        "scenes_read": len(placements),
        "glossary_terms": dict(Counter(g["section"] for g in glossary.values())),
    }
    return {
        "source": {"game": game, "decomp_commit": _git_commit(decomp), "rom_sha1": rom_sha1,
                   "generator": "plugins.common.zelda64_context"},
        "messages": {f"0x{i:04X}": entries[i] for i in sorted(entries)},
        "glossary": sorted(glossary.values(), key=lambda g: (g["section"], g["term"].lower())),
        "stats": stats,
    }


def dumps(context: dict) -> str:
    """JSON with one message / glossary entry per line: readable diffs at a third of the indented size."""
    parts = []
    for key, value in context.items():
        if key == "messages":
            body = ",\n".join(f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in value.items())
            parts.append(f" {json.dumps(key)}: {{\n{body}\n }}")
        elif isinstance(value, list):
            body = ",\n".join(f"  {json.dumps(v, ensure_ascii=False)}" for v in value)
            parts.append(f" {json.dumps(key)}: [\n{body}\n ]")
        else:
            parts.append(f" {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)}")
    return "{\n" + ",\n".join(parts) + "\n}\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", choices=sorted(GAMES), required=True)
    parser.add_argument("--decomp", type=Path, required=True)
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    context = build_context(args.game, args.decomp, args.rom)
    tmp = args.out.with_suffix(args.out.suffix + ".tmp")
    tmp.write_text(dumps(context), encoding="utf-8")
    tmp.replace(args.out)
    print(json.dumps(context["stats"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
