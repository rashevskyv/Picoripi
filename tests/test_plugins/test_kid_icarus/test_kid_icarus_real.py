"""Kid Icarus: Uprising plugin on the real EU game files (skipped where the workspace is not on this machine).

Every English MSBT loads and saves back byte for byte with no raw tags left; both bitmap fonts open and pack
back unchanged; every language-dependent CGFX picture reads and writes back unchanged.
"""
import json
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.kid_icarus.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Kid Icarus Uprising")
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "kid_icarus"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_every_english_msbt_saves_back_byte_for_byte():
    files = sorted(_need(SOURCE / "romfs" / "eu").rglob("*.msbt"))
    assert len(files) == 148
    assert not any(path.name.startswith(("msg_01", "msg_02", "msg_03", "msg_04", "msg_06")) for path in files)
    messages = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, _names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        assert not any("{tag:" in text for text in blocks[0]), path.name
        messages += len(blocks[0])
    assert messages == 25833


def test_both_fonts_open_and_pack_back_unchanged():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert [source.name for source in found] == ["04.bin", "fnt.bin"]
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract("bcfnt", data)
        assert font_formats.pack("bcfnt", metadata, sheets, data) == data
        assert "Ж" not in font_formats.char_map(metadata)


def test_every_language_picture_reads_and_writes_back():
    """The descriptor names all 985 language CGFX files (a full sweep, 263 s, was byte-exact for all 6367
    textures); the test resolves the info screens through the same descriptor and writes each file back."""
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    assert len(list(_need(SOURCE / "romfs" / "eu").rglob("*.bcres"))) == 985
    info = [dict(d, path=d["path"].replace("**", "info/b*.zrc/**")) for d in descriptors]
    found = texture_sources.resolve(info, {"source_path": str(SOURCE), "translation_path": ""})
    files = sorted({source.source_path for source in found})
    assert len(files) == 14
    formats = set()
    for path in files:
        data = Path(path).read_bytes()
        textures = texture_formats.read("cgfx", data)
        formats.update(texture.pixel_format for texture in textures)
        assert texture_formats.write("cgfx", data, {i: texture.image for i, texture in enumerate(textures)}) == data, path
    assert "ETC1" in formats
