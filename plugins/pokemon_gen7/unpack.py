"""The files the unpack step takes from a Pokémon Sun / Moon or Ultra Sun / Ultra Moon image (3DS).

Same set as ``zt/pkgen7.py``: the English text GARCs ``a/0/3/2`` and ``a/0/4/2``, the fonts ``a/0/2/5`` and the
pictures. Every GARC member goes to ``romfs/<garc>/NNN.<ext>`` as plain bytes (LZ11 undone), so the project's source
folder matches the workspace ``source/`` folder. An Ultra update CIA (title 0004000E...) overrides the base GARC of
the same path, as the game does.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from core.i18n import tr
from core.project_library import images
from plugins.common import garc_mod, gfmsg
from plugins.common.garc import Garc

TEXT = ("a/0/3/2", "a/0/4/2")
FONTS = ("a/0/2/5",)
PICTURES = ("a/0/6/1", "a/0/6/2", "a/1/5/4", "a/1/5/9", "a/2/6/0", "a/2/6/9", "a/2/8/1", "a/2/9/1")
GARCS = TEXT + FONTS + PICTURES
EXT = {"text": "dat", "font": "bffnt", "picture": "bflim"}


def kind_of(garc: str, plain: bytes) -> Optional[str]:
    """``text`` / ``font`` / ``picture`` for a member of the group, else None."""
    if garc in TEXT:
        return "text" if gfmsg.is_gfmsg(plain) else None
    if garc in FONTS:
        return "font" if plain[:4] == b"FFNT" else None
    if garc in PICTURES and b"FLIM" in plain[-0x40:]:
        return "picture"
    return None


def member_name(index: int, bit: int, kind: str) -> str:
    return f"{index:03d}.{EXT[kind]}" if bit == 0 else f"{index:03d}.{bit}.{EXT[kind]}"


def _garc_bytes(image, rel: str) -> Optional[bytes]:
    entry = next((e for e in image.entries() if e.path == f"romfs/{rel}"), None)
    return image.read(entry) if entry is not None else None


def extract(base: str, update: Optional[str], target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the text, font and picture members of ``base`` (and of ``update`` where it has the GARC) into
    ``target_dir``. Returns ``target_dir``, or None when cancelled. Raises ValueError for a mismatched update."""
    with images.open_image(base) as image:
        base_title = str(image.program["title_id"]).lower()
        if update is None:
            return _write(image, None, base_title, target_dir, progress, is_cancelled)
        with images.open_image(update) as overlay:
            if str(overlay.program["title_id"]).lower() != "0004000e" + base_title[8:]:
                raise ValueError(tr("The update file is not the update of this game."))
            return _write(image, overlay, base_title, target_dir, progress, is_cancelled)


def _write(image, overlay, base_title: str, target_dir: str, progress, is_cancelled) -> Optional[str]:
    total = len(GARCS)
    for number, rel in enumerate(GARCS, 1):
        if is_cancelled():
            return None
        progress(100 * (number - 1) // total, rel)
        data = _garc_bytes(overlay, rel) if overlay is not None else None
        if data is None:
            data = _garc_bytes(image, rel)
        if not data:                                     # an empty archive in this game
            continue
        garc_mod.store_original(Path(target_dir), base_title, rel, data)   # the build starts from these archives
        garc = Garc(data)
        for index in range(len(garc.files)):
            for bit in garc.bits(index):
                plain, _compressed = garc.member(index, bit)
                kind = kind_of(rel, plain)
                if kind is None:
                    continue
                out = Path(target_dir, "romfs", *rel.split("/"), member_name(index, bit, kind))
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(plain)
    progress(100, "")
    return target_dir
