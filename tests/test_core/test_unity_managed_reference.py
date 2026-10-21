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


def _q(value):
    return struct.pack("<q", value)


def _i(value):
    return struct.pack("<i", value)


def _speaker_resolver(reference):
    return Node("Speaker", "Speaker", 0, 0, children=[Node("int", "voice", 4, 0)])


def _registry_root(speaker_children=()):
    """A class whose field ``target`` is a managed reference (its id only) and whose ``references`` block is the
    file's ManagedReferencesRegistry: a version and the RefIds (id, type name, data)."""
    item = Node("ReferencedObject", "data", -1, 0, children=[
        Node("SInt64", "rid", 8, 0),
        Node("ReferencedManagedType", "type", -1, 0, children=[
            Node("string", "class", -1, 0), Node("string", "ns", -1, 0), Node("string", "asm", -1, 0),
        ]),
        Node("ReferencedObjectData", "data", 0, 0),
    ])
    refids = Node("vector", "RefIds", -1, 0, children=[Node("Array", "Array", -1, 0, children=[
        Node("int", "size", 4, 0), item])])
    registry = Node("ManagedReferencesRegistry", "references", -1, 0, children=[Node("int", "version", 4, 0), refids])
    return Node("MonoBehaviour", "Base", 0, 0, children=[
        Node("managedReference", "target", 8, 0, children=[Node("SInt64", "rid", 8, 0)]),
        registry,
    ])


def _registry_bytes():
    """The field (id 42), then the registry: version 2, one RefIds item (id 42, a Speaker with voice 9)."""
    return (_q(42) + _i(2) + _i(1) + _q(42) + _pack_string("Speaker") + _pack_string("") + _pack_string("Asm")
            + _i(9))


def test_a_managed_reference_field_takes_its_id_and_the_registry_holds_the_data():
    value = read_value(_registry_root(), Reader(_registry_bytes(), 0, "<"), _speaker_resolver)
    assert value["target"] == {"rid": 42}
    assert value["references"]["RefIds"][0]["data"] == {"voice": 9}


def test_the_registry_writes_back_the_same_bytes():
    from core.unity.binary import Writer
    from core.unity.typetree import write_value

    value = read_value(_registry_root(), Reader(_registry_bytes(), 0, "<"), _speaker_resolver)
    writer = Writer("<")
    write_value(_registry_root(), value, writer, _speaker_resolver)
    assert bytes(writer.buf) == _registry_bytes()


def test_a_registry_inside_a_managed_type_is_skipped_because_the_object_has_one():
    # The Speaker type has its own registry field; the object's registry is read once, so this one is not in the data.
    def resolver(reference):
        return Node("Speaker", "Speaker", 0, 0, children=[
            Node("int", "voice", 4, 0),
            Node("ManagedReferencesRegistry", "references", -1, 0, children=[Node("int", "version", 4, 0)]),
        ])

    value = read_value(_registry_root(), Reader(_registry_bytes(), 0, "<"), resolver)
    assert value["references"]["RefIds"][0]["data"] == {"voice": 9}


def test_aligned_array_items_align_once_after_the_array():
    from core.unity.typetree import ALIGN_FLAG

    item = Node("Item", "data", 1, ALIGN_FLAG, children=[Node("UInt8", "a", 1, 0)])
    root = Node("Base", "Base", 0, 0, children=[
        Node("vector", "items", -1, 0, children=[Node("Array", "Array", -1, 0, children=[Node("int", "size", 4, 0), item])]),
        Node("int", "after", 4, 0),
    ])
    data = _i(3) + bytes([1, 2, 3]) + b"\x00" + _i(77)
    value = read_value(root, Reader(data, 0, "<"))
    assert value == {"items": [{"a": 1}, {"a": 2}, {"a": 3}], "after": 77}
    from core.unity.binary import Writer
    from core.unity.typetree import write_value

    writer = Writer("<")
    write_value(root, value, writer)
    assert bytes(writer.buf) == data


def test_the_common_string_table_names_the_file_size_type():
    from core.unity.common_strings import COMMON_STRINGS

    assert COMMON_STRINGS[1152] == "FileSize"
