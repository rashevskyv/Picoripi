"""Unity serialized files (``CAB-...`` entries of a bundle, format 9 to 22): the object table, the type trees and the
values of the objects.

Layout: a 20-byte header (big-endian: metadata size, file size, format version, data offset; then an endian byte and
three reserved bytes), the metadata (little-endian here: the unity version, the types with their type trees, the
objects, the script types and the externals), padding, and the object data at ``data offset``. An object's bytes start
at ``data offset + byte start``. Format 22 has a 48-byte header: after the endian byte and reserved bytes come the
metadata size (u32, big-endian), the file size (i64), the data offset (i64) and one unknown i64; its object byte starts
are i64 (format 21 and older: u32).

``SerializedFile.read(path_id)`` returns the object's value as a dict (its type tree). ``replace`` writes the file again
with other bytes for some objects: the object table is patched in place; a changed object is appended after the data.
Only little-endian files of format 9 to 22 are read; anything else raises ``SerializedError``.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.unity.binary import Reader, Writer
from core.unity.typetree import Node, TypeTreeError, parse_blob, read_value, write_value

HEADER = 20
HEADER_V22 = 48
FORMAT_LARGE_OFFSETS = 22   # the first format whose header and object byte starts are 64-bit


class SerializedError(ValueError):
    """The bytes are not a serialized file this reader supports."""


@dataclass
class SerializedType:
    class_id: int
    script_index: int
    node: Optional[Node]
    class_name: str = ""     # reference types only: the managed class, its namespace and assembly
    namespace: str = ""
    assembly: str = ""


@dataclass
class ObjectInfo:
    path_id: int
    start: int          # absolute offset of the object's bytes in the file
    size: int
    type_id: int
    class_id: int
    field_at: int       # metadata offset of the object's byte start (its size follows)


class SerializedFile:
    def __init__(self, data: bytes):
        if len(data) < HEADER:
            raise SerializedError("serialized file too short")
        metadata_size, file_size, version, data_offset = struct.unpack_from(">IIII", data, 0)
        if not 9 <= version <= 22:
            raise SerializedError(f"serialized file format {version} is not supported")
        if data[16]:
            raise SerializedError("big-endian serialized files are not supported")
        header = HEADER
        if version >= FORMAT_LARGE_OFFSETS:
            if len(data) < HEADER_V22:
                raise SerializedError("serialized file too short for its header")
            (metadata_size,) = struct.unpack_from(">I", data, 20)
            file_size, data_offset, _unknown = struct.unpack_from(">qqq", data, 24)
            header = HEADER_V22
            if file_size < 0 or data_offset < 0:
                raise SerializedError("serialized file has a negative size or offset")
        self.data = data
        self.version = version
        self.header_size = header
        self.data_offset = data_offset
        self.metadata_end = header + metadata_size
        if self.metadata_end > len(data) or data_offset < self.metadata_end:
            raise SerializedError("metadata does not fit the file")
        self.file_size = file_size
        reader = Reader(data, header, "<")
        self.unity_version = reader.cstr() if version >= 7 else ""
        if version >= 8:
            reader.unpack("i")   # target platform
        self.enable_type_tree = bool(reader.unpack("B")) if version >= 13 else False
        self.types = [self._read_type(reader, False) for _ in range(reader.unpack("i"))]
        self.objects: List[ObjectInfo] = []
        self.by_path: Dict[int, ObjectInfo] = {}
        for _ in range(reader.unpack("i")):
            obj = self._read_object(reader)
            self.objects.append(obj)
            self.by_path[obj.path_id] = obj
        self.ref_types: List[SerializedType] = []
        if version >= 11:   # script types: an index and a local identifier each
            for _ in range(reader.unpack("i")):
                reader.unpack("i")
                if version >= 14:
                    reader.align()
                    reader.unpack("q")
                else:
                    reader.unpack("i")
        for _ in range(reader.unpack("i")):   # externals: a path, and a guid and type from version 5
            if version >= 6:
                reader.cstr()
            if version >= 5:
                reader.bytes(16)
                reader.unpack("i")
            reader.cstr()
        if version >= 20:
            self.ref_types = [self._read_type(reader, True) for _ in range(reader.unpack("i"))]

    def _read_type(self, reader: Reader, is_ref: bool) -> SerializedType:
        version = self.version
        class_id = reader.unpack("i")
        if version >= 16:
            reader.unpack("B")   # stripped
        script_index = reader.unpack("h") if version >= 17 else -1
        if version >= 13:
            if (is_ref and script_index >= 0) or (version < 16 and class_id < 0) or (version >= 16 and class_id == 114):
                reader.bytes(16)   # script id
            reader.bytes(16)       # old type hash
        node = None
        names = ("", "", "")
        if self.enable_type_tree:
            try:
                node = parse_blob(reader, version)
            except (TypeTreeError, struct.error, ValueError) as exc:
                raise SerializedError(f"type tree of class {class_id} is not readable: {exc}") from None
            if version >= 21:
                if is_ref:
                    names = (reader.cstr(), reader.cstr(), reader.cstr())
                else:
                    reader.bytes(4 * reader.unpack("i"))   # type dependencies
        return SerializedType(class_id, script_index, node, *names)

    def _reference_node(self, reference: Dict[str, Any]) -> Optional[Node]:
        """The type tree of a managed reference, from its type name; None for a null reference (no class name)."""
        kind = reference.get("type") or {}
        key = (kind.get("class", ""), kind.get("ns", ""), kind.get("asm", ""))
        if key[0] == "":
            return None
        for item in self.ref_types:
            if (item.class_name, item.namespace, item.assembly) == key:
                if item.node is None:
                    raise SerializedError(f"managed type {key[0]} has no type tree")
                return item.node
        raise SerializedError(f"managed type {key[0]} is not among the reference types")

    def _read_object(self, reader: Reader) -> ObjectInfo:
        if self.version >= 14:
            reader.align()
            path_id = reader.unpack("q")
        else:
            path_id = reader.unpack("i")
        field_at = reader.pos
        byte_start = reader.unpack("q") if self.version >= FORMAT_LARGE_OFFSETS else reader.unpack("I")
        start = byte_start + self.data_offset
        size = reader.unpack("I")
        type_id = reader.unpack("i")
        if self.version < 16:
            class_id = reader.unpack("H")
        else:
            if not 0 <= type_id < len(self.types):
                raise SerializedError(f"object {path_id} names type {type_id} of {len(self.types)}")
            class_id = self.types[type_id].class_id
        if self.version < 11:
            reader.unpack("H")   # destroyed
        if 11 <= self.version < 17:
            reader.unpack("h")   # script type index
        if self.version in (15, 16):
            reader.unpack("B")   # stripped
        if start < self.data_offset or start + size > len(self.data):
            raise SerializedError(f"object {path_id} lies outside the file")
        return ObjectInfo(path_id, start, size, type_id, class_id, field_at)

    def object_bytes(self, path_id: int) -> bytes:
        obj = self.by_path[path_id]
        return self.data[obj.start:obj.start + obj.size]

    def type_node(self, path_id: int) -> Node:
        node = self.types[self.by_path[path_id].type_id].node
        if node is None:
            raise SerializedError("this file has no type trees (the object values are not readable)")
        return node

    def read(self, path_id: int) -> Any:
        """The object's value: a dict of its type tree (a MonoBehaviour's fields, a PPtr's file and path id, ...)."""
        node = self.type_node(path_id)
        raw = self.object_bytes(path_id)
        reader = Reader(raw, 0, "<")
        try:
            value = read_value(node, reader, self._reference_node)
        except (TypeTreeError, EOFError, struct.error, ValueError) as exc:
            raise SerializedError(f"object {path_id} does not read: {exc}") from None
        if reader.pos != len(raw):
            raise SerializedError(f"object {path_id}: {len(raw) - reader.pos} bytes left after its type tree")
        return value

    def write(self, path_id: int, value: Any) -> bytes:
        """The bytes of an object for ``value`` (the same shape ``read`` gives)."""
        writer = Writer("<")
        try:
            write_value(self.type_node(path_id), value, writer, self._reference_node)
        except (TypeTreeError, KeyError, TypeError, struct.error) as exc:
            raise SerializedError(f"object {path_id} does not write: {exc}") from None
        return bytes(writer.buf)

    def replace(self, changed: Dict[int, bytes]) -> bytes:
        """The file with the object bytes ``changed`` (path id -> bytes); every other object keeps its bytes.

        An unchanged object keeps its bytes and place; a changed one is appended after the data, eight-byte aligned. Without
        changes the file is returned as it was read.
        """
        unknown = set(changed) - set(self.by_path)
        if unknown:
            raise SerializedError(f"no object {sorted(unknown)[0]} in the file")
        body = bytearray(self.data[self.data_offset:])
        placed: Dict[int, tuple] = {}   # path id -> (start in the data, size)
        for obj in self.objects:
            if obj.path_id in changed:
                raw = changed[obj.path_id]
                body += b"\x00" * (-len(body) % 8)
                placed[obj.path_id] = (len(body), len(raw))
                body += raw
            else:   # an unchanged object keeps its bytes and its place
                placed[obj.path_id] = (obj.start - self.data_offset, obj.size)
        metadata = bytearray(self.data[self.header_size:self.metadata_end])
        start_format = "<q" if self.version >= FORMAT_LARGE_OFFSETS else "<I"
        for obj in self.objects:
            start, size = placed[obj.path_id]
            struct.pack_into(start_format + "I", metadata, obj.field_at - self.header_size, start, size)
        head = bytearray(self.data[:self.header_size])
        total = self.data_offset + len(body)
        if self.version >= FORMAT_LARGE_OFFSETS:
            struct.pack_into(">q", head, 24, total)
        else:
            struct.pack_into(">I", head, 4, total)
        padding = self.data[self.metadata_end:self.data_offset]
        return bytes(head) + bytes(metadata) + padding + bytes(body)
