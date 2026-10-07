"""One Metal Gear Solid text file as Picoripi blocks, and how to save it.

The plugin gets bytes, not names, so ``parse`` tells the files apart by their shape: ``RADIO.DAT``
(codec calls, one block per call), a ``.subs`` file (one block per subtitle block), a GCX script (one
block), the program or a stage overlay (``PS-X EXE`` or anything else: strings edited in place, found
by their shape on the source file and remembered by the file's layout for its translation copy).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from . import codec, gcx, program, radio, subs

CODEC, SUBTITLE, SCRIPT, PROGRAM = "codec", "subtitle", "script", "program"


class FormatError(ValueError):
    """The text does not fit the game file."""


@dataclass
class Line:
    raw: bytes
    kind: str                      # codec, contact, save, prompt, subtitle, script, program
    where: str
    newline: bytes = codec.RADIO_LF
    quote: bytes = codec.QUOTE
    wide: bool = False
    room: int = 0                  # program: bytes the string may take with its NUL

    def text(self, reverse_map: Optional[Dict[str, str]] = None) -> str:
        return codec.decode(self.raw, self.newline, self.quote, reverse_map)


@dataclass
class Doc:
    kind: str
    blocks: List[List[Line]] = field(default_factory=list)
    names: Dict[str, str] = field(default_factory=dict)
    places: List[List[int]] = field(default_factory=list)       # per block: index of each line in its unit
    calls: List[radio.Call] = field(default_factory=list)
    script: Optional[gcx.Script] = None
    records: List[subs.Record] = field(default_factory=list)
    regions: List[Tuple[int, int]] = field(default_factory=list)  # program: (start, room)

    def texts(self, reverse_map: Optional[Dict[str, str]] = None) -> List[List[str]]:
        return [[line.text(reverse_map) for line in block] for block in self.blocks]


def layout_key(data: bytes, regions: Sequence[Tuple[int, int]]) -> str:
    """What a program file and its translation share: everything outside its strings."""
    blank = bytearray(data)
    for start, room in regions:
        blank[start:start + room] = bytes(room)
    return hashlib.sha1(bytes(blank)).hexdigest()


def parse(data: bytes, known: Optional[Dict[str, List[Tuple[int, int]]]] = None) -> Doc:
    if subs.is_subs(data):
        return _subs_doc(data)
    if radio.looks_like(data):
        return _radio_doc(data)
    if not program.is_program(data) and gcx.looks_like(data):
        return _gcx_doc(data)
    return _program_doc(data, known)


def _radio_doc(data: bytes) -> Doc:
    calls = radio.read(data)
    doc = Doc("radio", calls=calls)
    for number, call in enumerate(calls):
        lines, places = [], []
        for index, text in enumerate(call.texts):
            raw = data[text.start:text.end]
            kind = CODEC if text.kind == "talk" else text.kind
            where = f"call {number} ({call.frequency / 100:.2f}) {text.kind} {index}"
            if text.kind == "talk":
                where += f" (character {text.speaker:04x})"
            lines.append(Line(raw, kind, where, wide=codec.is_wide(raw)))
            places.append(index)
        doc.names[str(len(doc.blocks))] = f"Codec {call.frequency / 100:.2f} #{number:03d}"
        doc.blocks.append(lines)
        doc.places.append(places)
    return doc


def _gcx_doc(data: bytes) -> Doc:
    script = gcx.read(data)
    lines = [Line(data[s:e], SCRIPT, f"script string {i}", codec.SUB_LF, codec.PLAIN_QUOTE, codec.is_wide(data[s:e]))
             for i, (s, e) in enumerate(script.strings)]
    return Doc("gcx", [lines], {"0": "Script"}, [list(range(len(lines)))], script=script)


def _subs_doc(data: bytes) -> Doc:
    records = subs.read(data)
    doc = Doc("subs", records=records)
    for number, record in enumerate(records):
        block = subs.Block.parse(record.raw)
        disc, _kind, a, _b = record.places[0]
        lines = [Line(entry.text, SUBTITLE, f"{record.kind} disc {disc} @{a:#x} line {i}", codec.SUB_LF)
                 for i, entry in enumerate(block.entries)]
        doc.names[str(number)] = f"{record.kind.capitalize()} {number:03d} (disc {disc})"
        doc.blocks.append(lines)
        doc.places.append(list(range(len(lines))))
    return doc


def _program_doc(data: bytes, known: Optional[Dict[str, List[Tuple[int, int]]]]) -> Doc:
    regions = None
    if known:
        for key, candidate in known.items():
            if all(start + room <= len(data) for start, room in candidate) and layout_key(data, candidate) == key:
                regions = [tuple(r) for r in candidate]
                break
    if regions is None:
        regions = program.find(data)
    lines = []
    for start, room in regions:
        end = data.find(b"\0", start, start + room)
        end = start + room - 1 if end < 0 else end
        lines.append(Line(data[start:end], PROGRAM, f"offset {start:#x} ({room - 1} bytes)", codec.SUB_LF,
                          codec.PLAIN_QUOTE, room=room))
    return Doc("program", [lines] if lines else [], {"0": "Program strings"} if lines else {},
               [list(range(len(lines)))], regions=list(regions))


def remember(data: bytes, doc: Doc, known: Dict[str, List[Tuple[int, int]]]) -> None:
    if doc.kind == "program" and doc.regions:
        known.setdefault(layout_key(data, doc.regions), [tuple(r) for r in doc.regions])


def build(source: bytes, doc: Doc, data: List[List[Optional[str]]], translation_map: Optional[Dict[str, str]] = None,
          missing: Optional[Set[str]] = None, name: str = "file",
          reverse_map: Optional[Dict[str, str]] = None) -> bytes:
    """The file with the editor's texts, built from the source file. A line that still reads as the
    source string keeps its bytes."""
    def new_raw(line: Line, text: Optional[str]) -> Optional[bytes]:
        if text is None or text == line.text(reverse_map):
            return None
        return codec.encode(text, line.newline, line.quote, line.wide, translation_map, missing)

    changed: Dict[Tuple[int, int], bytes] = {}
    for number, block in enumerate(doc.blocks):
        texts = data[number] if number < len(data) else []
        for index, line in enumerate(block):
            raw = new_raw(line, texts[index] if index < len(texts) else None)
            if raw is not None:
                changed[(number, index)] = raw
    if not changed:
        return bytes(source)
    try:
        if doc.kind == "radio":
            return radio.build(source, doc.calls, changed)[0]
        if doc.kind == "gcx":
            return gcx.build(source, doc.script, {index: raw for (_n, index), raw in changed.items()})
        if doc.kind == "subs":
            return _build_subs(doc, changed, name)
        return _build_program(source, doc, changed, name)
    except (gcx.FormatError, radio.FormatError, ValueError) as error:
        if isinstance(error, FormatError):
            raise
        raise FormatError(f"{name}: {error}") from error


def _build_subs(doc: Doc, changed: Dict[Tuple[int, int], bytes], name: str) -> bytes:
    records = []
    for number, record in enumerate(doc.records):
        lines = doc.blocks[number]
        if not any((number, i) in changed for i in range(len(lines))):
            records.append(record)
            continue
        block = subs.Block.parse(record.raw)
        texts = [changed.get((number, i), line.raw) for i, line in enumerate(lines)]
        raw = block.build(texts)
        if len(raw) > record.room:
            raise FormatError(f"{name}: {doc.names[str(number)]} is {len(raw) - record.room} bytes too long "
                              f"(the game has room for {record.room} bytes of this block); shorten its lines")
        records.append(subs.Record(record.room, record.places, raw))
    return subs.write(records)


def _build_program(source: bytes, doc: Doc, changed: Dict[Tuple[int, int], bytes], name: str) -> bytes:
    out = bytearray(source)
    for (_block, index), raw in changed.items():
        start, room = doc.regions[index]
        if len(raw) + 1 > room:
            raise FormatError(f"{name}: '{doc.blocks[0][index].text()}' may take {room - 1} bytes, "
                              f"the translation takes {len(raw)}")
        out[start:start + room] = raw + bytes(room - len(raw))
    return bytes(out)
