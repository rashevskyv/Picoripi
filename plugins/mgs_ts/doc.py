"""One Twin Snakes text file as Picoripi blocks: which game string each line is, and how to save it.

A file is either GCX script text (``codec.dat``, the ``*.gcx`` scripts the unpack step takes out
of stage.dat) or a ``.subs`` file of cutscene / voice / movie subtitles. Only English strings
become lines. Identical string tables (codec.dat repeats some calls up to eight times) are one
block; a save writes the block into every copy.

Which strings of a GCX table are English is detected (``gcx.segment``), so it is detected on the
source file only and remembered by the file's layout (``layout_key``): the translation copy, full
of Ukrainian, is read with the source's answer.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from . import gcx, subtitles, textcodec

_SPEAKERS_FILE = Path(__file__).with_name("speakers.json")


def speaker_names() -> Dict[int, str]:
    """24-bit name hash -> display name, from ``speakers.json`` (``{"campbell": "Roy Campbell"}``;
    ``"#9331f5"`` names a hash whose name is unknown)."""
    try:
        raw = json.loads(_SPEAKERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    names = {}
    for key, name in raw.items():
        if key.startswith("#"):
            names[int(key[1:], 16)] = str(name)
        elif not key.startswith("_"):
            names[gcx.strcode24(key)] = str(name)
    return names


@dataclass
class Line:
    """One English game string shown in the editor."""

    raw: bytes
    kind: str                         # codec, script, cutscene, voice, movie
    speaker: Optional[int] = None     # name hash
    timing: Optional[Tuple[int, int]] = None
    where: str = ""
    newline: bytes = textcodec.LF


@dataclass
class Doc:
    kind: str                                         # "gcx" or "subs"
    blocks: List[List[Line]] = field(default_factory=list)
    names: Dict[str, str] = field(default_factory=dict)
    # gcx: per block, the section numbers that share its table, and the English string indices
    sections: List[List[int]] = field(default_factory=list)
    indices: List[List[int]] = field(default_factory=list)
    # subs: per block, (record number, entry number) of each line
    places: List[List[Tuple[int, int]]] = field(default_factory=list)
    # gcx: English string indices of every section, blocks or not (what ``layout_key`` remembers)
    english: List[List[int]] = field(default_factory=list)

    def texts(self, reverse_map: Optional[Dict[str, str]] = None) -> List[List[str]]:
        return [[textcodec.decode(line.raw, reverse_map) for line in block] for block in self.blocks]


def layout_key(data: bytes) -> str:
    """What stays the same between a GCX file and its translation: the section layout."""
    sections = gcx.read_sections_layout(data)
    digest = hashlib.sha1(repr((len(data), sections)).encode("ascii")).hexdigest()
    return digest


def parse(data: bytes, file_name: str = "", known: Optional[Dict[str, List[List[int]]]] = None) -> Doc:
    """Read a file; ``known`` maps layout keys to the English indices of each section."""
    if data[:len(subtitles.MAGIC)] == subtitles.MAGIC:
        return _parse_subs(data, file_name)
    return _parse_gcx(data, file_name, known)


def _parse_gcx(data: bytes, file_name: str, known: Optional[Dict[str, List[List[int]]]]) -> Doc:
    remembered = (known or {}).get(layout_key(data))
    sections = gcx.read_sections(data, segment=remembered is None)
    english = remembered if remembered is not None else [section.table.english for section in sections]
    doc = Doc("gcx", english=english)
    groups: Dict[bytes, int] = {}
    stem = Path(file_name).stem or "script"
    is_codec = len(sections) > 1
    for number, section in enumerate(sections):
        if not english[number]:
            continue
        key = hashlib.sha1(section.table.raw).digest()
        if key in groups:
            doc.sections[groups[key]].append(number)
            continue
        groups[key] = len(doc.blocks)
        kind = "codec" if is_codec else "script"
        lines = [Line(section.table.strings[i], kind, section.speakers.get(i),
                      where=f"{stem} section {number} string {i}") for i in english[number]]
        doc.names[str(len(doc.blocks))] = f"Codec {number:03d}" if is_codec else stem
        doc.blocks.append(lines)
        doc.sections.append([number])
        doc.indices.append(list(english[number]))
    return doc


def english_indices(data: bytes) -> List[List[int]]:
    """The English string indices of every section of a GCX file (the expensive detection)."""
    return [section.table.english for section in gcx.read_sections(data)]


def _parse_subs(data: bytes, file_name: str) -> Doc:
    records = subtitles.read(data)
    stem = Path(file_name).stem or "subtitles"
    kind = subtitles.kind_of(data)
    doc = Doc("subs")
    by_slot: Dict[int, List[int]] = {}
    for number, record in enumerate(records):
        if record.lang == subtitles.ENGLISH:
            by_slot.setdefault(record.slot_start, []).append(number)
    one_block = kind == "voice"
    for slot_number, (slot, numbers) in enumerate(sorted(by_slot.items())):
        if one_block and doc.blocks:
            lines, places = doc.blocks[0], doc.places[0]
        else:
            lines, places = [], []
            doc.blocks.append(lines)
            doc.places.append(places)
            label = {"cutscene": "Cutscene", "movie": "Movie", "voice": "Voice clips"}[kind]
            doc.names[str(len(doc.blocks) - 1)] = label if one_block else f"{label} {slot_number + 1:03d}"
        for number in numbers:
            for entry_number, entry in enumerate(records[number].entries):
                lines.append(Line(entry.text, kind, entry.speaker or None, (entry.start, entry.end),
                                  where=f"{stem} slot {slot:#x}",
                                  newline=textcodec.newline_of(entry.text, textcodec.SUB_LF)))
                places.append((number, entry_number))
    return doc


def build(source: bytes, doc: Doc, data: List[List[str]], translation_map: Optional[Dict[str, str]] = None,
          missing: Optional[Set[str]] = None, notes: Optional[List[str]] = None) -> bytes:
    """The file with the editor's texts, built from the source file and its parsed ``doc``."""
    def encoded(block: int, line: int) -> Optional[bytes]:
        if block >= len(data) or line >= len(data[block]) or data[block][line] is None:
            return None
        original = doc.blocks[block][line]
        new = textcodec.encode(str(data[block][line]), original.newline, translation_map, missing)
        return None if new == original.raw else new

    if doc.kind == "subs":
        records = subtitles.read(source)
        texts: Dict[int, List[bytes]] = {}
        for block, places in enumerate(doc.places):
            for line, (number, entry_number) in enumerate(places):
                new = encoded(block, line)
                if new is not None:
                    texts.setdefault(number, [entry.text for entry in records[number].entries])[entry_number] = new
        if not texts:
            return bytes(source)
        raws, slot_notes = subtitles.rebuild(records, texts)
        if notes is not None:
            notes.extend(slot_notes)
        return subtitles.write(records, raws, subtitles.kind_of(source))

    sections = gcx.read_sections(source)        # languages of the source decide what may be reclaimed
    changes: Dict[int, Dict[int, bytes]] = {}
    for block, numbers in enumerate(doc.sections):
        block_changes = {}
        for line, index in enumerate(doc.indices[block]):
            new = encoded(block, line)
            if new is not None:
                block_changes[index] = new
        if block_changes:
            for number in numbers:
                changes[number] = block_changes
    return gcx.rebuild(source, sections, changes) if changes else bytes(source)
