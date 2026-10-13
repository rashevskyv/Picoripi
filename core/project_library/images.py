"""Game images for a plugin's unpack step: recognise a supported image by content, and write its files to a folder.

``identify`` reads only the headers, by content, never by file name. ``extract`` writes the files a plugin asks for, in
the folder layout of the zt scripts' ``source`` folder. NKit GameCube discs are read as they are (the layout is the
same). Nintendo 3DS programs are read when they are decrypted (NoCrypto); encrypted 3DS, Switch and Wii content raises
``ImageError`` from ``core.containers.console_crypto``. Formats this module does not read (RVZ, WIA, other NKit
kinds) raise ``ImageError`` with the reason: a plugin reports it, and never converts an image.
All functions run on a worker thread: they read and write files, never touch widgets.
"""
from __future__ import annotations

import struct
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Container, Dict, Iterator, Optional, Sequence

from core.containers import n3ds, switch_images, wii_disc
from core.containers.console_crypto import encrypted_error
from core.containers.gcm import GameCubeImage, HEADER_SIZE, is_gamecube_header
from core.containers.image_files import ImageError, ImageFile, ImageReader, copy_range
from core.containers.nds import NdsImage, is_nds_header
from core.i18n import tr

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]

KIND_GC = "gc"
KIND_NDS = "nds"
KIND_3DS = "3ds"
KIND_SWITCH = "switch"
KIND_WII = "wii"
CONSOLE_OF_KIND = {KIND_3DS: "3ds", KIND_SWITCH: "switch", KIND_WII: "wii"}
CONSOLE_LABEL = {"3ds": "Nintendo 3DS", "switch": "Nintendo Switch", "wii": "Wii"}
UNPACK_KINDS = frozenset((KIND_GC, KIND_NDS, KIND_3DS))   # the kinds an unpack step can write today
WII_MAGIC_AT = wii_disc.WII_MAGIC_AT
WII_MAGIC = wii_disc.WII_MAGIC
_UNSUPPORTED = {
    b"RVZ\x01": "an RVZ image: convert it to a plain ISO first",
    b"WIA\x01": "a WIA image: convert it to a plain ISO first",
}


def _describe(stream: Any, head: bytes) -> Optional[Dict[str, Any]]:
    """``{"kind", "game_id", "encrypted", ...}`` of a supported image, or None. Leaves the stream at offset 0."""
    if is_gamecube_header(head):
        return {"kind": KIND_GC, "game_id": head[:6].decode("ascii", "replace"), "encrypted": False}
    if is_nds_header(head):
        return {"kind": KIND_NDS, "game_id": head[0x0C:0x10].decode("ascii", "replace"), "encrypted": False}
    found = wii_disc.locate(head)
    if found is None:
        reader = ImageReader(stream)
        stream.seek(0)
        program = n3ds.locate(reader, head)
        found = n3ds.identify_fields(program) if program is not None else switch_images.locate(reader, head)
        stream.seek(0)
    return found


def identify(path: str | Path) -> Optional[Dict[str, Any]]:
    """The fields of a supported image (``kind``, ``game_id``, ``encrypted``, ``title_id``), or None for any other file."""
    try:
        with open(path, "rb") as stream:
            return _describe(stream, stream.read(HEADER_SIZE))
    except (OSError, ValueError, struct.error):   # ImageError is a ValueError: a broken image is not identified
        return None


def base_identity(path: str | Path, game_codes: Container[str]) -> Optional[Dict[str, str]]:
    """``{"role": "base", "platform": <kind>}`` when ``path`` is an image of one of ``game_codes``."""
    found = identify(path)
    if found is None or found["game_id"] not in game_codes:
        return None
    return {"role": "base", "platform": found["kind"]}


def needs_key(path: str | Path) -> Optional[str]:
    """The console whose key file an image needs, or None when it needs none or is not a supported image.

    Only a kind an unpack step can write (``UNPACK_KINDS``) asks for a key. A Switch or Wii file that no
    plugin unpacks yet asks for none.
    """
    found = identify(path)
    if found is None or not found.get("encrypted") or found["kind"] not in UNPACK_KINDS:
        return None
    return CONSOLE_OF_KIND.get(found["kind"])


def _reader(stream: Any) -> ImageReader:
    head = stream.read(HEADER_SIZE)
    stream.seek(0)
    # An NKit GameCube disc keeps the GameCube header and layout, so the GameCube reader reads it as it is.
    if is_gamecube_header(head):
        return GameCubeImage(stream)
    if is_nds_header(head):
        return NdsImage(stream)
    found = _describe(stream, head)
    if found is not None:
        if found["kind"] == KIND_3DS:
            return n3ds.N3dsImage(stream)   # raises the encrypted error itself for encrypted content
        if found.get("encrypted"):
            kind = found["kind"]
            raise encrypted_error(CONSOLE_OF_KIND[kind], tr(CONSOLE_LABEL[kind]))
    for magic, reason in _UNSUPPORTED.items():
        if head.startswith(magic):
            raise ImageError(f"Picoripi cannot read {reason}")
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
            if entry.decode is None:
                if not copy_range(reader.stream, entry.offset, entry.size, out, is_cancelled, on_bytes):
                    return False
            else:
                out.write(entry.decode(reader.read(entry)))   # a whole entry: a decoded code section is not streamed
                on_bytes(entry.size)
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
