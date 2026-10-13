"""Rhythm Paradise Megamix plugin: the plugin loads and validates; on the real EU game files (skipped where the
workspace is not on this machine) every English MSBT loads and saves back byte for byte with no raw tags left,
the ten fonts open and pack back unchanged and the English pictures read and write back unchanged."""
import romhacking_root
import json
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.font_formats import sources as font_sources
from plugins.rhythm_paradise_megamix import tags
from plugins.rhythm_paradise_megamix.rules import GameRules
from plugins.testing import check_loads, check_validator

PLUGIN_NAME = "rhythm_paradise_megamix"
WS = romhacking_root.under('Rhythm Paradise Megamix')
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN_NAME


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_the_plugin_loads():
    check_loads(PLUGIN_NAME)


def test_the_validator_passes():
    check_validator(PLUGIN_NAME)


def test_tags_have_the_games_names():
    assert tags.TAGS[(1, 13)][0] == "GameName"
    assert tags.TAGS[(3, 2)][0] == "CharWait"


def test_every_english_msbt_saves_back_byte_for_byte():
    files = sorted(_need(SOURCE / "romfs" / "EUENmessage").rglob("*.msbt"))
    assert len(files) == 18
    messages = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        assert not any("{tag:" in text for text in blocks[0]), path.name
        messages += len(blocks[0])
    assert messages == 5715


def test_the_fonts_open_and_pack_back_unchanged():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert len(found) == 10
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract("bcfnt", data)
        assert font_formats.pack("bcfnt", metadata, sheets, data) == data, source.name


def test_a_few_pictures_read_and_write_back():
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    _need(SOURCE)
    total = 0
    for descriptor in descriptors:
        files = sorted(path for path in SOURCE.glob(descriptor["path"]) if path.is_file())
        assert files, descriptor["path"]
        total += len(files)
        for path in files[::150]:
            data = path.read_bytes()
            textures = texture_formats.read(descriptor["format"], data)
            assert texture_formats.write(descriptor["format"], data, {i: t.image for i, t in enumerate(textures)}) == data, path
    assert total == 2318
