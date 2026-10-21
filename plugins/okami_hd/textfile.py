"""Okami message files: the text of each record of a container file, and the same file with edited text written back.

``read_text`` gives one text row per record, in file order over all MSD sections. The strings of a record are joined by
a space: the engine puts a space between two strings of one record, so a space in a row is a string break. A newline in
a row is the line-break code (``charset``). Zero strings at the end of a record are pad (see ``msd``); they are not
shown. ``write_text`` takes the same list of rows and returns the file with the edits: a changed row is split at its
spaces into new strings, and the record keeps its header and tail. An unchanged row keeps its bytes. A row that does not
encode keeps its record as it was, and is reported. A file with no MSD section is not text: ``read_text`` returns an
empty list and ``write_text`` returns the file as it was.

``endian`` is the byte order of the file: little (the default) for the Switch and PS2 files, big for the Wii files.
"""
from __future__ import annotations

from typing import List, Tuple

from . import charset, msd


def _sections(data: bytes, endian: str):
    """(container, [(index, section)]) for the MSD sections the codec reads; (None, []) when not a container."""
    try:
        container = msd.parse_container(data, endian)
    except msd.MsdError:
        return None, []
    found = []
    for index, tag in enumerate(container.tags):
        if tag != "MSD":
            continue
        section = msd.parse_section(container.section_bytes(index), endian)
        if section is not None:
            found.append((index, section))
    return container, found


def _row(record: msd.Record, endian: str) -> str:
    """The text row of a record: its strings joined by spaces, without the trailing pad strings."""
    strings = list(record.strings)
    while strings and not strings[-1]:
        strings.pop()
    return " ".join(charset.decode(raw, endian) for raw in strings)


def _encode_row(text: str, endian: str) -> List[bytes]:
    """The strings of a row: one per piece between its spaces. An empty row is one empty string, so the record stays."""
    return [charset.encode(piece, endian) for piece in text.split(" ")]


def read_text(data: bytes, endian: str = "<") -> List[str]:
    """The text row of every record of the file, in file order."""
    _container, found = _sections(data, endian)
    return [_row(record, endian) for _index, section in found for record in section.records]


def write_text(data: bytes, texts: List[str], endian: str = "<") -> Tuple[bytes, List[str]]:
    """The file with ``texts`` written over its records. Returns (new bytes, warnings).

    ``texts`` must have one row per record of ``read_text``; otherwise the file is returned unchanged with a warning.
    """
    container, found = _sections(data, endian)
    if container is None or not found:
        return data, []
    total = sum(len(section.records) for _index, section in found)
    if len(texts) != total:
        return data, [f"row count changed ({len(texts)} for {total}); file not saved"]
    warnings: List[str] = []
    replacements = {}
    cursor = 0
    for index, section in found:
        new_records = []
        changed = False
        for record in section.records:
            text = texts[cursor]
            cursor += 1
            if text == _row(record, endian):
                new_records.append(record)
                continue
            try:
                strings = _encode_row(text, endian)
            except ValueError as error:
                warnings.append(f"row kept as it was: {error}")
                new_records.append(record)
                continue
            new_records.append(msd.Record(record.head, strings, record.tail))
            changed = True
        if not changed:
            continue
        new_section = msd.MsdSection(layout=section.layout, prefix=section.prefix, records=new_records,
                                     tail=section.tail, endian=endian)
        # A section never shrinks: the zero pad after the text is kept at its old length.
        replacements[index] = new_section.serialize(min_length=len(container.section_bytes(index)))
    try:
        return msd.serialize_container(container, replacements), warnings
    except msd.MsdError as error:
        return data, warnings + [str(error)]
