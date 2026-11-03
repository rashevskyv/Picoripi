"""Export a font's glyph sheets as PNG files for an image editor, and import them back.

``export_sheets`` writes, for each texture sheet, a clean PNG (``<name>_sheet_<n>.png``: grey ink, alpha equal to the
ink, no lines drawn on it) and a preview with a cell grid and the glyph numbers (``<name>_sheet_<n>_grid.png``). It
also writes ``<name>_cells.json``: for each glyph, its sheet, cell position and the characters the font maps to it.

``import_sheets`` reads the clean PNG files back and packs them over the original font with the format's own writer.
The preview files are never read.

A font of a project is named by its label in the plugin's ``font_sources.json`` (a unique prefix is enough). The
project commands read the project's current font (the translation copy, else the game's file), and the import writes
it with the font editor's own write (``FontSource.write``); the old translation copy is kept as ``<file>.bak_<time>``.

CLI (an agent can run it; the paths are the caller's):

    python -m core.font_formats.sheet_io export <format> <font file> <folder> [--name NAME] [--offset N --size N]
    python -m core.font_formats.sheet_io import <format> <font file> <folder> <out file> [--name NAME] [--offset N --size N]
    python -m core.font_formats.sheet_io project-export <project.uiproj> <label> <folder>
    python -m core.font_formats.sheet_io project-import <project.uiproj> <label> <folder>

``--offset`` and ``--size`` read the font from a slice of a file, e.g. the dialogue font inside a DOL. The file
commands take no game constants: a format that needs them (a texture grid's cell size and characters) is run through
the project commands.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw

from core.font_formats import char_map, extract, pack
from core.font_formats.sources import FontSource, resolve
from utils.constants import user_plugin_file_or_shipped


def _stem(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_") or "font"


def _cell_of(glyph: int, metadata: Dict[str, Any]) -> Optional[Dict[str, int]]:
    gly = metadata["GLY1"][0]
    first = gly["start_glyph"]
    if not first <= glyph <= gly["end_glyph"]:
        return None
    per_row, per_col = gly["glyph_horizontal_count"], gly["glyph_vertical_count"]
    per_sheet = per_row * per_col
    index = glyph - first
    cell = index % per_sheet
    return {"sheet": index // per_sheet, "x": (cell % per_row) * gly["cell_width"],
            "y": (cell // per_row) * gly["cell_height"]}


def export_sheets(fmt: str, data: bytes, folder: Path, name: str = "font", params: Optional[Dict[str, Any]] = None) -> List[Path]:
    metadata, sheets = extract(fmt, data, params or {})
    folder.mkdir(parents=True, exist_ok=True)
    stem = _stem(name)
    gly = metadata["GLY1"][0]
    cw, ch = gly["cell_width"], gly["cell_height"]
    written: List[Path] = []
    for index, sheet in enumerate(sheets):
        clean = folder / f"{stem}_sheet_{index}.png"
        sheet.save(clean)
        written.append(clean)
        grid = sheet.convert("RGB")
        draw = ImageDraw.Draw(grid)
        for x in range(0, grid.width + 1, cw):
            draw.line([(x, 0), (x, grid.height)], fill=(255, 0, 0))
        for y in range(0, grid.height + 1, ch):
            draw.line([(0, y), (grid.width, y)], fill=(255, 0, 0))
        path = folder / f"{stem}_sheet_{index}_grid.png"
        grid.save(path)
        written.append(path)
    chars: Dict[int, List[str]] = {}
    for char, glyph in char_map(metadata).items():
        chars.setdefault(glyph, []).append(char)
    cells = []
    for glyph in range(gly["start_glyph"], gly["end_glyph"] + 1):
        where = _cell_of(glyph, metadata)
        cells.append({"glyph": glyph, **where, "chars": sorted(chars.get(glyph, []))})
    info = folder / f"{stem}_cells.json"
    info.write_text(json.dumps({"format": fmt, "cell_width": cw, "cell_height": ch,
                                "sheets": len(sheets), "cells": cells}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    written.append(info)
    return written


def import_sheets(fmt: str, original: bytes, folder: Path, name: str = "font",
                  params: Optional[Dict[str, Any]] = None) -> bytes:
    metadata, sheets_of_original = extract(fmt, original, params or {})
    stem = _stem(name)
    count = len(sheets_of_original)
    sheets = []
    for index in range(count):
        with Image.open(folder / f"{stem}_sheet_{index}.png") as image:
            sheets.append(image.convert("RGBA"))
    return pack(fmt, metadata, sheets, original, params or {})


def _slice(path: Path, offset: Optional[int], size: Optional[int]) -> bytes:
    data = path.read_bytes()
    if offset is None:
        return data
    return data[offset:offset + size] if size else data[offset:]


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def project_source(project_file: Path, label: str) -> FontSource:
    """The font file of a project that the plugin describes with this label (a unique prefix of it is enough).

    The descriptors are the plugin's ``font_sources.json`` (the user's copy if there is one), resolved the way the
    font editor resolves them.
    """
    project = json.loads(Path(project_file).read_text(encoding="utf-8"))
    descriptors = json.loads(user_plugin_file_or_shipped(project["plugin_name"], "font_sources.json")
                             .read_text(encoding="utf-8"))
    return find_source(resolve(descriptors, project.get("metadata") or {}), label)


def find_source(sources: List[FontSource], label: str) -> FontSource:
    exact = [source for source in sources if source.label == label]
    matches = exact or [source for source in sources if source.label.startswith(label)]
    if len(matches) != 1:
        raise ValueError(f"{len(matches)} font files match the label {label!r}; give the full label")
    return matches[0]


def export_source(source: FontSource, folder: Path) -> List[Path]:
    """The font as it is now in the project (the translation copy, else the game's file), as sheets in ``folder``."""
    return export_sheets(source.format, source.read_current(), folder, source.name, source.params)


def import_source(source: FontSource, folder: Path) -> Path:
    """Write the sheets in ``folder`` over the project's current font. The old translation copy is kept as
    ``<file>.bak_<time>`` first; the write itself is the font editor's (``FontSource.write``)."""
    data = import_sheets(source.format, source.read_current(), folder, source.name, source.params)
    target = Path(source.translation_path)
    if target.is_file():
        shutil.copy2(target, target.with_name(f"{target.name}.bak_{_stamp()}"))
    source.write(data)
    return target


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m core.font_formats.sheet_io")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("export", "import"):
        p = sub.add_parser(command)
        p.add_argument("format")
        p.add_argument("font")
        p.add_argument("folder")
        if command == "import":
            p.add_argument("out")
        p.add_argument("--name", default="font")
        p.add_argument("--offset", type=lambda v: int(v, 0), default=None)
        p.add_argument("--size", type=lambda v: int(v, 0), default=None)
    for command in ("project-export", "project-import"):
        p = sub.add_parser(command)
        p.add_argument("project", help="the project file (.uiproj)")
        p.add_argument("label", help="the font's label in the plugin's font_sources.json (or a unique prefix)")
        p.add_argument("folder")
    args = parser.parse_args(argv)
    if args.command.startswith("project-"):
        source = project_source(Path(args.project), args.label)
        if args.command == "project-export":
            for path in export_source(source, Path(args.folder)):
                print(path)
        else:
            print(import_source(source, Path(args.folder)))
        return 0
    data = _slice(Path(args.font), args.offset, args.size)
    if args.command == "export":
        for path in export_sheets(args.format, data, Path(args.folder), args.name):
            print(path)
        return 0
    Path(args.out).write_bytes(import_sheets(args.format, data, Path(args.folder), args.name))
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
