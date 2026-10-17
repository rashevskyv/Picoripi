"""The source mark of a GameCube disc: the record ``unpack_sources`` writes next to an unpacked disc, so a build can
find the original image again and copy it through ``write_disc``.

The mark is ``.picoripi_disc.json`` in the unpacked folder: the image path and its size. A build refuses a mark whose
image is missing or changed size.
"""
import json
import os
from pathlib import Path

from core.i18n import tr

SOURCE_MARK = ".picoripi_disc.json"


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


def find_disc_root(folder: str | os.PathLike, levels: int = 4) -> Path:
    """The unpacked folder that holds the mark: ``folder`` or one of its parents, ``levels`` up at most.

    The host passes a project's source subfolder (for example ``unpacked/files/res/Msgus``), not the disc root.
    Raises ValueError when no mark is found.
    """
    current = Path(folder)
    for _ in range(levels + 1):
        if (current / SOURCE_MARK).is_file():
            return current
        if current.parent == current:
            break
        current = current.parent
    raise ValueError(tr("The source folder has no disc record: unpack the disc again."))
