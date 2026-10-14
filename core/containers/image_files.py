"""Shared parts of the game image readers (GameCube discs, Nintendo DS cartridges): a file entry and a copy.

A reader lists its files as ``ImageFile`` entries (path inside the image, absolute offset, size). Copies run in
chunks and check for a cancel between chunks, so a multi-gigabyte image never sits in memory.
"""
from __future__ import annotations

from typing import Any, BinaryIO, Callable, List, NamedTuple, Optional

CHUNK = 1 << 20
MAX_TABLE = 64 << 20  # a file system or name table above this size is refused: no real image has one
RESERVED_NAMES = frozenset({"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)),
                            *(f"LPT{n}" for n in range(1, 10))})


class ImageError(ValueError):
    """The file is not an image this reader supports, or its tables do not fit the file."""


class ImageFile(NamedTuple):
    """One file of an image. ``size`` is the size stored in the image. ``decode``, when set, turns the stored bytes
    into the file's bytes (for example a compressed ExeFS code section); it is then called once on the whole entry.
    ``stream``, when set, is a seekable view of decrypted bytes (``console_crypto.PlainView``); ``offset`` then
    addresses that view. Without it, ``offset`` addresses the image's own stream."""
    path: str
    offset: int
    size: int
    decode: Optional[Callable[[bytes], bytes]] = None
    stream: Optional[Any] = None


def check_name(name: str) -> str:
    """A name from an image's file table, or ImageError when it could not be a plain file name on Windows.

    Refused: empty, ``.`` and ``..``, a path separator or drive colon, a control character, a trailing dot or space
    (Windows drops them), and a device name such as ``CON`` or ``nul.txt``.
    """
    stem = name.split(".", 1)[0].upper()
    if (not name or name in (".", "..") or name.endswith((" ", ".")) or stem in RESERVED_NAMES
            or any(char in name for char in '/\\:*?"<>|') or any(ord(char) < 32 for char in name)):
        raise ImageError(f"unsafe file name in the image: {name!r}")
    return name


class ImageReader:
    """Base of the readers: the open stream, the file size, reads of one entry."""

    def __init__(self, stream: BinaryIO) -> None:
        self.stream = stream
        stream.seek(0, 2)
        self.size = stream.tell()

    def read_at(self, offset: int, size: int) -> bytes:
        """``size`` bytes at ``offset``; ImageError when the image ends before that."""
        if offset < 0 or size < 0 or offset + size > self.size:
            raise ImageError(f"the image ends before offset {offset:#x} + {size:#x}")
        self.stream.seek(offset)
        return self.stream.read(size)

    def read_table(self, offset: int, size: int) -> bytes:
        """A file or name table, read whole: ``read_at`` for at most ``MAX_TABLE`` bytes."""
        if size > MAX_TABLE:
            raise ImageError(f"a table of {size:#x} bytes is too large")
        return self.read_at(offset, size)

    def read(self, entry: ImageFile) -> bytes:
        if entry.stream is None:
            return self.read_at(entry.offset, entry.size)
        entry.stream.seek(entry.offset)
        data = entry.stream.read(entry.size)
        if len(data) != entry.size:
            raise ImageError(f"the image ends inside {entry.path}")
        return data

    def source(self, entry: ImageFile) -> BinaryIO:
        """The stream that holds ``entry``: its view when it has one, else the image's own stream."""
        return entry.stream if entry.stream is not None else self.stream

    def entries(self) -> List[ImageFile]:
        raise NotImplementedError


def copy_range(stream: BinaryIO, offset: int, size: int, out: BinaryIO,
               is_cancelled: Callable[[], bool], on_bytes: Callable[[int], None]) -> bool:
    """Copy ``size`` bytes at ``offset`` of ``stream`` into ``out``. False when cancelled first."""
    stream.seek(offset)
    left = size
    while left > 0:
        if is_cancelled():
            return False
        data = stream.read(min(CHUNK, left))
        if not data:
            raise ImageError("the image ends inside a file")
        out.write(data)
        left -= len(data)
        on_bytes(len(data))
    return True
