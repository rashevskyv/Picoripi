"""Serialized files of format 22 on synthetic bytes: the 48-byte header, 64-bit object starts, the unchanged round trip and
the appended changed object. The test writes the files itself."""
import struct

import pytest

from core.unity.binary import Reader, Writer
from core.unity.serialized import SerializedError, SerializedFile
from core.unity.typetree import parse_blob

FORMAT = 22


def _metadata(objects):
    """The metadata of a format 22 file: one type (class 114, no type tree) and the object table."""
    writer = Writer("<")
    writer.cstr("2022.3.0f1")          # unity version
    writer.pack("i", 19)               # target platform
    writer.pack("B", 0)                # type trees disabled
    writer.pack("i", 1)                # one type
    writer.pack("i", 114)              # class id
    writer.pack("B", 0)                # stripped
    writer.pack("h", -1)               # script index
    writer.bytes(bytes(16))            # script id
    writer.bytes(bytes(16))            # old type hash
    writer.pack("i", len(objects))
    for path_id, start, size in objects:
        writer.align()
        writer.pack("q", path_id)
        writer.pack("q", start)        # 64-bit byte start, relative to the data offset
        writer.pack("I", size)
        writer.pack("i", 0)            # type index
    writer.pack("i", 0)                # script types
    writer.pack("i", 0)                # externals
    writer.pack("i", 0)                # ref types
    writer.cstr("")                    # user information
    return bytes(writer.buf)


def _file(payloads, version=FORMAT):
    """A format 22 serialized file holding ``payloads`` (path id -> bytes) in its data region."""
    data = bytearray()
    objects = []
    for path_id, raw in payloads:
        data += b"\x00" * (-len(data) % 8)
        objects.append((path_id, len(data), len(raw)))
        data += raw
    meta = _metadata(objects)
    header = 48
    metadata_end = header + len(meta)
    data_offset = metadata_end + (-metadata_end % 16)
    total = data_offset + len(data)
    head = bytearray(header)
    struct.pack_into(">I", head, 0, len(meta))
    struct.pack_into(">I", head, 8, version)
    struct.pack_into(">I", head, 20, len(meta))
    struct.pack_into(">qqq", head, 24, total, data_offset, 0)
    return bytes(head) + meta + bytes(data_offset - metadata_end) + bytes(data)


def test_header_and_objects_are_read_at_64_bit_offsets():
    payloads = {1: b"A" * 13, 2: b"BB" * 5}
    raw = _file(list(payloads.items()))
    sf = SerializedFile(raw)
    assert sf.version == FORMAT
    assert sf.header_size == 48
    assert [obj.path_id for obj in sf.objects] == [1, 2]
    assert sf.object_bytes(1) == payloads[1]
    assert sf.object_bytes(2) == payloads[2]


def test_unchanged_file_round_trips_byte_for_byte():
    raw = _file([(7, b"\x01\x02\x03" * 9), (8, b"tail")])
    assert SerializedFile(raw).replace({}) == raw


def test_changed_object_is_appended_and_the_others_keep_their_bytes():
    raw = _file([(1, b"first object"), (2, b"second object")])
    sf = SerializedFile(raw)
    out = sf.replace({1: b"XYZ changed"})
    again = SerializedFile(out)
    assert again.object_bytes(1) == b"XYZ changed"
    assert again.object_bytes(2) == b"second object"
    assert again.data_offset == sf.data_offset


def test_format_23_is_refused():
    raw = _file([(1, b"x")], version=23)
    with pytest.raises(SerializedError):
        SerializedFile(raw)


def test_format_22_type_tree_blob_parses():
    buffer = b"Base\x00"
    record = struct.pack("<hBBIIiiiQ", 1, 0, 0, 0, 0, -1, 0, 0, 0)
    blob = struct.pack("<ii", 1, len(buffer)) + record + buffer
    node = parse_blob(Reader(blob, 0, "<"), FORMAT)
    assert node.type == "Base"
    assert node.children == []
