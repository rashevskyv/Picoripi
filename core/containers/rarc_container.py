"""
RARC (Resource ARChive) container for Nintendo GameCube/Wii games.

Supports reading and writing RARC archives in-memory, including archives
wrapped in Yaz0 compression (which is how all Twilight Princess .arc files
are stored on disk).

Binary format (big-endian):

    RARC Header (0x20 bytes, at offset 0x00):
        0x00  char[4]   magic         = "RARC"
        0x04  u32       file_size     total size of archive in bytes
        0x08  u32       dh_off        offset to data header (always 0x20)
        0x0C  u32       data_off_rel  offset to file data, relative to dh_off
        0x10  u32       total_data    total bytes of all file data
        0x14  u32       mram_size     MRAM preload size (set == total_data)
        0x18  u32       aram_size     ARAM preload size (unused, 0)
        0x1C  u32       padding       (0)

    Data Header (0x20 bytes, at dh_off = 0x20):
        +0x00  u32   num_nodes          number of directory nodes
        +0x04  u32   node_list_off      offset to node list, relative to dh_off
        +0x08  u32   total_entries      total number of file entries
        +0x0C  u32   entries_off        offset to file entry list, relative to dh_off
        +0x10  u32   str_list_size      size of string table in bytes
        +0x14  u32   str_list_off       offset to string table, relative to dh_off
        +0x18  u16   next_free_id       next available file ID
        +0x1A  u8    sync_ids           whether file IDs are synced with entry indices
        +0x1B  u8    padding
        +0x1C  u32   padding

    Node (16 bytes each):
        char[4]  type           directory type tag (e.g. "ROOT", "RESF")
        u32      name_off       offset of name string in string table
        u16      name_hash      hash of name string
        u16      num_files      number of file entries belonging to this node
        u32      first_file_idx index of the first file entry for this node

    File Entry (20 bytes each):
        u16   file_id       0xFFFF for directory entries, else unique file ID
        u16   name_hash     hash of name string
        u16   flags         attribute flags (0x1100 = normal file, 0x0200 = directory)
        u16   name_off      offset of name string in string table
        u32   data_off      for files: offset from start of data section;
                            for dirs: index of the node this entry points to
                            (0xFFFFFFFF for the ".." entry of the root node)
        u32   size          for files: size in bytes;
                            for dirs: unused (often 16)
        u32   padding       (0)
"""

import struct
from .base_container import BaseArchiveContainer
from . import yaz0


_RARC_MAGIC = b"RARC"
_YAZ0_MAGIC = b"Yaz0"

# Struct format strings (big-endian)
_HDR_FMT = ">4sIIIIIII"      # RARC header
_DH_FMT  = ">IIIIIIHBBI"    # data header (note: HBB = u16, u8, u8; last I = u32 pad)
_NODE_FMT = ">4sIHHI"        # node entry
_ENTRY_FMT = ">HHHHI II"     # file entry  (note: space after HHHHI is intentional gap for clarity)

_NODE_SIZE  = 16
_ENTRY_SIZE = 20
_FILE_DATA_ALIGN = 0x20       # align each file's data to 32-byte boundary within data section


class RarcContainer(BaseArchiveContainer):
    """
    In-memory reader/writer for RARC (and Yaz0-wrapped RARC) archives.

    The archive is fully parsed into Python objects on construction.
    Individual files can be read or replaced (write_file). pack() reassembles
    the archive bytes, updating data offsets and sizes but preserving the
    directory/node/string-table structure unchanged.
    """

    MAGIC = _RARC_MAGIC

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        if len(data) < 4:
            return False
        if data[:4] == _RARC_MAGIC:
            return True
        if data[:4] == _YAZ0_MAGIC:
            # Peek inside: decompress only enough to check inner magic.
            # For small archives this is fast; for large ones Yaz0 is O(n) but still fast.
            try:
                inner = yaz0.decompress(data)
                return inner[:4] == _RARC_MAGIC
            except Exception:
                return False
        return False

    def __init__(self, data: bytes) -> None:
        # Detect and strip Yaz0 wrapper
        self._is_yaz0: bool = data[:4] == _YAZ0_MAGIC
        if self._is_yaz0:
            data = yaz0.decompress(data)

        if data[:4] != _RARC_MAGIC:
            raise ValueError(f"Not a RARC archive (magic={data[:4]!r})")

        self._raw: bytes = data
        self._overlay: dict[str, bytes] = {}  # staged file writes

        self._parse()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self) -> None:
        d = self._raw

        # RARC header
        self._dh_off: int = struct.unpack_from(">I", d, 0x08)[0]   # data header offset (0x20)
        self._data_off_rel: int = struct.unpack_from(">I", d, 0x0C)[0]  # file data start, rel to dh_off
        self._abs_data_off: int = self._data_off_rel + self._dh_off

        # Data header fields (we keep these for faithful round-tripping)
        dh = self._dh_off
        self._num_nodes: int    = struct.unpack_from(">I", d, dh + 0x00)[0]
        self._node_list_off: int = struct.unpack_from(">I", d, dh + 0x04)[0] + dh
        self._total_entries: int = struct.unpack_from(">I", d, dh + 0x08)[0]
        self._entries_off: int   = struct.unpack_from(">I", d, dh + 0x0C)[0] + dh
        self._str_list_size: int = struct.unpack_from(">I", d, dh + 0x10)[0]
        self._str_list_off: int  = struct.unpack_from(">I", d, dh + 0x14)[0] + dh
        self._next_free_id: int  = struct.unpack_from(">H", d, dh + 0x18)[0]
        self._sync_ids: int      = struct.unpack_from(">B", d, dh + 0x1A)[0]

        # String table (kept verbatim – we never rename files)
        self._str_data: bytes = d[self._str_list_off : self._str_list_off + self._str_list_size]

        # Parse nodes
        self._nodes: list[dict] = []
        for i in range(self._num_nodes):
            off = self._node_list_off + i * _NODE_SIZE
            typ       = d[off : off + 4].decode("ascii", "replace").rstrip("\x00")
            name_off  = struct.unpack_from(">I", d, off + 4)[0]
            name_hash = struct.unpack_from(">H", d, off + 8)[0]
            num_files = struct.unpack_from(">H", d, off + 10)[0]
            first_fi  = struct.unpack_from(">I", d, off + 12)[0]
            self._nodes.append({
                "type": typ,
                "name_off": name_off,
                "name": self._get_string(name_off),
                "name_hash": name_hash,
                "num_files": num_files,
                "first_file_index": first_fi,
                "raw_off": off,  # absolute byte offset in self._raw
            })

        # Parse file entries
        self._entries: list[dict] = []
        for i in range(self._total_entries):
            off = self._entries_off + i * _ENTRY_SIZE
            file_id   = struct.unpack_from(">H", d, off + 0)[0]
            name_hash = struct.unpack_from(">H", d, off + 2)[0]
            flags     = struct.unpack_from(">H", d, off + 4)[0]
            name_off  = struct.unpack_from(">H", d, off + 6)[0]
            data_off  = struct.unpack_from(">I", d, off + 8)[0]
            size      = struct.unpack_from(">I", d, off + 12)[0]
            # 4 bytes of padding at off+16

            is_dir = (file_id == 0xFFFF)
            abs_data_off = (self._abs_data_off + data_off) if not is_dir else None

            self._entries.append({
                "file_id": file_id,
                "name_hash": name_hash,
                "flags": flags,
                "name_off": name_off,
                "name": self._get_string(name_off),
                "data_off": data_off,       # relative to data section start
                "abs_data_off": abs_data_off,
                "size": size,
                "is_dir": is_dir,
                "raw_off": off,             # absolute byte offset in self._raw
            })

        # Build unix_path → entry_index map by traversing the node tree
        self._file_paths: dict[str, int] = {}  # {unix_path: entry_idx}
        if self._nodes:
            self._traverse_node(node_idx=0, prefix="", visited=set())

    def _get_string(self, str_off: int) -> str:
        """Read a null-terminated ASCII string from the string table."""
        end = self._str_data.index(b"\x00", str_off)
        return self._str_data[str_off:end].decode("ascii", "replace")

    def _traverse_node(self, node_idx: int, prefix: str, visited: set) -> None:
        """Recursively walk the node tree and populate self._file_paths."""
        if node_idx in visited:
            return
        visited.add(node_idx)

        node = self._nodes[node_idx]
        for i in range(node["num_files"]):
            entry_idx = node["first_file_index"] + i
            if entry_idx >= len(self._entries):
                break
            entry = self._entries[entry_idx]
            if entry["is_dir"]:
                if entry["name"] in (".", ".."):
                    continue
                child_node_idx = entry["data_off"]
                if 0 <= child_node_idx < len(self._nodes):
                    child_prefix = f"{prefix}/{entry['name']}" if prefix else entry["name"]
                    self._traverse_node(child_node_idx, child_prefix, visited)
            else:
                path = f"{prefix}/{entry['name']}" if prefix else entry["name"]
                self._file_paths[path] = entry_idx

    # ------------------------------------------------------------------
    # BaseArchiveContainer interface
    # ------------------------------------------------------------------

    def list_files(self) -> list[str]:
        return list(self._file_paths.keys())

    def read_file(self, path: str) -> bytes:
        if path in self._overlay:
            return self._overlay[path]
        if path not in self._file_paths:
            raise KeyError(f"File not found in RARC archive: {path!r}")
        entry = self._entries[self._file_paths[path]]
        off = entry["abs_data_off"]
        return self._raw[off : off + entry["size"]]

    def write_file(self, path: str, data: bytes) -> None:
        if path not in self._file_paths:
            raise KeyError(f"File not found in RARC archive: {path!r}")
        self._overlay[path] = data

    def pack(self) -> bytes:
        """
        Reassemble the archive, incorporating any staged writes.

        Strategy:
          - The structural prefix (RARC header + data header + nodes +
            file entries + string table) is copied verbatim.
          - File entry data_off and size fields are patched in-place for
            changed files.
          - The file data section is rebuilt from scratch, with files laid
            out in their original order and each aligned to _FILE_DATA_ALIGN.
          - RARC header fields (file_size, total_data_size, mram_size) are
            updated to reflect the new data section size.

        Returns:
            Complete RARC bytes (or Yaz0-wrapped RARC if the source was Yaz0).
        """
        if not self._overlay:
            # No changes – return original bytes (re-wrapped if necessary)
            return yaz0.compress(self._raw) if self._is_yaz0 else self._raw

        # --- Build new data section ---
        # Collect non-directory entries sorted by their original data offset
        # so files appear in the same order as in the original archive.
        ordered: list[tuple[int, str, int]] = []  # (original_data_off, path, entry_idx)
        for path, entry_idx in self._file_paths.items():
            entry = self._entries[entry_idx]
            ordered.append((entry["data_off"], path, entry_idx))
        ordered.sort(key=lambda t: t[0])

        new_data_section = bytearray()
        new_offsets: dict[int, tuple[int, int]] = {}  # entry_idx → (new_rel_off, new_size)

        for _, path, entry_idx in ordered:
            # Align to _FILE_DATA_ALIGN
            pad = (_FILE_DATA_ALIGN - len(new_data_section) % _FILE_DATA_ALIGN) % _FILE_DATA_ALIGN
            new_data_section += b"\x00" * pad

            rel_off = len(new_data_section)
            content = self.read_file(path)
            new_data_section += content
            new_offsets[entry_idx] = (rel_off, len(content))

        # Pad data section to alignment boundary
        pad = (_FILE_DATA_ALIGN - len(new_data_section) % _FILE_DATA_ALIGN) % _FILE_DATA_ALIGN
        new_data_section += b"\x00" * pad

        # --- Patch structural prefix ---
        # Everything before the data section stays the same; we just patch
        # specific fields within it.
        prefix = bytearray(self._raw[: self._abs_data_off])

        # Patch each file entry: data_off (at +8) and size (at +12)
        for entry_idx, (new_rel_off, new_size) in new_offsets.items():
            raw_off = self._entries[entry_idx]["raw_off"]
            struct.pack_into(">I", prefix, raw_off + 8,  new_rel_off)
            struct.pack_into(">I", prefix, raw_off + 12, new_size)

        # Patch RARC header: total_data_size (0x10) and mram_size (0x14)
        new_total_data = len(new_data_section)
        struct.pack_into(">I", prefix, 0x10, new_total_data)
        struct.pack_into(">I", prefix, 0x14, new_total_data)  # mram = all data

        # Patch RARC header: file_size (0x04)
        new_file_size = len(prefix) + len(new_data_section)
        struct.pack_into(">I", prefix, 0x04, new_file_size)

        result = bytes(prefix) + bytes(new_data_section)

        if self._is_yaz0:
            return yaz0.compress(result)
        return result
