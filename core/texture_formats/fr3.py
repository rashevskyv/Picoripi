"""Jak and Daxter level textures (``.fr3``, the OpenGOAL port): the texture records of a tfrag3 level file.

File: a u64 size of the payload, then one zstd frame of the payload (the port writes it with
``compress_zstd``). Payload: u16 version, a string level name (u64 length, bytes), a u64 texture count and
the textures, each (``Texture::serialize`` in common/custom_data/Tfrag3Data.cpp): u16 w, u16 h, u32 combo id,
a u32 vector (RGBA words 0xAABBGGRR), two strings (debug name, tpage name), a bool, a u8 format (0 RGBA,
1 BC1, 3 BC3), a byte vector of compressed mips and a u32 vector of mip offsets. Everything after the
textures is kept as it was.

Version 43 (upstream OpenGOAL v0.3.8, the PC build) stores every texture as RGBA8 words with no BC blocks; it
is read and written in place the same way (``_parse_v43``).

``read`` returns one texture per record (RGBA8, BC1 or BC3 base mip decoded). ``write`` re-encodes only the
images that differ from what ``read`` gives, with the same size and mip layout, and recompresses the frame.
Writing the images ``read`` returned gives the original bytes back (the file is returned unchanged).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from PIL import Image

from core import zstd_frame
from core.texture_formats import Texture, pixels

FORMATS = {0: "RGBA8", 1: "BC1", 3: "BC3"}
_BC_NAME = {"BC1": "BC1", "BC3": "BC3"}


@dataclass
class _Record:
    """One texture record: its fields and where its pixel and mip bytes lie in the payload."""

    name: str
    tpage: str
    width: int
    height: int
    combo_id: int
    format: int
    data_start: int
    data_count: int
    bcn_start: int
    bcn_count: int
    mip_start: int
    mip_count: int
    mip_offsets: List[int] = field(default_factory=list)


def _parse(payload: bytes) -> Tuple[List[_Record], int]:
    """The records of a payload and the offset where the texture list ends."""
    (version,) = struct.unpack_from("<H", payload, 0)
    if version == 43:
        return _parse_v43(payload)
    pos = 2  # u16 version
    (name_len,) = struct.unpack_from("<Q", payload, pos)
    pos += 8 + name_len
    (count,) = struct.unpack_from("<Q", payload, pos)
    pos += 8
    records = []
    for _ in range(count):
        width, height = struct.unpack_from("<HH", payload, pos)
        (combo_id,) = struct.unpack_from("<I", payload, pos + 4)
        pos += 8
        (n_data,) = struct.unpack_from("<Q", payload, pos)
        pos += 8
        data_start, data_count = pos, n_data
        pos += 4 * n_data
        strings = []
        for _s in range(2):
            (n,) = struct.unpack_from("<Q", payload, pos)
            strings.append(payload[pos + 8:pos + 8 + n].decode("latin-1"))
            pos += 8 + n
        pos += 1  # bool load_to_pool
        fmt = payload[pos]
        pos += 1
        (n_bcn,) = struct.unpack_from("<Q", payload, pos)
        pos += 8
        bcn_start, bcn_count = pos, n_bcn
        pos += n_bcn
        (n_mips,) = struct.unpack_from("<Q", payload, pos)
        pos += 8
        mip_start = pos
        mip_offsets = list(struct.unpack_from(f"<{n_mips}I", payload, pos)) if n_mips else []
        pos += 4 * n_mips
        records.append(_Record(strings[0], strings[1], width, height, combo_id, fmt, data_start, data_count,
                               bcn_start, bcn_count, mip_start, n_mips, mip_offsets))
    return records, pos


def _parse_v43(payload: bytes) -> Tuple[List[_Record], int]:
    """Version 43 (upstream OpenGOAL v0.3.8): every texture is RGBA8 words, with no BC blocks or mips.

    A record is: u16 width, u16 height, u32 combo id, u64 word count, the RGBA words (0xAABBGGRR, the
    texture's own pixels), two strings (debug name, tpage name), and a bool (load to pool).
    """
    pos = 2  # u16 version
    (name_len,) = struct.unpack_from("<Q", payload, pos)
    pos += 8 + name_len
    (count,) = struct.unpack_from("<Q", payload, pos)
    pos += 8
    records = []
    for _ in range(count):
        width, height = struct.unpack_from("<HH", payload, pos)
        (combo_id,) = struct.unpack_from("<I", payload, pos + 4)
        pos += 8
        (n_data,) = struct.unpack_from("<Q", payload, pos)
        pos += 8
        data_start, data_count = pos, n_data
        pos += 4 * n_data
        strings = []
        for _s in range(2):
            (n,) = struct.unpack_from("<Q", payload, pos)
            strings.append(payload[pos + 8:pos + 8 + n].decode("latin-1"))
            pos += 8 + n
        pos += 1  # bool load_to_pool
        records.append(_Record(strings[0], strings[1], width, height, combo_id, 0, data_start, data_count,
                               0, 0, 0, 1, []))
    return records, pos


def _payload(data: bytes) -> bytes:
    (size,) = struct.unpack_from("<Q", data, 0)
    payload = zstd_frame.decompress(data[8:], "fr3")
    if len(payload) != size:
        raise ValueError(f"fr3: payload size {len(payload)} does not match the header {size}")
    return payload


def _mip_range(record: _Record, level: int) -> Tuple[int, int]:
    start = record.mip_offsets[level]
    end = record.mip_offsets[level + 1] if level + 1 < len(record.mip_offsets) else record.bcn_count
    return start, end


def _base_image(payload: bytes, record: _Record) -> Image.Image:
    if record.format == 0:
        raw = payload[record.data_start:record.data_start + 4 * record.data_count]
        return Image.frombytes("RGBA", (record.width, record.height), raw)
    codec = pixels.codec(_BC_NAME[FORMATS[record.format]])
    start = record.bcn_start
    end = start + (record.mip_offsets[1] if len(record.mip_offsets) > 1 else record.bcn_count)
    # Blocks cover whole 4x4 cells: decode the padded size and crop (small mips are 1-3 pixels wide).
    w4, h4 = (record.width + 3) // 4 * 4, (record.height + 3) // 4 * 4
    image = codec.decode(payload[start:end], w4, h4)
    return image.crop((0, 0, record.width, record.height))


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    payload = _payload(data)
    records, _end = _parse(payload)
    textures = []
    for record in records:
        if record.format not in FORMATS:
            raise ValueError(f"fr3: texture format {record.format} is not supported")
        textures.append(Texture(record.name, _base_image(payload, record), FORMATS[record.format],
                                max(1, record.mip_count)))
    return textures


def _encode_rgba(image: Image.Image) -> bytes:
    return image.convert("RGBA").tobytes()


def _encode_bc(record: _Record, image: Image.Image) -> bytes:
    """A new mip chain for the image, in the record's block format and with its mip count."""
    codec = pixels.codec(_BC_NAME[FORMATS[record.format]])
    out = []
    level_image = image.convert("RGBA")
    for level in range(max(1, record.mip_count)):
        w = max(1, record.width >> level)
        h = max(1, record.height >> level)
        mip = level_image.resize((w, h), Image.LANCZOS) if level else level_image
        padded = Image.new("RGBA", ((w + 3) // 4 * 4, (h + 3) // 4 * 4), (0, 0, 0, 0))
        padded.paste(mip, (0, 0))
        out.append(codec.encode(padded))
    blob = b"".join(out)
    return blob


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    payload = _payload(data)
    records, _end = _parse(payload)
    patched = bytearray(payload)
    changed = False
    for index, image in images.items():
        record = records[index]
        if image.size != (record.width, record.height):
            raise ValueError(f"fr3: texture {record.name} is {record.width}x{record.height}, not {image.size}")
        if record.format == 0:
            new = _encode_rgba(image)
            old = bytes(patched[record.data_start:record.data_start + 4 * record.data_count])
            if new != old:
                patched[record.data_start:record.data_start + len(new)] = new
                changed = True
        else:
            if _base_image(payload, record).convert("RGBA").tobytes() == image.convert("RGBA").tobytes():
                continue
            new = _encode_bc(record, image)
            old = bytes(patched[record.bcn_start:record.bcn_start + record.bcn_count])
            if len(new) != record.bcn_count:
                raise ValueError(f"fr3: texture {record.name} mip chain changed size")
            if new != old:
                patched[record.bcn_start:record.bcn_start + record.bcn_count] = new
                changed = True
    if not changed:
        return data
    frame = zstd_frame.compress(bytes(patched), "fr3", level=1)
    return struct.pack("<Q", len(patched)) + frame
