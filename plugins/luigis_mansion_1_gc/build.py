"""Build target of Luigi's Mansion (GameCube): the translated disc image (``gc_iso``).

The source folder is the disc as ``images.extract`` writes it (``sys/`` and ``files/``), with each archive folded into
a folder of its members: ``files/Event/event01.szp/message/message01.csv`` (the ``.szp`` archives are Yay0 around a
RARC) and ``files/system/system.arc/font_12.bfn``. The disc itself is never changed: ``unpack_sources`` records its
path in ``.picoripi_disc.json`` and the build copies it through ``write_disc``.

A changed member is written into a copy of its archive (read from the disc). The wrapper stays the same kind: Yay0 for
``.szp`` (``yay0.compress``, literal bytes only), Yaz0 when the disc has it, or none for a plain RARC. ``sys/main.dol`` is
never written: the Luigi's Mansion Recompiled port checks its hash, and its text tables are archives.
"""
import os
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from core.containers import yay0, yaz0
from core.containers.gcm import GameCubeImage
from core.containers.gcm_writer import write_disc
from core.containers.rarc_container import RarcContainer
from core.containers.wia import open_disc
from core.i18n import tr
from plugins.common.disc_source import SOURCE_MARK, disc_of_source

from . import messages

ISO_NAME = "Luigi's Mansion (UA).iso"
ARCHIVE_SUFFIXES = (".szp", ".arc")

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def unwrap(data: bytes) -> bytes:
    """The RARC inside ``data``: Yay0 or Yaz0 removed, a plain RARC as it is."""
    if data[:4] == b"Yay0":
        return yay0.decompress(data)
    if data[:4] == b"Yaz0":
        return yaz0.decompress(data)
    return data


def wrap(data: bytes, original: bytes) -> bytes:
    """``data`` (a RARC) in the same wrapper as ``original`` was."""
    if original[:4] == b"Yay0":
        return yay0.compress(data)
    if original[:4] == b"Yaz0":
        return yaz0.compress(data, max_candidates=16)
    return data


def fold_archives(target_dir: str | os.PathLike, is_cancelled: Cancelled = lambda: False) -> bool:
    """Turn each RARC archive (``.szp``, ``.arc``) under ``files/`` into a folder of its members. False when cancelled.

    A file that is not a RARC after its wrapper stays a file. The folder takes the archive's name, so the file is
    removed first. Member bytes are written as they are in the archive.
    """
    for path in sorted(Path(target_dir, "files").rglob("*")):
        if is_cancelled():
            return False
        if not path.is_file() or path.suffix.lower() not in ARCHIVE_SUFFIXES:
            continue
        data = unwrap(path.read_bytes())
        if data[:4] not in (b"RARC", b"CRAR"):
            continue
        container = RarcContainer(data)
        path.unlink()
        for name in container.list_files():
            _write(path / name, container.read_file(name))
    return True


def archive_split(rel: str) -> Optional[Tuple[str, str]]:
    """``(archive path, member path)`` when ``rel`` lies inside an archive folder (``x.szp/``), else None."""
    parts = rel.split("/")
    for index, part in enumerate(parts[:-1]):
        if part.lower().endswith(ARCHIVE_SUFFIXES):
            return "/".join(parts[:index + 1]), "/".join(parts[index + 1:])
    return None


def changed_files(source_dir: str | os.PathLike, translation_dir: str | os.PathLike) -> Dict[str, bytes]:
    """{path in the source tree: new bytes} for each file of the translation folder that differs from the source.

    A message file keeps its record count: the script reads a record by its number. A file the source does not hold is
    refused, so no file is added.
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
        if rel.lower().endswith(".csv") and len(messages.Table(data).texts()) != len(messages.Table(old).texts()):
            raise ValueError(tr("{0}: the number of records changed; only the text may change", rel))
        changes[rel] = data
    return changes


def _archive_bytes(image: Path, archive: str, members: Dict[str, bytes]) -> bytes:
    """The archive ``archive`` of the disc, with ``members`` written into it, in the wrapper it had."""
    with open_disc(image) as stream:   # a WIA or RVZ source is read as its disc; the source is never written
        disc = GameCubeImage(stream)
        entry = next((e for e in disc.entries() if e.path == archive), None)
        if entry is None:
            raise ValueError(tr("{0}: not on the disc (new files are not written)", archive))
        data = disc.read(entry)
    container = RarcContainer(unwrap(data))
    for member, body in members.items():
        if member not in container.list_files():
            raise ValueError(tr("{0}: the archive holds no member {1} (new files are not written)", archive, member))
        container.write_file(member, body)
    return wrap(container.pack(), data)


def build_gc_iso(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Progress, is_cancelled: Cancelled) -> str:
    """Write the translated disc into ``output_dir`` and return its path. The original disc is copied, never changed."""
    image = disc_of_source(source_dir)
    changes = changed_files(source_dir, translation_dir)
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
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out = Path(output_dir) / ISO_NAME
    write_disc(image, out, changes, progress, is_cancelled)
    return str(out)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
