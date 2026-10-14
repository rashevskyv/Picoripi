"""LAS Recomp: the version check of an unpacked base game and the ``lasrecomp`` build target (``romfs.bin``).

The recomp runs only Link's Awakening v1.0.0. It checks 8 bytes of ``exefs/main`` at 0x40 and reads ``romfs.bin`` from
its data folder. The build writes that image from the unpacked ``romfs`` tree, with the translated files replaced.

The game draws its text with the console's Standard font, which no game file holds. The recomp loads it from
``<data root>/fonts/nintendo_udsg-r_std_003.ttf`` (``runtime/hle/pl.c``). Its font engine needs TrueType (``glyf``)
outlines and crashes on CFF. The build copies the project's font there: the file named by ``lasrecomp_font`` in
``project_settings.json``, else a ``.ttf`` in ``<project>/fonts/``. It refuses a font without the Ukrainian letters.
"""
from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path
from typing import Callable, Dict, List

from core.containers.romfs_write import RomfsWriteCancelled, write_romfs
from core.font_formats.bfotf import OpenType
from core.i18n import tr

TITLE_ID = "01006BB00C6F0000"
TARGET_ID = "lasrecomp"
BUILD_ID_AT = 0x40
BUILD_ID = bytes.fromhex("ae16f71e002af8cb")      # Link's Awakening v1.0.0, the id the recomp's launcher checks
ROMFS_NAME = "romfs.bin"
FONT_DIR = "fonts"                               # in the project folder, and in the recomp's data root
FONT_NAME = "nintendo_udsg-r_std_003.ttf"        # the Standard font name pl.c loads (its "Import fonts" takes it too)
FONT_SETTING = "lasrecomp_font"                  # project_settings.json: a .ttf file or a folder
FONT_LICENCE = "OFL.txt"                         # copied with the font when it lies beside it
UKRAINIAN = "ІіЇїЄєҐґʼ"
TRUETYPE = b"\x00\x01\x00\x00"
README = r"""Link's Awakening (Switch) for LAS Recomp

<data root> is the folder of lasrecomp.exe, or LARECOMP_DATA_ROOT when it is set.

1. Copy romfs.bin over <data root>\extracted\romfs.bin.
2. Copy the files under romfs\ over <data root>\extracted\romfs\ (same paths). The recomp reads them too.
3. Copy the files under fonts\ into <data root>\fonts\. The game draws its text with
   fonts\nintendo_udsg-r_std_003.ttf. Delete fonts\nintendo_udsg-r_std_003.bfttf if it is there: the recomp
   loads it first. Do not set LARECOMP_FONT: it wins over both.
4. Start the recomp. Do not run its setup again: setup would rebuild romfs.bin from the old files.
"""


def check_unpacked(folder: str | Path) -> None:
    """Raise ValueError unless ``folder`` holds the base game v1.0.0 (the one the recomp runs)."""
    root = Path(folder)
    if not (root / "romfs").is_dir():
        raise ValueError("The package has no RomFS. It is an update, not the base game. Use the base game package.")
    try:
        with open(root / "exefs" / "main", "rb") as handle:
            handle.seek(BUILD_ID_AT)
            build_id = handle.read(len(BUILD_ID))
    except OSError:
        build_id = b""
    if build_id != BUILD_ID:
        raise ValueError("This is not Link's Awakening v1.0.0. LAS Recomp runs only v1.0.0. Use the base game package.")


def _font_problem(path: Path) -> str:
    """Why the recomp cannot draw Ukrainian with the font ``path``; empty when it can."""
    try:
        data = path.read_bytes()
        font = OpenType(data)
        mapped = font.cmap()
    except (OSError, ValueError, struct.error):
        return tr("cannot read it")
    if data[:4] != TRUETYPE or "glyf" not in font.tables or "CFF " in font.tables:
        return tr("not a TrueType font with glyf outlines")
    missing = "".join(char for char in UKRAINIAN if ord(char) not in mapped)
    return tr("no letters {0}", missing) if missing else ""


def find_font(project_dir: Path) -> Path:
    """The project's font for the recomp. Raises ValueError, with each file's reason, when there is none usable."""
    folder = project_dir / FONT_DIR
    try:
        setting = json.loads((project_dir / "project_settings.json").read_text(encoding="utf-8")).get(FONT_SETTING)
    except (OSError, ValueError, AttributeError):
        setting = None
    if setting:
        folder = project_dir / str(setting)       # an absolute path stays as it is
    files = [folder] if folder.is_file() else sorted(folder.glob("*.ttf")) if folder.is_dir() else []
    reasons: List[str] = []
    for path in files:
        problem = _font_problem(path)
        if not problem:
            return path
        reasons.append(f"{path.name}: {problem}")
    raise ValueError(tr("LAS Recomp needs a TrueType font (.ttf, glyf outlines) with the letters {0}. Put one into {1}, "
                        "or name it with \"{2}\" in project_settings.json.", UKRAINIAN, str(folder), FONT_SETTING)
                     + "".join(f"\n{line}" for line in reasons))


def _overlay(romfs: Path, translation: Path) -> Dict[str, str]:
    """Translation files that replace a file of the unpacked romfs: relative path ("/") -> file on disk.

    A path with a dot-name part is skipped: the RomFS writer leaves those out of the image and refuses them as overlay.
    """
    found: Dict[str, str] = {}
    if not translation.is_dir():
        return found
    for path in sorted(translation.rglob("*")):
        rel = path.relative_to(translation).as_posix()
        if any(part.startswith(".") for part in rel.split("/")):
            continue
        if path.is_file() and (romfs / rel).is_file():   # a file the 1.0.0 tree does not have is not added
            found[rel] = str(path)
    return found


def build(source_dir: str, translation_dir: str, output_dir: str,
          progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """Write ``romfs.bin``, the overlaid files under ``romfs/``, the font under ``fonts/`` and a README into
    ``output_dir``. Raises ValueError, before anything is written, when the project has no usable font."""
    out = Path(output_dir)
    font = find_font(out.parent.parent)       # build.run_build writes into <project>/build/.<target>-<id>
    overlay = _overlay(Path(source_dir), Path(translation_dir))

    def on_bytes(done: int, total: int) -> None:
        progress(100 * done // max(total, 1), ROMFS_NAME)

    try:
        write_romfs(source_dir, str(out / ROMFS_NAME), on_bytes, is_cancelled, overlay)
    except RomfsWriteCancelled:
        return output_dir          # build.run_build sees the cancel and removes the folder
    for rel, source in overlay.items():   # texpatch and movie read these from the folder, not from romfs.bin
        target = out / "romfs" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (out / FONT_DIR).mkdir()
    shutil.copyfile(font, out / FONT_DIR / FONT_NAME)
    if (font.parent / FONT_LICENCE).is_file():
        shutil.copyfile(font.parent / FONT_LICENCE, out / FONT_DIR / FONT_LICENCE)
    (out / "README.txt").write_text(README, encoding="utf-8")
    return output_dir
