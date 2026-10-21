"""Wario Land: Shake It! Wii build: a plain disc image (ISO) with the English message pack replaced.

The base is the USA disc (ISO, WIA or RVZ, from ``versions/wii/source.json``). ``wii_writer.copy_as_iso`` writes a plain
ISO copy and seals every partition again. ``write_changes`` then replaces the English (USA) message pack in the DATA
partition. The rebuilt pack is smaller than the original, so it keeps its place. The original disc is never changed.

The pack is rebuilt from its source pack: each BMG file is rebuilt from its text document, an unchanged file keeps
its bytes, and the GFAC archive keeps the header fields and the entry checksums.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Dict, List

from core.containers import gfac, wii_disc, wii_writer
from core.i18n import tr
from core.project_library import console_keys
from core.project_library.build import Cancel

from . import bmgtext, unpack

ISO_TARGET = "wii_iso"
ISO_NAME = "WarioLandShakeItUA.iso"
Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def _common_key() -> bytes:
    path = console_keys.path_for("wii")
    if not path:
        raise ValueError(tr("Set the Wii key file in the console keys first."))
    return wii_disc.load_common_key(path)


def _texts(doc_path: Path) -> List[str]:
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    return [message["text"] for message in doc["messages"]]


def rebuilt_pack(source_root: Path, translation_dir: Path) -> bytes:
    """The pack bytes with every translated BMG rebuilt. Raises ``ValueError`` when a document does not fit its file."""
    pack_bytes = (source_root / unpack.VERSIONS / unpack.WII / unpack.PACK_REL).read_bytes()
    archive = gfac.read_gfac(pack_bytes)
    for entry in archive.entries:
        doc_rel = unpack.doc_rel(entry.name)
        doc_path = translation_dir / doc_rel
        if not doc_path.is_file():
            doc_path = source_root / doc_rel
        entry.data = bmgtext.rebuild(entry.data, _texts(doc_path))
    return gfac.write_gfac(archive)


def changed_packs(source_root: Path, translation_dir: Path) -> Dict[str, bytes]:
    """The font and picture packs whose translation copy differs from the source (disc path -> bytes).

    The font and the picture packs are edited in the translation folder (``versions/wii/files/env/...``), so their
    edited copy is what the disc gets. The message pack is rebuilt from the documents (``rebuilt_pack``).
    """
    out: Dict[str, bytes] = {}
    copy_root = translation_dir / unpack.VERSIONS / unpack.WII
    if not copy_root.is_dir():
        return out
    for copy in sorted(copy_root.joinpath("files").rglob("*.gfa")):
        rel = copy.relative_to(copy_root).as_posix()
        if rel == unpack.PACK_REL:
            continue
        data = copy.read_bytes()
        source = source_root / unpack.VERSIONS / unpack.WII / rel
        if not source.is_file() or source.read_bytes() != data:
            out[rel] = data
    return out


def build_iso(source_dir: str, translation_dir: str, output_dir: str,
              progress: Progress, is_cancelled: Cancelled) -> str:
    """Write the translated disc image into ``output_dir`` and return its path."""
    source_root = Path(source_dir)
    trans = Path(translation_dir) if translation_dir else source_root
    image = json.loads((source_root / unpack.VERSIONS / unpack.WII / "source.json")
                       .read_text(encoding="utf-8"))["image"]
    common = _common_key()
    progress(0, "")
    pack = rebuilt_pack(source_root, trans)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / ISO_NAME
    tmp = target.with_name(target.name + ".tmp")
    try:
        if not wii_writer.copy_as_iso(str(image), str(tmp), common, progress, is_cancelled):
            raise Cancel()
        progress(96, "")
        changes = {unpack.PACK_REL: pack, **changed_packs(source_root, trans)}
        with open(tmp, "r+b") as stream:
            wii_writer.write_changes(stream, common, changes)
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    progress(100, "")
    return str(target)
