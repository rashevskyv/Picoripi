"""Super Mario Galaxy 1 and 2: unpack every version's text and fonts into one project source folder.

Layout of the unpacked folder (the project's source root)::

    MessageData/<archive>.smgmsg        the editable messages of one message archive: one row per label over every
                                        version (messages.py). SMG1 has Message.arc (and System.arc on the Switch);
                                        SMG2 keeps one archive per zone, so it has one document per zone.
    references.smgref                   every other language and version by archive and label (reference columns)
    versions/wii/...                    the USA Wii disc: sys/*, every <Lang>/MessageData/*.arc, LayoutData/Font.arc
    versions/switch/romfs/...           the Switch game: every <Lang>/MessageData/*.arc, the English Font.arc
    versions/<game id>/...              any other Wii disc of the game (a reference only): its message archives
    versions/<version>/source.json      the image it came from

``GAMES`` holds what differs between the games (disc ids, Switch title ids, Nebula); files are found by their path,
never by game. The English slot of a version is the first of ``WII_SLOTS`` / ``SWITCH_SLOTS`` that holds a
``MessageData`` folder (SMG1, checked on the discs: Wii USA ``UsEnglish``, no ``LocalizeData``; Switch ``EuEnglish``
and ``UsEnglish``; SMG2 Switch ``LocalizeData/EuEnglish``). A build writes every English slot of the Switch.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core.project_library import images
from utils.atomic_io import atomic_write_bytes

from . import messages

WII = "wii"
SWITCH = "switch"
GAMES = {
    "smg1": {"name": "Super Mario Galaxy", "wii": "RMGE01", "wii_prefix": "RMG", "switch": "010099C022B96000",
             "nebula": True},
    "smg2": {"name": "Super Mario Galaxy 2", "wii": "SB4E01", "wii_prefix": "SB4", "switch": "0100FD8022DAA000",
             "nebula": False},
}
WII_REVISION = 0
DOCUMENT_DIR = "MessageData"
DOCUMENT_SUFFIX = ".smgmsg"
REFERENCES = "references.smgref"
VERSIONS = "versions"
MESSAGE_DIR = "MessageData"
FONT = "LayoutData/Font.arc"
WII_SLOTS = ("files/LocalizeData/UsEnglish", "files/UsEnglish", "files")
SWITCH_SLOTS = ("romfs/LocalizeData/EuEnglish", "romfs/LocalizeData/UsEnglish", "romfs/EuEnglish", "romfs/UsEnglish")

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def identify(path: str) -> Optional[Dict[str, str]]:
    """``{"role", "platform", "game"}`` of a file of either game: the USA Wii disc rev 0, the Switch game, or another
    Wii disc of the game (a reference)."""
    found = images.identify(path)
    if not found:
        return None
    game_id = str(found["game_id"]).upper()
    for game, facts in GAMES.items():
        if found["kind"] == images.KIND_WII and game_id == facts["wii"] and found.get("revision") == WII_REVISION:
            return {"role": WII, "platform": WII, "game": game}
        if found["kind"] == images.KIND_WII and game_id.startswith(facts["wii_prefix"]):
            return {"role": "wii_reference", "platform": WII, "game": game}
        if found["kind"] == images.KIND_SWITCH and game_id == facts["switch"] and \
                found.get("title_kind") in ("base", ""):
            return {"role": SWITCH, "platform": SWITCH, "game": game}
    return None


def _is_message(path: str) -> bool:
    return f"/{MESSAGE_DIR}/" in path and path.endswith(".arc")


def _wanted(role: str) -> Callable[[str], bool]:
    if role == WII:
        return lambda path: path.startswith("sys/") or _is_message(path) or path.endswith("/" + FONT)
    if role == SWITCH:
        return lambda path: _is_message(path) or path.endswith(("EuEnglish/" + FONT, "UsEnglish/" + FONT))
    return _is_message


def unpack(sources: Dict[str, str], target_dir: str, progress: Progress, is_cancelled: Cancelled) -> Optional[str]:
    """Extract each role's files into ``target_dir/versions/<version>`` and write the message documents.

    Returns ``target_dir``, or None when cancelled or when no source is the Wii or Switch game.
    """
    target = Path(target_dir)
    order = [role for role in (WII, SWITCH) if sources.get(role)] + \
        sorted(role for role in sources if role not in (WII, SWITCH) and sources[role])
    if not any(role in (WII, SWITCH) for role in order):
        return None
    for step, role in enumerate(order):
        found = images.identify(sources[role]) or {}
        version = role if role in (WII, SWITCH) else str(found.get("game_id") or role)
        folder = target / VERSIONS / version

        def report(percent: int, text: str, step: int = step) -> None:
            progress((100 * step + percent) // (len(order) + 1), text)
        if images.extract(sources[role], folder, report, is_cancelled, select=_wanted(role)) is None:
            return None
        atomic_write_bytes(folder / "source.json", json.dumps(
            {"image": str(sources[role]), "game_id": found.get("game_id", ""), "role": role}, indent=1).encode())
    write_documents(target)
    write_references(target, is_cancelled)
    progress(100, "")
    return str(target)


# -- where the English text is ------------------------------------------------------------------------------------

def english_slots(source_root: Path, version: str) -> List[str]:
    """The English slots (folders inside the version that hold ``MessageData``): Wii the one the game reads, Switch
    every one."""
    base = source_root / VERSIONS / version
    candidates = WII_SLOTS if version == WII else SWITCH_SLOTS
    found = [slot for slot in candidates if any((base / slot / MESSAGE_DIR).glob("*.arc"))]
    return found[:1] if version == WII else found


def archives(source_root: Path, version: str) -> Dict[str, Path]:
    """``{archive stem: file}`` of the message archives in the version's first English slot."""
    slots = english_slots(source_root, version)
    if not slots:
        return {}
    folder = source_root / VERSIONS / version / slots[0] / MESSAGE_DIR
    return {path.stem: path for path in sorted(folder.glob("*.arc"))}


def document_rel(stem: str) -> str:
    """The project path of the document of message archive ``stem``."""
    return f"{DOCUMENT_DIR}/{stem}{DOCUMENT_SUFFIX}"


def english_versions(source_root: Path, stem: str) -> List[Tuple[str, Dict[str, str]]]:
    """``[(version, {label: text})]`` of archive ``stem`` in the first English slot of each unpacked version."""
    found = []
    for version in (WII, SWITCH):
        path = archives(source_root, version).get(stem)
        if path is not None:
            found.append((version, messages.texts_by_label(path.read_bytes())))
    return found


def write_documents(source_root: Path) -> List[str]:
    """One ``.smgmsg`` per message archive: the Wii English messages, then the labels only the Switch has."""
    stems = sorted(set(archives(source_root, WII)) | set(archives(source_root, SWITCH)))
    for stem in stems:
        rows = messages.union_rows(english_versions(source_root, stem))
        atomic_write_bytes(source_root / document_rel(stem), messages.make_document(rows))
    return [document_rel(stem) for stem in stems]


def game_of(source_root: Path) -> Optional[str]:
    """``smg1`` or ``smg2`` from the game id of the unpacked versions, or None."""
    for path in sorted((source_root / VERSIONS).glob("*/source.json")):
        try:
            game_id = str(json.loads(path.read_text(encoding="utf-8")).get("game_id", "")).upper()
        except (OSError, ValueError):
            continue
        for game, facts in GAMES.items():
            if game_id.startswith(facts["wii_prefix"]) or game_id == facts["switch"]:
                return game
    return None


# -- reference columns --------------------------------------------------------------------------------------------

def write_references(source_root: Path, is_cancelled: Cancelled) -> None:
    """``references.smgref``: every other language and version as ``{column: {archive: {label: text}}}``, read here
    (on the unpack worker) so opening the project reads one file. The project's own English slot is left out."""
    own = {source_root / VERSIONS / WII / slot / MESSAGE_DIR for slot in english_slots(source_root, WII)}
    columns: Dict[str, Dict[str, Dict[str, str]]] = {}
    for folder in sorted({path.parent for path in (source_root / VERSIONS).glob(f"**/{MESSAGE_DIR}/*.arc")}):
        if is_cancelled():
            return
        if folder in own:
            continue
        version = folder.relative_to(source_root / VERSIONS).parts[0]
        column = f"{folder.parent.name} ({version})"
        columns[column] = {path.stem: messages.texts_by_label(path.read_bytes()) for path in sorted(folder.glob("*.arc"))}
    add_references(source_root, columns)


def add_references(source_root: Path, columns: Dict[str, Dict[str, Dict[str, str]]]) -> None:
    """Add or replace reference columns (``{column: {archive stem: {label: text}}}``) in ``references.smgref``."""
    path = source_root / REFERENCES
    try:
        known = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        known = {}
    known.update(columns)
    atomic_write_bytes(path, json.dumps(known, ensure_ascii=False).encode("utf-8"))
