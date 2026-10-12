"""Split a TrueType collection (.ttc) into one standalone sfnt file per face, read only.

Each face keeps every table byte for byte. Only the table directory and the table offsets change, so
the editor's ``ttf`` reader can open a face like any .ttf. Used by the vWii system workspace for
WiiNTLG-Regular.ttc (two faces that share the glyph data of the collection).
"""
from __future__ import annotations

import struct
from typing import List


class TtcError(ValueError):
    """Raised when the file is not a TrueType collection."""


def split_ttc(data: bytes) -> List[bytes]:
    if data[:4] != b"ttcf":
        raise TtcError("not a TrueType collection (no ttcf tag)")
    count = struct.unpack_from(">I", data, 8)[0]
    faces = []
    for index in range(count):
        face_offset = struct.unpack_from(">I", data, 12 + 4 * index)[0]
        num_tables = struct.unpack_from(">H", data, face_offset + 4)[0]
        records = []
        for i in range(num_tables):
            tag, checksum, offset, length = struct.unpack_from(">4sIII", data, face_offset + 12 + 16 * i)
            records.append((tag, checksum, offset, length))
        header_size = 12 + 16 * num_tables
        body = bytearray()
        new_records = []
        for tag, checksum, offset, length in records:
            table = data[offset:offset + length]
            if len(table) != length:
                raise TtcError("table runs past the end of the file")
            new_records.append((tag, checksum, header_size + len(body), length))
            body += table
            body += b"\x00" * (-len(table) % 4)
        head = bytearray(data[face_offset:face_offset + 12])
        for tag, checksum, offset, length in new_records:
            head += struct.pack(">4sIII", tag, checksum, offset, length)
        faces.append(bytes(head) + bytes(body))
    return faces
