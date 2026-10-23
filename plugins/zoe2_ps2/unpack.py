"""Zone of the Enders: The 2nd Runner (PlayStation 2, USA): the stage scripts of the disc, one file per stage.

The disc is read in place. ``ZOE2/STAGE.DAT`` holds 110 stages; each has one script (``<stage>.scx``) in its cache
group. A script is written to ``scx/<stage>.scx``, byte for byte as the game reads it, and the text layer
(``plugins.zoe2_ps2.scx``) reads and writes it. ``source_image.ref`` holds the absolute path of the disc, so the build can
write a new disc image from it.
"""
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from core.containers.image_files import ImageError
from core.i18n import tr
from plugins.zoe2_ps2 import disc, stagedat

SCRIPT_DIR = "scx"
SCRIPT_SUFFIX = ".scx"
REF_NAME = "source_image.ref"
SCX_EXT = stagedat.str_code32("scx")


def identify(path: str) -> Optional[Dict[str, Any]]:
    """``{"role", "platform", "libraries"}`` of the PlayStation 2 disc of Zone of the Enders: The 2nd Runner (USA)."""
    if not disc.identify_path(path):
        return None
    return {"role": "base", "platform": "ps2", "libraries": []}


def find_script(stage: stagedat.Stage) -> Optional[Tuple[int, int]]:
    """(position of the group in ``stage.groups``, position of the member in it) of the stage's script, or None."""
    for gi, group in enumerate(stage.groups):
        for mi, member in enumerate(group.members):
            if member.ext == SCX_EXT and member.hash == stagedat.str_code32(stage.name + SCRIPT_SUFFIX):
                return gi, mi
    return None


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    base = sources.get("base")
    if not base:
        return None
    if identify(base) is None:
        raise ImageError(tr("The file is not the Zone of the Enders: The 2nd Runner PlayStation 2 disc."))
    with open(base, "rb") as image:
        entry = disc.find_path(image, disc.STAGE_PATH)
        if entry is None:
            raise ImageError(tr("The disc has no {0}.", disc.STAGE_PATH))
        read = disc.file_reader(image, entry)
        toc = stagedat.read_toc(read)
        folder = os.path.join(target_dir, SCRIPT_DIR)
        os.makedirs(folder, exist_ok=True)
        for position, (name, sector) in enumerate(toc.stages, start=1):
            if is_cancelled():
                return None
            progress(100 * position // len(toc.stages), name)
            stage = stagedat.parse_stage(read, toc, name, sector)
            found = find_script(stage)
            if found is None:
                continue
            group = stage.groups[found[0]]
            data = stagedat.member_bytes(read, stage, group, group.members[found[1]])
            Path(folder, name + SCRIPT_SUFFIX).write_bytes(data)
    Path(target_dir, REF_NAME).write_text(json.dumps({"game_id": "SLUS_205.45", "image": os.path.abspath(base)}),
                                          encoding="utf-8")
    progress(100, "")
    return target_dir
