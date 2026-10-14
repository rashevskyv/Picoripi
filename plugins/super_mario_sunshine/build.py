"""Build targets of Super Mario Sunshine: a GameCube disc image (``gc_iso``) and the PC/Switch port pack (``port_pack``).

The source folder is the whole disc as ``images.extract`` writes it (``sys/`` and ``files/``). The disc itself is
never changed: ``unpack_sources`` records its path in ``.picoripi_disc.json`` and the ISO build copies it through
``write_disc``. The translation folder holds only the files that were saved; every one of them must exist in the
source, so no file is added to the disc. An archive (``.szs``) is replaced as a whole. The port pack writes only the
archive members that changed, under ``files/<disc path of the archive>/<member>``: the port's overlay rule.
"""
import json
import os
from pathlib import Path
from typing import Callable, Dict, Optional

from core.containers import ContainerManager
from core.containers.gcm_writer import write_disc
from core.i18n import tr
from . import dol_patch

SOURCE_MARK = ".picoripi_disc.json"
ISO_NAME = "Super Mario Sunshine (UA).iso"
PACK_README = """Super Mario Sunshine: Ukrainian text (uk), an overlay for the PC and Switch ports.

The pack holds only the files that changed. Each file goes where the disc keeps it. A folder named after an archive
(for example files/data/scene/mare0.szs/map/message.bmg) replaces the file inside that archive.

PC port (sms-pc-port):
  1. Copy the mods folder next to the port's settings file, so that mods/uk/files exists.
  2. In settings.txt set:  mod = uk
  3. Use a stock GMSE01 image (any .iso that the port reads). The pack does not change the disc.

Switch port (sms-switch):
  1. Copy the mods folder to sdmc:/switch/sms/mods/uk, so that the files sit in sdmc:/switch/sms/mods/uk/files.
  2. In sdmc:/switch/sms/settings.txt set:  mod = uk

The main.dol (game code) is not part of this pack: the ports do not read it from the disc.
"""

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def write_source_mark(source_dir: str | os.PathLike, image: str | os.PathLike) -> None:
    """Record the disc the source was unpacked from, so the build can copy it. Written atomically."""
    path = Path(source_dir) / SOURCE_MARK
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"image": os.path.abspath(str(image)), "size": os.path.getsize(image)}, indent=1),
                   encoding="utf-8")
    os.replace(tmp, path)


def disc_of_source(source_dir: str | os.PathLike) -> Path:
    """The disc the source was unpacked from. Raises ValueError when the mark is missing or the disc changed size."""
    mark = Path(source_dir) / SOURCE_MARK
    if not mark.is_file():
        raise ValueError(tr("The source folder has no disc record: unpack the disc again."))
    record = json.loads(mark.read_text(encoding="utf-8"))
    image = Path(record["image"])
    if not image.is_file() or image.stat().st_size != record["size"]:
        raise ValueError(tr("The disc image is missing or changed: {0}", str(image)))
    return image


def _section(data: bytes, name: bytes) -> Optional[bytes]:
    """The bytes of the BMG section ``name`` (INF1, DAT1 ...), or None."""
    offset = 0x20
    while offset + 8 <= len(data):
        magic = data[offset:offset + 4]
        length = int.from_bytes(data[offset + 4:offset + 8], "big")
        if length == 0 or offset + length > len(data):
            return None
        if magic == name:
            return data[offset:offset + length]
        offset += length
    return None


def _member_changes(base: bytes, new: bytes, archive: str) -> Dict[str, bytes]:
    """The members of the archive ``new`` that differ from ``base``. A member may not be added, and a BMG keeps its INF1.

    INF1 holds the attributes of each message (box type, speaker and so on). The BMG save path does not reproduce
    every INF1 layout byte for byte (four Shift-JIS files in pinnaBeach*.szs), so a change to INF1 is refused.
    """
    base_container = ContainerManager.open(base)
    new_container = ContainerManager.open(new)
    if base_container is None or new_container is None:
        raise ValueError(tr("{0}: not an archive Picoripi can read", archive))
    names = set(base_container.list_files())
    changed: Dict[str, bytes] = {}
    for name in new_container.list_files():
        if name not in names:
            raise ValueError(tr("{0}: the archive holds no member {1} (new files are not written)", archive, name))
        data = new_container.read_file(name)
        old = base_container.read_file(name)
        if data == old:
            continue
        if name.lower().endswith(".bmg") and _section(data, b"INF1") != _section(old, b"INF1"):
            raise ValueError(tr("{0}/{1}: the message attributes (INF1) changed; only the text may change",
                                archive, name))
        changed[name] = data
    return changed


def changed_files(source_dir: str | os.PathLike, translation_dir: str | os.PathLike) -> Dict[str, bytes]:
    """{disc path: new bytes} for each file of the translation folder that differs from the source.

    An archive is compared member by member (so the INF1 guard applies), and returned whole. A file the source does
    not hold is refused.
    """
    source, translation = Path(source_dir), Path(translation_dir)
    changes: Dict[str, bytes] = {}
    for path in sorted(translation.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(translation).as_posix()
        if rel == SOURCE_MARK:
            continue
        base = source / rel
        if not base.is_file():
            raise ValueError(tr("{0}: not on the disc (new files are not written)", rel))
        data = path.read_bytes()
        old = base.read_bytes()
        if data == old:
            continue
        if rel.lower().endswith((".szs", ".arc")):
            _member_changes(old, data, rel)
        changes[rel] = data
    return changes


def build_gc_iso(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Progress, is_cancelled: Cancelled) -> str:
    """Write the translated disc into ``output_dir`` and return its path. The original disc is copied, never changed."""
    image = disc_of_source(source_dir)
    changes = changed_files(source_dir, translation_dir)
    if changes and "sys/main.dol" not in changes:
        # Any translated file brings the speech-balloon fix in the retail executable (see dol_patch.py).
        changes["sys/main.dol"] = dol_patch.apply((Path(source_dir) / "sys" / "main.dol").read_bytes())
    out = Path(output_dir) / ISO_NAME
    write_disc(image, out, changes, progress, is_cancelled)
    return str(out)


def build_port_pack(source_dir: str, translation_dir: str, output_dir: str,
                    progress: Progress, is_cancelled: Cancelled) -> str:
    """Write ``mods/uk`` (the overlay for the PC and Switch ports) into ``output_dir`` and return its path."""
    source = Path(source_dir)
    changes = changed_files(source_dir, translation_dir)
    root = Path(output_dir) / "mods" / "uk"
    files = root / "files"
    count = len(changes) or 1
    for index, (rel, data) in enumerate(changes.items()):
        if is_cancelled():
            break
        progress(100 * index // count, rel)
        if not rel.startswith("files/"):   # sys/main.dol: the ports do not read it from the disc
            continue
        disc_path = rel[len("files/"):]
        if rel.lower().endswith((".szs", ".arc")):
            base = (source / rel).read_bytes()
            for member, member_data in _member_changes(base, data, rel).items():
                _write(files / disc_path / member, member_data)
        else:
            _write(files / disc_path, data)
    _write(root / "README.txt", PACK_README.encode("utf-8"))
    progress(100, "")
    return str(root)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
