"""Unity type trees (the embedded ``TypeTreeNode`` blob of a serialized file) and the values they describe.

A type tree is a list of nodes in depth-first order (``version`` 10 and later: a node count, a string buffer size, then
per node: i16 version, u8 level, u8 type flags, u32 type-name offset, u32 field-name offset, i32 byte size, i32 index,
i32 meta flags, and for version 19 and later a u64 reference type hash). A name offset with the top bit set names a
common string of the engine (``common_strings``); any other offset is a position in the string buffer.

``read_value`` turns the bytes of one object into the same dict / list / str / number shape that UnityPy's
``read_typetree`` gives (dict keys are field names in tree order); ``write_value`` writes such a value back in the same
layout. Meta flag 0x4000 aligns the value to four bytes after it is read or written.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any, List

from core.unity.binary import Reader, Writer
from core.unity.common_strings import COMMON_STRINGS

ALIGN_FLAG = 0x4000
_PRIMITIVE = {
    "SInt8": "b", "UInt8": "B", "char": "B",
    "short": "h", "SInt16": "h", "unsigned short": "H", "UInt16": "H",
    "int": "i", "SInt32": "i", "unsigned int": "I", "UInt32": "I", "Type*": "I",
    "long long": "q", "SInt64": "q", "unsigned long long": "Q", "UInt64": "Q", "FileSize": "Q",
    "float": "f", "double": "d", "bool": "?",
}


class TypeTreeError(ValueError):
    """A type tree or an object does not follow the layout this reader knows."""


@dataclass
class Node:
    type: str
    name: str
    size: int
    meta: int
    version: int = 0
    flags: int = 0
    index: int = 0
    level: int = 0
    ref_hash: int = 0
    children: List["Node"] = field(default_factory=list)


def _aligned(node: Node) -> bool:
    return bool(node.meta & ALIGN_FLAG)


def _string(buffer: bytes, value: int) -> str:
    if value & 0x80000000:
        return COMMON_STRINGS.get(value & 0x7FFFFFFF, str(value & 0x7FFFFFFF))
    end = buffer.index(b"\x00", value)
    return buffer[value:end].decode("utf-8", "replace")


def parse_blob(reader: Reader, version: int) -> Node:
    """The type tree at the reader's position (version 10 and 12 to 21 layout); the reader moves past it."""
    if version < 10 or version == 11 or version >= 22:
        raise TypeTreeError(f"type tree version {version} is not supported")
    count = reader.unpack("i")
    buffer_size = reader.unpack("i")
    record = struct.Struct(reader.endian + "hBBIIiii" + ("Q" if version >= 19 else ""))
    raw = reader.bytes(record.size * count)
    buffer = reader.bytes(buffer_size)
    nodes = []
    for fields in record.iter_unpack(raw):
        node_version, level, flags, type_at, name_at, size, index, meta = fields[:8]
        nodes.append(Node(type=_string(buffer, type_at), name=_string(buffer, name_at), size=size, meta=meta,
                          version=node_version, flags=flags, index=index, level=level,
                          ref_hash=fields[8] if len(fields) > 8 else 0))
    if not nodes:
        raise TypeTreeError("empty type tree")
    root = nodes[0]
    stack = [root]
    for node in nodes[1:]:
        while stack[-1].level >= node.level:
            stack.pop()
        stack[-1].children.append(node)
        stack.append(node)
    return root


def _primitive(reader: Reader, node: Node) -> Any:
    if node.type in _PRIMITIVE:
        return reader.unpack(_PRIMITIVE[node.type])
    if node.type == "string":
        return reader.aligned_str()
    if node.type == "TypelessData":
        return list(reader.bytes(reader.unpack("i")))
    raise TypeTreeError(f"not a primitive: {node.type}")


def _write_primitive(writer: Writer, node: Node, value: Any) -> None:
    if node.type in _PRIMITIVE:
        writer.pack(_PRIMITIVE[node.type], value)
    elif node.type == "string":
        writer.aligned_str(value)
    elif node.type == "TypelessData":
        writer.pack("i", len(value))
        writer.bytes(bytes(value))
    else:
        raise TypeTreeError(f"not a primitive: {node.type}")


def _is_primitive(node: Node) -> bool:
    return node.type in _PRIMITIVE or node.type in ("string", "TypelessData")


def _is_vector(node: Node) -> bool:
    return bool(node.children) and node.children[0].type == "Array"


def read_value(node: Node, reader: Reader) -> Any:
    align = _aligned(node)
    if _is_primitive(node):
        value = _primitive(reader, node)
    elif node.type == "ReferencedObject":
        raise TypeTreeError(f"{node.type} is not supported")
    elif _is_vector(node):
        if _aligned(node.children[0]):
            align = True
        size = reader.unpack("i")
        if size < 0:
            raise TypeTreeError("negative array length")
        value = _read_array(node.children[0].children[1], reader, size)
    else:
        value = {}
        for child in node.children:
            if child.type == "ManagedReferencesRegistry":
                raise TypeTreeError("managed references are not supported")
            value[child.name] = read_value(child, reader)
    if align:
        reader.align()
    return value


def _read_array(subtype: Node, reader: Reader, size: int) -> List[Any]:
    if not _aligned(subtype):
        return [read_value(subtype, reader) for _ in range(size)]
    if subtype.type in _PRIMITIVE:
        fmt = _PRIMITIVE[subtype.type]
        raw = reader.bytes(struct.calcsize(fmt) * size)
        values = list(struct.unpack(reader.endian + fmt * size, raw)) if size else []
    elif subtype.type == "string":
        values = [reader.aligned_str() for _ in range(size)]
    else:
        values = [read_value(subtype, reader) for _ in range(size)]
    reader.align()
    return values


def write_value(node: Node, value: Any, writer: Writer) -> None:
    align = _aligned(node)
    if _is_primitive(node):
        _write_primitive(writer, node, value)
    elif node.type == "ReferencedObject":
        raise TypeTreeError(f"{node.type} is not supported")
    elif _is_vector(node):
        if _aligned(node.children[0]):
            align = True
        writer.pack("i", len(value))
        _write_array(node.children[0].children[1], value, writer)
    else:
        for child in node.children:
            if child.type == "ManagedReferencesRegistry":
                raise TypeTreeError("managed references are not supported")
            write_value(child, value[child.name], writer)
    if align:
        writer.align()


def _write_array(subtype: Node, values: List[Any], writer: Writer) -> None:
    if not _aligned(subtype):
        for item in values:
            write_value(subtype, item, writer)
        return
    if subtype.type in _PRIMITIVE:
        fmt = _PRIMITIVE[subtype.type]
        writer.bytes(struct.pack(writer.endian + fmt * len(values), *values) if values else b"")
    elif subtype.type == "string":
        for item in values:
            writer.aligned_str(item)
    else:
        for item in values:
            write_value(subtype, item, writer)
    writer.align()
