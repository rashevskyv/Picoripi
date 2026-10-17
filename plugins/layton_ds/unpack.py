"""The files the unpack step takes from the four Professor Layton DS ROMs (Europe): the same set as zt/layton_ds.py.

The game comes from the title at 0x00 (LAYTON1 Curious Village, LAYTON2 Pandora's Box, LAYTON3 Lost Future, LAYTON4
Spectre's Call). Curious Village, Pandora's Box and Lost Future keep their files in the NitroFS, at their paths: a
text file in a text folder is taken when the plugin finds a string in it (``formats.Document``, as the current zt
script does); fonts and pictures are taken by their paths. Spectre's Call keeps them in three GFSA archives (``lt4_*.fa``): each member is written
at its archive path; a script (``.cb``) is taken when its GSD1 table shows a string.
"""
from __future__ import annotations

from core.i18n import tr
import re
import struct
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core.containers import level5
from core.containers.image_files import ImageError, ImageFile, check_name
from core.project_library import images
from .formats import Document

GAMES = {
    b"LAYTON1": dict(code=b"LAYTON1", root="data", lang="en",
                     text_dirs=("etext", "htext", "itext", "otext", "qtext", "stext", "storytext", "wifi", "room",
                                "script")),
    b"LAYTON2": dict(code=b"LAYTON2", root="data_lt2", lang="en",
                     text_dirs=("txt", "rc", "event", "nazo", "place", "script")),
    b"LAYTON3": dict(code=b"LAYTON3", root="lt3", lang="uk", text_dirs=("txt", "rc")),
    b"LAYTON4": dict(code=b"LAYTON4", root="", lang="uk", text_dirs=("txt", "res"),
                     archives=("lt4_main_uk.fa", "lt4_seq.fa", "lt4_sub.fa")),
}
AUDIO = (".sad", ".swd", ".sdat", ".mods", ".csnd", ".cse", ".smd", ".sed")
TEXT_EXT = (".pcm", ".plz", ".dlz", ".cpck", ".cbin", ".cdat", ".gds", ".txt", ".cb")


def _is_text_path(game: dict, path: str) -> bool:
    low = path.lower()
    if not low.endswith(TEXT_EXT):
        return False
    first = path.split("/")[0] if not game["root"] else path.split("/")[1] if "/" in path else ""
    if first not in game["text_dirs"]:
        return False
    if low.endswith(".gds"):
        # the other languages of the multi-language cartridge are not translated into: only the English slot
        return not re.search(r"/(de|es|fr|it|ja)/", "/" + low)
    return f"/{game['lang']}/" in "/" + path or low.endswith(("keys.pcm", "input_txt.plz"))


def _is_font(game: dict, path: str) -> bool:
    low = path.lower()
    code = game["code"]
    if code in (b"LAYTON1", b"LAYTON2"):
        return low.endswith(".nftr")
    if code == b"LAYTON3":
        return low.startswith("lt3/fnt/") and low.endswith(".cfnt")
    return low.startswith("fnt/") and low.endswith((".cf", ".cp", ".ca"))


def _is_picture(game: dict, path: str) -> bool:
    """Every picture and animation file: the language folders hold the translated ones, the others hold the logos,
    credits and screens that carry English text as well."""
    low = path.lower()
    if low.endswith(AUDIO):
        return False
    code = game["code"]
    if code in (b"LAYTON1", b"LAYTON2"):
        return low.endswith((".arc", ".arj")) and ("/bg/" in "/" + path or "/ani/" in "/" + path)
    if code == b"LAYTON3":
        return low.endswith((".cimg", ".cani")) and not low.startswith("lt3/fnt/")
    return low.endswith((".ci", ".ca")) and not low.startswith("fnt/")


def _has_text(path: str, data: bytes) -> bool:
    """A file the plugin shows at least one string of (the rows of ``formats.Document``)."""
    try:
        return len(Document(data, path).texts()) > 0
    except Exception:
        return False


def _gsd1_has_text(plain: bytes) -> bool:
    """A ``GSD1`` script with a string the game shows: referenced by an operand of type 0x18, not Japanese."""
    if plain[:4] != b"GSD1" or len(plain) < 16:
        return False
    entries, _b, ops = struct.unpack_from("<3H", plain, 4)
    first, end = 0x10 + entries * 6 + 2, 0x10 + entries * 6 + 2 + ops * 5
    if end > len(plain):
        return False
    refs = {struct.unpack_from("<I", plain, at + 1)[0] for at in range(first, end, 5) if plain[at] == 0x18}
    table = (end + 3) & ~3
    start = min((v for v in refs if table <= v < len(plain)), default=None)
    if start is None:
        return False
    pos = start
    while pos < len(plain):
        stop = plain.find(b"\0", pos)
        stop = len(plain) if stop < 0 else stop
        raw = plain[pos:stop]
        if pos in refs and raw and not any(b >= 0x80 for b in raw) and re.search(rb"[A-Za-z]", raw):
            return True
        pos = stop + 1
    return False


def _x25(name: bytes) -> int:
    """CRC-16 X-25, the hash of a GFSA folder name."""
    crc = 0xFFFF
    for byte in name:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc ^ 0xFFFF


class _Gfsa:
    """A GFSA archive: ``files`` maps each member path to its (offset in the data, size)."""

    def __init__(self, raw: bytes) -> None:
        if raw[:4] != b"GFSA":
            raise ImageError(tr("a Spectre's Call archive is not a GFSA archive"))
        head = struct.unpack_from("<11I", raw, 0)
        offs, dir_count, file_count = head[1:6], head[6], head[7]
        self.raw, self.data_at = raw, offs[4]
        tables = [raw[offs[i]:offs[i + 1]] for i in range(4)]
        dirs, files, _hash, names = (level5.decompress(table) for table in tables)
        parts = names.split(b"\0")
        dir_names, file_names = parts[:dir_count], parts[dir_count:dir_count + file_count]
        by_hash = {_x25(name): name for name in dir_names}
        folder: Dict[int, bytes] = {}
        for at in range(dir_count):
            hashed, first = struct.unpack_from("<II", dirs, 8 * at)
            name = by_hash.get(hashed & 0xFFFF)
            if name is None:
                raise ImageError(tr("a GFSA archive has a folder without a name"))
            for index in range(first, first + (hashed >> 16)):
                folder[index] = name
        self.files: Dict[str, Tuple[int, int]] = {}
        for index in range(file_count):
            a, b = struct.unpack_from("<II", files, 8 * index)
            offset = ((b >> 16) & 0xFFF) << 18 | (a >> 16) << 2
            size = (b >> 28) << 16 | (b & 0xFFFF)
            member = (folder[index] + file_names[index]).decode("shift-jis")
            self.files[_safe_member(member)] = (offset, size)

    def read(self, member: str) -> bytes:
        offset, size = self.files[member]
        start = self.data_at + offset
        if start + size > len(self.raw):
            raise ImageError(tr("{0} ends after the end of its archive", member))
        return self.raw[start:start + size]


def _safe_member(member: str) -> str:
    """A member path of an archive, each part checked as a file name: no traversal, no device name."""
    for part in member.split("/"):
        check_name(part)
    return member


def _put(target_dir: str, rel: str, data: bytes) -> None:
    out = Path(target_dir).joinpath(*rel.split("/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    with images.open_image(base) as image:
        title = image.read_at(0, 7)
        game = GAMES.get(title)
        if game is None:
            raise ImageError(tr("not a Professor Layton DS ROM (title {0!r})", title))
        if "archives" in game:
            return _extract_archives(image, game, target_dir, progress, is_cancelled)
        taken: List[ImageFile] = []
        for entry in image.entries():
            if _is_text_path(game, entry.path):
                if _has_text(entry.path, image.read(entry)):
                    taken.append(entry)
            elif _is_font(game, entry.path) or _is_picture(game, entry.path):
                taken.append(entry)
        if not images.write_entries(image, taken, target_dir, progress, is_cancelled):
            return None
    return str(target_dir)


def _extract_archives(image, game: dict, target_dir: str, progress, is_cancelled) -> Optional[str]:
    by_path = {entry.path: entry for entry in image.entries()}
    members: Dict[str, List[Tuple[str, _Gfsa]]] = {}
    for name in game["archives"]:
        if name not in by_path:
            raise ImageError(tr("the ROM has no {0}", name))
        archive = _Gfsa(image.read(by_path[name]))
        for member in archive.files:
            members.setdefault(member, []).append((name, archive))
    for number, member in enumerate(sorted(members), 1):
        if is_cancelled():
            return None
        progress(100 * number // len(members), member)
        homes = members[member]
        data = homes[0][1].read(member)
        if _is_text_path(game, member) and not member.lower().endswith(".gds"):
            taken = _gsd1_has_text(level5.decompress(data))
        else:
            taken = _is_font(game, member) or _is_picture(game, member)
        if not taken:
            continue
        if any(other.read(member) != data for _name, other in homes[1:]):
            raise ImageError(tr("{0} differs between {1}", member, ", ".join(name for name, _a in homes)))
        _put(target_dir, member, data)
    return str(target_dir)
