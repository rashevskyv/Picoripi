"""Share a project with another person: pack it into one zip, and unpack such a zip with the other person's paths.

The package holds the project folder, the translation files and the linked series glossaries. It never holds the
original game files: the other person points the imported project at their own copy. Every absolute path in the
project's JSON files is written as a token of the folder it is in (``{share:source}/romfs/a.msbt``); a path outside
those folders is cleared, so the package carries no path of the sender's computer. Import writes the new absolute
paths back, because the editor reads ``source_path`` and ``translation_path`` as absolute paths.

Both functions run on a worker thread.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from core.glossary.series import GROUP_METADATA_KEY, METADATA_KEY
from core.i18n import tr
from utils.atomic_io import atomic_write_json
from utils.constants import APP_VERSION

FORMAT = 1
MANIFEST = "share.json"
PROJECT, TRANSLATION, GLOSSARIES = "project", "translation", "glossaries"
TOKEN = "{share:%s}"
PROJECT_FILE_NAME = "project.uiproj"
# Caches, backups and folders made again on the other computer. Names that start with a dot (the session files,
# temporary unpack and export folders) are never packed either: the session is a pickle, unsafe to load from others.
_SKIP_DIRS = {"unpacked", "build", "__pycache__"}
_SKIP_FILES = {"issues_cache.json", "archive_scan.json"}


def _skipped(name: str, is_dir: bool) -> bool:
    if name.startswith("."):
        return True
    if is_dir:
        return name in _SKIP_DIRS
    return name in _SKIP_FILES or ".bak" in name or name.endswith((".tmp", ".unreadable"))


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _is_absolute(value: str) -> bool:
    return len(value) > 2 and (os.path.isabs(value) or value[1:3] in (":\\", ":/") or value.startswith("\\\\"))


def _inside(path: Path, folder: Optional[Path]) -> bool:
    return folder is not None and (path == folder or folder in path.parents)


def _exported(value: Any, roots: List[Tuple[str, str]], exact: Dict[str, str], cleared: List[str], where: str) -> Any:
    """``value`` with every absolute path as a token of its root, or "" (recorded in ``cleared``) without a root."""
    if isinstance(value, dict):
        return {key: _exported(item, roots, exact, cleared, f"{where}.{key}") for key, item in value.items()}
    if isinstance(value, list):
        return [_exported(item, roots, exact, cleared, where + "[]") for item in value]
    if not isinstance(value, str) or not _is_absolute(value):
        return value
    norm = _norm(value)
    if norm in exact:
        return exact[norm]
    for root, token in roots:  # the longest root first: a translation folder inside the project folder wins
        if norm == root or norm.startswith(root.rstrip(os.sep) + os.sep):
            rest = os.path.normpath(value)[len(root):].strip("\\/").replace("\\", "/")
            return token + ("/" + rest if rest else "")
    cleared.append(where)
    return ""


def _imported(value: Any, roots: Dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _imported(item, roots) for key, item in value.items()}
    if isinstance(value, list):
        return [_imported(item, roots) for item in value]
    if isinstance(value, str) and value.startswith("{share:"):
        token, _, rest = value.partition("}")
        root = roots.get(token + "}")
        if root is None:
            return ""
        return os.path.normpath(os.path.join(root, *[part for part in rest.split("/") if part]))
    return value


def _linked_glossaries(metadata: Dict[str, Any]) -> List[Path]:
    found = []
    for key in (METADATA_KEY, GROUP_METADATA_KEY):
        links = metadata.get(key)
        for link in [links] if isinstance(links, str) else (links if isinstance(links, list) else []):
            if isinstance(link, str) and link.strip() and Path(link).is_file():
                found.append(Path(link))
    return found


def export_project(project_file: str | os.PathLike, package: str | os.PathLike) -> Dict[str, Any]:
    """Write the share package of a project to ``package`` (a zip). Returns a summary for the user.

    The zip is written beside its final name and renamed into place when it is complete.
    """
    project_path = Path(project_file)
    project_dir = project_path.parent
    data = json.loads(project_path.read_text(encoding="utf-8-sig"))
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    source = Path(metadata["source_path"]) if metadata.get("source_path") else None
    translation = Path(metadata["translation_path"]) if metadata.get("translation_path") else None
    if translation is not None and source is not None and _inside(translation, source):
        translation = None  # the translation is written into the game files: those are never packed

    # A single translation file goes in as translation/<name>, so its root is its folder.
    translation_root = translation.parent if translation is not None and translation.is_file() else translation
    roots = [(_norm(str(folder)), TOKEN % name) for folder, name in
             ((source, "source"), (translation_root, TRANSLATION), (project_dir, PROJECT)) if folder is not None]
    roots.sort(key=lambda root: len(root[0]), reverse=True)
    exact: Dict[str, str] = {}
    glossaries: List[Tuple[Path, str]] = []
    for number, glossary in enumerate(_linked_glossaries(metadata), start=1):
        if _norm(str(glossary)) not in exact and not any(_inside(glossary, f) for f in (project_dir, translation)):
            member = f"{number}_{glossary.name}"
            exact[_norm(str(glossary))] = TOKEN % GLOSSARIES + "/" + member
            glossaries.append((glossary, member))

    cleared: List[str] = []
    counts = {"project_files": 0, "translation_files": 0, "glossaries": len(glossaries)}
    target = Path(package)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for root, dirs, files in os.walk(project_dir):
                here = Path(root)
                dirs[:] = sorted(name for name in dirs if not _skipped(name, True)
                                 and not _inside(here / name, source) and not _inside(here / name, translation))
                for name in sorted(files):
                    path = here / name
                    if _skipped(name, False) or path == translation or _inside(path, source):
                        continue
                    member = f"{PROJECT}/{path.relative_to(project_dir).as_posix()}"
                    _pack_file(archive, path, member, roots, exact, cleared)
                    counts["project_files"] += 1
            if translation is not None and translation.is_file():
                archive.write(translation, f"{TRANSLATION}/{translation.name}")
                counts["translation_files"] += 1
            elif translation is not None and translation.is_dir():
                for path in sorted(p for p in translation.rglob("*") if p.is_file()):
                    archive.write(path, f"{TRANSLATION}/{path.relative_to(translation).as_posix()}")
                    counts["translation_files"] += 1
            for glossary, member in glossaries:
                _pack_file(archive, glossary, f"{GLOSSARIES}/{member}", roots, exact, cleared)
            manifest = {
                "format": FORMAT, "app_version": APP_VERSION, "name": data.get("name", ""),
                "plugin_name": data.get("plugin_name", ""), "project_file": project_path.name,
                "is_directory_mode": bool(metadata.get("is_directory_mode", True)),
                "source_name": source.name if source is not None else "", "cleared": cleared, **counts,
            }
            archive.writestr(MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False))
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return manifest


def _pack_file(archive: zipfile.ZipFile, path: Path, member: str, roots, exact, cleared: List[str]) -> None:
    """A JSON file goes in with its paths rewritten; any other file goes in as it is."""
    if path.suffix.lower() in (".json", ".uiproj"):
        try:
            content = json.loads(path.read_text(encoding="utf-8-sig"))
        except (ValueError, UnicodeDecodeError):
            archive.write(path, member)
            return
        content = _exported(content, roots, exact, cleared, member)
        archive.writestr(member, json.dumps(content, indent=2, ensure_ascii=False))
    else:
        archive.write(path, member)


def read_manifest(package: str | os.PathLike) -> Dict[str, Any]:
    """The manifest of a share package. Raises ``ValueError`` when the file is not one this version reads."""
    try:
        with zipfile.ZipFile(package) as archive:
            manifest = json.loads(archive.read(MANIFEST).decode("utf-8"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        raise ValueError(tr("This file is not a shared Picoripi project.")) from exc
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise ValueError(tr("This shared project was made by a newer Picoripi. Update Picoripi to import it."))
    return manifest


def _member_path(name: str) -> Optional[PurePosixPath]:
    """The safe relative path of a zip member, or None for a name that would leave the folder."""
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or ":" in name or not path.parts:
        return None
    return path


def import_package(package: str | os.PathLike, destination: str | os.PathLike,
                   source_path: str | os.PathLike) -> Dict[str, Any]:
    """Unpack a share package into ``destination`` and point it at ``source_path`` (the person's own game files).

    The project goes to ``destination/picoripi``, the translation to ``destination/translation`` and the glossaries
    to ``destination/glossaries``. None of them may hold files yet. Returns the manifest with ``project_file``, the new
    project file. The files are unpacked into a temporary folder first and moved into place when all are written.
    """
    manifest = read_manifest(package)
    dest = Path(os.path.abspath(str(destination)))
    places = {PROJECT: dest / "picoripi", TRANSLATION: dest / TRANSLATION, GLOSSARIES: dest / GLOSSARIES}
    for place in places.values():
        if place.exists() and any(place.iterdir()):
            raise ValueError(tr("The folder is not empty: {0}", place))
    roots = {TOKEN % "source": os.path.abspath(str(source_path)),
             **{TOKEN % name: os.path.abspath(str(place)) for name, place in places.items()}}
    dest.mkdir(parents=True, exist_ok=True)
    temporary = dest / f".share-import-{uuid.uuid4().hex}"
    try:
        with zipfile.ZipFile(package) as archive:
            for info in archive.infolist():
                member = _member_path(info.filename)
                if member is None or member.parts[0] not in places:
                    if info.filename != MANIFEST:
                        raise ValueError(tr("The shared project holds a file outside its folders: {0}",
                                            info.filename))
                    continue
                if info.is_dir():
                    continue
                target = temporary.joinpath(*member.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as stream, open(target, "wb") as out:
                    shutil.copyfileobj(stream, out)
        for path in list(temporary.rglob("*")):
            if path.is_file() and path.suffix.lower() in (".json", ".uiproj") and path.parts[len(temporary.parts)] != TRANSLATION:
                _rewrite_imported(path, roots)
        project_file = temporary / PROJECT / str(manifest.get("project_file") or PROJECT_FILE_NAME)
        if not project_file.is_file():
            raise ValueError(tr("This file is not a shared Picoripi project."))
        data = json.loads(project_file.read_text(encoding="utf-8"))
        data["id"] = str(uuid.uuid4())  # a copy beside the original must not share its temporary folder
        metadata = data.setdefault("metadata", {})
        metadata["source_path"] = roots[TOKEN % "source"]
        mapped = Path(str(metadata.get("translation_path") or ""))
        if not _inside(mapped, places[TRANSLATION]):  # it was cleared, or it pointed into the game files
            metadata["translation_path"] = roots[TOKEN % TRANSLATION]
        atomic_write_json(project_file, data, indent=4, ensure_ascii=False)
        for name, place in places.items():
            if (temporary / name).exists():
                if place.exists():
                    place.rmdir()  # checked empty above
                os.replace(temporary / name, place)
        places[TRANSLATION].mkdir(exist_ok=True)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return {**manifest, "project_file": str(places[PROJECT] / project_file.name)}


def _rewrite_imported(path: Path, roots: Dict[str, str]) -> None:
    try:
        content = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return
    atomic_write_json(path, _imported(content, roots), indent=2, ensure_ascii=False)
