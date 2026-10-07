"""Vagrant Story (PlayStation) picture formats: ``GIM`` screens, help sprites, the title screen.

Three backends (``core.texture_formats`` names ``vs_gim``, ``vs_hf1``, ``vs_rle``); colours are
PlayStation CLUT entries (``pixels.psx_clut``). Writing maps new colours to the nearest CLUT entry,
re-encodes only the cells / blocks whose pixels changed and keeps the file size; an unchanged
image gives the original bytes back.

``vs_gim`` -- ``GIM/*.GIM``, a screen of 64 x 15-pixel cells over a shared tile sheet. Headers and
maps, ``1 + extra`` times: ``u8 cols, rows, sheet_rows (first only), clut_rows (first only)``,
``u16 mode`` (first: number of 256-colour CLUTs, 0 = 4-bit only; others: 0 4-bit, 1 8-bit),
``u16 extra`` (first only), ``u16 map[rows * cols]``. Then (4-aligned) ``clut_rows`` x 16 colours
(8-bit CLUTs start after the first four rows when there are 20 or more) and the sheet:
``sheet_rows`` x 15 lines of 128 bytes. A map cell is 0 (empty) or ``(page + 2) << 8 | row * 4 +
column`` (17 tile rows a page; a tile is 32 bytes of a line at 4 bits, 64 at 8). Each layer is a
texture ``layer<n>``; a 4-bit layer shows CLUT row ``n``, an 8-bit one the first 256-colour CLUT.
The CLUT choice was worked out from the files, not from the game's code: colours may differ from
the screen, the indices are kept exactly.

``vs_hf1`` -- ``SMALL/HELP*.HF1``, the pictures of a help page: ``u32 blocks, u32 clut_rows``,
blocks of 8 x 16 8-bit pixels (128 bytes), then the CLUT rows (a 256-colour CLUT is 16 rows).
The help page (``.HF0``) places them; the plugin copies its sprite table into ``params.sprites``:
``[{name, width, height, clut, blocks}]`` (blocks row by row, ``ceil(width / 8)`` a row).

``vs_rle`` -- a 16-bit VRAM image compressed in a program (``TITLE.PRG``'s title screen): ``u32``
words from ``offset`` to ``end``, each control word ``literal count << 16 | fill count`` followed by
the literals; a fill word is ``0x80008000``. ``width`` x ``height`` 16-bit pixels; ``textures``:
``[{name, pixel_format, x, y, width, height}]`` -- rectangles of it (``x`` in 16-bit units), e.g.
``psx:RGB555`` for the picture, ``psx:4bpp`` for 4-bit sprites stored inside it. A new picture is
compressed again into the same bytes (the run of fill words just before literals is spent to keep
the size); one that does not fit raises ``ValueError``.
"""
from __future__ import annotations

import struct
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image

from core.texture_formats import Texture, pixels, surface

CELL_W, CELL_H, LINE = 64, 15, 128
PAGE_ROWS = 17


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _clut(data: bytes, offset: int, count: int) -> List[Tuple[int, int, int, int]]:
    decode, _encode = pixels.psx_clut()
    count = max(0, min(count, (len(data) - offset) // 2))
    return [decode(v) for v in struct.unpack_from(f"<{count}H", data, offset)]


def _indexed(bits: int, palette: Sequence[Tuple[int, int, int, int]]) -> pixels.Codec:
    palette = list(palette) + [(0, 0, 0, 0)] * ((1 << bits) - len(palette))
    return pixels.palette_codec(f"psx:CI{bits}", bits, palette, endian="<", low_first=True)


def _block_bytes(data: bytes, base: int, stride: int, width_bytes: int, height: int) -> bytes:
    return b"".join(data[base + y * stride:base + y * stride + width_bytes] for y in range(height))


def _put_block(out: bytearray, base: int, stride: int, width_bytes: int, raw: bytes) -> None:
    for y in range(len(raw) // width_bytes):
        out[base + y * stride:base + y * stride + width_bytes] = raw[y * width_bytes:(y + 1) * width_bytes]


# -- GIM screens -------------------------------------------------------------------------------------


def _gim(data: bytes) -> Dict[str, Any]:
    if len(data) < 8:
        raise ValueError("Not a Vagrant Story GIM")
    sheet_rows, clut_rows = data[2], data[3]
    wide, extra = struct.unpack_from("<HH", data, 4)
    layers, at = [], 0
    for number in range(extra + 1):
        cols, rows = data[at], data[at + 1]
        mode = (1 if wide else 0) if number == 0 else data[at + 4]
        if at + 8 + 2 * cols * rows > len(data):
            raise ValueError("Not a Vagrant Story GIM")
        layers.append({"cols": cols, "rows": rows, "bits": 8 if mode else 4,
                       "map": struct.unpack_from(f"<{cols * rows}H", data, at + 8)})
        at += 8 + 2 * cols * rows
    cluts = (at + 3) & ~3
    sheet = cluts + clut_rows * 32
    if len(data) != sheet + sheet_rows * CELL_H * LINE:
        raise ValueError("Not a Vagrant Story GIM (size)")
    return {"layers": layers, "cluts": cluts, "clut_rows": clut_rows, "wide": wide, "sheet": sheet,
            "sheet_rows": sheet_rows}


def _gim_codec(data: bytes, gim: Dict[str, Any], number: int) -> pixels.Codec:
    bits = gim["layers"][number]["bits"]
    if bits == 4:
        row = min(number, max(0, gim["clut_rows"] - 1))
        return _indexed(4, _clut(data, gim["cluts"] + row * 32, 16))
    first = 64 if gim["clut_rows"] >= 20 else 0
    return _indexed(8, _clut(data, gim["cluts"] + first * 2, 256))


def _gim_tile(gim: Dict[str, Any], value: int, bits: int) -> Optional[int]:
    """Offset of the tile a map cell shows, or None."""
    row = ((value >> 8) - 2) * PAGE_ROWS + ((value & 0xFF) >> 2)
    column = value & 3
    if not value or not 0 <= row < gim["sheet_rows"] or (bits == 8 and column > 1):
        return None
    return gim["sheet"] + row * CELL_H * LINE + column * CELL_W * bits // 8


def _gim_cells(gim: Dict[str, Any], number: int):
    layer = gim["layers"][number]
    for r in range(layer["rows"]):
        for c in range(layer["cols"]):
            tile = _gim_tile(gim, layer["map"][r * layer["cols"] + c], layer["bits"])
            if tile is not None:
                yield (c * CELL_W, r * CELL_H), tile


def _gim_read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    gim = _gim(data)
    out = []
    for number, layer in enumerate(gim["layers"]):
        codec = _gim_codec(data, gim, number)
        width_bytes = CELL_W * layer["bits"] // 8
        image = Image.new("RGBA", (layer["cols"] * CELL_W, layer["rows"] * CELL_H))
        for place, tile in _gim_cells(gim, number):
            image.paste(codec.decode(_block_bytes(data, tile, LINE, width_bytes, CELL_H), CELL_W, CELL_H), place)
        out.append(Texture(f"layer{number}", image, f"GIM {layer['bits']}-bit"))
    return out


def _gim_write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    gim = _gim(data)
    out = bytearray(data)
    for number, image in images.items():
        layer = gim["layers"][number]
        codec = _gim_codec(data, gim, number)
        width_bytes = CELL_W * layer["bits"] // 8
        image = image.convert("RGBA")
        for (x, y), tile in _gim_cells(gim, number):
            old = _block_bytes(data, tile, LINE, width_bytes, CELL_H)
            cell = image.crop((x, y, x + CELL_W, y + CELL_H))
            if cell.tobytes() != codec.decode(old, CELL_W, CELL_H).tobytes():
                _put_block(out, tile, LINE, width_bytes, codec.encode(cell))
    return bytes(out)


# -- help page sprites ---------------------------------------------------------------------------------


def _hf1(data: bytes, params: Dict[str, Any]):
    blocks, clut_rows = struct.unpack_from("<II", data, 0)
    cluts = 8 + blocks * 128
    if cluts + clut_rows * 32 != len(data):
        raise ValueError("Not a Vagrant Story HF1")
    sprites = []
    for sprite in params.get("sprites") or []:
        width, height = _int(sprite["width"]), _int(sprite["height"])
        numbers = [_int(b) for b in sprite["blocks"]]
        if any(not 0 <= b < blocks for b in numbers):
            raise ValueError(f"HF1 sprite {sprite.get('name')}: block out of range")
        sprites.append({"name": str(sprite.get("name") or ""), "width": width, "height": height,
                        "codec": _indexed(8, _clut(data, cluts + _int(sprite.get("clut", 0)) * 512, 256)),
                        "blocks": numbers, "cols": -(-width // 8)})
    return sprites


def _hf1_full(data: bytes, sprite: Dict[str, Any]) -> Image.Image:
    rows = -(-len(sprite["blocks"]) // sprite["cols"])
    image = Image.new("RGBA", (sprite["cols"] * 8, rows * 16))
    for j, block in enumerate(sprite["blocks"]):
        at = 8 + block * 128
        image.paste(sprite["codec"].decode(data[at:at + 128], 8, 16), ((j % sprite["cols"]) * 8, (j // sprite["cols"]) * 16))
    return image


def _hf1_read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(s["name"], _hf1_full(data, s).crop((0, 0, s["width"], s["height"])), "HF1 8-bit")
            for s in _hf1(data, params)]


def _hf1_write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    sprites = _hf1(data, params)
    out = bytearray(data)
    for index, image in images.items():
        sprite = sprites[index]
        full = _hf1_full(data, sprite)
        full.paste(image.convert("RGBA"), (0, 0))
        for j, block in enumerate(sprite["blocks"]):
            x, y = (j % sprite["cols"]) * 8, (j // sprite["cols"]) * 16
            at = 8 + block * 128
            piece = full.crop((x, y, x + 8, y + 16))
            if piece.tobytes() != sprite["codec"].decode(data[at:at + 128], 8, 16).tobytes():
                out[at:at + 128] = sprite["codec"].encode(piece)
    return bytes(out)


# -- RLE-compressed VRAM image --------------------------------------------------------------------------

FILL = 0x80008000


def _rle_span(params: Dict[str, Any]) -> Tuple[int, int, int, int]:
    return _int(params["offset"]), _int(params["end"]), _int(params["width"]), _int(params["height"])


def _rle_decode(data: bytes, params: Dict[str, Any]) -> bytes:
    start, end, width, height = _rle_span(params)
    need = width * height // 2
    words: List[int] = []
    at = start
    while len(words) < need:
        if at + 4 > end:
            raise ValueError("The compressed picture ends early")
        control = struct.unpack_from("<I", data, at)[0]
        literal = control >> 16
        words += [FILL] * (control & 0xFFFF)
        words += struct.unpack_from(f"<{literal}I", data, at + 4)
        at += 4 + 4 * literal
    return struct.pack(f"<{need}I", *words[:need])


def _rle_encode(vram: bytes, room: int) -> bytes:
    words = struct.unpack(f"<{len(vram) // 4}I", vram)
    runs: List[List[Any]] = []          # [fill count, literals]
    i, n = 0, len(words)
    while i < n:
        fill = 0
        while i < n and words[i] == FILL and fill < 0xFFFF:
            fill += 1
            i += 1
        j = i
        while j < n and j - i < 0xFFFF and words[j] != FILL:
            j += 1
        runs.append([fill, list(words[i:j])])
        i = j
    size = sum(4 + 4 * len(literals) for _f, literals in runs)
    if size > room:
        raise ValueError(f"The picture compresses to {size} bytes, its place has {room}: use fewer colours")
    spare = (room - size) // 4
    for run in runs:                   # spend fill words as literals until the stream fills its place
        while spare and run[0] and len(run[1]) < 0xFFFF:
            run[0] -= 1
            run[1].insert(0, FILL)
            spare -= 1
    out = b"".join(struct.pack(f"<I{len(lit)}I", len(lit) << 16 | fill, *lit) for fill, lit in runs)
    return out + bytes(room - len(out))


def _rle_rects(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    _start, _end, width, height = _rle_span(params)
    out = []
    for entry in params.get("textures") or [{"name": "", "pixel_format": "psx:RGB555"}]:
        codec = pixels.codec(str(entry.get("pixel_format", "psx:RGB555")))
        x, y = _int(entry.get("x", 0)), _int(entry.get("y", 0))
        w, h = _int(entry.get("width", width)), _int(entry.get("height", height))
        per_row = w // codec.block[0]
        offsets = [((y + row) * width + x) * 2 + e * codec.size for row in range(h) for e in range(per_row)]
        out.append({"name": str(entry.get("name") or ""), "codec": codec, "size": (w, h), "offsets": offsets})
    return out


def _rle_read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    vram = _rle_decode(data, params)
    return [Texture(r["name"], surface.read(vram, 0, r["codec"], *r["size"], offsets=r["offsets"]),
                    r["codec"].name.split(":")[-1]) for r in _rle_rects(params)]


def _rle_write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    start, end, _w, _h = _rle_span(params)
    vram = _rle_decode(data, params)
    new = bytearray(vram)
    rects = _rle_rects(params)
    for index, image in images.items():
        r = rects[index]
        surface.write(new, 0, r["codec"], *r["size"], image, offsets=r["offsets"])
    if new == vram:
        return data
    return data[:start] + _rle_encode(bytes(new), end - start) + data[end:]


gim = SimpleNamespace(read=_gim_read, write=_gim_write)
hf1 = SimpleNamespace(read=_hf1_read, write=_hf1_write)
rle = SimpleNamespace(read=_rle_read, write=_rle_write)
