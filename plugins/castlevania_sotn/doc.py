"""One Symphony of the Night program file as Picoripi blocks, and how to save it.

The plugin gets bytes, not names. Every program file of the USA disc has its own size, and a
translation keeps it, so the size picks the file's entry in ``layout_us.json`` (made from the
decompilation by the workspace tool ``tools\\sotn_layout.py``): where each string, cutscene script
and the staff roll are.

- A string that only data points at may move inside its pool (a run of string slots): a
  translation may be longer than the English when other strings of the pool get shorter. When the
  pool is full it moves into a ``spare`` range (data the decompilation marks unused and nothing
  points at). The pointers are rewritten. A string code points at keeps its place and its slot.
- A translated file is read through the same pointers, so a moved string is found again.
- Cutscene scripts and the staff roll keep their regions (``script``); a longer cutscene
  continues in a spare range through a jump command.
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from . import codec, script

LAYOUT_FILE = Path(__file__).resolve().parent / "layout_us.json"
STAGES = {
    "ARE": "Colosseum", "CAT": "Catacombs", "CEN": "Center (Dracula's room)", "CHI": "Abandoned Mine",
    "DAI": "Royal Chapel", "DRE": "Nightmare", "LIB": "Long Library", "MAD": "Debug room",
    "NO0": "Marble Gallery", "NO1": "Outer Wall", "NO2": "Olrox's Quarters", "NO3": "Castle Entrance",
    "NO4": "Underground Caverns", "NP3": "Castle Entrance (after Death)", "NZ0": "Alchemy Laboratory",
    "NZ1": "Clock Tower", "ST0": "Prologue (Dracula's castle, 1792)", "TOP": "Castle Keep",
    "WRP": "Warp rooms", "SEL": "Title, file select, endings, staff roll", "TE1": "Test stage",
    "MAR": "Maria (boss stage)",
}


class FormatError(ValueError):
    """The text does not fit the game file."""


@lru_cache(maxsize=1)
def layout() -> dict:
    return json.loads(LAYOUT_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def by_size() -> Dict[int, str]:
    return {entry["size"]: path for path, entry in layout()["files"].items()}


def file_of(data: bytes) -> Optional[str]:
    """The disc path of a program file, by its size."""
    return by_size().get(len(data))


def place_name(path: str) -> str:
    stage = path.split("/")[-1].split(".")[0]
    plain = stage[1:] if stage.startswith("R") and stage[1:] in STAGES else stage
    name = STAGES.get(plain, "")
    if stage != plain:
        name = f"{name} (inverted castle)" if name else "Inverted castle"
    if path.startswith("BOSS/") and stage not in STAGES:
        name = "Boss stage"
    return f"{stage} - {name}" if name else stage


@dataclass
class Line:
    raw: bytes
    kind: str
    where: str
    enc: str = "s8"                  # s8, sj, cs (cutscene), cr (staff roll)
    newline: str = ""
    room: int = 0                    # a fixed string: bytes it may take with its end bytes
    speaker: str = ""
    ref: Tuple = ()                  # ("s", string index) / ("c", script index, line) / ("r", region, entry)
    plain: Optional[str] = None      # a script line: its editor text (already decoded)

    def text(self, reverse_map: Optional[Dict[str, str]] = None) -> str:
        if self.plain is not None:
            return self.plain
        return codec.decode(self.raw, self.enc, self.newline, reverse_map if self.enc == "s8" else None)


@dataclass
class Doc:
    path: str
    blocks: List[List[Line]] = field(default_factory=list)
    names: Dict[str, str] = field(default_factory=dict)

    def texts(self, reverse_map: Optional[Dict[str, str]] = None) -> List[List[str]]:
        return [[line.text(reverse_map) for line in block] for block in self.blocks]


def string_at(data: bytes, entry: dict, item: dict) -> int:
    """Where a string is now: through its first pointer when it may move."""
    if item["fixed"]:
        return item["at"]
    return struct.unpack_from("<I", data, item["refs"][0])[0] - entry["base"]


def parse(data: bytes, reverse_map: Optional[Dict[str, str]] = None) -> Doc:
    path = file_of(data)
    if path is None:
        raise ValueError(f"not a Symphony of the Night program file ({len(data)} bytes)")
    entry = layout()["files"][path]
    doc = Doc(path)
    place = place_name(path)
    groups: Dict[str, List[Line]] = {}
    for index, item in enumerate(entry["strings"]):
        if item.get("hide"):
            continue
        at = string_at(data, entry, item)
        raw = codec.read_raw(data, at, item["enc"])
        line = Line(raw, item["kind"], f"{place}: {item['group']} @{item['at']:#x}", item["enc"],
                    item.get("nl", ""), item["room"] if item["fixed"] else 0, ref=("s", index))
        groups.setdefault(item["group"], []).append(line)
    for name, lines in groups.items():
        doc.names[str(len(doc.blocks))] = f"{name}"
        doc.blocks.append(lines)
    actors = entry.get("actors") or []
    for number, region in enumerate(entry.get("scripts", [])):
        if region["kind"] == "credits":
            lines = []
            count = 0
            for _at, op, x, raw in script.credit_entries(data, region["start"], region["end"]):
                if op == 0:
                    continue
                text = script.credit_text(op, x, raw, reverse_map)
                lines.append(Line(raw, "credits", f"{place}: staff roll entry {count}", "cr",
                                  ref=("r", number, count), plain=text))
                count += 1
            doc.names[str(len(doc.blocks))] = "Staff roll"
            doc.blocks.append(lines)
            continue
        ops = script.parse_flow(data, region["start"], region["end"], entry["base"], entry.get("spare", ()))
        lines = []
        for count, item in enumerate(script.lines_of(ops)):
            speaker = actors[item.speaker] if 0 <= item.speaker < len(actors) else ""
            text = script.line_text(ops, item, reverse_map)
            lines.append(Line(b"", "dialogue", f"{place}: cutscene {region['name']} line {count}", "cs",
                              speaker=speaker, ref=("c", number, count), plain=text))
        doc.names[str(len(doc.blocks))] = f"Cutscene: {region['name']}"
        doc.blocks.append(lines)
    return doc


# ---------------------------------------------------------------- saving

def build(source: bytes, data: Sequence[Sequence[Optional[str]]], mapping: Optional[Dict[str, str]] = None,
          missing: Optional[Set[str]] = None, reverse_map: Optional[Dict[str, str]] = None) -> bytes:
    """The file with the editor's texts, built from the English ``source``. A line that still reads as
    the source text keeps its bytes; an unchanged file comes back byte for byte."""
    doc = parse(source, reverse_map)
    entry = layout()["files"][doc.path]
    new_strings: Dict[int, bytes] = {}
    new_script: Dict[int, Dict[int, bytes]] = {}
    for number, block in enumerate(doc.blocks):
        texts = data[number] if number < len(data) else []
        for index, line in enumerate(block):
            text = texts[index] if index < len(texts) else None
            if text is None:
                continue
            if text == line.text(reverse_map):
                continue
            kind = line.ref[0]
            try:
                if kind == "s":
                    item = entry["strings"][line.ref[1]]
                    font_map = mapping if item["enc"] == "s8" else None
                    new_strings[line.ref[1]] = codec.encode(text, item["enc"], item.get("nl", ""), font_map, missing)
                elif kind == "c":
                    new_script.setdefault(line.ref[1], {})[line.ref[2]] = script.encode_line(text, mapping, missing)
                else:
                    new_script.setdefault(line.ref[1], {})[line.ref[2]] = script.encode_credit(text, mapping, missing)
            except script.ScriptError as error:
                raise FormatError(f"{doc.path}: {line.where}: {error}") from error
    if not new_strings and not new_script:
        return bytes(source)
    out = bytearray(source)
    spare = script.Spare(entry.get("spare", ()))
    if new_strings:
        _write_strings(out, source, entry, new_strings, doc.path, spare)
    for number, lines in new_script.items():
        region = entry["scripts"][number]
        try:
            if region["kind"] == "credits":
                part = script.build_credits(source, region["start"], region["end"], lines)
            else:
                part = script.build(source, region["start"], region["end"], lines, entry["base"],
                                    region.get("anchors", ()), spare)
        except script.ScriptError as error:
            raise FormatError(f"{doc.path}: cutscene {region['name']}: {error}") from error
        out[region["start"]:region["end"]] = part
    for at, raw in spare.writes:
        out[at:at + len(raw)] = raw
    return bytes(out)


def _write_strings(out: bytearray, source: bytes, entry: dict, new: Dict[int, bytes], path: str,
                   spare: script.Spare) -> None:
    strings = entry["strings"]
    by_pool: Dict[int, List[int]] = {}
    for index in new:
        by_pool.setdefault(strings[index]["pool"], []).append(index)
    for pool, _changed in by_pool.items():
        members = [i for i, s in enumerate(strings) if s["pool"] == pool]
        start, end = entry["pools"][pool]
        payload = {}
        for i in members:
            item = strings[i]
            payload[i] = new[i] if i in new else source[item["at"]:item["at"] + _stored_len(source, item)]
        if all(len(payload[i]) <= strings[i]["room"] for i in members):
            for i in members:
                item = strings[i]
                if i in new:
                    out[item["at"]:item["at"] + item["room"]] = payload[i] + bytes(item["room"] - len(payload[i]))
            continue
        _repack(out, entry, members, payload, start, end, path, spare)


def _stored_len(source: bytes, item: dict) -> int:
    raw = codec.read_raw(source, item["at"], item["enc"])
    return len(raw) + (2 if item["enc"] == "s8" else 1)


def _repack(out: bytearray, entry: dict, members: List[int], payload: Dict[int, bytes], start: int, end: int,
            path: str, spare: script.Spare) -> None:
    strings = entry["strings"]
    reserved = []
    for i in members:
        item = strings[i]
        if item["fixed"]:
            if len(payload[i]) > item["room"]:
                raise FormatError(f"{path}: the string at {item['at']:#x} ({item['group']}) may take "
                                  f"{item['room']} bytes, the translation takes {len(payload[i])}")
            reserved.append((item["at"], item["at"] + item["room"]))
    free = []
    cursor = start
    for left, right in sorted(reserved):
        if left > cursor:
            free.append([cursor, left])
        cursor = max(cursor, right)
    if cursor < end:
        free.append([cursor, end])
    placed: Dict[int, int] = {}
    for i in members:
        if strings[i]["fixed"]:
            continue
        size = len(payload[i])
        for gap in free:
            at = (gap[0] + 3) & ~3
            if at + size <= gap[1]:
                placed[i] = at
                gap[0] = at + size
                break
        else:
            at = spare.take(size, 4)          # a free range elsewhere in the file
            if at is None:
                need = sum(len(payload[j]) for j in members if not strings[j]["fixed"])
                room = sum(r - l for l, r in free) + spare.room
                raise FormatError(f"{path}: the strings of '{strings[i]['group']}' do not fit: they need about "
                                  f"{need} bytes, the game has {room} free; shorten some of them")
            placed[i] = at
    # clear the movable space, then write
    for i in members:
        if not strings[i]["fixed"]:
            item = strings[i]
            out[item["at"]:item["at"] + item["room"]] = bytes(item["room"])
    for i in members:
        item = strings[i]
        if item["fixed"]:
            out[item["at"]:item["at"] + item["room"]] = payload[i] + bytes(item["room"] - len(payload[i]))
        else:
            at = placed[i]
            out[at:at + len(payload[i])] = payload[i]
            for ref in item["refs"]:
                struct.pack_into("<I", out, ref, entry["base"] + at)


# ---------------------------------------------------------------- context

def source_ref(path: str, line: Line) -> str:
    """Where the decompilation (sotn-decomp, US build) describes this text."""
    if line.enc == "cs":
        return f"sotn-decomp config/assets.us.yaml: {path} cutscene script ({line.where.split(': ', 1)[-1]})"
    if line.enc == "cr":
        return f"sotn-decomp config/assets.us.yaml: {path} credits"
    folder = path.split("/")
    if path == "DRA.BIN":
        return f"sotn-decomp src/dra ({line.where.split(': ', 1)[-1]}; tables in src/config_us.h)"
    kind = "boss" if folder[0] == "BOSS" else "st"
    return f"sotn-decomp src/{kind}/{folder[-2].lower()} ({line.where.split(': ', 1)[-1]})"


_GLOSSARY = {"Equipment names": ("Equipment", 4), "Accessory names": ("Accessories", 4),
             "Relic names": ("Relics", 4), "Spell names": ("Spells", 8), "Enemy names": ("Enemies", 0)}


def glossary(data: bytes) -> List[Dict[str, str]]:
    """Seed terms of DRA.BIN: item, relic, spell and enemy names, each with its description."""
    entry = layout()["files"]["DRA.BIN"]
    by_ref = {ref: index for index, item in enumerate(entry["strings"]) for ref in item["refs"]}
    out, seen = [], set()
    for index, item in enumerate(entry["strings"]):
        section = _GLOSSARY.get(item["group"])
        if section is None or item.get("hide"):
            continue
        name = codec.decode(codec.read_raw(data, string_at(data, entry, item), item["enc"]), item["enc"]).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        description = ""
        if section[1]:
            desc_index = next((by_ref[r + section[1]] for r in item["refs"] if r + section[1] in by_ref), None)
            if desc_index is not None:
                desc = entry["strings"][desc_index]
                description = codec.decode(codec.read_raw(data, string_at(data, entry, desc), desc["enc"]),
                                           desc["enc"])
        out.append({"term": name, "description": description, "section": section[0],
                    "source_ref": f"DRA.BIN {item['group']} @{item['at']:#x}"})
    return out


def text_regions(path: str) -> List[Tuple[int, int]]:
    """The byte ranges of a file that hold its text: string pools, their pointers, scripts."""
    entry = layout()["files"][path]
    regions = [tuple(pool) for pool in entry["pools"]]
    regions += [(ref, ref + 4) for item in entry["strings"] for ref in item["refs"]]
    regions += [(region["start"], region["end"]) for region in entry.get("scripts", [])]
    regions += [tuple(area) for area in entry.get("spare", [])]
    return sorted(regions)


def merge(current: bytes, built: bytes) -> bytes:
    """``current`` (the translation copy, maybe with edited pictures) with the text of ``built``."""
    path = file_of(built)
    if path is None or len(current) != len(built):
        return bytes(built)
    out = bytearray(current)
    for start, end in text_regions(path):
        out[start:end] = built[start:end]
    return bytes(out)
