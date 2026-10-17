"""Add the game's own terms (species, moves, items, places ...) to a series glossary file. Prints counts only.

Usage (venv interpreter, -I):
    python -I scripts/seed_series_glossary.py <project.uiproj> <series_glossary.json>

The project is read, never written. The series file is created when it does not exist; existing entries are kept.
Seeded terms have no translation. Run it on a scratch copy first; the series file is the owner's.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project_file", type=Path)
    parser.add_argument("series_file", type=Path)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(REPO))
    from core.glossary.series_seeds import seed_series_file

    counts = seed_series_file(args.project_file, args.series_file)
    print(f"offered {counts['offered']} terms, added {counts['added']}, already in the file {counts['present']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
