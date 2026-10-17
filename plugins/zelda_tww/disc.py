"""The Wind Waker (GameCube) disc: write a playable ISO from the unpacked tree and the translation.

The unpacked tree holds ``sys/`` (boot.bin, bi2.bin, apploader.img, fst.bin, main.dol) and ``files/`` (every
file the FST names). The image is written from scratch, in this order: the header, bi2, the apploader, main.dol,
fst.bin with new file offsets, then every file in FST order, each on a 0x800 boundary. A translated file replaces
the source file of the same name. Unlike the workspace's ``gc.py``, no original ``.iso`` is needed.
"""
import shutil
import struct
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

SECTOR = 0x800
HEADER_SIZE = 0x440
BI2_SIZE = 0x2000
APPLOADER_AT = 0x2440
DOL_ALIGN = 0x100
COPY_BUFFER = 1024 * 1024

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def _align(value: int, unit: int) -> int:
    return (value + unit - 1) // unit * unit


def file_entries(fst: bytes) -> List[Tuple[int, str]]:
    """``(FST entry index, "files/<path>")`` of every file in the FST, in FST order."""
    count = struct.unpack_from(">I", fst, 8)[0]
    names = count * 12
    found: List[Tuple[int, str]] = []

    def name_of(index: int) -> str:
        word = struct.unpack_from(">I", fst, index * 12)[0]
        start = names + (word & 0xFFFFFF)
        return fst[start:fst.index(b"\0", start)].decode("shift_jis", "replace")

    def walk(first: int, end: int, prefix: str) -> None:
        index = first
        while index < end:
            word, _offset, next_index = struct.unpack_from(">III", fst, index * 12)
            if word >> 24:
                walk(index + 1, next_index, prefix + name_of(index) + "/")
                index = next_index
            else:
                found.append((index, prefix + name_of(index)))
                index += 1

    walk(1, count, "files/")
    return found


def read_files(iso: bytes) -> Dict[str, bytes]:
    """``{"files/<path>": data}`` of a GameCube image, from its FST (used to check a built image)."""
    fst_off, fst_size = struct.unpack_from(">II", iso, 0x424)
    fst = iso[fst_off:fst_off + fst_size]
    result = {}
    for index, rel in file_entries(fst):
        offset, size = struct.unpack_from(">II", fst, index * 12 + 4)
        result[rel] = iso[offset:offset + size]
    return result


def _pick(rel: str, source: Path, translation: Optional[Path]) -> Path:
    """The translated copy of ``rel`` when the translation has one, else the source copy."""
    if translation is not None and (translation / rel).is_file():
        return translation / rel
    return source / rel


def build_disc(source: Path, translation: Optional[Path], out: Path, translated_dol: bool,
               progress: Progress, is_cancelled: Cancelled) -> None:
    """Write the disc image ``out`` from ``source`` (sys\\ and files\\) with ``translation`` over it.

    ``translated_dol`` takes ``sys/main.dol`` from the translation too. A DOL of another size than the source
    is refused, because the messages and the font inside it change in place. Returns early (no complete image)
    when ``is_cancelled()`` turns true; the caller then discards the output folder.
    """
    sys_dir = source / "sys"
    boot = bytearray((sys_dir / "boot.bin").read_bytes())
    if len(boot) < HEADER_SIZE:
        raise ValueError("sys/boot.bin is too short")
    bi2 = (sys_dir / "bi2.bin").read_bytes()
    if len(bi2) > BI2_SIZE:
        raise ValueError("sys/bi2.bin is too long")
    apploader = (sys_dir / "apploader.img").read_bytes()
    fst = bytearray((sys_dir / "fst.bin").read_bytes())

    dol_source = sys_dir / "main.dol"
    dol_path = dol_source
    if translated_dol and translation is not None and (translation / "sys" / "main.dol").is_file():
        dol_path = translation / "sys" / "main.dol"
        if dol_path.stat().st_size != dol_source.stat().st_size:
            raise ValueError("sys/main.dol changed its size; such a file cannot be built into the disc")
    dol_size = dol_path.stat().st_size

    entries = file_entries(bytes(fst))
    paths = {rel: _pick(rel, source, translation) for _index, rel in entries}
    position = APPLOADER_AT + len(apploader)
    dol_off = _align(position, DOL_ALIGN)
    position = dol_off + dol_size
    fst_off = _align(position, DOL_ALIGN)
    position = fst_off + len(fst)
    placed: Dict[int, Tuple[int, int]] = {}
    for index, rel in entries:
        size = paths[rel].stat().st_size
        offset = _align(position, SECTOR)
        placed[index] = (offset, size)
        position = offset + size
    for index, (offset, size) in placed.items():
        struct.pack_into(">II", fst, index * 12 + 4, offset, size)
    struct.pack_into(">II", boot, 0x420, dol_off, fst_off)
    struct.pack_into(">I", boot, 0x428, len(fst))

    total = len(entries)
    with open(out, "wb") as stream:
        stream.write(bytes(boot[:HEADER_SIZE]))
        stream.write(bi2.ljust(BI2_SIZE, b"\0"))
        stream.write(apploader)
        _pad_to(stream, dol_off)
        _copy(stream, dol_path)
        _pad_to(stream, fst_off)
        stream.write(bytes(fst))
        for done, (index, rel) in enumerate(entries, start=1):
            if is_cancelled():
                return
            _pad_to(stream, placed[index][0])
            _copy(stream, paths[rel])
            progress(100 * done // max(1, total), rel)


def _pad_to(stream, offset: int) -> None:
    gap = offset - stream.tell()
    if gap < 0:
        raise ValueError("disc layout overlaps itself")
    stream.write(b"\0" * gap)


def _copy(stream, path: Path) -> None:
    with open(path, "rb") as source:
        shutil.copyfileobj(source, stream, COPY_BUFFER)
