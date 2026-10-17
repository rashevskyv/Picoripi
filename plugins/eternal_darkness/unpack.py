"""The files the unpack step takes from Eternal Darkness: Sanity's Requiem (GameCube, USA): the same set as zt/ed.py.

The disc's ``files/`` folder is written without that prefix, so ``source\\game\\`` is the disc's file tree:
the *SK_ASC* files (RmTxt*.cmp, E*Menu.cmp, EInsane.cmp, credits\\*.cmp, Chars\\cin*\\cin*.bin) decompressed
(``edasc``: the u32 size prefix is dropped), the plain text, font and texture files (EBootPak.bin, EBookPak.bin,
EMemcardText.bin, *.tpl, Chars\\*.tpl) as they are, and ``sys/main.dol``.
"""
from core.i18n import tr
import fnmatch
import struct
from pathlib import Path
from typing import Callable, List, Optional

from core.containers import edasc
from core.containers.image_files import ImageFile
from core.project_library import images

FILES = "files/"
DOL = "sys/main.dol"
# Patterns match one path segment each, as zt's Path.glob does: "*.tpl" is the top folder only.
PACKED = ("RmTxt*.cmp", "E*Menu.cmp", "EInsane.cmp", "credits/*.cmp", "Chars/cin*/cin*.bin")
PLAIN = ("EBootPak.bin", "EBookPak.bin", "EMemcardText.bin", "*.tpl", "Chars/*.tpl")


def _matches(rel: str, patterns: tuple) -> bool:
    parts = rel.split("/")
    for pattern in patterns:
        wanted = pattern.split("/")
        if len(wanted) == len(parts) and all(fnmatch.fnmatchcase(p, w) for p, w in zip(parts, wanted)):
            return True
    return False


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    game = Path(target_dir)
    with images.open_image(base) as image:
        plain: List[ImageFile] = []
        packed: List[ImageFile] = []
        for entry in image.entries():
            if entry.path == DOL:
                plain.append(entry)
            elif entry.path.startswith(FILES):
                rel = entry.path[len(FILES):]
                if _matches(rel, PACKED):
                    packed.append(entry._replace(path=rel))
                elif _matches(rel, PLAIN):
                    plain.append(entry._replace(path=rel))
        if not images.write_entries(image, plain, target_dir, progress, is_cancelled):
            return None
        for index, entry in enumerate(packed):
            if is_cancelled():
                return None
            progress(100 * index // len(packed), entry.path)
            data = image.read(entry)
            if data[:len(edasc.MAGIC)] != edasc.MAGIC:
                continue
            body = edasc.decompress(data, is_cancelled)
            if body is None:
                return None
            if struct.unpack_from(">I", body, 0)[0] != len(body) - 4:
                raise ValueError(tr("{0}: the size after decompression does not match", entry.path))
            out_path = game.joinpath(*entry.path.split("/"))
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(body[4:])
    progress(100, "")
    return str(target_dir)
