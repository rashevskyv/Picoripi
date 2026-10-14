"""Build targets of Super Mario Sunshine: a GameCube disc image (``gc_iso``) and the PC/Switch port pack (``port_pack``).

The source folder is the disc as ``images.extract`` writes it (``sys/`` and ``files/``), with each RARC archive
(``*.szs``) turned into a folder of its members: ``files/data/scene/bianco0.szs/map/message.bmg``. Its executable text
is ``sys/main_strings.dolstr`` (see dol_text.py). The disc itself is never changed: ``unpack_sources`` records its
path in ``.picoripi_disc.json`` and the ISO build copies it through ``write_disc``.

The translation folder holds only the files that were saved; each must exist in the source, so no file is added.
A changed archive member is written into a copy of its archive (read from the disc), and the archive replaces the
disc's file. The port pack writes the changed members as they are, under ``files/<archive>/<member>``: the port's
overlay rule. No container is registered with ``ContainerManager``: the scan and the other games are not changed.
"""
import json
import os
import struct
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from core.containers import yaz0
from core.containers.gcm import GameCubeImage
from core.containers.gcm_writer import write_disc
from core.containers.rarc_container import RarcContainer
from core.containers.wia import open_disc
from core.i18n import tr

from . import dol_patch, dol_text

SOURCE_MARK = ".picoripi_disc.json"
TEXT_MEMBER = "sys/main_strings.dolstr"
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


def fold_archives(target_dir: str | os.PathLike, is_cancelled: Cancelled = lambda: False) -> bool:
    """Turn each RARC ``*.szs`` under ``files/`` into a folder of its members. False when cancelled.

    A file that is not a RARC archive (after Yaz0) stays a file. The folder takes the archive's name, so the file is
    removed first. The member bytes are written as they are in the archive.
    """
    for path in sorted(Path(target_dir, "files").rglob("*.szs")):
        if is_cancelled():
            return False
        raw = path.read_bytes()
        data = yaz0.decompress(raw) if raw[:4] == b"Yaz0" else raw
        if data[:4] != b"RARC":
            continue
        container = RarcContainer(data)
        path.unlink()
        for name in container.list_files():
            _write(path / name, container.read_file(name))
    return True


def write_text_member(target_dir: str | os.PathLike) -> None:
    """Write the executable's English text next to ``sys/main.dol`` as ``sys/main_strings.dolstr``."""
    target = Path(target_dir)
    dol = (target / "sys" / "main.dol").read_bytes()
    _write(target / TEXT_MEMBER, dol_text.document_of(dol))


def archive_split(rel: str) -> Optional[Tuple[str, str]]:
    """``(archive path, member path)`` when ``rel`` lies inside an archive folder (``x.szs/``), else None."""
    parts = rel.split("/")
    for index, part in enumerate(parts[:-1]):
        if part.lower().endswith(".szs"):
            return "/".join(parts[:index + 1]), "/".join(parts[index + 1:])
    return None


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


def changed_files(source_dir: str | os.PathLike, translation_dir: str | os.PathLike) -> Dict[str, bytes]:
    """{path in the source tree: new bytes} for each file of the translation folder that differs from the source.

    A BMG member keeps its INF1 (the message attributes): a change to INF1 is refused. A file the source does not hold
    is refused, so no file is added.
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
        if rel.lower().endswith(".bmg") and _attributes(_section(data, b"INF1")) != _attributes(_section(old, b"INF1")):
            raise ValueError(tr("{0}: the message attributes (INF1) changed; only the text may change", rel))
        changes[rel] = data
    return changes


def _attributes(inf1: Optional[bytes]) -> Optional[tuple]:
    """What a text edit must keep of an INF1 section: its header fields and each entry's attribute bytes.

    An entry's first four bytes are the string's offset into DAT1, which a text edit moves; they are not compared.
    """
    if inf1 is None or len(inf1) < 16:
        return None
    count, entry_len = struct.unpack_from(">HH", inf1, 8)
    tails = tuple(bytes(inf1[16 + i * entry_len + 4:16 + (i + 1) * entry_len]) for i in range(count))
    return (bytes(inf1[8:16]), tails)


def _archive_bytes(image: Path, archive: str, members: Dict[str, bytes]) -> bytes:
    """The archive ``archive`` of the disc, with ``members`` written into it. Yaz0 is kept when the disc has it."""
    with open_disc(image) as stream:   # a WIA or RVZ source is read as its disc; the source is never written
        disc = GameCubeImage(stream)
        entry = next((e for e in disc.entries() if e.path == archive), None)
        if entry is None:
            raise ValueError(tr("{0}: not on the disc (new files are not written)", archive))
        data = disc.read(entry)
    raw = yaz0.decompress(data) if data[:4] == b"Yaz0" else data
    container = RarcContainer(raw)
    for member, body in members.items():
        if member not in container.list_files():
            raise ValueError(tr("{0}: the archive holds no member {1} (new files are not written)", archive, member))
        container.write_file(member, body)
    packed = container.pack()
    return yaz0.compress(packed, max_candidates=16) if data[:4] == b"Yaz0" else packed


def build_gc_iso(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Progress, is_cancelled: Cancelled) -> str:
    """Write the translated disc into ``output_dir`` and return its path. The original disc is copied, never changed."""
    image = disc_of_source(source_dir)
    changes = changed_files(source_dir, translation_dir)
    text = changes.pop(TEXT_MEMBER, None)
    archives: Dict[str, Dict[str, bytes]] = {}
    for rel in list(changes):
        split = archive_split(rel)
        if split is not None:
            archive, member = split
            archives.setdefault(archive, {})[member] = changes.pop(rel)
    for archive, members in archives.items():
        if is_cancelled():
            break
        progress(0, archive)
        changes[archive] = _archive_bytes(image, archive, members)
    if changes or text is not None:
        # Any translated file brings the speech-balloon fix into the executable being written (see dol_patch.py).
        dol = (Path(source_dir) / "sys" / "main.dol").read_bytes()
        if text is not None:
            dol = dol_text.apply_document(dol, text)
        changes["sys/main.dol"] = dol_patch.ensure(dol)
    out = Path(output_dir) / ISO_NAME
    write_disc(image, out, changes, progress, is_cancelled)
    return str(out)


def build_port_pack(source_dir: str, translation_dir: str, output_dir: str,
                    progress: Progress, is_cancelled: Cancelled) -> str:
    """Write ``mods/uk`` (the overlay for the PC and Switch ports) into ``output_dir`` and return its path."""
    changes = changed_files(source_dir, translation_dir)
    root = Path(output_dir) / "mods" / "uk"
    files = root / "files"
    count = len(changes) or 1
    for index, (rel, data) in enumerate(changes.items()):
        if is_cancelled():
            break
        progress(100 * index // count, rel)
        if not rel.startswith("files/"):   # sys/: the ports do not read the executable from the disc
            continue
        _write(files / rel[len("files/"):], data)
    _write(root / "README.txt", PACK_README.encode("utf-8"))
    progress(100, "")
    return str(root)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
