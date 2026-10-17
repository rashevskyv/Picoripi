"""A Unity ``pair`` (a sprite's render key: two named fields) reads and writes like a record."""
from core.unity.binary import Reader, Writer
from core.unity.typetree import Node, read_value, write_value


def test_a_pair_reads_and_writes_its_two_fields_as_a_record():
    node = Node("pair", "m_RenderDataKey", 16, 0, children=[
        Node("SInt64", "first", 8, 0),
        Node("SInt64", "second", 8, 0),
    ])
    writer = Writer()
    write_value(node, {"first": 5, "second": -7}, writer)
    assert read_value(node, Reader(bytes(writer.buf))) == {"first": 5, "second": -7}
