"""Unpack, build, export and emulator launch for the Project Manager. Every function here runs on a worker thread.

A result folder is written beside its final name and renamed into place only when it is complete, so a cancel or a
crash leaves no half-written folder behind. Only folders this module made are removed.
"""
from __future__ import annotations

import os
import shlex
import shutil
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core import formats
from core.containers import console_crypto
from core.i18n import tr
from core.project_library import images
from core.project_library.registry import EMULATOR_KEY, emulator_setting
from utils.logging_utils import log_info

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]

UNPACKED_NAME = "unpacked"
BUILD_DIR_NAME = "build"
WARNINGS_FILE = "BUILD_WARNINGS.txt"   # the warnings of a build, beside its result
PLACEHOLDER = "{path}"
MB = 1024 * 1024
MIN_MARGIN = 256 * MB   # the room an unpack needs beyond the image: 10 % of its size or this, whichever is larger


class Cancel(Exception):
    """Raised when the user cancels a job that has no partial result to keep."""


def _unique_sibling(parent: Path, name: str) -> Path:
    """``parent/name``, or ``parent/name-2``, ``name-3`` ... when that name is taken."""
    candidate = parent / name
    number = 2
    while candidate.exists():
        candidate = parent / f"{name}-{number}"
        number += 1
    return candidate


def source_subfolders(rules: Any) -> List[str]:
    """The source folders ``get_source_subfolder`` names (one path or a list of paths), in order."""
    value = rules.get_source_subfolder()
    if not value:
        return []
    return [value] if isinstance(value, str) else [str(item) for item in value if item]


def source_root(rules: Any, root: Path) -> Optional[Path]:
    """The first named source folder that exists under ``root``; ``root`` when the plugin names none; else None."""
    candidates = source_subfolders(rules)
    if not candidates:
        return root
    folders = (root.joinpath(*item.split("/")) for item in candidates)
    return next((folder for folder in folders if folder.is_dir()), None)


def _remove_own(folder: Path) -> None:
    """Remove a folder this module made (a temporary one). Never called on a folder the user chose."""
    shutil.rmtree(folder, ignore_errors=True)


def run_unpack(rules: Any, sources: Dict[str, str], project_dir: str | os.PathLike,
               progress: Progress, is_cancelled: Cancelled,
               key_provider: Optional[Callable[[str], Optional[str]]] = None) -> Optional[str]:
    """Unpack the role files of a new project into ``project_dir/unpacked``.

    Returns the project's source folder, or None when the plugin needs no unpacking. That is the unpacked folder,
    or the first subfolder from ``get_source_subfolder`` that exists. Raises ``Cancel`` when the user cancelled; the temporary folder
    is then removed and nothing else is touched. Raises ``ValueError`` before writing when the drive has too little
    room for a game image, when the plugin unpacks nothing and has no file format for a chosen game image, or when the
    unpacked tree lacks the source subfolder. ``key_provider`` maps a console id to its key file path for this job
    only (see ``console_crypto.key_source``).
    """
    project = Path(project_dir)
    _check_free_space(project, sources)
    temporary = project / f".unpack-{uuid.uuid4().hex}"
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        with console_crypto.key_source(key_provider):
            result = rules.unpack_sources(sources, str(temporary), progress, is_cancelled)
        if is_cancelled():
            raise Cancel()
        if result is None:
            _refuse_unread_image(rules, sources)
            _remove_own(temporary)
            # A game image is used as it is only when the plugin has a file format for it.
            if any(images.identify(path) and formats.resolve(rules, path) is None for path in sources.values()):
                raise ValueError(tr("This game's plugin cannot unpack this image. Choose an already-extracted "
                                    "game folder with its text tables unpacked from game archives."))
            return None
        root = source_root(rules, temporary)
        if root is None:
            raise ValueError(tr("The unpacked files have no folder {0}.", " | ".join(source_subfolders(rules))))
        final = _unique_sibling(project, UNPACKED_NAME)
        os.replace(temporary, final)
        log_info(f"Unpacked {len(sources)} source files into {final}.")
        return str(final / root.relative_to(temporary))
    except BaseException:
        _remove_own(temporary)
        raise


def remove_new_entries(project_dir: str | os.PathLike, before: Optional[List[str]]) -> None:
    """Remove what a create added to its folder: every entry whose name was not in ``before``.

    ``before`` is the list of names the folder held before the create, or None when the folder did not exist then;
    that folder is removed whole. Entries from before are never touched.
    """
    folder = Path(project_dir)
    if before is None:
        _remove_own(folder)
        return
    if not folder.is_dir():
        return
    kept = set(before)
    for entry in list(folder.iterdir()):
        if entry.name in kept:
            continue
        if entry.is_dir() and not entry.is_symlink():
            _remove_own(entry)
        else:
            entry.unlink(missing_ok=True)


def entries_before(project_dir: str | os.PathLike) -> Optional[List[str]]:
    """The names in ``project_dir`` now (for ``remove_new_entries``), or None when the folder does not exist."""
    folder = Path(project_dir)
    if not folder.is_dir():
        return None
    return [entry.name for entry in folder.iterdir()]


def _refuse_unread_image(rules: Any, sources: Dict[str, str]) -> None:
    """Refuse a game image that the plugin neither unpacked nor reads as it is (it has no file format for it).

    The plugin returned no folder for it (no unpack hook, or none for this image), so nothing is created.
    """
    for path in sources.values():
        kind = (images.identify(path) or {}).get("kind")
        if kind in images.UNPACK_KINDS and formats.resolve(rules, path) is None:
            raise ValueError(tr("This game cannot read the {0} image {1}. Unpack the image into a folder first, "
                                "then add that folder.", tr(images.KIND_LABEL[kind]), Path(path).name))


def _free_bytes(path: Path) -> int:
    """Free bytes on the drive of ``path``, or of its nearest existing parent."""
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def _check_free_space(project: Path, sources: Dict[str, str]) -> None:
    """Fail before anything is written when the drive cannot hold the unpacked files of a game image.

    Every game image that an unpack step reads (``images.UNPACK_KINDS``: GameCube, Nintendo DS, 3DS, Switch, Wii)
    needs the room. Any other file is used as it is, so it is not checked. The room is the image size plus 10 % of
    it, or ``MIN_MARGIN``, whichever is larger.
    """
    found = [path for path in sources.values()
             if (images.identify(path) or {}).get("kind") in images.UNPACK_KINDS]
    if not found:
        return
    size = sum(images.unpack_room(path) for path in found)   # an .nsz counts its decompressed program too
    needed = size + max(size // 10, MIN_MARGIN)
    free = _free_bytes(project)
    if free < needed:
        raise ValueError(tr("Not enough free space on {0}: unpacking needs about {1} MB, and {2} MB is free.",
                            str(project), str(-(-needed // MB)), str(free // MB)))


def run_build(rules: Any, target_id: str, project_dir: str | os.PathLike, source_dir: str, translation_dir: str,
              progress: Progress, is_cancelled: Cancelled) -> str:
    """Build ``target_id`` into ``project_dir/build/<target id>`` and return the result path.

    The build is written to a temporary folder first. An existing result of the same target is replaced.
    Raises ``Cancel`` on cancel. Raises ``ValueError`` when the plugin declares no such target.
    """
    build_root = Path(project_dir) / BUILD_DIR_NAME
    build_root.mkdir(parents=True, exist_ok=True)
    temporary = build_root / f".{target_id}-{uuid.uuid4().hex}"
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        result = rules.build_target(target_id, source_dir, translation_dir, str(temporary), progress, is_cancelled)
        if is_cancelled():
            raise Cancel()
        final = build_root / target_id
        previous = None
        if final.exists():
            previous = build_root / f".{target_id}-old-{uuid.uuid4().hex}"
            os.replace(final, previous)
        os.replace(temporary, final)
        if previous is not None:
            _remove_own(previous)
    except BaseException:
        _remove_own(temporary)
        raise
    return _rebase(result, temporary, final)


def _rebase(result: str, temporary: Path, final: Path) -> str:
    """The build may return a path inside its temporary folder; that path moves with the folder."""
    try:
        return str(final / Path(result).relative_to(temporary))
    except ValueError:
        return result


def export_build(build_path: str | os.PathLike, destination: str | os.PathLike, progress: Progress,
                 is_cancelled: Cancelled) -> str:
    """Copy a build folder to ``destination``, a folder that does not exist yet or is empty.

    The copy goes to a temporary sibling first and is renamed into place. A single-file build is copied as a file.
    Raises ``ValueError`` when the destination already holds files.
    """
    source = Path(build_path)
    target = Path(destination)
    if target.exists() and any(target.iterdir()):
        raise ValueError(tr("The folder is not empty: {0}", target))
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = parent / f".export-{uuid.uuid4().hex}"
    try:
        if source.is_dir():
            files = [path for path in source.rglob("*") if path.is_file()]
            temporary.mkdir()
            for position, path in enumerate(files, start=1):
                if is_cancelled():
                    raise Cancel()
                relative = path.relative_to(source)
                (temporary / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, temporary / relative)
                progress(100 * position // max(1, len(files)), relative.as_posix())
        else:
            temporary.mkdir()
            shutil.copy2(source, temporary / source.name)
        if target.exists():
            target.rmdir()
        os.replace(temporary, target)
    except BaseException:
        _remove_own(temporary)
        raise
    return str(target if source.is_dir() else target / source.name)


def emulator_platform(target_platforms: List[str], project_platform: str) -> str:
    """The platform a build's result runs on: the target's only platform, else the project's platform, else "".

    A target that names several platforms (or none) takes the project's platform.
    """
    names = [name for name in target_platforms if name]
    if len(names) == 1:
        return names[0]
    return project_platform or ""


def emulator_template_for(settings: Dict[str, Any], platform: str) -> str:
    """The emulator command of ``platform``. A platform with its own setting (even an empty one) uses that setting;
    a platform without one uses the older shared command, so a registry written before per-platform commands keeps
    working until each platform has its own.
    """
    name = emulator_setting(platform) if platform else EMULATOR_KEY
    if name in settings:
        return str(settings.get(name) or "").strip()
    return str(settings.get(EMULATOR_KEY) or "").strip()


def emulator_working_dir(argv: List[str]) -> str:
    """The folder a launched emulator starts in: the folder of its program, as a launcher's pushd does.

    Empty when the program is a bare name or its folder is not there.
    """
    if not argv or not os.path.isabs(argv[0]):
        return ""
    folder = os.path.dirname(argv[0])
    return folder if os.path.isdir(folder) else ""


def emulator_argv(template: str, path: str, posix: Optional[bool] = None) -> List[str]:
    """The program and its arguments for a user's emulator command template.

    The template is split into words first, then ``{path}`` is replaced inside each word, so a path with spaces stays
    one argument. ``posix`` follows the platform by default (Windows keeps the quotes, so they are removed).
    Returns an empty list for an empty template.
    """
    if posix is None:
        posix = os.name != "nt"
    words = shlex.split(template, posix=posix)
    if not posix:
        words = [word[1:-1] if len(word) >= 2 and word[0] == word[-1] == '"' else word for word in words]
    if not words:
        return []
    argv = [word.replace(PLACEHOLDER, path) for word in words]
    if not any(PLACEHOLDER in word for word in words):
        argv.append(path)
    return argv


def write_warnings(folder: str | os.PathLike, lines: List[str]) -> None:
    """Write a build's warnings into its result folder, one per line, atomically. Writes nothing for no warning."""
    if not lines:
        return
    path = Path(folder) / WARNINGS_FILE
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_warnings(result: str | os.PathLike) -> List[str]:
    """The warnings of the build that wrote ``result`` (a file in the build folder, or the folder itself)."""
    path = Path(result)
    try:
        text = ((path if path.is_dir() else path.parent) / WARNINGS_FILE).read_text(encoding="utf-8")
    except OSError:
        return []
    return [line for line in text.splitlines() if line.strip()]
