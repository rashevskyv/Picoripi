"""Build the Zone of the Enders: The 2nd Runner PlayStation 2 disc image: changed stage scripts written into STAGE.DAT.

The output is a copy of the disc image. A changed stage is packed again from the translated script. It stays where it is
when it still fits the sectors the stage had; otherwise it is appended to the end of STAGE.DAT and the stage list points
there. STAGE.DAT has no free sectors after it on the disc, so a STAGE.DAT that grows is copied to the end of the image
and the directory record (extent and size) and the volume size follow. Nothing else changes. A build without changes is a
copy, byte for byte.
"""
import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from core.containers.image_files import ImageError
from core.i18n import tr
from plugins.common import romfs_mod
from plugins.okami_ps2 import iso
from plugins.zoe2_ps2 import disc, stagedat
from plugins.zoe2_ps2.unpack import REF_NAME, SCRIPT_DIR, SCRIPT_SUFFIX, find_script
from utils.logging_utils import log_warning

COPY_CHUNK = 8 * 1024 * 1024
IMAGE_NAME = "Zone of the Enders - The 2nd Runner (USA) Ukrainian.iso"
SECTOR = disc.SECTOR


def read_changes(source_dir: str, translation_dir: str) -> Dict[str, bytes]:
    """``{stage name: script bytes}`` of the translation scripts that differ from the unpacked source."""
    out: Dict[str, bytes] = {}
    for rel, data in romfs_mod.changed_files(source_dir, translation_dir).items():
        folder, _, name = rel.partition("/")
        if folder != SCRIPT_DIR or not name.endswith(SCRIPT_SUFFIX) or "/" in name:
            log_warning(f"zoe2_ps2: {rel} is not a stage script; it is not written")
            continue
        out[name[:-len(SCRIPT_SUFFIX)]] = data
    return out


def _copy(source: str, target: str, progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> None:
    total = os.path.getsize(source)
    done = 0
    with open(source, "rb") as src, open(target, "wb") as out:
        while True:
            if is_cancelled():
                raise InterruptedError()
            chunk = src.read(COPY_CHUNK)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            progress(100 * done // max(1, total), tr("Copying the disc image"))


def _room_bytes(extents: List[Tuple[int, int]], lba: int, volume: int) -> int:
    """The bytes from sector ``lba`` up to the next used sector of the disc (or the end of the volume)."""
    starts = [start for start, _count in extents if start > lba]
    return ((min(starts) if starts else volume) - lba) * SECTOR


def new_stage(read, toc: stagedat.Toc, name: str, sector: int, script: bytes) -> bytes:
    """The stored bytes of stage ``name`` with its script replaced."""
    stage = stagedat.parse_stage(read, toc, name, sector)
    found = find_script(stage)
    if found is None:
        raise ImageError(tr("The stage {0} has no script.", name))
    gi, mi = found
    group = stage.groups[gi]
    parts = stagedat.split_members(stagedat.group_data(read, stage, group), group)
    parts[mi] = script
    return stagedat.stage_bytes(read, toc, stage, {gi: parts})


def build_image(source_image: str, changes: Dict[str, bytes], output_path: str,
                progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """Write the disc image with the stage scripts of ``changes`` to ``output_path``."""
    _copy(source_image, output_path, progress, is_cancelled)
    if not changes:
        return output_path
    with open(source_image, "rb") as src, open(output_path, "r+b") as out:
        entry = disc.find_path(src, disc.STAGE_PATH)
        record = disc.record_of(src, disc.STAGE_PATH)
        if entry is None or record is None:
            raise ImageError(tr("The disc has no {0}.", disc.STAGE_PATH))
        read = disc.file_reader(src, entry)
        toc = stagedat.read_toc(read)
        names = [name for name, _sector in toc.stages]
        starts = sorted({sector for _name, sector in toc.stages} | {entry.size // SECTOR})
        in_place: Dict[int, bytes] = {}                  # first sector -> stored stage
        appended: List[Tuple[int, bytes]] = []           # (position in the stage list, stored stage)
        for name, script in changes.items():
            if name not in names:
                raise ImageError(tr("The disc has no stage {0}.", name))
            position = names.index(name)
            sector = toc.stages[position][1]
            stored = new_stage(read, toc, name, sector, script)
            room = starts[starts.index(sector) + 1] - sector
            if len(stored) // SECTOR <= room:
                in_place[sector] = stored
            else:
                appended.append((position, stored))
        grown = sum(len(stored) // SECTOR for _p, stored in appended)
        size = entry.size + grown * SECTOR
        lba = entry.lba
        if grown:
            extents = iso.used_extents(src)
            volume = iso.volume_sectors(src)
            if size > _room_bytes(extents, entry.lba, volume):
                lba = volume
                disc.copy_range(src, entry.lba * SECTOR, entry.size, out, lba * SECTOR, is_cancelled)
                iso.write_volume_sectors(out, volume + size // SECTOR)
        for sector, stored in in_place.items():
            out.seek(lba * SECTOR + sector * SECTOR)
            out.write(stored)
        sectors: Dict[int, int] = {}
        cursor = entry.size // SECTOR
        for position, stored in appended:
            out.seek(lba * SECTOR + cursor * SECTOR)
            out.write(stored)
            sectors[position] = cursor
            cursor += len(stored) // SECTOR
        if sectors:
            out.seek(lba * SECTOR + 4)
            out.write(stagedat.toc_with_sectors(read, toc, sectors))
        if lba != entry.lba or size != entry.size:
            iso.write_extent(out, record[0], lba, size)
        progress(100, tr("Writing {0}", disc.STAGE_PATH))
    return output_path


def build_ps2(source_dir: str, translation_dir: str, output_dir: str,
              progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """The disc image of the translation, written into ``output_dir``; returns its path."""
    ref = Path(source_dir, REF_NAME)
    if not ref.is_file():
        raise ValueError(tr("The unpacked folder has no {0}: unpack the disc again.", REF_NAME))
    image = json.loads(ref.read_text(encoding="utf-8")).get("image", "")
    if not os.path.isfile(image):
        raise ValueError(tr("The disc image {0} is not on disk.", image))
    changes = read_changes(source_dir, translation_dir)
    return build_image(image, changes, os.path.join(output_dir, IMAGE_NAME), progress, is_cancelled)
