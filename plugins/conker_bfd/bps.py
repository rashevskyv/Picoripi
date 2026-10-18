"""BPS patch writer and reader (byuu's format): source reads and target literals, with CRC32 checks.

A BPS patch keeps offsets as variable-length numbers, so it can carry the banks above 16 MiB where an IPS patch
cannot. This writer uses only two actions: SourceRead (bytes equal at the same offset) and TargetRead (new bytes).
"""
from __future__ import annotations

import struct
import zlib

from .n64_archive import RomError

_SOURCE_READ = 0
_TARGET_READ = 1
_MIN_SOURCE_RUN = 4  # shorter equal runs are cheaper inside a literal


def _encode_number(value: int) -> bytes:
    out = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        if value == 0:
            out.append(0x80 | low)
            return bytes(out)
        out.append(low)
        value -= 1


def _decode_number(data: bytes, pos: int):
    value = 0
    shift = 1
    while True:
        if pos >= len(data):
            raise RomError("BPS number runs past the end of the patch")
        byte = data[pos]
        pos += 1
        value += (byte & 0x7F) * shift
        if byte & 0x80:
            return value, pos
        shift <<= 7
        value += shift


def _command(kind: int, length: int) -> bytes:
    return _encode_number(((length - 1) << 2) | kind)


def make_bps(source: bytes, target: bytes) -> bytes:
    """A BPS patch that turns ``source`` into ``target``."""
    body = bytearray(b"BPS1")
    body += _encode_number(len(source)) + _encode_number(len(target)) + _encode_number(0)
    pos = 0
    literal_start = None
    while pos < len(target):
        same = pos < len(source) and source[pos] == target[pos]
        if same:
            run = 0
            while (pos + run < len(target) and pos + run < len(source)
                   and source[pos + run] == target[pos + run]):
                run += 1
            if run >= _MIN_SOURCE_RUN:
                if literal_start is not None:
                    body += _literal(target, literal_start, pos)
                    literal_start = None
                body += _command(_SOURCE_READ, run)
                pos += run
                continue
        if literal_start is None:
            literal_start = pos
        pos += 1
    if literal_start is not None:
        body += _literal(target, literal_start, len(target))
    body += struct.pack("<I", zlib.crc32(source) & 0xFFFFFFFF)
    body += struct.pack("<I", zlib.crc32(target) & 0xFFFFFFFF)
    body += struct.pack("<I", zlib.crc32(bytes(body)) & 0xFFFFFFFF)
    return bytes(body)


def _literal(target: bytes, start: int, end: int) -> bytes:
    return _command(_TARGET_READ, end - start) + bytes(target[start:end])


def apply_bps(source: bytes, patch: bytes) -> bytes:
    """Apply a BPS patch made by ``make_bps`` (SourceRead and TargetRead only). Checks every CRC."""
    if len(patch) < 16 or patch[:4] != b"BPS1":
        raise RomError("not a BPS patch")
    if struct.unpack_from("<I", patch, len(patch) - 12)[0] != zlib.crc32(source) & 0xFFFFFFFF:
        raise RomError("BPS patch is for another source file")
    if struct.unpack_from("<I", patch, len(patch) - 4)[0] != zlib.crc32(patch[:-4]) & 0xFFFFFFFF:
        raise RomError("BPS patch is damaged")
    pos = 4
    source_size, pos = _decode_number(patch, pos)
    target_size, pos = _decode_number(patch, pos)
    metadata, pos = _decode_number(patch, pos)
    pos += metadata
    if source_size != len(source):
        raise RomError("BPS source size differs")
    end = len(patch) - 12
    out = bytearray()
    while pos < end:
        word, pos = _decode_number(patch, pos)
        kind, length = word & 3, (word >> 2) + 1
        if kind == _SOURCE_READ:
            out += source[len(out):len(out) + length]
        elif kind == _TARGET_READ:
            out += patch[pos:pos + length]
            pos += length
        else:
            raise RomError("BPS copy actions are not used by this writer")
    if len(out) != target_size:
        raise RomError("BPS target size differs")
    if struct.unpack_from("<I", patch, len(patch) - 8)[0] != zlib.crc32(out) & 0xFFFFFFFF:
        raise RomError("BPS target CRC differs")
    return bytes(out)
