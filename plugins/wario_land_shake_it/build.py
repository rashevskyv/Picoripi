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
from typing import Callable, List

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
        with open(tmp, "r+b") as stream:
            wii_writer.write_changes(stream, common, {unpack.PACK_REL: pack})
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    progress(100, "")
    return str(target)
