"""Game images for a plugin's unpack step: recognise a GameCube or Nintendo DS image, and write its files to a folder.

``identify`` reads only the first 0x440 bytes, by content, never by file name. ``extract`` writes the files a plugin
asks for, in the folder layout of the zt scripts' ``source`` folder. NKit GameCube discs are read as they are (the
layout is the same). Formats this module does not read (RVZ, WIA, Wii, NKit of other kinds) raise ``ImageError``
with the reason: a plugin reports it, and never converts an image.
All functions run on a worker thread: they read and write files, never touch widgets.
"""
from __future__ import annotations

import struct
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Container, Dict, Iterator, Optional, Sequence

from core.containers.gcm import GameCubeImage, HEADER_SIZE, is_gamecube_header
from core.containers.image_files import ImageError, ImageFile, ImageReader, copy_range
from core.containers.nds import NdsImage, is_nds_header

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]

KIND_GC = "gc"
KIND_NDS = "nds"
WII_MAGIC_AT = 0x18          # a Wii disc keeps its magic here; a GameCube disc keeps its magic at 0x1C
WII_MAGIC = 0x5D1C9EA3
_UNSUPPORTED = {
    b"RVZ\x01": "an RVZ image: convert it to a plain ISO first",
    b"WIA\x01": "a WIA image: convert it to a plain ISO first",
}


def identify(path: str | Path) -> Optional[Dict[str, str]]:
    """``{"kind": "gc" | "nds", "game_id": ...}`` for a supported image, or None for any other file."""
    try:
        with open(path, "rb") as stream:
            head = stream.read(HEADER_SIZE)
    except OSError:
        return None
    if is_gamecube_header(head):
        return {"kind": KIND_GC, "game_id": head[:6].decode("ascii", "replace")}
    if is_nds_header(head):
        return {"kind": KIND_NDS, "game_id": head[0x0C:0x10].decode("ascii", "replace")}
    return None


def base_identity(path: str | Path, game_codes: Container[str]) -> Optional[Dict[str, str]]:
    """``{"role": "base", "platform": "gc" | "nds"}`` when ``path`` is an image of one of ``game_codes``."""
    found = identify(path)
    if found is None or found["game_id"] not in game_codes:
        return None
    return {"role": "base", "platform": found["kind"]}


def _reader(stream: Any) -> ImageReader:
    head = stream.read(HEADER_SIZE)
    stream.seek(0)
    # An NKit GameCube disc keeps the GameCube header and layout, so the GameCube reader reads it as it is.
    if is_gamecube_header(head):
        return GameCubeImage(stream)
    if is_nds_header(head):
        return NdsImage(stream)
    for magic, reason in _UNSUPPORTED.items():
        if head.startswith(magic):
            raise ImageError(f"Picoripi cannot read {reason}")
    if len(head) >= HEADER_SIZE and struct.unpack_from(">I", head, WII_MAGIC_AT)[0] == WII_MAGIC:
        raise ImageError("a Wii image: Picoripi does not read Wii images yet")
    if len(head) >= 0x204 and head[0x200:0x204] == b"NKIT":
        raise ImageError("an NKit image of an unknown kind: convert it to a plain ISO first")
    raise ImageError("not a GameCube or Nintendo DS image")


@contextmanager
def open_image(path: str | Path) -> Iterator[ImageReader]:
    """The reader of a supported image, open for the ``with`` block. Raises ImageError for anything else."""
    with open(path, "rb") as stream:
        yield _reader(stream)


def write_entries(reader: ImageReader, entries: Sequence[ImageFile], target_dir: str | Path,
                  progress: Progress, is_cancelled: Cancelled) -> bool:
    """Write ``entries`` under ``target_dir`` (created when missing). False when cancelled; the folder is then partial."""
    target = Path(target_dir)
    total = sum(entry.size for entry in entries) or 1
    done = 0

    def on_bytes(count: int) -> None:
        nonlocal done
        done += count
        progress(min(99, 100 * done // total), entry.path)

    for entry in entries:
        if is_cancelled():
            return False
        out_path = target.joinpath(*entry.path.split("/"))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as out:
            if not copy_range(reader.stream, entry.offset, entry.size, out, is_cancelled, on_bytes):
                return False
    progress(100, "")
    return True


def extract(path: str | Path, target_dir: str | Path, progress: Progress, is_cancelled: Cancelled,
            select: Optional[Callable[[str], bool]] = None) -> Optional[str]:
    """Write the files of the image ``path`` that ``select`` takes (all when None) into ``target_dir``.

    Returns ``target_dir``, or None when the user cancelled. Raises ImageError for an unsupported or broken image.
    """
    with open_image(path) as reader:
        entries = [entry for entry in reader.entries() if select is None or select(entry.path)]
        if not write_entries(reader, entries, target_dir, progress, is_cancelled):
            return None
    return str(target_dir)
