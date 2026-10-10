"""Tomodachi Life / Miitopia plugin on the real EU game files (skipped where a workspace is not on this machine).

Every English MSBT loads and saves back byte for byte, Tomodachi Life's tags are all named, the shipped catalogue is
the game's own message project, Miitopia's four fonts and every listed layout picture read and write back unchanged.
"""
import json
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.common import msbp
from plugins.mii_3ds.rules import GameRules

TOMODACHI = Path(r"E:\Emulators\RomHacking\Tomodachi Life")
MIITOPIA = Path(r"E:\Emulators\RomHacking\Miitopia\3DS")
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "mii_3ds"
UKRAINIAN = "ҐЄІЇґєії"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _meta(ws: Path) -> dict:
    return {"source_path": str(_need(ws / "source")), "translation_path": ""}


def _round_trip(files, allow_raw: bool) -> int:
    messages = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        if not allow_raw:
            assert not any("{tag:" in text for text in blocks[0]), path.name
        messages += len(blocks[0])
    return messages


def test_every_tomodachi_life_english_msbt_saves_back_byte_for_byte():
    files = sorted(_need(TOMODACHI / "source" / "romfs" / "message").rglob("*.msbt"))
    assert len(files) == 1038
    assert sum(1 for path in files if path.parent.name == "ArcVoice") == 399
    assert _round_trip(files, allow_raw=False) == 53195


def test_every_miitopia_english_msbt_saves_back_byte_for_byte():
    files = sorted(_need(MIITOPIA / "source" / "romfs" / "eu" / "svn_message").rglob("*.msbt"))
    assert len(files) == 388
    assert _round_trip(files, allow_raw=True) == 14979


def test_the_catalogue_is_tomodachi_lifes_message_project():
    import struct

    from core.containers.nitro import lz11_decompress
    plain = lz11_decompress(_need(TOMODACHI / "romfs" / "message" / "Game" / "Game_EU_English_LZ.bin").read_bytes())[0]
    at = plain.index(msbp.MAGIC)      # Game.msbp inside the darc; the LMS header holds the file size at 0x12
    project = plain[at:at + struct.unpack_from("<I", plain, at + 0x12)[0]]
    assert msbp.read(project) == json.loads((PLUGIN / "msbp.json").read_text(encoding="utf-8"))


def test_miitopias_fonts_open_and_pack_back_unchanged():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, _meta(MIITOPIA))
    assert [source.name for source in found] == ["FontInfo.bffnt", "FontCaption.bffnt", "FontCaptionOutline.bffnt",
                                                 "FontCutIn.bffnt"]
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract(source.format, data)
        assert font_formats.pack(source.format, metadata, sheets, data) == data, source.name
        chars = font_formats.char_map(metadata)
        assert "A" in chars and not any(char in chars for char in UKRAINIAN), source.name


@pytest.mark.parametrize("ws, count", [(TOMODACHI, 2467), (MIITOPIA, 1212)])
def test_every_listed_layout_picture_reads_and_writes_back(ws, count):
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    found = texture_sources.resolve(descriptors, _meta(ws))
    assert len(found) == count
    assert any(source.kind == "title_screen" for source in found)
    for source in found:
        data = Path(source.source_path).read_bytes()
        image = texture_formats.read(source.format, data, source.params)[source.index].image
        assert texture_formats.write(source.format, data, {source.index: image}, source.params) == data, source.key
