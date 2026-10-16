"""The files the unpack step takes from a Pokémon Mystery Dungeon 3DS image (Gates to Infinity or Super Mystery Dungeon).

The same set and the same names as the workspace ``source\\romfs`` that ``zt/pmd3ds.py`` makes, so a project opened on
either tree sees the same files:
  Gates to Infinity:     ``romfs/message/*.bin`` (no ``name_sort.bin``, no other-language copies), ``romfs/font/*.dic``
                         and ``*.img`` (no ``*_win.img``), ``romfs/image_2d/*.img`` (no other-language copies).
  Super Mystery Dungeon: the members of ``message_en.bin``, ``message_debug_en.bin`` and ``image_2d.bin`` (FARC packs,
                         ``core.containers.farc``) as ``romfs/<pack>/<name>``, and the fonts as above. The debug pack
                         holds one ``.dbin`` label table per message file (the same message count as ``message_en``).
  Both games:            every ``.lua`` script of the image that holds text (a Lua 5.1 string constant with a space;
                         the credits, the debug labels), at the same path under ``romfs``. See ``lua_text``.
The member names come from ``message_en.lst`` and the picture database (``pack_names``); a member no name fits is
``#<hash>.bin`` or ``#<hash>.img``.

The unpack also keeps each pack as the game has it (``garc_original/<title id>/romfs/<pack>``): the build starts from
those bytes, because a pack is rebuilt around its changed members.
"""
from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Optional

from core.containers import farc
from core.i18n import tr
from core.project_library import images

from . import lua_text

GTI_TITLE = "00040000000ba900"
PSMD_TITLE = "0004000000174400"
ORIGINAL_DIR = "garc_original"
LANG_SUFFIX = re.compile(r"_(de|es|fr|it|ge|sp)$")
PSMD_PACKS = {"message_en.bin": "*.bin", "message_debug_en.bin": "*.dbin", "image_2d.bin": "*.img"}   # pack -> names kept
GTI_LOOSE = (("message", "*.bin"), ("font", "*.dic"), ("font", "*.img"), ("image_2d", "*.img"))
PSMD_LOOSE = (("font", "*.dic"), ("font", "*.img"))
GTI_SKIP = {"message/name_sort.bin"}
_MAX_TABLE = 50_000_000                     # the picture database names come from the small tables only

Reader = Callable[[], bytes]


def game_of(title_id: str) -> Optional[str]:
    """``"gti"``, ``"psmd"`` or None for a title this plugin does not know."""
    title = str(title_id).lower()
    if title == GTI_TITLE:
        return "gti"
    if title == PSMD_TITLE:
        return "psmd"
    return None


def pack_names(top: Dict[str, Reader], pack: str) -> Dict[int, str]:
    """``{name hash: name}`` of the members of ``pack``: the names of ``message_en.lst``, and for ``image_2d.bin`` every
    lowercase identifier of the game's small top-level tables with the ``.img`` and ``.bsji`` extensions (zt's rule)."""
    stem = PurePosixPath(pack).stem
    names: List[str] = []
    listing = f"{stem}.lst"
    if listing in top:
        names += [line.strip().rsplit("/", 1)[-1] for line in top[listing]().decode("utf-8").splitlines()
                  if line.strip()]
    if f"{stem}_database.bin" in top:
        found = set()
        for table, read in sorted(top.items()):
            if not table.endswith(".bin") or table == pack:
                continue
            raw = read()
            if len(raw) >= _MAX_TABLE:
                continue
            found.update(s.decode("utf-16-le") for s in re.findall(rb"(?:[a-z0-9_]\x00){3,60}", raw))
            found.update(s.decode("ascii") for s in re.findall(rb"[a-z0-9_]{3,60}", raw))
        names += [n + ext for n in sorted(found) for ext in (".img", ".bsji")]
    return {farc.name_hash(n): n for n in names}


def pack_members(data: bytes, names: Dict[int, str]) -> Dict[str, bytes]:
    """``{name: bytes}`` of every member of a pack. A member with no known name is ``#<hash>`` and its kind."""
    out: Dict[str, bytes] = {}
    for h, offset, length in farc.members(data):
        blob = data[offset:offset + length]
        out[names.get(h) or f"#{h:08X}" + (".img" if blob[:4] == b"\0cte" else ".bin")] = blob
    return out


def _is_wanted(rel: str, game: str, loose: tuple) -> bool:
    """A loose file the unpack takes: the folder and pattern match, it is not a skipped name or another language."""
    parts = rel.split("/")
    if len(parts) != 2 or not any(parts[0] == folder and PurePosixPath(parts[1]).match(pattern)
                                  for folder, pattern in loose):
        return False
    if game == "gti" and rel in GTI_SKIP:
        return False
    stem = PurePosixPath(rel).stem
    if parts[0] == "font" and stem.endswith("_win"):      # the PC tools' linear copies: the 3DS does not read them
        return False
    return not LANG_SUFFIX.search(stem)


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the English files of the game in ``base`` into ``target_dir/romfs``. Returns ``target_dir``, or None when
    cancelled. Raises ValueError for a title this plugin does not know."""
    with images.open_image(base) as image:
        title = str(image.program["title_id"]).lower()
        game = game_of(title)
        if game is None:
            raise ValueError(tr("This Pokémon Mystery Dungeon title is not known: {0}.", title))
        entries = {e.path[len("romfs/"):]: e for e in image.entries() if e.path.startswith("romfs/")}
        readers: Dict[str, Reader] = {rel: (lambda e=e: image.read(e)) for rel, e in entries.items()}
        top = {rel: read for rel, read in readers.items() if "/" not in rel}
        root = Path(target_dir, "romfs")
        loose = GTI_LOOSE if game == "gti" else PSMD_LOOSE
        wanted = [rel for rel in sorted(readers) if _is_wanted(rel, game, loose)]
        for number, rel in enumerate(wanted, 1):
            if is_cancelled():
                return None
            progress(100 * number // (len(wanted) + 1), rel)
            out = root / Path(*rel.split("/"))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(readers[rel]())
        scripts = [rel for rel in sorted(readers) if rel.endswith(".lua")]      # only those with text (lua_text)
        for number, rel in enumerate(scripts, 1):
            if is_cancelled():
                return None
            progress(100 * number // (len(scripts) + 1), rel)
            raw = readers[rel]()
            try:
                has_text = bool(lua_text.prose_slots(raw))
            except lua_text.LuaError:
                has_text = False
            if has_text:
                out = root / Path(*rel.split("/"))
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(raw)
        for pack, pattern in sorted(PSMD_PACKS.items()) if game == "psmd" else ():
            if is_cancelled():
                return None
            progress(100, pack)
            data = readers[pack]()
            for name, blob in pack_members(data, pack_names(top, pack)).items():
                if PurePosixPath(name).match(pattern):
                    out = root / pack / name
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(blob)
            original = Path(target_dir, ORIGINAL_DIR, title, "romfs", pack)
            original.parent.mkdir(parents=True, exist_ok=True)
            original.write_bytes(data)
        Path(target_dir, ORIGINAL_DIR, title, "romfs").mkdir(parents=True, exist_ok=True)   # the title, for the build
    progress(100, "")
    return target_dir


def original_pack(source_dir: Path, pack: str) -> Path:
    """Where the unpack kept the game's own bytes of ``pack`` (the build starts from them)."""
    root = Path(source_dir, ORIGINAL_DIR)
    titles = [f for f in root.iterdir() if f.is_dir()] if root.is_dir() else []
    if len(titles) != 1:
        raise ValueError(tr("The source folder has no single game archive set: unpack the game again."))
    return titles[0] / "romfs" / pack
