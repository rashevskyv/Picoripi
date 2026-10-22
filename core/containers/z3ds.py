"""Z3DS: a compressed 3DS image (Azahar and Citra ``.zcia``, ``.zcci``, ``.zcxi``, ``.z3dsx``, ``.z3ds``).

The file is a 0x20-byte header, metadata (``metadata_size`` bytes at ``header_size``), then a zstd seekable stream: zstd
frames and a seek table in a skippable frame at the end. ``Z3dsStream`` reads the decompressed image through a seek, one
frame at a time, so a 3DS image is never held in memory whole. The decompressed image is then read as its own file
(``core.containers.n3ds``). Layout from Azahar's ``src/common/file_derived.h`` and ``file_derived.cpp``.

The zstd backend is the standard library's ``compression.zstd`` (Python 3.14), else the ``zstandard`` package, else
``pyzstd``. Without one, a Z3DS file is refused with the reason; nothing else in Picoripi needs zstd.
"""
from __future__ import annotations

import bisect
import struct
from collections import OrderedDict
from typing import Any, Callable, List, Optional, Tuple

from core.containers.image_files import ImageError
from core.i18n import tr

MAGIC = b"Z3DS"
VERSION = 1
HEADER = struct.Struct("<4s4sBBHIQQ")   # magic, underlying magic, version, reserved, header size, metadata size, sizes
HEADER_SIZE = HEADER.size               # 0x20
SEEK_FOOTER_MAGIC = 0x8F92EAB1          # the last 9 bytes of the zstd seekable stream: frame count, flags, magic
SKIPPABLE_MAGIC = 0x184D2A5E            # a skippable frame holds the seek table
FOOTER_SIZE = 9
CHECKSUM_FLAG = 0x80                    # seek table flag: each entry carries a 4-byte checksum
CACHE_FRAMES = 2                        # decompressed frames kept (Azahar writes 32 MiB frames for a CIA)


def is_z3ds(head: bytes) -> bool:
    """True when ``head`` starts with the Z3DS magic (content, never the file name)."""
    return head[:4] == MAGIC


def _backend() -> Callable[[bytes], bytes]:
    """The one-frame decompressor of the first zstd package that imports; ImageError when none does."""
    try:
        from compression import zstd as _stdlib_zstd   # Python 3.14+
    except ImportError:
        _stdlib_zstd = None
    if _stdlib_zstd is not None:
        return _stdlib_zstd.decompress
    try:
        import zstandard
    except ImportError:
        zstandard = None
    if zstandard is not None:
        return lambda frame: zstandard.ZstdDecompressor().decompressobj().decompress(frame)
    try:
        import pyzstd
    except ImportError:
        raise ImageError(tr("This compressed 3DS image needs the zstandard package (zstd support).")) from None
    return pyzstd.decompress


def _read_exact(stream: Any, offset: int, size: int) -> bytes:
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise ImageError(tr("the compressed 3DS image is damaged: it ends early"))
    return data


class Z3dsStream:
    """A read-only seekable view of the decompressed image of a Z3DS file (``seek``, ``tell``, ``read``, ``size``)."""

    def __init__(self, stream: Any) -> None:
        self._file = stream
        stream.seek(0, 2)
        file_size = stream.tell()
        magic, underlying, version, _reserved, header_size, metadata_size, _compressed, uncompressed = HEADER.unpack(
            _read_exact(stream, 0, HEADER_SIZE))
        if magic != MAGIC or version != VERSION or header_size != HEADER_SIZE:
            raise ImageError(tr("the compressed 3DS image has a header this version does not read"))
        self.underlying_magic = underlying
        self.size = uncompressed
        self._base = header_size + metadata_size
        self._frames = self._seek_table(file_size)   # (compressed offset, compressed size, decompressed size)
        if sum(frame[2] for frame in self._frames) != uncompressed:
            raise ImageError(tr("the compressed 3DS image is damaged: its seek table does not match its size"))
        starts, total = [], 0
        for frame in self._frames:
            starts.append(total)
            total += frame[2]
        self._starts: List[int] = starts
        self._pos = 0
        self._cache: "OrderedDict[int, bytes]" = OrderedDict()

    def _seek_table(self, file_size: int) -> List[Tuple[int, int, int]]:
        footer = _read_exact(self._file, file_size - FOOTER_SIZE, FOOTER_SIZE)
        count, flags, magic = struct.unpack("<IBI", footer)
        if magic != SEEK_FOOTER_MAGIC:
            raise ImageError(tr("the compressed 3DS image is damaged: no seek table"))
        width = 8 + (4 if flags & CHECKSUM_FLAG else 0)
        table_size = count * width
        table_at = file_size - FOOTER_SIZE - table_size - 8
        head = _read_exact(self._file, table_at, 8)
        skip_magic, frame_size = struct.unpack("<II", head)
        if skip_magic != SKIPPABLE_MAGIC or frame_size != table_size + FOOTER_SIZE or table_at < self._base:
            raise ImageError(tr("the compressed 3DS image is damaged: no seek table"))
        raw = _read_exact(self._file, table_at + 8, table_size)
        frames, offset = [], self._base
        for index in range(count):
            compressed, decompressed = struct.unpack_from("<II", raw, index * width)
            frames.append((offset, compressed, decompressed))
            offset += compressed
        if offset != table_at:
            raise ImageError(tr("the compressed 3DS image is damaged: its frames do not fill the file"))
        return frames

    def seek(self, offset: int, whence: int = 0) -> int:
        start = (0, self._pos, self.size)[whence]
        if start + offset < 0:
            raise ImageError(tr("seek before the start of a compressed 3DS image"))
        self._pos = start + offset
        return self._pos

    def tell(self) -> int:
        return self._pos

    def read(self, size: int = -1) -> bytes:
        out = bytearray()
        want = self.size - self._pos if size is None or size < 0 else min(size, self.size - self._pos)
        while want > 0:
            index = bisect.bisect_right(self._starts, self._pos) - 1
            frame = self._frame(index)
            inside = self._pos - self._starts[index]
            piece = frame[inside:inside + want]
            out += piece
            self._pos += len(piece)
            want -= len(piece)
        return bytes(out)

    def _frame(self, index: int) -> bytes:
        if index in self._cache:
            self._cache.move_to_end(index)
            return self._cache[index]
        offset, compressed, decompressed = self._frames[index]
        data = _backend()(_read_exact(self._file, offset, compressed))
        if len(data) != decompressed:
            raise ImageError(tr("the compressed 3DS image is damaged: a frame has the wrong size"))
        self._cache[index] = data
        if len(self._cache) > CACHE_FRAMES:
            self._cache.popitem(last=False)
        return data


def decompressed_size(stream: Any) -> Optional[int]:
    """The size of the decompressed image of a Z3DS file, or None when ``stream`` is not one."""
    stream.seek(0)
    if not is_z3ds(stream.read(4)):
        return None
    stream.seek(0)
    return Z3dsStream(stream).size
