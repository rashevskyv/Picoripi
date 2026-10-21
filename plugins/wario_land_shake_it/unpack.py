"""Identify the Wario Land: Shake It! USA Wii disc, extract its English message packs, and write the text documents.

The disc's English (USA) message archives are ``files/env/Message/English_USA/__PACK__.gfa``: GFAC archives with
GFCP (BPE) payloads, one BMG file per entry. The unpack writes them under ``versions/wii/`` (the source of a build)
and one text document per BMG file under ``MessageData/`` (what the project translates).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.containers import gfac
from core.project_library import images
from utils.atomic_io import atomic_write_bytes

from . import bmgtext

WII = "wii"
GAME_ID = "RWLE01"
GAME_PREFIX = "RWL"
REVISION = 0
PACK_DIR = "files/env/Message/English_USA/"
PACK_NAME = "__PACK__.gfa"
PACK_REL = PACK_DIR + PACK_NAME
VERSIONS = "versions"
DOC_DIR = "MessageData"
FORMAT_ID = "wario-land-bmg/1"

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def identify(path: str) -> Optional[Dict[str, str]]:
    """``{"role", "platform"}`` of the USA Wii disc (revision 0), or None."""
    found = images.identify(path)
    if not found or found.get("kind") != images.KIND_WII:
        return None
    if str(found.get("game_id", "")).upper() != GAME_ID or found.get("revision") != REVISION:
        return None
    return {"role": WII, "platform": WII}


# The game font (Common, one GFAC pack) and the English picture packs with words in them (U8 archives of TPLs).
FONT_PACK_REL = "files/env/Common/Common/__PACK__.gfa"          # GameFont: menus and messages
FONT_PACK_RELS = (FONT_PACK_REL, "files/env/Common/Movie/__PACK__.gfa", "files/env/Common/Ending/__PACK__.gfa")  # + movieFont (story subtitles), StaffRollFont
TEXTURE_PACK_RELS = (
    "files/env/Common/PadGuide/__PACK__.gfa",
    "files/env/English_USA/CommonResource/__PACK__.gfa",
    "files/env/English_USA/FileSelectResource/__PACK__.gfa",
    "files/env/English_USA/ResultResource/__PACK__.gfa",
    "files/env/English_USA/SelectMainResource/__PACK__.gfa",
    "files/env/English_USA/ShopResource/__PACK__.gfa",
    "files/env/English_USA/TitleResource/__PACK__.gfa",
)


def _select(path: str) -> bool:
    return (path.startswith(PACK_DIR) and path.endswith(PACK_NAME)) or path in FONT_PACK_RELS \
        or path in TEXTURE_PACK_RELS


def doc_rel(entry_name: str) -> str:
    """The document of one BMG entry, relative to the project folder (entry names are unique in the pack)."""
    return f"{DOC_DIR}/{Path(entry_name).stem}.json"


def unpack(sources: Dict[str, str], target_dir: str, progress: Progress, is_cancelled: Cancelled) -> Optional[str]:
    """Extract the English message packs of the disc into ``target_dir`` and write their documents.

    Returns ``target_dir``, or None when cancelled.
    """
    source = sources.get(WII)
    if not source:
        return None
    root = Path(target_dir)
    folder = root / VERSIONS / WII
    progress(0, "")

    def report(percent: int, text: str) -> None:
        progress(percent // 2, text)
    if images.extract(source, folder, report, is_cancelled, select=_select) is None:
        return None
    atomic_write_bytes(folder / "source.json", json.dumps(
        {"image": str(source), "game_id": GAME_ID, "role": WII}, indent=1).encode("utf-8"))
    if not (folder / PACK_REL).is_file():
        return None
    write_documents(root, folder / PACK_REL)
    progress(100, "")
    return str(root)


def write_documents(root: Path, pack_file: Path) -> List[str]:
    """Write one document per BMG entry of ``pack_file``. Returns the document paths."""
    archive = gfac.read_gfac(pack_file.read_bytes())
    written = []
    (root / DOC_DIR).mkdir(parents=True, exist_ok=True)
    for entry in archive.entries:
        doc = {
            "format": FORMAT_ID,
            "pack": PACK_REL,
            "entry": entry.name,
            "messages": bmgtext.read_messages(entry.data),
        }
        path = root / doc_rel(entry.name)
        atomic_write_bytes(path, json.dumps(doc, ensure_ascii=False, indent=1).encode("utf-8"))
        written.append(path.as_posix())
    return written
