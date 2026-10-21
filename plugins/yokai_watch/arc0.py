"""Bounded, read-only ARC0 index access: Yo-kai Watch reference text and the wizard unpack."""
from contextlib import nullcontext
from pathlib import Path, PurePosixPath
import struct
import zlib

from core.containers.level5 import decompress, size_of

MAX_TABLE = 32 * 1024 * 1024
MAX_MEMBER = 64 * 1024 * 1024


def _table(raw: bytes) -> bytes:
    if len(raw) < 4 or size_of(raw) > MAX_TABLE:
        raise ValueError("ARC0 index exceeds its size limit")
    size = size_of(raw)
    try:
        if raw[0] & 7 == 5:
            decoder = zlib.decompressobj()
            result = decoder.decompress(raw[4:], size + 1)
            if not decoder.eof:
                raise ValueError("Invalid ARC0 compressed index")
        else:
            result = decompress(raw)
    except (IndexError, struct.error, zlib.error) as error:
        raise ValueError("Invalid ARC0 compressed index") from error
    if len(result) != size:
        raise ValueError("Invalid ARC0 index size")
    return result


class Arc0:
    """Index the archive without loading its payload; read only requested members."""

    def __init__(self, source, is_cancelled=lambda: False):
        """``source`` is the archive's path, or a seekable binary stream that starts at the archive."""
        self.source = source if hasattr(source, "read") else Path(source)
        self.files = {}
        with self._open() as stream:
            stream.seek(0, 2)
            total = stream.tell()
            stream.seek(0)
            head = stream.read(0x48)
            if len(head) != 0x48 or head[:4] != b"ARC0":
                raise ValueError("Invalid ARC0 header")
            directory, hashes, files, names, self.data = struct.unpack_from("<5I", head, 4)
            dir_count, _hash_count, file_count = struct.unpack_from("<HHi", head, 0x18)
            if not (0x48 <= directory <= hashes <= files <= names <= self.data <= total):
                raise ValueError("Invalid ARC0 index offsets")
            if self.data - directory > MAX_TABLE or not 0 <= file_count <= 1_000_000:
                raise ValueError("ARC0 index exceeds its size limit")
            stream.seek(directory)
            raw = stream.read(self.data - directory)
        dirs = _table(raw[:hashes - directory])
        entries = _table(raw[files - directory:names - directory])
        strings = _table(raw[names - directory:])
        if len(dirs) < dir_count * 20 or len(entries) < file_count * 16:
            raise ValueError("Truncated ARC0 index")

        def name(at):
            if not 0 <= at < len(strings):
                raise ValueError("Invalid ARC0 name offset")
            return strings[at:strings.index(b"\0", at)].decode("shift-jis")

        for index in range(dir_count):
            if is_cancelled():
                return
            _crc, _first_dir, _dirs, first, count, prefix, folder_at = struct.unpack_from("<IHhHhii", dirs, index * 20)
            if count < 0 or first + count > file_count:
                raise ValueError("Invalid ARC0 directory range")
            folder = name(folder_at)
            for item in range(first, first + count):
                _crc, name_at, offset, size = struct.unpack_from("<4I", entries, item * 16)
                member = folder + name(prefix + name_at)
                parts = PurePosixPath(member).parts
                if not parts or member.startswith("/") or "\\" in member or ":" in member or ".." in parts:
                    raise ValueError("Invalid ARC0 member path")
                if member in self.files or offset + size > total - self.data:
                    raise ValueError("Invalid ARC0 member range")
                self.files[member] = (offset, size)
        if len(self.files) != file_count:
            raise ValueError("ARC0 file count mismatch")

    def _open(self):
        return nullcontext(self.source) if hasattr(self.source, "read") else self.source.open("rb")

    def read(self, member: str) -> bytes:
        offset, size = self.files[member]
        if size > MAX_MEMBER:
            raise ValueError("ARC0 reference table exceeds its size limit")
        with self._open() as stream:
            stream.seek(self.data + offset)
            raw = stream.read(size)
        if len(raw) != size:
            raise ValueError("Truncated ARC0 member")
        return raw
