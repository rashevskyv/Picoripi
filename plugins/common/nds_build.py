"""Builds a translated Nintendo DS cartridge image from a Picoripi project (Pokémon generation IV and V).

The unpack keeps a copy of the clean image in the source folder (``rom/base.nds``). The build reads the edited files of
the translation folder: a message bank under ``text/<narc folder>/NNNN.msg`` goes into its NARC member; any other file
of the translation folder replaces the NitroFS file of the same path. ``core.containers.nds_write`` and
``narc_write`` lay the image out again and write the header CRC. Nothing edited gives the clean image back.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Optional

from core.containers import narc_write, nds_write
from core.containers.narc_members import narc_members
from utils.atomic_io import atomic_write_bytes

BASE_ROM = Path("rom") / "base.nds"
UNIT_CODE_AT = 0x12
DSI_AREA = slice(0x180, 0x4000)


class NdsBuildError(ValueError):
    """A translation file the build cannot put into the image."""


def store_base_rom(base_path: str, source_dir: Path) -> None:
    """Copy the clean image into the source folder (read by the build later)."""
    target = source_dir / BASE_ROM
    target.parent.mkdir(parents=True, exist_ok=True)
    if not (target.is_file() and target.stat().st_size == Path(base_path).stat().st_size):
        shutil.copyfile(base_path, target)


def _to_ds_mode(image: bytes) -> bytes:
    """A DSi-enhanced dump: its DSi digest tables sit behind the NitroFS and do not survive an edit. The build is a plain
    NDS image (unit code 0), like the zt build did; every other patched Pokémon ROM boots in NDS mode the same way."""
    built = bytearray(image)
    built[UNIT_CODE_AT] = 0
    built[DSI_AREA] = bytes(DSI_AREA.stop - DSI_AREA.start)
    built[0x15E:0x160] = nds_write.crc16(bytes(built[:0x15E])).to_bytes(2, "little")
    return bytes(built)


def build_text_rom(source_dir: str, translation_dir: str, *, narc_of_folder: Callable[[str], str],
                   is_text: Callable[[bytes], bool], progress: Optional[Callable[[int, str], None]] = None,
                   is_cancelled: Callable[[], bool] = lambda: False) -> bytes:
    """The clean image of ``source_dir`` with the edited files of ``translation_dir`` put in."""
    source, translation = Path(source_dir), Path(translation_dir)
    base_path = source / BASE_ROM
    if not base_path.is_file():
        raise NdsBuildError(f"no clean image in the source folder: {base_path}")
    base = base_path.read_bytes()
    files = nds_write.nitro_files(base)
    narcs: dict = {}
    replace: dict = {}
    edited = [p for p in sorted(translation.rglob("*")) if p.is_file() and not p.name.endswith((".tmp", ".bak"))]
    for number, path in enumerate(edited, 1):
        if is_cancelled():
            raise NdsBuildError("the build was cancelled")
        if progress:
            progress(100 * number // max(1, len(edited)), path.name)
        rel = path.relative_to(translation).as_posix()
        data = path.read_bytes()
        original = source / rel
        if original.is_file() and original.read_bytes() == data:
            continue
        if rel.startswith("text/"):
            folder, name = rel[len("text/"):].split("/", 1)
            narc_name = narc_of_folder(folder)
            if narc_name not in files:
                raise NdsBuildError(f"{rel}: the game has no archive {narc_name}")
            if not is_text(data):
                raise NdsBuildError(f"{rel}: not a message bank of this game")
            index = int(Path(name).stem)
            if narc_name not in narcs:
                narcs[narc_name] = narc_members(files[narc_name])
            members = narcs[narc_name]
            if not 0 <= index < len(members):
                raise NdsBuildError(f"{rel}: the archive {narc_name} has {len(members)} members")
            members[index] = data
        elif rel in files:
            replace[rel] = data
        else:
            raise NdsBuildError(f"{rel}: no such file in the game")
    for name, members in narcs.items():
        replace[name] = narc_write.narc_rebuild(files[name], members)
    if not replace:
        return base
    built = nds_write.rebuild_nds(base, replace)
    if base[UNIT_CODE_AT]:
        built = _to_ds_mode(built)
    nds_write.check_header(built)
    check = nds_write.nitro_files(built)
    bad = [rel for rel, data in replace.items() if check[rel] != data]
    if bad:
        raise NdsBuildError("the built image does not read back: " + ", ".join(bad))
    return built


def write_rom(path: Path, data: bytes) -> None:
    atomic_write_bytes(str(path), data)
