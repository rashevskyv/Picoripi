"""A Link Between Worlds plugin on the real EU game files (skipped where the workspace is not on this machine).

Every English MSBT loads and saves back byte for byte with no raw tags left, the shipped catalogue is the
game's own message project, both fonts and every listed text image read and write back unchanged.
"""
import json
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.containers import yaz0
from core.containers.sarc import Sarc
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.common import msbp
from plugins.zelda_albw import tags
from plugins.zelda_albw.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Zelda\A Link Between Worlds")
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "zelda_albw"
UKRAINIAN = "ҐЄІЇґєії"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _sarc_hash(name: str, key: int = 0x65) -> str:
    value = 0
    for byte in name.encode():
        value = (value * key + byte) & 0xFFFFFFFF
    return f"{value:08x}"


def test_every_english_msbt_saves_back_byte_for_byte():
    files = sorted(_need(SOURCE / "romfs" / "EU_English").rglob("*.msbt"))
    assert len(files) == 190
    messages = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        assert not any("{tag:" in text for text in blocks[0]), path.name
        messages += len(blocks[0])
    assert messages == 4956


def test_the_catalogue_is_the_games_message_project():
    region = Sarc(yaz0.decompress(_need(WS / "romfs" / "EU" / "RegionBoot.szs").read_bytes()))
    project = msbp.read(region.files[_sarc_hash("World/Message/CTRJack.msbp")])
    assert project == json.loads((PLUGIN / "msbp.json").read_text(encoding="utf-8"))
    assert [group["name"] for group in tags.PROJECT["tag_groups"]] == ["System", "InsertMessage", "InsertName"]


def test_both_fonts_open_and_pack_back_unchanged():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert [source.name for source in found] == ["MessageFont.bffnt", "HyliaFont.bffnt"]
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract(source.format, data)
        assert font_formats.pack(source.format, metadata, sheets, data) == data
    message_font = font_formats.char_map(font_formats.extract("bcfnt", found[0].read_original())[0])
    assert "Ж" in message_font and not any(char in message_font for char in UKRAINIAN)


def test_every_listed_text_image_reads_and_writes_back():
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    found = texture_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert len(found) == 13
    assert {source.pixel_format for source in found} == {"ETC1A4", "A4", "RGBA8"}
    for source in found:
        data = Path(source.source_path).read_bytes()
        image = texture_formats.read("bflim", data)[0].image
        assert texture_formats.write("bflim", data, {0: image}) == data, source.key
