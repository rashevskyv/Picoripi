"""GBA / Nintendo DS character tiles: 8x8 tiles of 4 or 8 bit palette indices, as one sheet image.

The file is a NITRO NCGR (``RGCN``: depth, tile counts and the data offset come from its ``RAHC`` block) or
headerless tile data. Sprites stored one after another ("1D" mapping) are drawn as cells of ``cell`` =
``[w, h]`` tiles, ``per_row`` cells to a row; ``[1, 1]`` with ``per_row`` = tiles across is a plain sheet.
The palette lives in other files, so the indices are shown as grey levels (index 0 transparent; ``pixels``
codecs ``nds:4bpp`` / ``nds:8bpp``) and written back from them.

Params (all optional for an NCGR): ``bpp`` (4 / 8), ``offset`` (first tile), ``tiles`` (count), ``cell``,
``per_row``, ``name``; or ``textures``: a list of such entries for several sheets in one file.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels

MAGIC = b"RGCN"


def detect(data: bytes) -> bool:
    return data[:4] == MAGIC


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _entries(data: bytes, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    base: Dict[str, Any] = {}
    if data[:4] == MAGIC:
        tiles_y, tiles_x, depth = struct.unpack_from("<HHI", data, 0x18)
        size, offset = struct.unpack_from("<II", data, 0x28)
        bpp = 8 if depth == 4 else 4
        base = {"bpp": bpp, "offset": 0x18 + offset, "tiles": size * 8 // bpp // 64,
                "per_row": tiles_x if tiles_x not in (0, 0xFFFF) else 32}
    out = []
    for entry in params.get("textures") or [{}]:
        merged = {**base, **params, **entry}
        bpp = _int(merged.get("bpp", 4))
        offset = _int(merged.get("offset", 0))
        tiles = _int(merged.get("tiles", (len(data) - offset) * 8 // bpp // 64))
        cell_w, cell_h = (_int(v) for v in merged.get("cell", (1, 1)))
        per_row = _int(merged.get("per_row", max(1, 32 // cell_w)))
        cells = -(-tiles // (cell_w * cell_h))
        rows = -(-cells // per_row)
        out.append({"name": str(merged.get("name") or ""), "bpp": bpp, "offset": offset, "tiles": tiles,
                    "cell": (cell_w, cell_h), "per_row": per_row,
                    "size": (per_row * cell_w * 8, rows * cell_h * 8)})
    return out


def _places(entry: Dict[str, Any]):
    """``(tile index, x, y)`` of every tile of a sheet."""
    cell_w, cell_h = entry["cell"]
    per_cell = cell_w * cell_h
    for tile in range(entry["tiles"]):
        cell, inner = divmod(tile, per_cell)
        x = (cell % entry["per_row"]) * cell_w * 8 + (inner % cell_w) * 8
        y = (cell // entry["per_row"]) * cell_h * 8 + (inner // cell_w) * 8
        yield tile, x, y


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    out = []
    for entry in _entries(data, params):
        codec = pixels.codec(f"nds:{entry['bpp']}bpp")
        span = entry["bpp"] * 8
        image = Image.new("RGBA", entry["size"], (0, 0, 0, 0))
        for tile, x, y in _places(entry):
            at = entry["offset"] + tile * span
            image.paste(codec.decode(data[at:at + span], 8, 8), (x, y))
        out.append(Texture(entry["name"], image, f"{entry['bpp']}bpp tiles"))
    return out


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    entries = _entries(data, params)
    for index, image in images.items():
        entry = entries[index]
        if image.size != entry["size"]:
            raise ValueError(f"The image is {image.width}x{image.height}, the tiles {entry['size'][0]}x{entry['size'][1]}")
        codec = pixels.codec(f"nds:{entry['bpp']}bpp")
        span = entry["bpp"] * 8
        image = image.convert("RGBA")
        for tile, x, y in _places(entry):
            at = entry["offset"] + tile * span
            old = bytes(out[at:at + span])
            piece = image.crop((x, y, x + 8, y + 8))
            if piece.tobytes() != codec.decode(old, 8, 8).tobytes():
                out[at:at + span] = codec.encode(piece)
    return bytes(out)
