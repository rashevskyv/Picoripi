"""Build the Lunar: Silver Star Story Remastered mod: a patched ``data.cpk`` in a LayeredFS folder.

Each translation file (``FIL/TEXTnnn.DAT``) changes the English file of the same name in the archive (``FIL_us``, the
file the game shows for English). The English file keeps its bytecode; only the strings change. The archive is patched
in place (``core.containers.cpk_write``): every other file keeps its bytes. The result is
``atmosphere/contents/0100DCD01E9EE000/romfs/data.cpk``.
"""
import os
from pathlib import Path
from typing import Callable, Dict

from core.containers.cpk_write import patch
from utils.logging_utils import log_warning

from . import text
from .config import TITLE_ID
from .unpack import TEXT_RE

TARGET = "layeredfs"
PC_TARGET = "pc"
MOD_DIR = "atmosphere"


def build_switch(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    out = Path(output_dir) / MOD_DIR / "contents" / TITLE_ID / "romfs" / "data.cpk"
    return _patched_cpk(source_dir, translation_dir, out, progress, is_cancelled)


def build_pc(source_dir: str, translation_dir: str, output_dir: str,
             progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """The patched ``data.cpk`` for the PC game folder: copy it over the game's ``data.cpk``. Nothing else changes."""
    return _patched_cpk(source_dir, translation_dir, Path(output_dir) / "data.cpk", progress, is_cancelled)


def _patched_cpk(source_dir: str, translation_dir: str, out: Path,
                 progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    source, translation = Path(source_dir), Path(translation_dir)
    folder = translation / "FIL"
    files = sorted(folder.glob("TEXT*.DAT")) if folder.is_dir() else []
    replacements: Dict[str, bytes] = {}
    for number, path in enumerate(files, start=1):
        if is_cancelled():
            raise InterruptedError()
        if not TEXT_RE.match(path.name):
            continue
        lines = text.read_translation(path.read_bytes())
        if lines is None:
            continue
        progress(100 * number // len(files), path.name)
        english = (source / "FIL_us" / path.name).read_bytes()
        japanese = (source / "FIL" / path.name).read_bytes()
        new, missing = text.english_with_translation(english, japanese, lines)
        if missing:
            log_warning(f"lunar_sssc_remastered: {path.name}: characters the English encoder cannot write were "
                        f"saved as '?': {''.join(sorted(missing))}")
        if new != english:
            replacements[f"FIL_us/{path.name}"] = new
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(out.name + ".tmp")
    with open(source / "data.cpk", "rb") as stream, open(temporary, "wb") as target:
        patch(stream, replacements, target)
    os.replace(temporary, out)
    return str(out)
