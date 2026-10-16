"""Game images for a plugin's unpack step: recognise a supported image by content, and write its files to a folder.

``identify`` reads only the headers, by content, never by file name. ``extract`` writes the files a plugin asks for, in
the folder layout of the zt scripts' ``source`` folder. NKit GameCube discs are read as they are (the layout is the
same). Nintendo 3DS programs are read when they are decrypted (NoCrypto); encrypted 3DS, Switch and Wii content raises
``ImageError`` from ``core.containers.console_crypto``. GameCube and Wii WIA and RVZ images are read as the plain
disc they hold (``core.containers.wia``; a Wii one needs no key, its partition is stored decrypted); the file is never
converted or written. Formats this module does not read (other NKit kinds) raise ``ImageError`` with the reason.
All functions run on a worker thread: they read and write files, never touch widgets.
"""
from __future__ import annotations

import importlib.util
import os
import struct
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Container, Dict, Iterator, Optional, Sequence

from core.containers import n3ds, switch_crypto, switch_images, wii_disc
from core.containers.console_crypto import encrypted_error, key_path
from core.containers.gcm import GameCubeImage, HEADER_SIZE, is_gamecube_header
from core.containers.image_files import ImageError, ImageFile, ImageReader, copy_range
from core.containers.nds import NdsImage, is_nds_header
from core.containers.wia import WiaStream, is_wia_or_rvz
from core.i18n import tr

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]

KIND_GC = "gc"
KIND_NDS = "nds"
KIND_3DS = "3ds"
KIND_SWITCH = "switch"
KIND_WII = "wii"
CONSOLE_OF_KIND = {KIND_3DS: "3ds", KIND_SWITCH: "switch", KIND_WII: "wii"}
CONSOLE_LABEL = {"3ds": "Nintendo 3DS", "switch": "Nintendo Switch", "wii": "Wii", "oodle": "Oodle library"}
UNPACK_KINDS = frozenset((KIND_GC, KIND_NDS, KIND_3DS, KIND_SWITCH, KIND_WII))   # the kinds an unpack step can read
WII_MAGIC_AT = wii_disc.WII_MAGIC_AT
WII_MAGIC = wii_disc.WII_MAGIC


def _describe(stream: Any, head: bytes) -> Optional[Dict[str, Any]]:
    """``{"kind", "game_id", "encrypted", ...}`` of a supported image, or None. Leaves the stream at offset 0."""
    if is_wia_or_rvz(head):   # the decoded disc's header
        stream.seek(0)
        disc_head = WiaStream(stream).read(HEADER_SIZE)
        stream.seek(0)
        if is_gamecube_header(disc_head):
            return {"kind": KIND_GC, "game_id": disc_head[:6].decode("ascii", "replace"), "encrypted": False,
                    "revision": disc_head[7]}
        found = wii_disc.locate(disc_head)
        if found is not None:   # the image holds the partition decrypted: no key file is needed
            found["encrypted"] = False
        return found
    if is_gamecube_header(head):
        return {"kind": KIND_GC, "game_id": head[:6].decode("ascii", "replace"), "encrypted": False,
                "revision": head[7]}
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
    except (OSError, ValueError, struct.error, MemoryError):   # ImageError is a ValueError: a broken image is not identified
        return None


def unpack_room(path: str | Path) -> int:
    """Bytes an unpack of this image needs beside it: the file, and for a Switch .nsz its decompressed program twice
    (the cache copy, then the extracted files). ponytail: estimated from the NCZ tables, not measured; the real use can
    differ by the size of the ExeFS and the table overhead."""
    size = os.path.getsize(path)
    if (identify(path) or {}).get("kind") != KIND_SWITCH:
        return size
    try:
        with open(path, "rb") as stream:
            return size + 2 * switch_images.ncz_nca_bytes(ImageReader(stream))
    except (OSError, ValueError, struct.error):
        return size


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


def _has_pycryptodome() -> bool:
    """True when the pycryptodome package can be imported; the decrypting readers need it."""
    return importlib.util.find_spec("Crypto") is not None


def _reader(stream: Any, cache_dir: Optional[str | Path] = None,
            is_cancelled: Optional[Cancelled] = None, progress: Optional[Progress] = None) -> ImageReader:
    head = stream.read(HEADER_SIZE)
    stream.seek(0)
    # An NKit GameCube disc keeps the GameCube header and layout, so the GameCube reader reads it as it is.
    if is_gamecube_header(head):
        return GameCubeImage(stream)
    if is_nds_header(head):
        return NdsImage(stream)
    if is_wia_or_rvz(head):   # the decoded disc, read in place: the file is never written
        disc = WiaStream(stream)
        if wii_disc.locate(disc.read(HEADER_SIZE)) is not None:
            return wii_disc.WiiImage(disc, None)
        return GameCubeImage(disc)
    found = _describe(stream, head)
    if found is not None:
        kind = found["kind"]
        encrypted = bool(found.get("encrypted"))
        # A 3DS reader checks its keys before it decrypts, so it refuses a key file with no keys without pycryptodome.
        needs_crypto = kind != KIND_3DS and not _has_pycryptodome()
        if encrypted and (key_path(CONSOLE_OF_KIND[kind]) is None or needs_crypto):
            raise encrypted_error(CONSOLE_OF_KIND[kind], tr(CONSOLE_LABEL[kind]))
        if kind == KIND_3DS:   # the reader loads the key file only for encrypted content
            return n3ds.N3dsImage(stream, key_path("3ds"))
        if kind == KIND_WII and encrypted:
            return wii_disc.WiiImage(stream, wii_disc.load_common_key(str(key_path("wii"))))
        if kind == KIND_SWITCH and encrypted:   # an .xci is refused by the reader with its reason
            keys = switch_crypto.load_keys(str(key_path("switch")))
            return switch_images.SwitchImage(stream, keys, cache_dir, is_cancelled, progress)
    if len(head) >= 0x204 and head[0x200:0x204] == b"NKIT":
        raise ImageError("an NKit image of an unknown kind: convert it to a plain ISO first")
    raise ImageError("not a GameCube or Nintendo DS image")


@contextmanager
def open_image(path: str | Path, cache_dir: Optional[str | Path] = None,
               is_cancelled: Optional[Cancelled] = None, progress: Optional[Progress] = None) -> Iterator[ImageReader]:
    """The reader of a supported image, open for the ``with`` block. Raises ImageError for anything else.

    ``cache_dir`` holds the decompressed copy of a Switch .nsz program; the copy is deleted when the block ends.
    ``is_cancelled`` stops that decompression and ``progress`` reports it.
    """
    with open(path, "rb") as stream:
        reader = _reader(stream, cache_dir, is_cancelled, progress)
        try:
            yield reader
        finally:
            if isinstance(reader, switch_images.SwitchImage):
                reader.close()


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
                if not copy_range(reader.source(entry), entry.offset, entry.size, out, is_cancelled, on_bytes):
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
    with open_image(path, target_dir, is_cancelled, progress) as reader:   # an .nsz is decompressed into target_dir
        entries = [entry for entry in reader.entries() if select is None or select(entry.path)]
        if is_cancelled() or not write_entries(reader, entries, target_dir, progress, is_cancelled):
            return None
    return str(target_dir)
