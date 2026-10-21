"""A managed reference (SerializeReference) reads its data with the type tree that its type names. The test builds the
bytes and the type trees itself."""
import struct

import pytest

from core.unity.binary import Reader
from core.unity.typetree import Node, TypeTreeError, read_value


def _reference_node():
    """A ReferencedObject: the id, the type (class, namespace, assembly) and the data."""
    return Node("ReferencedObject", "Entry", 0, 0, children=[
        Node("SInt64", "rid", 8, 0),
        Node("ReferencedObjectType", "type", 0, 0, children=[
            Node("string", "class", 0, 0),
            Node("string", "ns", 0, 0),
            Node("string", "asm", 0, 0),
        ]),
        Node("ReferencedObjectData", "data", 0, 0),
    ])


def _resolver(reference):
    if reference["type"]["class"] == "Speaker":
        return Node("Speaker", "Speaker", 0, 0, children=[Node("int", "voice", 4, 0)])
    return None


def _pack_string(text):
    raw = text.encode("utf-8")
    return struct.pack("<i", len(raw)) + raw + b"\x00" * (-len(raw) % 4)


def test_managed_reference_reads_its_data_with_the_named_type():
    data = struct.pack("<q", 42) + _pack_string("Speaker") + _pack_string("Game") + _pack_string("Asm") + struct.pack("<i", 9)
    value = read_value(_reference_node(), Reader(data, 0, "<"), _resolver)
    assert value["rid"] == 42
    assert value["type"] == {"class": "Speaker", "ns": "Game", "asm": "Asm"}
    assert value["data"] == {"voice": 9}


def test_null_reference_has_no_data():
    data = struct.pack("<q", 7) + _pack_string("") + _pack_string("") + _pack_string("")
    value = read_value(_reference_node(), Reader(data, 0, "<"), _resolver)
    assert value["rid"] == 7
    assert "data" not in value


def test_managed_reference_without_a_resolver_is_refused():
    data = struct.pack("<q", 1) + _pack_string("Speaker") + _pack_string("") + _pack_string("") + struct.pack("<i", 0)
    with pytest.raises(TypeTreeError):
        read_value(_reference_node(), Reader(data, 0, "<"))


def test_managed_reference_writes_back_the_same_bytes():
    from core.unity.binary import Writer
    from core.unity.typetree import write_value

    data = struct.pack("<q", 42) + _pack_string("Speaker") + _pack_string("Game") + _pack_string("Asm") + struct.pack("<i", 9)
    value = read_value(_reference_node(), Reader(data, 0, "<"), _resolver)
    writer = Writer("<")
    write_value(_reference_node(), value, writer, _resolver)
    assert bytes(writer.buf) == data
