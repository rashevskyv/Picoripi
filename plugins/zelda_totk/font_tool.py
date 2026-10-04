"""Character widths from TotK's fonts (BFFNT), as Picoripi font maps. Offline tool.

    python -m plugins.zelda_totk.font_tool <romfs>/Font/<name>.bfarc.zs <output folder>

Accepts a ``.bffnt`` or a font archive (``.bfarc`` / ``.bfarc.zs``, a SARC of BFFNTs) and writes one
``<font>.json`` per font: ``{"A": {"width": 21}, ...}`` with the advance width from the font's CWDH
table, looked up through its CMAP. Put the output into ``plugins/zelda_totk/fonts/`` or the custom
fonts folder from Settings. zstd archives need ``ZsDic.pack.zs`` (see ``sarc.py``).
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Dict

from utils.atomic_io import atomic_write_text

from . import sarc


def _sections(raw: bytes, e: str):
    """FINF offsets of the CWDH and CMAP chains (NX/Cafe layout)."""
    header_size = struct.unpack_from(e + "H", raw, 6)[0]
    if raw[header_size:header_size + 4] != b"FINF":
        raise ValueError("BFFNT without FINF")
    cwdh, cmap = struct.unpack_from(e + "II", raw, header_size + 8 + 16)
    return cwdh - 8 if cwdh else 0, cmap - 8 if cmap else 0


def font_map(raw: bytes) -> Dict[str, Dict[str, int]]:
    """``{character: {"width": advance}}`` of one FFNT font (Switch: little-endian, 32-bit codes)."""
    if raw[:4] != b"FFNT":
        raise ValueError("Not a BFFNT font")
    e = "<" if raw[4:6] == b"\xff\xfe" else ">"
    wide_codes = e == "<"     # NX fonts store 32-bit character codes; Wii U fonts 16-bit
    cwdh, cmap = _sections(raw, e)

    widths: Dict[int, int] = {}
    seen = set()
    while cwdh and cwdh not in seen and raw[cwdh:cwdh + 4] == b"CWDH":
        seen.add(cwdh)
        first, last, following = struct.unpack_from(e + "HHI", raw, cwdh + 8)
        for index in range(last - first + 1):
            widths[first + index] = raw[cwdh + 16 + index * 3 + 2]
        cwdh = following - 8 if following else 0

    glyphs: Dict[int, int] = {}
    seen = set()
    while cmap and cmap not in seen and raw[cmap:cmap + 4] == b"CMAP":
        seen.add(cmap)
        position = cmap + 8
        if wide_codes:
            begin, end = struct.unpack_from(e + "II", raw, position)
            position += 8
        else:
            begin, end = struct.unpack_from(e + "HH", raw, position)
            position += 4
        method, _reserved, following = struct.unpack_from(e + "HHI", raw, position)
        position += 8
        if method == 0:       # direct: a run of codes to a run of glyphs
            offset = struct.unpack_from(e + "H", raw, position)[0]
            for code in range(begin, end + 1):
                glyphs.setdefault(code, code - begin + offset)
        elif method == 1:     # table: one glyph index per code
            for code in range(begin, end + 1):
                index = struct.unpack_from(e + "h", raw, position)[0]
                position += 2
                if index != -1:
                    glyphs.setdefault(code, index)
        elif method == 2:     # scan: (code, glyph) pairs
            count = struct.unpack_from(e + "H", raw, position)[0]
            position += 4 if wide_codes else 2
            for _ in range(count):
                if wide_codes:
                    code, index = struct.unpack_from(e + "Ih", raw, position)
                    position += 8
                else:
                    code, index = struct.unpack_from(e + "Hh", raw, position)
                    position += 4
                if index != -1:
                    glyphs.setdefault(code, index)
        else:
            raise ValueError(f"Unknown CMAP mapping method {method}")
        cmap = following - 8 if following else 0

    return {chr(code): {"width": widths[index]} for code, index in sorted(glyphs.items()) if index in widths}


def fonts_in(path: Path) -> Dict[str, bytes]:
    """``{font name: BFFNT bytes}`` of a font file or font archive."""
    raw = path.read_bytes()
    if raw[:4] == b"FFNT":
        return {path.stem: raw}
    if raw[:4] == sarc.ZSTD_MAGIC:
        raw = sarc.decompress(raw)[0]
    return {Path(name).stem: data for name, data in sarc.Sarc(raw).files.items() if data[:4] == b"FFNT"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("font", type=Path, help=".bffnt, .bfarc or .bfarc.zs")
    parser.add_argument("output", type=Path, help="folder for the font maps")
    parser.add_argument("--dictionaries", type=Path, help="folder with Pack/ZsDic.pack.zs (default: near the font)")
    args = parser.parse_args(argv)
    sarc.dictionary_dirs = lambda: [args.dictionaries or args.font.parent]
    args.output.mkdir(parents=True, exist_ok=True)
    for name, raw in fonts_in(args.font).items():
        target = args.output / f"{name}.json"
        mapping = font_map(raw)
        atomic_write_text(target, json.dumps(mapping, ensure_ascii=False, indent=1))
        print(f"{target}: {len(mapping)} characters")
    return 0


if __name__ == "__main__":
    sys.exit(main())
