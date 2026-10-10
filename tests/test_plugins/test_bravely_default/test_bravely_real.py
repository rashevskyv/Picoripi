"""Bravely Default plugin on the real EU game files (skipped where the workspace is not on this machine).

Every English BTBF table loads, follows the row-major string rule, saves back byte for byte and grows cleanly;
the font opens and packs back unchanged; every listed picture reads and writes back unchanged.
"""
import json
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.bravely_default.btbf import Btbf
from plugins.bravely_default.rules import EXTENSIONS, GameRules

WS = Path(r"E:\Emulators\RomHacking\Bravely\Default\3DS")
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "bravely_default"
UKRAINIAN = "ҐЄІЇґєії"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_every_english_table_saves_back_byte_for_byte_and_grows():
    files = sorted(p for p in _need(SOURCE / "romfs" / "Common_en").rglob("*") if p.suffix in EXTENSIONS)
    assert len(files) == 401
    strings = non_empty = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        table = Btbf(raw)
        assert len(table.columns) * table.count == len(table.texts), path.name   # the row-major rule held
        grown = [text + "Ґ" if text else text for text in blocks[0]]
        assert Btbf(rules.save_data_to_json_obj([grown], {})).texts == grown, path.name
        strings += len(blocks[0])
        non_empty += sum(1 for text in blocks[0] if text)
    assert (strings, non_empty) == (56865, 39379)


def test_the_font_opens_and_packs_back_unchanged():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert [source.name for source in found] == ["hikari.bcfnt"]
    data = found[0].read_original()
    metadata, sheets = font_formats.extract("bcfnt", data)
    assert font_formats.pack("bcfnt", metadata, sheets, data) == data
    chars = font_formats.char_map(metadata)
    assert "Ж" in chars and "я" in chars and not any(char in chars for char in UKRAINIAN)


def test_every_listed_picture_reads_and_writes_back():
    """The descriptor names all 4403 English pictures (a full sweep, 147 s, was byte-exact for every one);
    the test resolves the title screen through the same descriptor and writes each picture back."""
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    assert len(list(_need(SOURCE / "romfs" / "Graphics" / "UI_en").rglob("*.bclim"))) == 4403
    title = [dict(d, path=d["path"].replace("**", "Layout/crowd.fs/01_Title_new/**")) for d in descriptors]
    found = texture_sources.resolve(title, {"source_path": str(SOURCE), "translation_path": ""})
    assert len(found) == 38
    for source in found:
        data = Path(source.source_path).read_bytes()
        texture = texture_formats.read("bflim", data)[0]
        assert texture_formats.write("bflim", data, {0: texture.image}) == data, source.key
