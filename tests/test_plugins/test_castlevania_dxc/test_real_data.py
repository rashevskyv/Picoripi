"""Castlevania: The Dracula X Chronicles on the developer's own files (skipped where they are not on this machine).

Every text file of the workspace's ``source`` saves back byte for byte; the fonts pack back unchanged; every text
picture writes back unchanged and keeps an edit; the workspace script (``_shared\\scripts\\zt\\dxc.py``) lays every
RESC pack out again byte for byte and unpacks what ``source`` holds.
"""
import json
import sys
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.castlevania_dxc.rules import GameRules

PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "castlevania_dxc"
RH = Path(r"E:\Emulators\RomHacking")
WS = RH / "Castlevania" / "Dracula X Chronicles"
SOURCE = WS / "source"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _zt():
    scripts = _need(RH / "_shared" / "scripts" / "zt" / "dxc.py").parents[1]
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from zt import dxc, umd
    return dxc, umd


def test_every_text_file_saves_back_byte_for_byte():
    count = lines = 0
    for path in sorted(_need(SOURCE).rglob("*")):
        if path.suffix.lower() not in (".txt", ".bin") or not path.is_file():
            continue
        data = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(data)
        assert rules.save_data_to_json_obj(blocks, names) == data, path
        count, lines = count + 1, lines + len(blocks[0])
    assert count == 41 and lines > 1800


def test_fonts_and_pictures(tmp_path):
    meta = {"source_path": str(_need(SOURCE)), "translation_path": str(tmp_path), "is_directory_mode": True}
    for font in font_sources.resolve(json.loads((PLUGIN / "font_sources.json").read_text("utf-8")), meta):
        raw = font.read_current()
        metadata, sheets = font_formats.extract(font.format, raw, font.params)
        assert font_formats.pack(font.format, metadata, sheets, raw, font.params) == raw
    pictures = texture_sources.resolve(json.loads((PLUGIN / "texture_sources.json").read_text("utf-8")), meta)
    assert len(pictures) >= 190
    for picture in pictures:
        assert not picture.write(picture.read_current().image), picture.key
    for fmt in ("gim", "raw", "tim2", "tim"):
        picture = next(p for p in pictures if p.format == fmt)
        image = picture.read_current().image.copy()
        ImageDraw.Draw(image).rectangle((0, 0, 3, 3), fill=(255, 0, 0, 255))
        assert picture.write(image)
        assert picture.read_current().image.tobytes() != picture.read_original().image.tobytes()


def test_workspace_script_packs_and_unpacks():
    dxc, umd = _zt()
    iso = next(iter(sorted(_need(WS / "ISO").glob("*.iso"))), None) or pytest.skip("no image")
    image = umd.Umd(iso)
    for pack in dxc._packs(image)[:40]:
        data = image.read(dxc.RES + pack)
        assert dxc.resc_build(data, {}) == data, pack
    files = dxc.source_files(image)
    assert all((SOURCE / rel).read_bytes() == data for rel, data in files.items())
    grown = dxc.resc_build(data, {0: b"x" * 70000})
    assert dxc.resc_member(grown, dxc.resc_entries(grown)[0]) == b"x" * 70000 and len(grown) % 2048 == 0
