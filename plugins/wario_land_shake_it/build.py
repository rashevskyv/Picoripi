"""Wario Land: Shake It! Wii build: a Riivolution patch and a Dolphin launcher for the USA disc.

The English (USA) message pack is rebuilt from its source pack: each BMG file is rebuilt from its text document, an
unchanged file keeps its bytes, and the GFAC archive is written with the same header fields and entry checksums.
The patch replaces that one pack on the disc.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, List

from core.containers import gfac
from utils.atomic_io import atomic_write_bytes

from . import bmgtext, unpack

MOD_NAME = "WarioLandShakeItUA"
Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def riivolution_xml(name: str, game: str, disc_paths: List[str]) -> str:
    """A Riivolution patch for the USA disc of ``game`` (its three-letter id) that replaces ``disc_paths``."""
    lines = "\n".join(f'\t\t<file disc="/{path}" external="{path}" />' for path in disc_paths)
    return (
        '<wiidisc version="1">\n'
        f'\t<id game="{game}">\n\t\t<region type="E" />\n\t</id>\n'
        f'\t<options>\n\t\t<section name="{name}">\n'
        '\t\t\t<option name="Ukrainian translation" default="1">\n'
        f'\t\t\t\t<choice name="On"><patch id="{name}" /></choice>\n'
        '\t\t\t</option>\n\t\t</section>\n\t</options>\n'
        f'\t<patch id="{name}" root="/{name}">\n{lines}\n\t</patch>\n'
        '</wiidisc>\n')


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
        new_data = bmgtext.rebuild(entry.data, _texts(doc_path))
        entry.data = new_data
    return gfac.write_gfac(archive)


def build_wii_riivolution(source_dir: str, translation_dir: str, output_dir: str, progress: Progress,
                          is_cancelled: Cancelled) -> str:
    source_root = Path(source_dir)
    trans = Path(translation_dir) if translation_dir else source_root
    out = Path(output_dir)
    progress(10, "")
    if is_cancelled():
        return str(out)
    pack = rebuilt_pack(source_root, trans)
    disc_path = unpack.PACK_REL
    atomic_write_bytes(out / MOD_NAME / disc_path, pack)
    progress(70, "")
    xml = out / "riivolution" / f"{MOD_NAME}.xml"
    atomic_write_bytes(xml, riivolution_xml(MOD_NAME, unpack.GAME_PREFIX, [disc_path]).encode("utf-8"))
    image = json.loads((source_root / unpack.VERSIONS / unpack.WII / "source.json").read_text(encoding="utf-8"))["image"]
    descriptor = {"type": "dolphin-game-mod-descriptor", "version": 1, "base-file": image,
                  "display-name": "Wario Land: Shake It! (UA)",
                  "riivolution": {"patches": [{
                      "xml": f"riivolution/{MOD_NAME}.xml", "root": ".",
                      "options": [{"section-name": MOD_NAME, "option-name": "Ukrainian translation", "choice": 1}]}]}}
    atomic_write_bytes(out / f"{MOD_NAME}.json", json.dumps(descriptor, indent=1).encode("utf-8"))
    progress(100, "")
    return str(out)
