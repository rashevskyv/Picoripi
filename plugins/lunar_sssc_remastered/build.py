"""Build the Lunar: Silver Star Story mods from the Japanese-keyed translation.

Each translation file (``FIL/TEXTnnn.DAT``) changes an English file of the same name: the file keeps its bytecode, only
the strings change (``text.english_with_translation``). Switch and PC: the English file of the archive (``FIL_us``, the
file the game shows for English), with ``data.cpk`` patched in place (``core.containers.cpk_write``), so every other
file keeps its bytes. The fonts edited in the font editor (``FIL/CUSTOM/Font/n/`` of the translation folder) go
into the archive too. The Switch result is ``atmosphere/contents/0100DCD01E9EE000/romfs/data.cpk``.

PlayStation: the English file of the PS1 disc (``LUNADATA/``, unpacked from the disc). The result is
``LUNADATA/TEXTnnn.DAT`` for each changed file; the workspace's PS1 build puts them back on both discs.
"""
import os
from pathlib import Path
from typing import Callable, Dict

from core.containers.cpk_write import patch
from core.i18n import tr
from utils.logging_utils import log_warning

from . import text
from .config import TITLE_ID
from .unpack import FONT_FOLDERS, PS1_FOLDER, TEXT_RE

TARGET = "layeredfs"
PC_TARGET = "pc"
PS1_TARGET = "psx"
MOD_DIR = "atmosphere"


def build_switch(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    out = Path(output_dir) / MOD_DIR / "contents" / TITLE_ID / "romfs" / "data.cpk"
    return _patched_cpk(source_dir, translation_dir, out, progress, is_cancelled)


def build_pc(source_dir: str, translation_dir: str, output_dir: str,
             progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """The patched ``data.cpk`` for the PC game folder: copy it over the game's ``data.cpk``. Nothing else changes."""
    return _patched_cpk(source_dir, translation_dir, Path(output_dir) / "data.cpk", progress, is_cancelled)


def build_ps1(source_dir: str, translation_dir: str, output_dir: str,
              progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """The changed PS1 dialogue files in ``output_dir/LUNADATA``. ValueError when the PS1 disc was not unpacked."""
    if not (Path(source_dir) / PS1_FOLDER).is_dir():
        raise ValueError(tr("The PlayStation files are missing: add the PS1 disc to the project's sources."))
    folder = Path(output_dir) / PS1_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in _translated(source_dir, translation_dir, PS1_FOLDER, progress, is_cancelled).items():
        temporary = folder / f"{name}.tmp"
        temporary.write_bytes(data)
        os.replace(temporary, folder / name)
    return str(folder)


def _translated(source_dir: str, translation_dir: str, english_folder: str,
                progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Dict[str, bytes]:
    """``{file name: new English file}`` for every translated file that changes its English file."""
    source, folder = Path(source_dir), Path(translation_dir) / "FIL"
    files = sorted(folder.glob("TEXT*.DAT")) if folder.is_dir() else []
    out: Dict[str, bytes] = {}
    for number, path in enumerate(files, start=1):
        if is_cancelled():
            raise InterruptedError()
        english_path = source / english_folder / path.name
        if not TEXT_RE.match(path.name) or not english_path.is_file():
            continue
        lines = text.read_translation(path.read_bytes())
        if lines is None:
            continue
        progress(100 * number // len(files), path.name)
        english = english_path.read_bytes()
        new, missing = text.english_with_translation(english, (source / "FIL" / path.name).read_bytes(), lines)
        if missing:
            log_warning(f"lunar_sssc_remastered: {english_folder}/{path.name}: characters the English encoder cannot "
                        f"write were saved as '?': {''.join(sorted(missing))}")
        if new != english:
            out[path.name] = new
    return out


def _patched_cpk(source_dir: str, translation_dir: str, out: Path,
                 progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    replacements = {f"FIL_us/{name}": data
                    for name, data in _translated(source_dir, translation_dir, "FIL_us", progress, is_cancelled).items()}
    for folder in FONT_FOLDERS:
        fonts = Path(translation_dir).joinpath(*folder.split("/"))
        for path in sorted(fonts.glob("*")) if fonts.is_dir() else []:
            if path.is_file() and not path.name.endswith(".tmp"):
                replacements[f"{folder}/{path.name}"] = path.read_bytes()
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(out.name + ".tmp")
    with open(Path(source_dir) / "data.cpk", "rb") as stream, open(temporary, "wb") as target:
        patch(stream, replacements, target)
    os.replace(temporary, out)
    return str(out)
