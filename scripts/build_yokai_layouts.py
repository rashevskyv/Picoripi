"""Measure the Yo-kai Watch width limits (``plugins/yokai_watch/layout.json``) from a game's own text and font.

For every kind of text (``rules.layout_key``: the file group, the entry kind, the parameter) the widest English line,
measured with the game's main font, is the limit a translation must keep (``max``). ``count`` is the number of rows,
``warn`` the 99th percentile of the row widths (a row's width is its widest line), and ``lines`` the 95th percentile
of the lines on one page, stored when it is more than one. These are the rules the stored Yo-kai Watch 1 and 3
limits follow (checked: every value of both games is measured again the same).

    python scripts/build_yokai_layouts.py <source folder> [--game ywnx] [--write]

Without ``--write`` it prints the result and, for a game already in ``layout.json``, how it compares.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import font_formats  # noqa: E402
from core.font_formats.sources import join_pair  # noqa: E402
from plugins.yokai_watch import tags  # noqa: E402
from plugins.yokai_watch.rules import GameRules, layout_key  # noqa: E402
from plugins.yokai_watch.speakers import game_of  # noqa: E402
from plugins.yokai_watch.textfile import TextFile, is_japanese  # noqa: E402

LAYOUT = Path(__file__).resolve().parents[1] / "plugins" / "yokai_watch" / "layout.json"


def main_font(root: Path, game: str) -> Dict[str, Dict[str, int]]:
    """The width map of the game's main text font (the first preview font of ``get_font_sources``)."""
    rules = GameRules()
    rules._source_root = lambda: root  # the measurement has no project; the plugin finds its fonts from here
    for source in rules.get_font_sources():
        paths = source["path"] if isinstance(source["path"], list) else [source["path"]]
        for relative in paths:
            path = (root / relative).resolve()
            if path.is_file():
                data = path.read_bytes()
                if source.get("companion"):  # a G4 font table and its texture are read as one blob
                    data = join_pair(data, (root / source["companion"]).read_bytes())
                metadata, _sheets = font_formats.extract(source["format"], data, source.get("params"))
                print(f"font: {path}", file=sys.stderr)
                return font_formats.font_map(metadata)
    raise SystemExit(f"no main font found under {root} for {game}")


def _percentile(values: List[int], percent: int) -> int:
    ordered = sorted(values)
    return ordered[int(percent / 100 * (len(ordered) - 1))]


def measure(root: Path, font_map: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
    widths: Dict[str, List[int]] = {}
    page_lines: Dict[str, List[int]] = {}
    for path in sorted(root.rglob("*.cfg.bin")):
        rel = path.relative_to(root).as_posix()
        try:
            text_file = TextFile(path.read_bytes(), path.name, japanese=True)
        except Exception as error:  # a table this reader does not know is not text
            print(f"skip {rel}: {error}", file=sys.stderr)
            continue
        for row in text_file.rows:
            if not row.text or is_japanese(row.text):
                continue
            key = layout_key(rel, row.kind, row.param)
            pages = [page.split("\n") for page in tags.to_editor(row.text).split("{PAGE}")]
            widths.setdefault(key, []).append(max(GameRules._width(line, font_map) for page in pages for line in page))
            page_lines.setdefault(key, []).extend(len(page) for page in pages)
    result = {}
    for key in sorted(widths):
        entry = {"count": len(widths[key]), "max": max(widths[key]), "warn": _percentile(widths[key], 99)}
        lines = _percentile(page_lines[key], 95)
        if lines > 1:
            entry["lines"] = lines
        result[key] = entry
    return result


def compare(new: Dict[str, Dict[str, int]], old: Dict[str, Dict[str, int]]) -> None:
    fields = ("max", "warn", "lines")
    same = sum(1 for key in old if all(new.get(key, {}).get(f) == old[key].get(f) for f in fields))
    print(f"compared with layout.json: {same} of {len(old)} kinds have the same max, warn and lines", file=sys.stderr)
    for key in sorted(old):
        if any(new.get(key, {}).get(f) != old[key].get(f) for f in fields):
            print(f"  {key}: stored {old[key]} measured {new.get(key)}", file=sys.stderr)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("--game", help="yw1, yw2, yw3, ywnx, yw4 or yay (default: told from the folder)")
    parser.add_argument("--write", action="store_true", help="store the result in layout.json under the game")
    args = parser.parse_args(argv)
    root = args.source.resolve()
    game = args.game or game_of(root)
    result = measure(root, main_font(root, game))
    stored = json.loads(LAYOUT.read_text(encoding="utf-8"))
    if game in stored:
        compare(result, stored[game])
    print(json.dumps({game: result}, indent=1))
    if args.write:
        stored[game] = result
        text = json.dumps(stored, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
        LAYOUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"layout.json: {game} written ({len(result)} kinds)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
