"""Okami HD message files: the strings of a container file as text, and the same file with edited text written back.

``read_text`` gives one text per string, in file order over all MSD sections. ``write_text`` takes the same list
and returns the file with the edits. A longer or shorter text changes its record's length; the table offsets of the
record, the section offsets of the container and the RUNOFS64 section starts are rewritten (``msd``). Every
record whose length changed is reported as a warning, because the growth is not yet proven in the game. A text
that does not encode keeps its original bytes and is reported. A file with no MSD section is not text: ``read_text``
returns an empty list and ``write_text`` returns the file as it was.
"""
from __future__ import annotations

from typing import List, Tuple

from . import charset, msd


def _sections(data: bytes):
    """(container, [(index, section)]) for the MSD sections the codec reads; (None, []) when not a container."""
    try:
        container = msd.parse_container(data)
    except msd.MsdError:
        return None, []
    found = []
    for index, tag in enumerate(container.tags):
        if tag != "MSD":
            continue
        section = msd.parse_section(container.section_bytes(index))
        if section is not None:
            found.append((index, section))
    return container, found


def read_text(data: bytes) -> List[str]:
    """The decoded text of every string of the file, in file order."""
    _container, found = _sections(data)
    texts: List[str] = []
    for _index, section in found:
        texts.extend(charset.decode(raw) for raw in msd.strings_of(section))
    return texts


def write_text(data: bytes, texts: List[str]) -> Tuple[bytes, List[str]]:
    """The file with ``texts`` written over its strings. Returns (new bytes, warnings).

    ``texts`` must have one entry per string of ``read_text``; otherwise the file is returned unchanged with a
    warning.
    """
    container, found = _sections(data)
    if container is None or not found:
        return data, []
    total = sum(len(msd.strings_of(section)) for _index, section in found)
    if len(texts) != total:
        return data, [f"string count changed ({len(texts)} for {total}); file not saved"]
    warnings: List[str] = []
    replacements = {}
    cursor = 0
    for index, section in found:
        originals = msd.strings_of(section)
        wanted = texts[cursor:cursor + len(originals)]
        cursor += len(originals)
        new_records = []
        position = 0
        for record in section.records:
            raws = []
            for original in record.strings:
                text = wanted[position]
                position += 1
                try:
                    raws.append(charset.encode(text))
                except ValueError as error:
                    warnings.append(f"string kept as it was: {error}")
                    raws.append(original)
            candidate = msd.Record(record.head, raws, record.tail)
            if candidate.byte_length() != record.byte_length():
                # Growth: the table offsets and the RUNOFS64 section starts are rewritten. Not proven in the game
                # yet (see docs/OPEN_ITEMS.md), so the translator is told.
                warnings.append(f"record length changed by {candidate.byte_length() - record.byte_length():+d} bytes "
                                "(layout changed; not yet proven in the game)")
            new_records.append(candidate)
        section = msd.MsdSection(layout=section.layout, prefix=section.prefix, records=new_records, tail=section.tail)
        replacements[index] = section.serialize()
    try:
        return msd.serialize_container(container, replacements), warnings
    except msd.MsdError as error:
        return data, warnings + [str(error)]
