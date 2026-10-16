"""The files the unpack step takes from a Pokémon X / Y or Omega Ruby / Alpha Sapphire CIA (3DS).

Same set as ``zt/pkgen6.py``: the English game and story text, the name-entry keyboard rows, the font, the English
title pictures, and every language GARC that has English and French subfiles (its English members: text tables,
pictures in packs). Each member goes to ``romfs/<garc>/<name>`` as plain bytes, so the project's source folder
matches the workspace ``source`` folder. Every GARC of the game is kept whole in ``garc_original`` for the build.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional

from core.i18n import tr
from core.project_library import images
from plugins.common import garc_mod
from plugins.common.garc import Garc
from . import pack
from .pack import EN, FR

XY = dict(text=("a/0/7/4", "a/0/8/2"), fonts="a/1/8/5", keyboard="a/0/2/0",
          title={"a/1/6/5": {473: ("timg/logo_x*.bclim", "timg/push_start.bclim"),
                             480: ("timg/logo_y*.bclim", "timg/push_start.bclim")}},
          skip=("a/1/9/4",))
ORAS = dict(text=("a/0/7/3", "a/0/8/1"), fonts="a/1/6/7", keyboard="a/0/2/0",
            title={"a/1/5/2": {1119: ("timg/presented_by.bclim", "timg/gf_logo.bclim"),
                               1120: ("timg/title_logo_sapphire.bclim",),
                               1127: ("timg/title_logo_*.bclim", "timg/push_start.bclim"),
                               1128: ("timg/title_logo_sapphire.bclim",),
                               1135: ("timg/title_logo_*.bclim", "timg/push_start.bclim")}},
            skip=("a/1/7/4",))
# base title id (lower case) -> game table
GAMES = {"0004000000055d00": XY, "0004000000055e00": XY,
         "000400000011c400": ORAS, "000400000011c500": ORAS}


def _fixed(game: dict) -> set:
    return set(game["text"]) | {game["fonts"], game["keyboard"]} | set(game["title"])


def _is_language_garc(data: bytes) -> bool:
    """A GARC with at least one file that has both English and French subfiles."""
    if data[:4] != b"CRAG":
        return False
    garc = Garc(data)
    return any(EN in garc.bits(i) and FR in garc.bits(i) for i in range(len(garc.files)))


def _members(garc: Garc, rel: str, game: dict) -> Dict[str, bytes]:
    members: Dict[str, bytes] = {}
    title = game["title"].get(rel, {})
    for i in range(len(garc.files)):
        if rel in game["text"] or rel == game["fonts"] or EN in garc.bits(i):
            members.update(pack.english_members(garc, i))
        elif i in title:
            from fnmatch import fnmatchcase
            members.update({name: blob for name, blob in pack.english_members(garc, i).items()
                            if any(fnmatchcase(name.split("/", 1)[-1], pattern) for pattern in title[i])})
    return members


def _entries(image) -> Dict[str, object]:
    return {e.path[len("romfs/"):]: e for e in image.entries() if e.path.startswith("romfs/a/")}


def wanted_garcs(image, game: dict) -> Dict[str, bytes]:
    """``{garc: bytes}`` of every archive the unpack takes (the fixed ones and the language GARCs), in path order."""
    entries = _entries(image)
    out: Dict[str, bytes] = {}
    for rel in sorted(entries):
        if rel in game["skip"]:
            continue
        if rel in _fixed(game) or _is_language_garc(image.read(entries[rel])):
            out[rel] = image.read(entries[rel])
    return out


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the English members of the game in ``base`` into ``target_dir``. Returns ``target_dir``, or None when
    cancelled. Raises ValueError for a CIA this plugin does not know."""
    with images.open_image(base) as image:
        title = str(image.program["title_id"]).lower()
        game = GAMES.get(title)
        if game is None:
            raise ValueError(tr("This Pokémon X / Y or Omega Ruby / Alpha Sapphire title is not known: {0}.", title))
        garcs = wanted_garcs(image, game)
        total = max(1, len(garcs))
        for number, (rel, data) in enumerate(garcs.items(), 1):
            if is_cancelled():
                return None
            progress(100 * (number - 1) // total, rel)
            garc_mod.store_original(Path(target_dir), title, rel, data)   # the build starts from these archives
            garc = Garc(data)
            for name, blob in _members(garc, rel, game).items():
                out = Path(target_dir, "romfs", *rel.split("/"), *name.split("/"))
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(blob)
    progress(100, "")
    return target_dir
