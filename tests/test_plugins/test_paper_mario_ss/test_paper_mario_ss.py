"""Paper Mario: Sticker Star plugin: the tag catalogue (synthetic) and the real EU game files (skipped where the
workspace is not on this machine).

Real data: every English MSBT loads and saves back byte for byte; both bitmap fonts open and pack back unchanged;
every text picture reads and writes back unchanged.
"""
import romhacking_root
import json
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.common.msbt import Tag
from plugins.paper_mario_ss import tags
from plugins.paper_mario_ss.rules import GameRules

WS = romhacking_root.under('Paper Mario\\Sticker Star')
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "paper_mario_ss"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _u16(text: str) -> bytes:
    return text.encode("utf-16-le")


def test_named_tags_encode_back_to_the_same_bytes():
    icon = Tag(2, 2, len(_u16("mic_a")).to_bytes(2, "little") + _u16("mic_a") + bytes([0x12, 0, 5, 0, 0x18, 0, 0x18, 0]))
    choice = Tag(3, 0, bytes([0, 0, 0xFF, 0xFF, 0, 0, 0x64, 0]) + len(_u16("yesno")).to_bytes(2, "little") + _u16("yesno"))
    number = Tag(3, 2, bytes([0, 0]) + len(_u16("%2d")).to_bytes(2, "little") + _u16("%2d"))
    wait = Tag(4, 4, (1000).to_bytes(4, "little"))
    for token, shown in ((icon, "{Icon:mic_a:18:5:24:24}"), (choice, "{Choice:0:-1:0:100:yesno}"),
                         (number, "{Number:0:%2d}"), (wait, "{Wait:1000}")):
        text = tags.to_editor([token], True)
        assert text == shown
        assert tags.from_editor(text, True) == [token]


def test_unknown_tags_stay_raw_and_round_trip():
    token = Tag(2, 1, bytes(2))
    text = tags.to_editor([token], True)
    assert text == "{tag:2:1:0000}"
    assert tags.from_editor(text, True) == [token]


def test_every_english_msbt_saves_back_byte_for_byte():
    files = sorted(_need(SOURCE / "romfs" / "messages" / "EU_English").glob("*.msbt"))
    assert len(files) == 46
    messages = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        messages += len(blocks[0])
    assert messages == 2859


def test_both_fonts_open_and_pack_back_unchanged():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert [source.name for source in found] == ["pop_120px.bcfnz", "pop_240px.bcfnz"]
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract("bcfnt", data)
        assert font_formats.pack("bcfnt", metadata, sheets, data) == data
        assert "Ж" not in font_formats.char_map(metadata)


def test_every_text_picture_reads_and_writes_back():
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    found = texture_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    files = sorted({source.source_path for source in found})
    assert len(files) == 103   # 51 language pictures, 50 UI layouts with textures, 2 atlases
    formats = set()
    for path in files:
        data = Path(path).read_bytes()
        textures = texture_formats.read("cgfx", data)
        formats.update(texture.pixel_format for texture in textures)
        assert texture_formats.write("cgfx", data, {i: texture.image for i, texture in enumerate(textures)}) == data, path
    assert {"ETC1", "ETC1A4", "RGBA4"} <= formats
