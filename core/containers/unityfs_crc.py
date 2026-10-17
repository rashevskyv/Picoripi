"""Unity AssetBundle (UnityFS) CRC for Addressables catalogs, and a same-length patch of a catalog's CRC values.

The CRC that Addressables stores per bundle (``m_Crc`` in the catalog extra data) is the zlib CRC32 of the
uncompressed data blocks, concatenated. The header and the block info are not part of it (proven on all 204
records of the Metal Gear Solid 3 Master Collection launcher catalog).

The catalog extra data holds UTF-16LE JSON records. ``patch_catalog_crc`` changes only the digits of ``m_Crc``
values, padded with spaces to the old width, so every offset in the extra data stays where it was.
"""
from __future__ import annotations

from core.i18n import tr
import base64
import json
import zlib

from core.containers.retro_pak import lz4_block

_CRC_KEY = '"m_Crc":'


def _be(data: bytes, at: int, size: int) -> int:
    return int.from_bytes(data[at:at + size], "big")


def _align16(value: int) -> int:
    return (value + 15) & ~15


def _blocks(data: bytes) -> list[bytes]:
    """The uncompressed data blocks of a UnityFS bundle whose block info is at the start (LZ4 or stored)."""
    if not data.startswith(b"UnityFS\x00"):
        raise ValueError(tr("not a UnityFS bundle"))
    q = data.index(b"\x00") + 1          # signature
    q += 4                              # format version
    q = data.index(b"\x00", q) + 1       # unity version
    q = data.index(b"\x00", q) + 1       # unity revision
    q += 8                              # file size
    header_end = q + 12                 # block info sizes and flags
    compressed, uncompressed, flags = _be(data, q, 4), _be(data, q + 4, 4), _be(data, q + 8, 4)
    if flags & 0x80:
        raise ValueError(tr("block info at the end of the bundle is not supported"))
    info_at = _align16(header_end) if flags & 0x200 else header_end
    info = _unpack(data[info_at:info_at + compressed], flags & 0x3F, uncompressed)
    count = _be(info, 16, 4)
    pos = _align16(info_at + compressed) if flags & 0x200 else info_at + compressed
    out = []
    for i in range(count):
        at = 20 + 10 * i
        usize, csize, bflags = _be(info, at, 4), _be(info, at + 4, 4), _be(info, at + 8, 2)
        out.append(_unpack(data[pos:pos + csize], bflags & 0x3F, usize))
        pos += csize
    return out


def _unpack(raw: bytes, compression: int, size: int) -> bytes:
    if compression == 0:
        return raw
    if compression in (2, 3):
        return lz4_block(raw, size)
    raise ValueError(tr("compression {0} is not supported", compression))


def bundle_crc(data: bytes) -> int:
    """zlib CRC32 of the uncompressed data blocks: the value Addressables keeps in the catalog."""
    return zlib.crc32(b"".join(_blocks(data))) & 0xFFFFFFFF


def patch_catalog_crc(catalog: bytes, edits: dict[int, int]) -> bytes:
    """Replace the m_Crc values in a catalog.json ({old CRC: new CRC}) without changing any offset.

    Each old value must occur exactly once in the extra data. A new value must not have more digits than the old one;
    it is padded with spaces (JSON allows whitespace after a number). The base64 text is swapped in the original
    file bytes, so the rest of the catalog is untouched.
    """
    doc = json.loads(catalog.decode("utf-8"))
    extra = bytearray(base64.b64decode(doc["m_ExtraDataString"]))
    key_units = len(_CRC_KEY) * 2
    for old, new in edits.items():
        width = len(str(old))
        if len(str(new)) > width:
            raise ValueError(tr("CRC {0} has more digits than {1}", new, old))
        needle = (_CRC_KEY + f"{old},").encode("utf-16-le")
        if extra.count(needle) != 1:
            raise ValueError(tr("m_Crc {0} occurs {1} times, expected once", old, extra.count(needle)))
        at = extra.find(needle) + key_units
        extra[at:at + width * 2] = str(new).ljust(width).encode("utf-16-le")
    old_text = doc["m_ExtraDataString"]
    new_text = base64.b64encode(bytes(extra)).decode("ascii")
    if len(new_text) != len(old_text):
        raise ValueError(tr("extra data length changed"))
    return catalog.replace(old_text.encode("ascii"), new_text.encode("ascii"), 1)
