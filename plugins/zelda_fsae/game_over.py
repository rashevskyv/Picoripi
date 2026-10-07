"""GAME OVER of the European English game: the word, its letter sprites and their places, in the ARM9 program.

The game draws GAME OVER from big letter sprites (``zeldat_eu_en.bin`` #10, 4 bpp, tiles one after another),
not from the font. The ARM9 (``main.arm9`` in the workspace) holds, at fixed offsets:

- ``WORDS``: the word of each language slot, UTF-16, 0x20 bytes (at most 15 letters); slot 2 is English (EU);
- ``LETTERS``: the English letter table, 16 entries of ``u32 character, u32 first tile in #10, u32 sprite
  shape`` (OBJ attribute 0 in the low half, attribute 1 in the high half: shape and size give 32x32, 16x32,
  8x32...); the game uses G A M E O V R, 9 entries are free (character 0);
- ``PLACES``: the x position of each letter of the word, 16 u32 per language slot.

Editor form (one block, three texts): the word; one line per letter ``<character> <first tile> <W>x<H>``; the
x positions separated by spaces. #10 has 128 tiles: a 32x32 letter takes 16 tiles, a 16x32 one 8, an 8x32 one
4; the eighth 32x32 cell (tiles 112-127) is empty. The sheet cannot grow: the next graphics follow it in VRAM.
Saving checks that every letter of the word is in the table and fits in #10, and writes the bytes in place.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

WORDS, SLOT, WORD_SIZE = 0xD9D8C, 2, 0x20
LETTERS, LETTER_COUNT = 0xD9ECC, 16
PLACES, PLACE_STRIDE = 0xDA1DC, 0x40
SHEET_TILES = 128
SIZES: Dict[Tuple[int, int], Tuple[int, int]] = {
    (0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
    (1, 0): (16, 8), (1, 1): (32, 8), (1, 2): (32, 16), (1, 3): (64, 32),
    (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64)}
NAMES = ("GAME OVER: word (English EU)", "GAME OVER: letters (character, first tile in zeldat_eu_en #10, size)",
         "GAME OVER: x of each letter")


class FormatError(ValueError):
    """Not the ARM9 this module knows, or an editor text it cannot write."""


def looks_like(data: bytes) -> bool:
    return (len(data) > PLACES + PLACE_STRIDE * 10
            and data[WORDS:WORDS + 16] == "GAMEOVER".encode("utf-16-le")
            and struct.unpack_from("<I", data, LETTERS)[0] == ord("G"))


def read(data: bytes) -> List[str]:
    if not looks_like(data):
        raise FormatError("Not the Four Swords Anniversary Edition ARM9")
    at = WORDS + WORD_SIZE * SLOT
    word = data[at:at + WORD_SIZE].decode("utf-16-le").split("\0")[0]
    lines = []
    for index in range(LETTER_COUNT):
        char, tile, attrs = struct.unpack_from("<3I", data, LETTERS + 12 * index)
        if not char:
            continue
        width, height = SIZES.get((attrs >> 14 & 3, attrs >> 30 & 3), (0, 0))
        lines.append(f"{chr(char)} {tile} {width}x{height}")
    places = struct.unpack_from("<16I", data, PLACES + PLACE_STRIDE * SLOT)
    return [word, "\n".join(lines), " ".join(str(x) for x in places[:len(word)])]


def write(data: bytes, texts: List[str]) -> bytes:
    """``data`` with the word, letter table and positions of ``texts``; unchanged texts give the same bytes."""
    if [str(t) for t in texts] == read(data):
        return bytes(data)
    word, letters, places = (str(t).strip() for t in texts)
    if not word or len(word) > WORD_SIZE // 2 - 1:
        raise FormatError(f"The GAME OVER word takes 1-{WORD_SIZE // 2 - 1} letters, not {len(word)}")
    table = []
    for line in letters.splitlines():
        parts = line.split()
        if not parts:
            continue
        if len(parts) != 3 or len(parts[0]) != 1 or "x" not in parts[2]:
            raise FormatError(f"GAME OVER letter line '{line}': write <character> <first tile> <width>x<height>")
        size = tuple(int(v) for v in parts[2].split("x"))
        shape = next((key for key, value in SIZES.items() if value == size), None)
        if shape is None:
            raise FormatError(f"GAME OVER letter '{parts[0]}': sprites are 8, 16, 32 or 64 pixels, not {parts[2]}")
        tile = int(parts[1])
        if tile < 0 or tile + size[0] * size[1] // 64 > SHEET_TILES:
            raise FormatError(f"GAME OVER letter '{parts[0]}' does not fit in the {SHEET_TILES} tiles of the letters")
        table.append((ord(parts[0]), tile, shape[0] << 14 | shape[1] << 30))
    if len(table) > LETTER_COUNT:
        raise FormatError(f"GAME OVER has room for {LETTER_COUNT} letters, not {len(table)}")
    missing = sorted({c for c in word if ord(c) not in {entry[0] for entry in table}})
    if missing:
        raise FormatError(f"GAME OVER letters without a sprite line: {' '.join(missing)}")
    xs = [int(v) for v in places.split()]
    if len(xs) != len(word) or any(not 0 <= x < 256 for x in xs):
        raise FormatError(f"GAME OVER needs one x (0-255) for each of the {len(word)} letters, not {len(xs)}")
    out = bytearray(data)
    at = WORDS + WORD_SIZE * SLOT
    out[at:at + WORD_SIZE] = word.encode("utf-16-le").ljust(WORD_SIZE, b"\0")
    out[LETTERS:LETTERS + 12 * LETTER_COUNT] = b"".join(struct.pack("<3I", *e) for e in table).ljust(12 * LETTER_COUNT, b"\0")
    out[PLACES + PLACE_STRIDE * SLOT:PLACES + PLACE_STRIDE * (SLOT + 1)] = struct.pack("<16I", *(xs + [0] * (16 - len(xs))))
    return bytes(out)
