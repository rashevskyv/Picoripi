"""The files the unpack step takes from Phantom Hourglass and Spirit Tracks (DS, USA): the same set as zt/zelda_ds.py.

Text: the BMG files under ``English/Message/`` and ``staff.bmg``. Fonts: ``Font/*.nftr``. Pictures: the NCGR and NCLR
files, found by their content. A Download Play child program (a ``.srl`` with its own file system) gives its pictures
under ``_children/<program>/``; the program file itself is not kept.
"""
import io
import struct
from typing import Callable, Optional

from core.containers.image_files import ImageFile
from core.containers.nds import ARM9_NAME, NdsImage
from core.project_library import images
from plugins.zelda_ds import pictures

TEXT_DIR = "English/Message/"
TEXT_ROOT = ("staff.bmg",)   # Spirit Tracks keeps its credits next to the language folders
CHILD_DIR = "_children/"


def _is_text(path: str) -> bool:
    return (path.startswith(TEXT_DIR) and path.lower().endswith(".bmg")) or path in TEXT_ROOT


def _is_font(path: str) -> bool:
    return path.startswith("Font/") and path.lower().endswith(".nftr")


def _is_picture(path: str, data: bytes) -> bool:
    if path.lower().endswith((".bin", ".ncgr", ".nclr")) or bytes(data[:4]) in (b"RGCN", b"RLCN"):
        return pictures.is_picture_file(data)
    return False


def _child_program(data: bytes) -> Optional[NdsImage]:
    """The Download Play child program in ``data``, or None when it has no readable file system."""
    try:
        child = NdsImage(io.BytesIO(data))
        child.entries()
    except (ValueError, IndexError, struct.error):
        return None
    return child


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    with images.open_image(base) as image:
        top, children = [], []
        for entry in image.entries():
            if entry.path == ARM9_NAME:
                continue
            if _is_text(entry.path) or _is_font(entry.path):
                top.append(entry)
            elif entry.path.lower().endswith(".srl"):
                children.append(entry)
            elif _is_picture(entry.path, image.read(entry)):
                top.append(entry)
        if not images.write_entries(image, top, target_dir, progress, is_cancelled):
            return None
        for entry in children:
            child = _child_program(image.read(entry))
            if child is None:
                continue
            found: list[ImageFile] = [
                child_entry._replace(path=f"{CHILD_DIR}{entry.path}/{child_entry.path}")
                for child_entry in child.entries()
                if child_entry.path != ARM9_NAME and _is_picture(child_entry.path, child.read(child_entry))
            ]
            if not images.write_entries(child, found, target_dir, lambda *_: None, is_cancelled):
                return None
    return str(target_dir)
