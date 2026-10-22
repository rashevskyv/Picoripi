"""Write the portrait colour table of Lunar SSSC from a reference sprite sheet.

Usage: python scripts/lunar_portrait_colours.py <LUNADATA folder> <sheet.png> <output.json>

Reads ``FACE_*.TIZ`` from the LUNADATA folder, matches each portrait frame to a cell of the sheet, and writes the
index -> colour table as JSON. The shipped table is ``plugins/lunar_sssc/face_palettes.json``:

    python scripts/lunar_portrait_colours.py <LUNADATA> <sheet.png> plugins/lunar_sssc/face_palettes.json

The game files and the sheet are only read.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plugins.lunar_sssc import portrait_colours as pc  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    folder, sheet_path, output = Path(argv[0]), Path(argv[1]), Path(argv[2])
    files = {path.name: path.read_bytes() for path in sorted(folder.glob("FACE_*.TIZ"))}
    if not files:
        print("No FACE_*.TIZ files in the folder.")
        return 1
    sheet = np.array(Image.open(sheet_path).convert("RGBA"))
    matches = pc.match_file(files, pc.SheetIndex(sheet))
    colours = pc.vote(files, sheet, matches)
    pc.write_colours(output, colours)
    frames = sum(1 for name in files for index in pc.frames_of(files[name]) if index.any())
    matched = sum(len(cells) for cells in matches.values())
    print(f"matched {matched} of {frames} non-empty frames; colours for {sum(len(t) for t in colours.values())} indices")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
