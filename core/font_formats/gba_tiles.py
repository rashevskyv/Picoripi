"""GBA 8x8 4bpp tile font inside an LZ77-packed multiboot program (The Wind Waker's Tingle Tuner client).

The file is a GBA multiboot image whose loader unpacks one LZ77 stream at ``program_offset`` to
``program_address`` (and first copies the data after the stream, the "tail", somewhere else; the
loader's two literals at ``tail_pointers`` hold the tail's start and end addresses). Inside the
unpacked program, the LZ77 (Vram-safe) block at ``tiles_address`` holds the background tiles; glyph
``i`` is the 32-byte tile at ``glyph_offset + 32 * i`` of that block (rows of 4 bytes, low nibble
first). Every glyph advances ``advance`` px (the game's constant; widths are not edited).

Pixels: nibble 1 is the text background and 15 the ink; the sheet shows 1 as transparent, 15 as
white and any other nibble ``n`` as grey ``17 * n`` (0 as 17), so an unedited font packs back to the
same bytes. The tile of a character (chars, slots) is saved with those two values only.

Params: ``program_offset``, ``program_address``, ``tail_pointers``, ``tiles_address``, ``tiles_room``
(bytes the packed tile block may take), ``glyph_offset``, ``glyph_count``, ``advance``, ``chars``
(``{"0x01": "A", ...}``: glyph code -> character), optional ``slots``: ``codes`` (``{"0x8E": "0x78"}``,
an accent code drawn from a free tile) and ``tables`` (``[first, last, table address, accent tile]``
per accent-code range). Saving an edited font points the slot codes' table entries at their tiles
with no accent offset and blanks the accent tiles of those ranges.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, Tuple

from PIL import Image

from core.containers import lz10
from core.font_formats import Metadata, Sheets, char_code, coverage, map_entries

TILE = 8
TILE_BYTES = 32
BACKGROUND, INK = 1, 15
_COLUMNS = 16


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _unpack(data: bytes, params: Dict[str, Any]) -> Tuple[bytes, int, bytes, int]:
    """``(program, end of its stream in the file, tile block, end of the block's stream in the program)``."""
    program, end = lz10.decompress(data, _int(params["program_offset"]))
    at = _int(params["tiles_address"]) - _int(params["program_address"])
    tiles, tiles_end = lz10.decompress(program, at)
    return program, end, tiles, tiles_end


def _grey(nibble: int) -> int:
    return 0 if nibble == BACKGROUND else 17 if nibble == 0 else nibble * 17


def _nibble(grey: int, two_tone: bool) -> int:
    if two_tone:
        return INK if grey >= 128 else BACKGROUND
    level = min(15, (grey + 8) // 17)
    return BACKGROUND if level == 0 else 0 if level == 1 else level


def _glyph_tiles(params: Dict[str, Any]) -> Dict[int, int]:
    """Glyph code -> tile: itself, or the free tile of a slot code."""
    slots = {_int(code): _int(tile) for code, tile in ((params.get("slots") or {}).get("codes") or {}).items()}
    return {code: slots.get(code, code) for code in (_int(c) for c in (params.get("chars") or {}))}


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    _program, _end, tiles, _tiles_end = _unpack(data, params)
    count, base = _int(params.get("glyph_count", 256)), _int(params.get("glyph_offset", 0))
    rows = -(-count // _COLUMNS)
    stride = _COLUMNS * TILE
    ink = bytearray(stride * rows * TILE)
    for glyph in range(count):
        tile = tiles[base + glyph * TILE_BYTES:base + (glyph + 1) * TILE_BYTES]
        x0, y0 = (glyph % _COLUMNS) * TILE, (glyph // _COLUMNS) * TILE
        for y in range(TILE):
            for x in range(TILE):
                byte = tile[y * 4 + x // 2]
                ink[(y0 + y) * stride + x0 + x] = _grey(byte >> 4 if x & 1 else byte & 0xF)
    grey = Image.frombytes("L", (stride, rows * TILE), bytes(ink))
    sheet = Image.merge("RGBA", (grey, grey, grey, grey))

    chars = params.get("chars") or {}
    pairs = [(char_code(chars[key]), tile) for key, tile in
             ((key, _glyph_tiles(params)[_int(key)]) for key in chars) if tile < count]
    advance = _int(params.get("advance", TILE))
    metadata = {
        "header": {"signature": "GBA tiles", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": 7, "descent": 1, "width": advance, "leading": 12,
                  "fallback_code": 0, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": TILE, "cell_height": TILE,
                  "page_data_size": count * TILE_BYTES, "texture_format": 0,
                  "glyph_horizontal_count": _COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": stride, "texture_height": rows * TILE}],
        "MAP1": [map_entries(sorted(set(pairs)))],
        "WID1": [{"first_code_included": 0, "last_code_included": count,
                  "packets": [{"kerning": 0, "width": advance} for _ in range(count)]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    program, _end, tiles, _tiles_end = _unpack(original, params)
    count, base = _int(params.get("glyph_count", 256)), _int(params.get("glyph_offset", 0))
    ink = coverage(sheets[0]).tobytes()
    stride = sheets[0].width
    new_tiles = bytearray(tiles)
    letters = set(_glyph_tiles(params).values())
    for glyph in range(count):
        at = base + glyph * TILE_BYTES
        x0, y0 = (glyph % _COLUMNS) * TILE, (glyph // _COLUMNS) * TILE
        for two_tone in (False, True):
            for y in range(TILE):
                for x in range(0, TILE, 2):
                    row = (y0 + y) * stride + x0 + x
                    low, high = _nibble(ink[row], two_tone), _nibble(ink[row + 1], two_tone)
                    new_tiles[at + y * 4 + x // 2] = high << 4 | low
            # an unchanged tile keeps its bytes; an edited letter is drawn in ink and background only
            if new_tiles[at:at + TILE_BYTES] == tiles[at:at + TILE_BYTES] or glyph not in letters:
                break
    if bytes(new_tiles) == tiles:
        return bytes(original)

    new_program = bytearray(program)
    program_address = _int(params["program_address"])
    slots = params.get("slots") or {}
    blank = bytes([BACKGROUND << 4 | BACKGROUND]) * TILE_BYTES
    slot_codes = {_int(code): _int(tile) for code, tile in (slots.get("codes") or {}).items()}
    for first, last, table, accent in ((_int(v) for v in entry) for entry in slots.get("tables") or []):
        if any(first <= code <= last for code in slot_codes):
            new_tiles[base + accent * TILE_BYTES:base + (accent + 1) * TILE_BYTES] = blank
        for code, tile in slot_codes.items():
            if first <= code <= last:
                struct.pack_into("BB", new_program, table - program_address + 2 * (code - first), tile, 0)

    block = lz10.compress(bytes(new_tiles), vram=True)
    room = _int(params["tiles_room"])
    if len(block) > room:
        raise ValueError(f"The font tiles pack into {len(block)} bytes; the program has room for {room}. "
                         "Simplify some glyphs.")
    at = _int(params["tiles_address"]) - program_address
    new_program[at:at + room] = block + bytes(room - len(block))
    return replace_program(original, bytes(new_program), params)


def read_program(data: bytes, params: Dict[str, Any]) -> bytes:
    """The unpacked program of a client file."""
    return lz10.decompress(data, _int(params["program_offset"]))[0]


def replace_program(original: bytes, new_program: bytes, params: Dict[str, Any]) -> bytes:
    """``original`` with its program packed again from ``new_program``; the tail after it moves up (and the
    loader's tail pointers with it) when the packed program grew."""
    start = _int(params["program_offset"])
    program_address = _int(params["program_address"])
    pointers = [_int(pointer) for pointer in params.get("tail_pointers") or []]
    # the tail starts where the loader copies it from (the stream may be followed by padding)
    end = (struct.unpack_from("<I", original, pointers[0])[0] - 0x02000000 if pointers
           else lz10.decompress(original, start)[1])
    stream = lz10.compress(new_program)
    old_length = end - start
    out = bytearray(original[:start])
    tail = original[end:]
    if len(stream) <= old_length:
        out += stream + bytes(old_length - len(stream)) + tail
        return bytes(out)
    # The program grew: the tail moves up and the loader is told where it now starts and ends.
    out += stream + bytes(-len(stream) % 4)
    shift = len(out) - end
    if 0x02000000 + len(out) > program_address:
        raise ValueError("The packed program no longer fits below its unpacked address")
    out += tail
    for offset in pointers:
        struct.pack_into("<I", out, offset, struct.unpack_from("<I", out, offset)[0] + shift)
    return bytes(out)
