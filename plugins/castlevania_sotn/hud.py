"""The Richter HUD digits of the prologue stage (ST0) for the dialogue preview. Headless, PIL only.

ST0 draws its HUD with ``DrawRichterHud`` (``src/dra/5F60C.c``). The hearts count is two 8x8 sprites that
read the ``richter_hud`` sheet at ``v = 96``, ``u = digit * 8``, with CLUT 0x103. The sheet is a ``cmpgfx``
stream (``tools/sotn-assets/sotn/inflate.go``) at ``ST/ST0/ST0.BIN`` offset 0x14448: 128 x 128, 4bpp.
CLUT 0x103 (VRAM 48, 4) is bank index 3 of ``F_GAME2.BIN`` (offset 0x40060). The digit cells, the palette and
the hearts position are read from the disc; the hearts value is not traced and is shown as 30 (the owner's frame).
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

RICHTER_HUD_OFFSET = 0x14448   # cmpgfx stream of richter_hud in ST0.BIN (config/assets.us.yaml)
HUD_SIZE = 128                 # the decoded sheet is 128 x 128 pixels, 4bpp (0x2000 bytes)
HUD_CLUT_OFFSET = 0x40060      # CLUT 0x103 in F_GAME2.BIN: bank index 3, 16 colours (R5G5B5A1)
DIGIT_V = 96                   # hearts digits: v = 96 in the sheet
CELL = 8
HEARTS_CELLS = ((14, 8), (22, 8))  # (tens, ones) origins in the native frame; fitted to owner_02
DEFAULT_HEARTS = 30            # shown value of the owner's frame; the prologue's start value is not traced


def inflate(src: bytes) -> bytes:
    """Decode a ``cmpgfx`` stream: 8 dictionary bytes, then nibble opcodes. Low nibble of each output byte first.

    Port of ``sotn.Inflate`` in the decomp's sotn-assets tool. Raises ValueError when the stream ends before
    its end opcode (15).
    """
    if len(src) < 8:
        raise ValueError("cmpgfx stream is shorter than its dictionary")
    dictionary = src[:8]
    out = bytearray()
    cursor = {"pos": 8, "half": 0, "write_half": 0}

    def read() -> int:
        if cursor["pos"] >= len(src):
            raise ValueError("cmpgfx stream ends before its end opcode")
        if cursor["half"] == 0:
            cursor["half"] = 1
            return (src[cursor["pos"]] >> 4) & 15
        cursor["half"] = 0
        cursor["pos"] += 1
        return src[cursor["pos"] - 1] & 15

    def put(nibble: int) -> None:
        if cursor["write_half"] == 0:
            cursor["write_half"] = 1
            out.append(nibble & 15)
        else:
            cursor["write_half"] = 0
            out[-1] = (out[-1] + ((nibble & 15) << 4)) & 0xFF

    while True:
        op = read()
        if op == 0:
            amount = read() << 4
            amount += read() + 0x13
            for _ in range(amount):
                put(0)
        elif op == 1:
            put(read())
        elif op == 2:
            nibble = read()
            put(nibble)
            put(nibble)
        elif op == 3:
            put(read())
            put(read())
        elif op == 4:
            put(read())
            put(read())
            put(read())
        elif op == 5:
            nibble = read()
            for _ in range(read() + 3):
                put(nibble)
        elif op == 6:
            for _ in range(read() + 3):
                put(0)
        elif op == 15:
            return bytes(out)
        else:
            kind = dictionary[op - 7] & 0xF0
            amount = dictionary[op - 7] & 0x0F
            if kind == 0x10:
                put(amount)
            elif kind == 0x20:
                put(amount)
                put(amount)
            elif kind == 0x60:
                for _ in range(amount + 3):
                    put(0)


def _to_8bit(channel: int) -> int:
    return (channel << 3) | (channel >> 2)


def clut_rgba(data: bytes, offset: int) -> List[Tuple[int, int, int, int]]:
    """16 RGBA colours of a CLUT (R5G5B5A1, little endian). Index 0 is transparent, as on the console."""
    colours = []
    for index in range(16):
        value = data[offset + 2 * index] | (data[offset + 2 * index + 1] << 8)
        colours.append((_to_8bit(value & 31), _to_8bit((value >> 5) & 31), _to_8bit((value >> 10) & 31),
                        0 if index == 0 else 255))
    return colours


def richter_hud_sheet(st0: bytes, game2: bytes) -> Image.Image:
    """The Richter HUD sheet (RGBA, 128 x 128) from ``ST0.BIN`` and the CLUT of ``F_GAME2.BIN``.

    Raises ValueError when the stream or the palette is cut short.
    """
    pixels = inflate(st0[RICHTER_HUD_OFFSET:])
    if len(pixels) != HUD_SIZE * HUD_SIZE // 2:
        raise ValueError(f"richter_hud decodes to {len(pixels)} bytes")
    if len(game2) < HUD_CLUT_OFFSET + 32:
        raise ValueError("F_GAME2.BIN is too short for the HUD CLUT")
    palette = clut_rgba(game2, HUD_CLUT_OFFSET)
    indices = []
    for byte in pixels:
        indices.append(byte & 15)
        indices.append(byte >> 4)
    sheet = Image.new("RGBA", (HUD_SIZE, HUD_SIZE))
    sheet.putdata([palette[index] for index in indices])
    return sheet


def read_richter_hud(st0_path: str, game2_path: str) -> Optional[Image.Image]:
    """The HUD sheet from two files, or None when a file is missing or does not decode."""
    st0, game2 = Path(st0_path), Path(game2_path)
    if not (st0.is_file() and game2.is_file()):
        return None
    try:
        return richter_hud_sheet(st0.read_bytes(), game2.read_bytes())
    except ValueError:
        return None


def draw_hearts(frame: Image.Image, sheet: Image.Image, hearts: int = DEFAULT_HEARTS) -> Image.Image:
    """Compose the hearts digits onto ``frame`` (native frame coordinates). Two digits, 0 to 99."""
    value = max(0, min(99, hearts))
    for (x, y), digit in zip(HEARTS_CELLS, (value // 10, value % 10)):
        cell = sheet.crop((digit * CELL, DIGIT_V, digit * CELL + CELL, DIGIT_V + CELL))
        frame.alpha_composite(cell, (x, y))
    return frame
