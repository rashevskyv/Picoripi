"""Read the character map of a MonoGame SpriteFont (``.xnb``) used by Link's Awakening DX HD.

Only what the glyph check needs is read: the characters the font has a glyph for, and whether it has a
default character (``DefaultCharacter``). The game's fonts are stored uncompressed (header flag 0x00), which
is the only case handled here. Compressed files raise ``ValueError``.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SpriteFont:
    characters: List[str]
    glyph_count: int
    line_spacing: int
    default_character: Optional[str]
    exact: bool   # the parser consumed exactly the whole file


class _Reader:
    def __init__(self, data: bytes, pos: int):
        self.data = data
        self.pos = pos

    def u8(self) -> int:
        value = self.data[self.pos]
        self.pos += 1
        return value

    def i32(self) -> int:
        value = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return value

    def f32(self) -> float:
        value = struct.unpack_from("<f", self.data, self.pos)[0]
        self.pos += 4
        return value

    def skip(self, count: int) -> None:
        self.pos += count

    def v7(self) -> int:
        """7-bit encoded integer (BinaryReader.Read7BitEncodedInt)."""
        result = 0
        shift = 0
        while True:
            byte = self.u8()
            result |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return result
            shift += 7

    def string(self) -> str:
        length = self.v7()
        raw = self.data[self.pos:self.pos + length]
        self.pos += length
        return raw.decode("utf-8")

    def char(self) -> str:
        """One character as BinaryReader.ReadChar reads it: UTF-8, 1 to 3 bytes (BMP)."""
        lead = self.u8()
        if lead < 0x80:
            return chr(lead)
        if lead & 0xE0 == 0xC0:
            return chr(((lead & 0x1F) << 6) | (self.u8() & 0x3F))
        if lead & 0xF0 == 0xE0:
            second = self.u8()
            third = self.u8()
            return chr(((lead & 0x0F) << 12) | ((second & 0x3F) << 6) | (third & 0x3F))
        raise ValueError(f"unsupported UTF-8 lead byte {lead:#x} in a font character map")


def parse_sprite_font(data: bytes) -> SpriteFont:
    """Parse an uncompressed MonoGame SpriteFont XNB file."""
    if data[:3] != b"XNB":
        raise ValueError("not an XNB file")
    flags = data[5]
    if flags & 0x80:
        raise ValueError("compressed XNB (LZX) is not read here")
    reader = _Reader(data, 10)
    type_count = reader.v7()
    type_names = []
    for _ in range(type_count):
        type_names.append(reader.string())
        reader.i32()  # reader version
    reader.v7()  # shared resource count
    top = reader.v7()
    if "SpriteFontReader" not in type_names[top - 1]:
        raise ValueError("the XNB file is not a SpriteFont")

    texture = reader.v7()
    if "Texture2DReader" not in type_names[texture - 1]:
        raise ValueError("the SpriteFont does not start with its texture")
    reader.i32()  # surface format
    reader.i32()  # width
    reader.i32()  # height
    mip_count = reader.i32()
    for _ in range(mip_count):
        size = reader.i32()
        reader.skip(size)

    glyph_count = 0
    for index in range(2):  # glyphs, cropping: lists of Rectangle (4 x int32 each, no per-item type id)
        list_type = reader.v7()
        if "ListReader" not in type_names[list_type - 1]:
            raise ValueError("unexpected glyph list layout")
        count = reader.i32()
        if index == 0:
            glyph_count = count
        reader.skip(16 * count)

    list_type = reader.v7()
    if "ListReader" not in type_names[list_type - 1]:
        raise ValueError("unexpected character list layout")
    char_count = reader.i32()
    characters = [reader.char() for _ in range(char_count)]
    line_spacing = reader.i32()
    reader.f32()  # spacing
    reader.v7()  # kerning list type
    kerning_count = reader.i32()
    reader.skip(12 * kerning_count)
    has_default = reader.u8()
    default_character = reader.char() if has_default else None
    return SpriteFont(
        characters=characters,
        glyph_count=glyph_count,
        line_spacing=line_spacing,
        default_character=default_character,
        exact=reader.pos == len(data),
    )
