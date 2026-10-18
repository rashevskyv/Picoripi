"""Build the translated GameCube disc: the changed files of the translation folder go into a copy of the USA disc.

A field script (``field/*.sct``) is kept decoded in the translation folder and is compressed again (AKLZ) here.
The source disc is copied, never changed. A file the disc does not hold is refused: no file is added.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Dict

from core.containers import aklz
from core.containers.gcm_writer import write_disc
from core.i18n import tr

from . import scripts, unpack

SOURCE_MARK = ".picoripi_disc.json"
ISO_NAME = "Skies of Arcadia Legends (UA).iso"

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


def _refuse_over_budget(rel: str, base: bytes, data: bytes, big: bool) -> None:
    """Raise when a script's text is over its budget. Its typed text is in the file, but the build never writes it."""
    if len(data) <= len(base):   # a script within its budget keeps its length (scripts.write_strings)
        return
    state = scripts.budget_of(base, scripts.read_strings(data, big), big)
    lines = ", ".join(str(i + 1) for i, is_changed in enumerate(state.changed) if is_changed)
    raise ValueError(tr("{0}: the script's text is {1} bytes over its budget, so it is not built. Shorten these lines "
                        "or other lines of the script: {2}.").format(rel, -state.free, lines))


def changed_files(source_dir: str | os.PathLike, translation_dir: str | os.PathLike,
                  big: bool = scripts.BIG_ENDIAN) -> Dict[str, bytes]:
    """{path relative to the disc's files folder: new decoded bytes} for each translation file that differs.

    Raises ValueError for a script over its budget (both disc builds share this check; ``big`` is the script's byte order).
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
        data, old = path.read_bytes(), base.read_bytes()
        if data != old:
            if rel.lower().endswith(".sct"):
                _refuse_over_budget(rel, old, data, big)
            changes[rel] = data
    return changes


def disc_changes(changes: Dict[str, bytes]) -> Dict[str, bytes]:
    """The disc paths and bytes to write: scripts compressed again, every other file as it is."""
    out: Dict[str, bytes] = {}
    for rel, data in changes.items():
        if rel.startswith(unpack.SCRIPT_DIR) and rel.endswith(".sct"):
            packed = aklz.encode(data)
            if aklz.decode(packed) != data:   # never write a script the game would read differently
                raise ValueError(tr("{0}: the compressed script does not decode to the same bytes", rel))
            data = packed
        out[unpack.FILES + rel] = data
    return out


def build_gc_iso(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Progress, is_cancelled: Cancelled) -> str:
    """Write the translated disc into ``output_dir`` and return its path."""
    image = disc_of_source(source_dir)
    changes = disc_changes(changed_files(source_dir, translation_dir))
    progress(0, ISO_NAME)
    out = Path(output_dir) / ISO_NAME
    write_disc(image, out, changes, progress, is_cancelled)
    return str(out)
