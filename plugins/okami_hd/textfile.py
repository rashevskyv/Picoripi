"""Okami HD message files: the strings of a container file as text, and the same file with edited text written back.

``read_text`` gives one text per string, in file order over all MSD sections. ``write_text`` takes the same list
and returns the file with the edits. An edit is written only when its record keeps its byte length and the text
encodes; any other edit keeps the original bytes of that record and is reported as a warning. A file with no MSD
section is not text: ``read_text`` returns an empty list and ``write_text`` returns the file as it was.
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
                warnings.append("a record changed length; the record was kept as it was")
                candidate = record
            new_records.append(candidate)
        section = msd.MsdSection(layout=section.layout, prefix=section.prefix, records=new_records, tail=section.tail)
        replacements[index] = section.serialize()
    try:
        return msd.serialize_container(container, replacements), warnings
    except msd.MsdError as error:
        return data, warnings + [str(error)]
