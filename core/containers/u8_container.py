"""
U8 archive container for Nintendo GameCube/Wii games.

U8 is a flat-list archive format (magic 0x55AA382D, "U.8-") commonly used
in Wii titles (Mario Kart Wii, etc.) and some later GameCube games.
It is structurally simpler than RARC: a single flat node array forms the
entire directory tree, and directory nodes store child ranges by index.

Binary format (big-endian):

    Header (0x20 bytes, at offset 0x00):
        0x00  u32   magic       = 0x55AA382D ("U.8-")
        0x04  u32   root_off    offset to first node (always 0x20)
        0x08  u32   hdr_size    total size of (node list + string table)
        0x0C  u32   data_off    offset to file data section (0x20-aligned)
        0x10  u8[16] padding    (zeros)

    Nodes (12 bytes each, starting at root_off = 0x20):
        0x00  u16   type        0x0000=file, 0x0100=directory
        0x02  u16   name_off    offset into string table
        0x04  u32   data_off    for file: offset from file start; for dir: first child index
        0x08  u32   size        for file: bytes; for dir: one-past-last child index

    String table: immediately after node array
        str_table_off = root_off + total_nodes * 12
        total_nodes   = root_node.size  (root's "one-past-last" = total count)

    File data: at data_off, each file at an offset recorded in its node.
"""

import struct
from .base_container import BaseArchiveContainer
from . import yaz0


_U8_MAGIC   = b"\x55\xaa\x38\x2d"
_YAZ0_MAGIC = b"Yaz0"
_NODE_SIZE  = 12
_DATA_ALIGN = 0x20

_NODE_FILE = 0x0000
_NODE_DIR  = 0x0100


class U8Container(BaseArchiveContainer):
    """
    In-memory reader/writer for U8 archives (and Yaz0-wrapped U8 archives).
    """

    MAGIC = _U8_MAGIC

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        if len(data) < 4:
            return False
        if data[:4] == _U8_MAGIC:
            return True
        if data[:4] == _YAZ0_MAGIC:
            try:
                inner = yaz0.decompress(data)
                return inner[:4] == _U8_MAGIC
            except Exception:
                return False
        return False

    def __init__(self, data: bytes) -> None:
        self._is_yaz0: bool = data[:4] == _YAZ0_MAGIC
        if self._is_yaz0:
            data = yaz0.decompress(data)

        if data[:4] != _U8_MAGIC:
            raise ValueError(f"Not a U8 archive (magic={data[:4]!r})")

        self._raw: bytes = data
        self._overlay: dict[str, bytes] = {}
        self._parse()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self) -> None:
        d = self._raw
        self._root_off: int = struct.unpack_from(">I", d, 0x04)[0]   # always 0x20
        self._hdr_size: int = struct.unpack_from(">I", d, 0x08)[0]   # nodes + str table
        self._data_off: int = struct.unpack_from(">I", d, 0x0C)[0]   # file data start

        # Root node is first — its `size` field = total number of nodes
        root_type     = struct.unpack_from(">H", d, self._root_off)[0]
        root_data_off = struct.unpack_from(">I", d, self._root_off + 4)[0]
        root_size     = struct.unpack_from(">I", d, self._root_off + 8)[0]

        if root_type != _NODE_DIR:
            raise ValueError("U8 root node is not a directory")

        self._total_nodes: int = root_size  # root.size = one-past-last child = total count

        # String table begins right after all nodes
        self._str_table_off: int = self._root_off + self._total_nodes * _NODE_SIZE

        # Parse all nodes
        self._nodes: list[dict] = []
        for i in range(self._total_nodes):
            off  = self._root_off + i * _NODE_SIZE
            typ      = struct.unpack_from(">H", d, off + 0)[0]
            name_off = struct.unpack_from(">H", d, off + 2)[0]
            data_off = struct.unpack_from(">I", d, off + 4)[0]
            size     = struct.unpack_from(">I", d, off + 8)[0]
            self._nodes.append({
                "type": typ,
                "name_off": name_off,
                "name": self._get_string(name_off),
                "data_off": data_off,
                "size": size,
                "raw_off": off,
            })

        # Build path → node_index map
        self._file_paths: dict[str, int] = {}   # {unix_path: node_idx}
        # Start from root's children (root itself is index 0, children start at 1)
        self._traverse_dir(node_idx=0, prefix="")

    def _get_string(self, name_off: int) -> str:
        d = self._raw
        start = self._str_table_off + name_off
        end   = d.index(b"\x00", start)
        return d[start:end].decode("ascii", "replace")

    def _traverse_dir(self, node_idx: int, prefix: str) -> None:
        node = self._nodes[node_idx]
        assert node["type"] == _NODE_DIR

        first_child = node["data_off"]   # index of first child node
        last_child  = node["size"]       # one-past-last child index

        i = first_child
        while i < last_child:
            child = self._nodes[i]
            if child["type"] == _NODE_DIR:
                child_prefix = f"{prefix}/{child['name']}" if prefix else child["name"]
                self._traverse_dir(i, child_prefix)
                # Skip to the node after this directory subtree
                i = child["size"]  # one-past-last of the subdirectory
            else:
                path = f"{prefix}/{child['name']}" if prefix else child["name"]
                self._file_paths[path] = i
                i += 1

    # ------------------------------------------------------------------
    # BaseArchiveContainer interface
    # ------------------------------------------------------------------

    def list_files(self) -> list[str]:
        return list(self._file_paths.keys())

    def read_file(self, path: str) -> bytes:
        if path in self._overlay:
            return self._overlay[path]
        if path not in self._file_paths:
            raise KeyError(f"File not found in U8 archive: {path!r}")
        node = self._nodes[self._file_paths[path]]
        return self._raw[node["data_off"] : node["data_off"] + node["size"]]

    def write_file(self, path: str, data: bytes) -> None:
        if path not in self._file_paths:
            raise KeyError(f"File not found in U8 archive: {path!r}")
        self._overlay[path] = data

    def pack(self) -> bytes:
        """
        Reassemble the U8 archive, incorporating any staged writes.

        Strategy: keep node array and string table verbatim; rebuild the file
        data section, patching each modified file node's data_off and size.
        """
        if not self._overlay:
            return yaz0.compress(self._raw) if self._is_yaz0 else self._raw

        # Sort files by original data offset for stable output ordering
        ordered: list[tuple[int, str, int]] = []
        for path, node_idx in self._file_paths.items():
            node = self._nodes[node_idx]
            ordered.append((node["data_off"], path, node_idx))
        ordered.sort(key=lambda t: t[0])

        # Build new data section
        new_data = bytearray()
        new_info: dict[int, tuple[int, int]] = {}  # node_idx → (new_abs_off, new_size)

        for _, path, node_idx in ordered:
            pad = (_DATA_ALIGN - len(new_data) % _DATA_ALIGN) % _DATA_ALIGN
            new_data += b"\x00" * pad
            abs_off = self._data_off + len(new_data)
            content = self.read_file(path)
            new_data += content
            new_info[node_idx] = (abs_off, len(content))

        pad = (_DATA_ALIGN - len(new_data) % _DATA_ALIGN) % _DATA_ALIGN
        new_data += b"\x00" * pad

        # Patch prefix (header + node list + string table)
        prefix = bytearray(self._raw[: self._data_off])

        for node_idx, (abs_off, new_size) in new_info.items():
            raw_off = self._nodes[node_idx]["raw_off"]
            struct.pack_into(">I", prefix, raw_off + 4, abs_off)   # data_off
            struct.pack_into(">I", prefix, raw_off + 8, new_size)  # size

        result = bytes(prefix) + bytes(new_data)

        if self._is_yaz0:
            return yaz0.compress(result)
        return result
