"""GBA / Nintendo DS (and Sega Saturn) character tiles: 8x8 tiles of 1, 4 or 8 bit palette indices, as one sheet image.

The file is a NITRO NCGR (``RGCN``: depth, tile counts and the data offset come from its ``RAHC`` block) or
headerless tile data. Sprites stored one after another ("1D" mapping) are drawn as cells of ``cell`` =
``[w, h]`` tiles, ``per_row`` cells to a row; ``[1, 1]`` with ``per_row`` = tiles across is a plain sheet.

Colours: the palette lives in other files, so the plugin passes it: ``palette`` (the game's BGR555 colours
as hex, little endian as stored), ``bank`` (the 16-colour bank of a 4 bpp sheet) and ``banks`` (one hex digit
per tile, for sheets whose tiles use several banks; ``.`` = ``bank``). Index 0 is transparent. Without a
palette the indices are grey levels (``pixels`` codecs ``nds:4bpp`` / ``nds:8bpp``).

Writing keeps the index of every pixel whose colour did not change (a palette may hold one colour twice) and
gives a changed pixel the nearest colour of its tile's bank (a redrawn PNG often has smoothed edges; refusing
every off-palette pixel would make most redraws fail, and the window shows the result at once). Painting where
the sheet has no tiles is refused.

``linear``: the data is a plain bitmap instead of tiles (rows of ``per_row`` x 8 pixels, the low nibble first),
as Konami's DS Castlevania games keep their sprite pictures; its "tiles" are 8 x 1 strips.

Params (all optional for an NCGR): ``bpp`` (1 / 4 / 8), ``offset`` (first tile), ``tiles`` (count), ``cell``,
``per_row``, ``name``, ``palette``, ``bank``, ``banks``, ``nibble`` (``high``: the first pixel of a 4 bpp byte is
its high nibble, as on the Saturn; default low, as on the GBA/DS), ``linear``; or ``textures``: a list of such entries.
1 bpp tiles are 8 bytes, a row a byte, the first pixel in the high bit (Saturn ASCII.FON).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Sequence, Tuple

from PIL import Image

from core.texture_formats import Texture

MAGIC = b"RGCN"
RGBA = Tuple[int, int, int, int]


def detect(data: bytes) -> bool:
    return data[:4] == MAGIC


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def bgr555(raw: bytes) -> List[RGBA]:
    """The colours of a GBA / DS palette (u16 little endian, 5 bits each of red, green, blue)."""
    out = []
    for (value,) in struct.iter_unpack("<H", raw[:len(raw) // 2 * 2]):
        r, g, b = value & 31, value >> 5 & 31, value >> 10 & 31
        out.append((r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, 255))
    return out


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
        height = 1 if merged.get("linear") else 8
        tiles = _int(merged.get("tiles", (len(data) - offset) * 8 // bpp // (8 * height)))
        cell_w, cell_h = (_int(v) for v in merged.get("cell", (1, 1)))
        per_row = _int(merged.get("per_row", max(1, 32 // cell_w)))
        cells = -(-tiles // (cell_w * cell_h))
        rows = -(-cells // per_row)
        out.append({"name": str(merged.get("name") or ""), "bpp": bpp, "offset": offset, "tiles": tiles,
                    "cell": (cell_w, cell_h), "per_row": per_row, "high": merged.get("nibble") == "high", "height": height,
                    "size": (per_row * cell_w * 8, rows * cell_h * height), "banks": _banks(merged, bpp, tiles)})
    return out


def _banks(params: Dict[str, Any], bpp: int, tiles: int) -> List[List[RGBA]]:
    """The colours each tile is drawn with (index 0 transparent)."""
    top = (1 << bpp) - 1
    if params.get("palette"):
        colours = bgr555(bytes.fromhex(str(params["palette"])))
    else:
        colours = [(v * 255 // top,) * 3 + (255,) for v in range(top + 1)]
    count = 1 << bpp
    default = _int(params.get("bank", 0)) if bpp == 4 else 0
    marks = str(params.get("banks") or "")
    found: Dict[int, List[RGBA]] = {}
    out = []
    for tile in range(tiles):
        mark = marks[tile] if tile < len(marks) else "."
        bank = default if mark == "." else int(mark, 16)
        if bank not in found:
            chosen = list(colours[bank * count:bank * count + count])
            chosen += [(0, 0, 0, 255)] * (count - len(chosen))
            chosen[0] = (0, 0, 0, 0)
            found[bank] = chosen
        out.append(found[bank])
    return out


def _places(entry: Dict[str, Any]):
    """``(tile index, x, y)`` of every tile of a sheet."""
    cell_w, cell_h = entry["cell"]
    per_cell, height = cell_w * cell_h, entry["height"]
    for tile in range(entry["tiles"]):
        cell, inner = divmod(tile, per_cell)
        x = (cell % entry["per_row"]) * cell_w * 8 + (inner % cell_w) * 8
        y = (cell // entry["per_row"]) * cell_h * height + (inner // cell_w) * height
        yield tile, x, y


def _indices(raw: bytes, bpp: int, high: bool = False) -> List[int]:
    if bpp == 8:
        return list(raw)
    out = []
    if bpp == 1:
        for byte in raw:
            out += ((byte >> (7 - bit)) & 1 for bit in range(8))
        return out
    for byte in raw:
        out += (byte >> 4, byte & 15) if high else (byte & 15, byte >> 4)
    return out


def _pack(indices: Sequence[int], bpp: int, high: bool = False) -> bytes:
    if bpp == 8:
        return bytes(indices)
    if bpp == 1:
        return bytes(sum((indices[i + bit] & 1) << (7 - bit) for bit in range(8)) for i in range(0, 64, 8))
    if high:
        return bytes(indices[i] << 4 | indices[i + 1] for i in range(0, 64, 2))
    return bytes(indices[i] | indices[i + 1] << 4 for i in range(0, len(indices), 2))


def _tile_image(indices: Sequence[int], colours: Sequence[RGBA]) -> Image.Image:
    return Image.frombytes("RGBA", (8, len(indices) // 8), b"".join(bytes(colours[i]) for i in indices))


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    out = []
    for entry in _entries(data, params):
        span = entry["bpp"] * entry["height"]
        image = Image.new("RGBA", entry["size"], (0, 0, 0, 0))
        for tile, x, y in _places(entry):
            at = entry["offset"] + tile * span
            image.paste(_tile_image(_indices(data[at:at + span], entry["bpp"], entry["high"]), entry["banks"][tile]),
                        (x, y))
        out.append(Texture(entry["name"], image, f"{entry['bpp']}bpp tiles"))
    return out


def _nearest(colour: RGBA, colours: Sequence[RGBA], cache: Dict[Tuple, int]) -> int:
    if colour[3] < 128:
        return 0
    key = (colour, id(colours))
    if key not in cache:
        cache[key] = min(range(1, len(colours)),
                         key=lambda i: sum((p - q) ** 2 for p, q in zip(colours[i][:3], colour[:3])))
    return cache[key]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    entries = _entries(data, params)
    for index, image in images.items():
        entry = entries[index]
        if image.size != entry["size"]:
            raise ValueError(f"The image is {image.width}x{image.height}, the tiles {entry['size'][0]}x{entry['size'][1]}")
        image = image.convert("RGBA")
        unused = image.getchannel("A")
        for _tile, x, y in _places(entry):
            unused.paste(0, (x, y, x + 8, y + entry["height"]))
        if unused.getbbox():
            raise ValueError("The picture is drawn where the sheet has no tiles (the empty end of the last row)")
        span = entry["bpp"] * entry["height"]
        cache: Dict[Tuple, int] = {}
        for tile, x, y in _places(entry):
            at = entry["offset"] + tile * span
            old = _indices(out[at:at + span], entry["bpp"], entry["high"])
            colours = entry["banks"][tile]
            piece = image.crop((x, y, x + 8, y + entry["height"]))
            if piece.tobytes() == _tile_image(old, colours).tobytes():
                continue
            pixels = list(piece.getdata())
            new = [i if colours[i] == pixel or (i == 0 and pixel[3] < 128) else _nearest(pixel, colours, cache)
                   for i, pixel in zip(old, pixels)]
            out[at:at + span] = _pack(new, entry["bpp"], entry["high"])
    return bytes(out)
