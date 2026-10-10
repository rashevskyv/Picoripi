"""Tile-map pictures: a pattern name map that places 8x8 cells of 4 or 8 bit palette indices (Saturn VDP2
screens, and any console whose backgrounds are a map plus a cell bank), shown and edited as one picture.

The file holds the map (big-endian 16-bit names, ``cols`` a row) at ``map_offset`` and the cells from
``cells_offset`` to the end of the file. A name holds the cell number in its low bits (``name_mask``, in units
of ``unit`` bytes: a Saturn name counts 32-byte steps, so an 8 bpp cell is two steps), an optional palette number
(``pal_shift``, ``pal_mask``: palette ``p`` is colours ``p * 2**bpp ...`` of ``palette``, BGR555 as hex,
little endian as stored) and optional flip bits (``hflip_bit``, ``vflip_bit``). Index 0 is transparent; without
``palette`` the indices are grey levels. ``textures``: ``[{name, map_offset, cols, rows}]`` for a file whose
map holds several screens. ``blank`` is the name of an empty cell (default 0). ``nibble`` as in ``tiles``.

Writing keeps every cell whose 8x8 block did not change. A changed block becomes index data in the cell's
palette (an empty cell takes the palette of its nearest neighbour; a colour that is not in the palette takes the
nearest one) and then: the same cell already in the bank is reused; a cell only this map entry refers to is
redrawn in place; else a cell no map entry refers to is taken, or a new cell is appended while the bank is
smaller than ``max_tiles`` (default: no growth). A block that is fully transparent becomes ``blank``.
"""
from __future__ import annotations

import struct
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image

from core.texture_formats import Texture
from core.texture_formats.tiles import RGBA, _indices, _int, _nearest, _pack, bgr555

CLEAR = (0, 0, 0, 0)


def _entries(data: bytes, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for entry in params.get("textures") or [{}]:
        merged = {**params, **entry}
        bpp = _int(merged.get("bpp", 4))
        cell = 8 * bpp
        unit = _int(merged.get("unit", 32))
        cols, rows = _int(merged.get("cols", 32)), _int(merged.get("rows", 32))
        cells_offset = _int(merged.get("cells_offset", 0))
        pal_shift = merged.get("pal_shift")
        out.append({"name": str(merged.get("name") or ""), "bpp": bpp, "cell": cell, "unit": unit,
                    "map_offset": _int(merged.get("map_offset", 0)), "cols": cols, "rows": rows,
                    "cells_offset": cells_offset, "high": merged.get("nibble") == "high",
                    "name_mask": _int(merged.get("name_mask", 0x3FF)),
                    "pal_shift": None if pal_shift is None else _int(pal_shift),
                    "pal_mask": _int(merged.get("pal_mask", 0xF)),
                    "hflip": merged.get("hflip_bit"), "vflip": merged.get("vflip_bit"),
                    "blank": _int(merged.get("blank", 0)),
                    "max_tiles": merged.get("max_tiles"),
                    "palette": str(merged.get("palette") or "")})
    return out


def _palettes(entry: Dict[str, Any]) -> List[List[RGBA]]:
    """Palette number -> colours (index 0 transparent)."""
    count = 1 << entry["bpp"]
    if entry["palette"]:
        colours = bgr555(bytes.fromhex(entry["palette"]))
    else:
        top = count - 1
        colours = [(v * 255 // top,) * 3 + (255,) for v in range(count)]
    out = []
    for start in range(0, max(len(colours), count), count):
        chosen = list(colours[start:start + count]) + [(0, 0, 0, 255)] * max(0, count - len(colours[start:start + count]))
        chosen[0] = CLEAR
        out.append(chosen)
    return out


def _tile_of(entry: Dict[str, Any], name: int) -> int:
    return (name & entry["name_mask"]) * entry["unit"] // entry["cell"]


def _name_of(entry: Dict[str, Any], tile: int, palette: int) -> int:
    name = tile * entry["cell"] // entry["unit"]
    if entry["pal_shift"] is not None:
        name |= (palette & entry["pal_mask"]) << entry["pal_shift"]
    return name


def _palette_of(entry: Dict[str, Any], name: int) -> int:
    return 0 if entry["pal_shift"] is None else (name >> entry["pal_shift"]) & entry["pal_mask"]


def _tiles(data: bytes, entry: Dict[str, Any]) -> List[bytes]:
    cell, start = entry["cell"], entry["cells_offset"]
    return [bytes(data[at:at + cell]) for at in range(start, len(data) - cell + 1, cell)]


def _names(data: bytes, entry: Dict[str, Any]) -> List[int]:
    count = entry["cols"] * entry["rows"]
    return list(struct.unpack_from(f">{count}H", data, entry["map_offset"]))


def _block(entry: Dict[str, Any], tile: bytes, name: int, palettes: Sequence[Sequence[RGBA]]) -> Image.Image:
    colours = palettes[min(_palette_of(entry, name), len(palettes) - 1)]
    image = Image.frombytes("RGBA", (8, 8), b"".join(bytes(colours[i]) for i in _indices(tile, entry["bpp"], entry["high"])))
    if entry["hflip"] is not None and name >> _int(entry["hflip"]) & 1:
        image = image.transpose(Image.FLIP_LEFT_RIGHT)
    if entry["vflip"] is not None and name >> _int(entry["vflip"]) & 1:
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
    return image


def _render(data: bytes, entry: Dict[str, Any], tiles: List[bytes], palettes) -> Image.Image:
    image = Image.new("RGBA", (entry["cols"] * 8, entry["rows"] * 8), CLEAR)
    empty = bytes(entry["cell"])
    for i, name in enumerate(_names(data, entry)):
        tile = _tile_of(entry, name)
        raw = tiles[tile] if tile < len(tiles) else empty
        if raw != empty:
            image.paste(_block(entry, raw, name, palettes), ((i % entry["cols"]) * 8, (i // entry["cols"]) * 8))
    return image


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    out = []
    for entry in _entries(data, params):
        tiles = _tiles(data, entry)
        out.append(Texture(entry["name"], _render(data, entry, tiles, _palettes(entry)), f"{entry['bpp']}bpp tile map"))
    return out


def _neighbour_palette(entry: Dict[str, Any], names: List[int], index: int) -> int:
    """The palette of the nearest map entry that is not blank (the entry's own when it has one)."""
    cols = entry["cols"]
    if names[index] != entry["blank"]:
        return _palette_of(entry, names[index])
    r0, c0 = divmod(index, cols)
    best: Optional[Tuple[int, int]] = None
    for i, name in enumerate(names):
        if name == entry["blank"]:
            continue
        r, c = divmod(i, cols)
        distance = abs(r - r0) + abs(c - c0)
        if best is None or distance < best[0]:
            best = (distance, _palette_of(entry, name))
    return best[1] if best else 0


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    entries = _entries(data, params)
    out = bytearray(data)
    tiles = _tiles(data, entries[0])
    refs: Counter = Counter(_tile_of(e, n) for e in entries for n in _names(data, e))
    known: Dict[bytes, int] = {}
    for i, raw in enumerate(tiles):
        known.setdefault(raw, i)
    empty = bytes(entries[0]["cell"])
    for index, image in images.items():
        entry = entries[index]
        palettes = _palettes(entry)
        if image.size != (entry["cols"] * 8, entry["rows"] * 8):
            raise ValueError(f"The image is {image.width}x{image.height}, the map {entry['cols'] * 8}x{entry['rows'] * 8}")
        image = image.convert("RGBA")
        names = _names(bytes(out), entry)
        limit = len(tiles) if entry["max_tiles"] is None else _int(entry["max_tiles"])
        cache: Dict[Tuple, int] = {}
        for i, name in enumerate(names):
            x, y = (i % entry["cols"]) * 8, (i // entry["cols"]) * 8
            block = image.crop((x, y, x + 8, y + 8))
            old_tile = _tile_of(entry, name)
            old_raw = tiles[old_tile] if old_tile < len(tiles) else empty
            if block.tobytes() == (_block(entry, old_raw, name, palettes) if old_raw != empty else Image.new("RGBA", (8, 8), CLEAR)).tobytes():
                continue
            pixels = list(block.getdata())
            if all(p[3] < 128 for p in pixels):
                new_name = entry["blank"]
            else:
                palette = _neighbour_palette(entry, names, i)
                colours = palettes[min(palette, len(palettes) - 1)]
                raw = _pack([_nearest(p, colours, cache) for p in pixels], entry["bpp"], entry["high"])
                if raw in known:
                    tile = known[raw]
                elif name != entry["blank"] and refs[old_tile] == 1 and old_tile < len(tiles):
                    tile = old_tile                            # only this map entry draws it: redraw in place
                    known.pop(tiles[tile], None)
                    tiles[tile] = raw
                    known.setdefault(raw, tile)
                else:
                    free = next((t for t in range(1, len(tiles)) if refs[t] == 0 and t != old_tile), None)
                    if free is None:
                        if len(tiles) >= limit:
                            raise ValueError(f"No room for another 8x8 piece: the bank holds {len(tiles)} cells and every "
                                             "one is in use. Reuse pieces or clear cells elsewhere")
                        tiles.append(raw)
                        free = len(tiles) - 1
                    else:
                        known.pop(tiles[free], None)
                        tiles[free] = raw
                    known.setdefault(raw, free)
                    tile = free
                new_name = _name_of(entry, tile, palette)
            refs[old_tile] -= 1
            refs[_tile_of(entry, new_name)] += 1
            names[i] = new_name
        struct.pack_into(f">{len(names)}H", out, entry["map_offset"], *names)
    del out[entries[0]["cells_offset"]:]
    out += b"".join(tiles)
    return bytes(out)
