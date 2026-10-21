"""Write the portrait colour table of a Lunar SSSC project from a reference sprite sheet.

Usage: python scripts/lunar_portrait_colours.py <project folder> <sheet.png>

Reads ``LUNADATA/FACE_*.TIZ`` of the project's source folder, matches each portrait frame to a cell of the sheet,
and writes ``<project folder>/portrait_colours.json``. The game files and the sheet stay where they are.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plugins.common.switch_message_preview import source_folder  # noqa: E402
from plugins.lunar_sssc import portrait_colours as pc  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    project, sheet_path = Path(argv[0]), Path(argv[1])
    source = source_folder(str(project))
    if not source:
        print("The project has no source folder (metadata.source_path in its .uiproj file).")
        return 1
    files = {path.name: path.read_bytes() for path in sorted((Path(source) / "LUNADATA").glob("FACE_*.TIZ"))}
    if not files:
        print("No FACE_*.TIZ files in the source folder.")
        return 1
    sheet = np.array(Image.open(sheet_path).convert("RGBA"))
    matches = pc.match_file(files, pc.SheetIndex(sheet))
    colours = pc.vote(files, sheet, matches)
    pc.write_colours(project / pc.COLOURS_FILE, colours)
    frames = sum(1 for name in files for index in pc.frames_of(files[name]) if index.any())
    matched = sum(len(cells) for cells in matches.values())
    print(f"matched {matched} of {frames} non-empty frames; colours for {sum(len(t) for t in colours.values())} indices")
    print(f"wrote {project / pc.COLOURS_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
