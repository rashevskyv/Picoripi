"""Skyward Sword HD for SkyRecomp (the Windows port of the v1.0.0 Switch game): the ``skyrecomp`` build target.

SkyRecomp reads a mod folder ``mods/<name>/romfs/`` next to its exe. A file there replaces the game file of the same
RomFS path. The game keeps its text in U8 archives (``US/Object/en_US/1-Town.arc``), so a changed MSBT goes back
into its archive: the archive is read from the game's raw ``romfs`` folder, the member is replaced, the archive is
packed again and the result is written under the mod. A changed file that is not in an archive (a font in
``US/Font/en_US/``) is copied as it is.

The raw ``romfs`` folder lies next to the project's source folder (the owner's layout: ``HD - Switch\\romfs`` and
``HD - Switch\\source``). When the game folder has ``exefs\\main``, its build id is checked; SkyRecomp checks it too.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from core.containers.u8_container import U8Container
from core.i18n import tr
from plugins.common import romfs_mod

TARGET_ID = "skyrecomp"
MOD_NAME = "Picoripi_UA"                    # the mod folder under mods/ (SkyRecomp lists every folder there)
BUILD_ID_AT = 0x40
BUILD_ID = bytes.fromhex("d824d4b1bbd45d03")  # Skyward Sword HD v1.0.0, main module (runtime/ui/launcher.mm)
README = """Skyward Sword HD (Switch) for SkyRecomp

1. Copy the folder mods\\Picoripi_UA into the mods\\ folder next to skyrecomp.exe.
2. Use the base game v1.0.0 (no update) in the SkyRecomp setup. Do not run the setup again after a rebuild
   of this mod: the mod is read at start.
3. The mod replaces the files under romfs\\ at their RomFS paths.
"""


def romfs_of(source_dir: str | Path) -> Path:
    """The raw RomFS folder of the game: ``romfs`` next to the source folder. Raises ValueError when it is missing."""
    romfs = Path(source_dir).parent / "romfs"
    if not romfs.is_dir():
        raise ValueError(tr("The SkyRecomp build needs the game's romfs folder next to the source folder: {0}",
                            str(romfs)))
    return romfs


def check_build_id(game_dir: Path) -> None:
    """Raise ValueError when ``game_dir/exefs/main`` is not Skyward Sword HD v1.0.0. A game folder without exefs passes."""
    main = game_dir / "exefs" / "main"
    if not main.is_file():
        return
    with open(main, "rb") as handle:
        handle.seek(BUILD_ID_AT)
        build_id = handle.read(len(BUILD_ID))
    if build_id != BUILD_ID:
        raise ValueError(tr("This is not Skyward Sword HD v1.0.0. SkyRecomp runs only v1.0.0. Use the base game package."))


def archive_of(rel: str) -> Optional[Tuple[str, str]]:
    """``(archive path under romfs, member path in it)`` of a source file, or None for a file outside an archive.

    ``US/Object/en_US/1-Town/100-Town.msbt`` -> ``("US/Object/en_US/1-Town.arc", "1-Town/100-Town.msbt")``;
    ``Layout/Title2D/text/en_US_titleBG_00.msbt`` -> ``("Layout/Title2D.arc", "text/en_US_titleBG_00.msbt")``.
    The member keeps the archive's own folder name for an object and not for a layout, as the archives hold them.
    """
    parts = rel.split("/")
    if len(parts) >= 5 and parts[1] == "Object":
        return "/".join(parts[:4]) + ".arc", "/".join(parts[3:])
    if len(parts) >= 3 and parts[0] == "Layout":
        return "/".join(parts[:2]) + ".arc", "/".join(parts[2:])
    return None


def build(source_dir: str, translation_dir: str, output_dir: str,
          progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """Write ``mods/Picoripi_UA/romfs/`` and a README into ``output_dir``. Raises ValueError, before anything is
    written when a translated file names no member of its archive."""
    romfs = romfs_of(source_dir)
    check_build_id(romfs.parent)
    changes = romfs_mod.changed_files(source_dir, translation_dir)
    archives: Dict[str, Dict[str, bytes]] = {}
    plain: Dict[str, bytes] = {}
    for rel, data in changes.items():
        found = archive_of(rel)
        if found and (romfs / found[0]).is_file():
            archives.setdefault(found[0], {})[found[1]] = data
        else:
            plain[rel] = data
    out = Path(output_dir) / "mods" / MOD_NAME / "romfs"
    total = max(len(archives) + len(plain), 1)
    done = 0
    for arc_rel, members in sorted(archives.items()):
        if is_cancelled():
            return output_dir          # build.run_build sees the cancel and removes the folder
        progress(100 * done // total, arc_rel)
        container = U8Container((romfs / arc_rel).read_bytes())
        names = set(container.list_files())
        for member, data in sorted(members.items()):
            if member not in names:
                raise ValueError(tr("{0} has no file {1}.", arc_rel, member))
            container.write_file(member, data)
        target = out.joinpath(*arc_rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(container.pack())
        done += 1
    for rel, data in sorted(plain.items()):
        if is_cancelled():
            return output_dir
        progress(100 * done // total, rel)
        target = out.joinpath(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        done += 1
    (Path(output_dir) / "README.txt").write_text(README, encoding="utf-8")
    progress(100, "")
    return output_dir
