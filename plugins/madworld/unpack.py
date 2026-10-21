"""MadWorld unpack: the English messages, fonts, pictures and HOME Menu / banner files of the disc into the source folder.

The source folder holds (the same paths the build reads back):
  text/<disc file>.mwt        the messages of one message table, as JSON blocks (an empty table is left out)
  font/font_subtitle.tpl, font/font_heading.tpl   the message fonts as glyph grids (IA8); font/system.tpl the ASCII font
  ui/<disc file>.tpl, ui/<disc file>@<offset>.tpl   each 2D picture with English text
  hbm/home.csv, hbm/home_nosave.csv, hbm/homeBtn_ENG.arc/...   the Wii HOME Menu
  opening.bnr/...             the disc banner
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from core.containers import wii_disc
from core.project_library import images

from . import archives, fonts, messages

GAME_ID = "RZZP8P"
HBM = "hbm/HomeButton2"


@dataclass
class Unit:
    """One English message unit of the disc, parsed."""

    rel: str
    kind: str
    atlas: Optional[str]
    raw: tuple
    msd: bytes
    mtd: bytes
    atlas_data: dict
    chars: Dict[int, tuple]


def scan_units(read: Callable[[str], bytes], names: Set[str], table: dict,
               progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[List[Unit]]:
    """The message units of the disc (None when cancelled). ``read(path)`` gives a disc file's bytes."""
    found = messages.text_files(names)
    out: List[Unit] = []
    for n, (rel, kind, mtd) in enumerate(found):
        if is_cancelled():
            return None
        progress(40 * n // max(1, len(found)), rel)
        loaded = messages.load_unit(read, rel, kind, mtd)
        if loaded is None:
            continue
        raw, msd, mtd_body = loaded
        atlas = messages.mtd_parse(mtd_body)
        out.append(Unit(rel, kind, mtd, raw, msd, mtd_body, atlas, messages.atlas_chars(atlas, table)))
    return out


def unit_strings(unit: Unit) -> tuple:
    """``(ids, strings, ends, unknown count)`` of a unit's messages in English."""
    flag, msgs = messages.msd_parse(unit.msd)
    strings, ends, unknown = [], [], 0
    for _ident, words in msgs:
        text, end = messages.words_to_text(words, unit.atlas_data["first"], unit.chars)
        unknown += text.count("<G:")
        strings.append(text)
        ends.append(end)
    return [i for i, _w in msgs], strings, ends, unknown


def text_json(unit: Unit, ids: list, ends: list, strings: list) -> bytes:
    body = {"file": unit.rel, "kind": unit.kind, "atlas": unit.atlas, "blocks": [
        {"name": unit.rel.rsplit("/", 1)[-1].rsplit(".", 1)[0], "ids": ids, "ends": ends, "strings": strings}]}
    return json.dumps(body, ensure_ascii=False, indent=1).encode("utf-8")


def picture_target(rel: str, at: int, size: int, data_len: int) -> str:
    """The source path of one picture: the whole file, or ``<file>@<offset>`` inside an archive."""
    if (at, size) == (0, data_len) or rel.endswith(".tpl"):
        return f"ui/{rel}.tpl"
    return f"ui/{rel}@{at:x}.tpl"


def unpack_disc(image: str, target_dir: str, progress: Callable[[int, str], None],
                is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the source tree of the MadWorld disc ``image`` into ``target_dir``; None when cancelled."""
    with images.open_image(image, None, is_cancelled, progress) as reader:
        if not isinstance(reader, wii_disc.WiiImage) or reader.game_id != GAME_ID:
            raise ValueError(f"{os.path.basename(image)}: not MadWorld Europe ({GAME_ID})")
        entries = {e.path[len("files/"):]: e for e in reader.entries() if e.path.startswith("files/")}

        def read(rel: str) -> bytes:
            if rel not in entries:
                raise ValueError(f"{rel}: not on the disc")
            return reader.read(entries[rel])

        table = messages.labels()
        units = scan_units(read, set(entries), table, progress, is_cancelled)
        if units is None:
            return None
        out = Path(target_dir)
        for n, unit in enumerate(units):
            if is_cancelled():
                return None
            ids, strings, ends, unknown = unit_strings(unit)
            if not any(s.strip() for s in strings):
                continue
            _write(out / "text" / f"{unit.rel}.mwt", text_json(unit, ids, ends, strings))
            progress(40 + 10 * n // max(1, len(units)), unit.rel)
        font_map = fonts.harvest_fonts([(u.atlas_data, u.chars) for u in units])
        index = fonts.font_index(font_map)
        for style, blob in fonts.grid_bytes(font_map, index).items():
            _write(out / "font" / f"font_{style}.tpl", blob)
        _write(out / "font" / "system.tpl", read("etc/font.tpl"))
        for rel in messages.ui_files(set(entries)):
            if is_cancelled():
                return None
            data = read(rel)
            for at, size in messages.pictures(data):
                _write(out / picture_target(rel, at, size, len(data)), data[at:at + size])
        progress(55, "HOME Menu and banner")
        _write(out / "hbm" / "home.csv", read(f"{HBM}/home.csv"))
        _write(out / "hbm" / "home_nosave.csv", read(f"{HBM}/home_nosave.csv"))
        _explode_to(read(f"{HBM}/homeBtn_ENG.arc"), "hbm/homeBtn_ENG.arc", out)
        _explode_to(read("opening.bnr"), "opening.bnr", out)
        progress(100, "done")
    return str(out)


def _explode_to(raw: bytes, prefix: str, out: Path) -> None:
    archives.explode(raw, prefix, lambda rel, blob: _write(out / rel, blob))


def _write(path: Path, blob: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
