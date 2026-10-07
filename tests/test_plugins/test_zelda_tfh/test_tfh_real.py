"""Tri Force Heroes plugin on the real EU game files (skipped where the workspace is not on this machine).

Every English MSBT loads and saves back byte for byte with no raw tags left, the shipped catalogue is the
game's own message project, both fonts, every listed text image and every BFLIM / CTPK of the unpacked
archives read and write back unchanged.
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
from plugins.zelda_tfh.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Zelda\Tri Force Heroes")
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "zelda_tfh"
UKRAINIAN = "ҐЄІЇґєії"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _meta() -> dict:
    return {"source_path": str(_need(SOURCE)), "translation_path": ""}


def test_every_english_msbt_saves_back_byte_for_byte():
    files = sorted(_need(SOURCE / "romfs" / "Archive" / "EU").rglob("*.msbt"))
    assert len(files) == 100
    messages = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        assert not any("{tag:" in text for text in blocks[0]), path.name
        messages += len(blocks[0])
    assert messages == 3382


def test_the_catalogue_is_the_games_message_project():
    region = Sarc(yaz0.decompress(_need(WS / "romfs" / "Archive" / "EU" / "RegionBoot.szs").read_bytes()))
    project = msbp.read(region.files["Common/Message/Alice.msbp"])
    assert project == json.loads((PLUGIN / "msbp.json").read_text(encoding="utf-8"))


def test_both_fonts_open_and_pack_back_unchanged():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, _meta())
    assert [source.name for source in found] == ["MessageFont.bffnt", "HyliaFont.bffnt"]
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract(source.format, data)
        assert font_formats.pack(source.format, metadata, sheets, data) == data
    message_font = font_formats.char_map(font_formats.extract("bcfnt", found[0].read_original())[0])
    assert "Ж" in message_font and not any(char in message_font for char in UKRAINIAN)


def test_every_listed_text_image_reads_and_writes_back():
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    found = texture_sources.resolve(descriptors, _meta())
    assert len(found) == 63
    assert {source.pixel_format for source in found} == {"ETC1A4", "RGBA4", "ETC1"}
    for source in found:
        data = Path(source.source_path).read_bytes()
        image = texture_formats.read(source.format, data, source.params)[source.index].image
        assert texture_formats.write(source.format, data, {source.index: image}, source.params) == data, source.key


def test_every_unpacked_bflim_and_ctpk_writes_back():
    count = 0
    for path in sorted(_need(SOURCE / "romfs").rglob("*")):
        fmt = {".bflim": "bflim", ".ctpk": "ctpk"}.get(path.suffix)
        if fmt:
            data = path.read_bytes()
            textures = texture_formats.read(fmt, data)
            assert texture_formats.write(fmt, data, {i: t.image for i, t in enumerate(textures)}) == data, path.name
            count += len(textures)
    assert count == 462
