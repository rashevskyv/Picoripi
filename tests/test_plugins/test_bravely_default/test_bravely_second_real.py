"""Bravely Second: End Layer (3DS, USA) on the real game files (skipped where the workspace is not on this machine).

The English tables (Common_en, the English Script/Scene files and Graphics/UI) load and save back byte for byte,
both fonts (Font and FontK) pack back unchanged, and every picture of a sample reads and writes back unchanged.
"""
import romhacking_root
import json
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.bravely_default.rules import EXTENSIONS, GameRules

WS = romhacking_root.under('Bravely\\Second\\3DS')
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "bravely_default"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_every_english_table_saves_back_byte_for_byte():
    files = sorted(p for p in _need(SOURCE / "romfs" / "Common_en").rglob("*") if p.suffix in EXTENSIONS)
    files += sorted(p for p in _need(SOURCE / "romfs" / "Script").rglob("*") if p.suffix in EXTENSIONS)
    assert len(files) == 1284
    strings = non_empty = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        strings += len(blocks[0])
        non_empty += sum(1 for text in blocks[0] if text)
    assert (strings, non_empty) == (71219, 49216)


def test_both_fonts_open_and_pack_back_unchanged():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert len(found) == 4, [source.source_path for source in found]
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract("bcfnt", data)
        assert font_formats.pack("bcfnt", metadata, sheets, data) == data, source.source_path


@pytest.mark.timeout(600)  # resolve() decodes all 5,073 ETC1 pictures: about 100 s alone, more under load
def test_sample_pictures_read_and_write_back():
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    _need(SOURCE / "romfs" / "Graphics" / "UI")
    found = texture_sources.resolve(descriptors, {"source_path": str(SOURCE), "translation_path": ""})
    assert len(found) >= 5073
    for source in found[:: max(1, len(found) // 40)]:
        data = Path(source.source_path).read_bytes()
        texture = texture_formats.read("bflim", data)[0]
        assert texture_formats.write("bflim", data, {0: texture.image}) == data, source.key
