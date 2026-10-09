"""Castlevania: Circle of the Moon plugin: text.json round trip, real font and textures, and the ROM build."""
import json
import random
import shutil
import sys
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from plugins.castlevania_cotm import rules as cvm_rules
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "castlevania_cotm"
WORKSPACE = Path(r"E:\Emulators\RomHacking\Castlevania\Circle of the Moon")
SOURCE = WORKSPACE / "source"
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
SAMPLE = json.dumps({"format": cvm_rules.FORMAT, "groups": [
    {"name": "Enemies", "items": [{"id": "40", "text": "Skeleton", "space": 39}]},
    {"name": "Story", "items": [{"id": "343", "text": "{1D 44}{1E 00}It's locked...{03}{1D C0}"}]}]},
    ensure_ascii=False, indent=1) + "\n"


def test_the_plugin_loads_round_trips_and_validates():
    check_loads(PLUGIN)
    check_round_trip(PLUGIN, SAMPLE)
    check_validator(PLUGIN)


def test_an_unchanged_save_is_the_same_file_and_texts_go_in_by_position():
    rules = check_loads(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert names == {"0": "Enemies", "1": "Story"}
    assert rules.save_data_to_json_obj(blocks, names) == SAMPLE
    saved = json.loads(rules.save_data_to_json_obj([["Скелет"], ["Зачинено..."]], names))
    assert saved["groups"][0]["items"][0] == {"id": "40", "text": "Скелет", "space": 39}
    assert rules.get_translation_context_for_string(1, 0)["content_role"] == "Dialogue"


def test_game_tags_are_curly_hex_codes():
    rules = check_loads(PLUGIN)
    assert rules.tag_manager.is_tag_legitimate("{1D 44}")
    assert rules.tag_manager.is_tag_legitimate("{02}")
    assert not rules.tag_manager.is_tag_legitimate("{player}")


# -- the workspace's real files (skipped where they are not on disk) -------------------------------

needs_source = pytest.mark.skipif(not (SOURCE / "text.json").is_file(), reason="Circle of the Moon not unpacked")


@needs_source
def test_real_text_saves_back_unchanged():
    rules = check_loads(PLUGIN)
    text = (SOURCE / "text.json").read_text(encoding="utf-8")
    blocks, names = rules.load_data_from_json_obj(text)
    assert sum(len(b) for b in blocks) == 527
    assert rules.save_data_to_json_obj(blocks, names) == text


@needs_source
def test_real_font_and_textures_open_and_pack_back_unchanged():
    rules = check_loads(PLUGIN)
    font = rules.get_font_sources()[0]
    data = (SOURCE / font["path"]).read_bytes()
    metadata, sheets = font_formats.extract(font["format"], data, font["params"])
    assert font_formats.pack(font["format"], metadata, sheets, data, font["params"]) == data
    assert all(ch in font["params"]["chars"] for ch in "eaSDЖїҐ")
    for texture in rules.get_texture_sources():
        data = (SOURCE / texture["path"]).read_bytes()
        images = texture_formats.read(texture["format"], data, texture["params"])
        assert texture_formats.write(texture["format"], data, {0: images[0].image}, texture["params"]) == data, \
            texture["label"]


@pytest.fixture(scope="module")
def zt_cotm():
    if not (SCRIPTS / "zt" / "cotm.py").is_file() or not list((WORKSPACE / "ISO").glob("*.gba")):
        pytest.skip("Circle of the Moon scripts or ROM not on disk")
    sys.path.insert(0, str(SCRIPTS))
    try:
        from zt import cotm
        return cotm, cotm.rom_bytes(WORKSPACE)
    finally:
        sys.path.remove(str(SCRIPTS))


def test_real_rom_every_string_encodes_back_to_its_own_bytes(zt_cotm):
    cotm, data = zt_cotm
    for at in cotm.string_offsets(data):
        raw = cotm.string_bytes(data, at)
        assert cotm.encode(cotm.decode(raw), cotm.space_of(raw, cotm.SPACE_TEXT)) == raw, hex(at)


def test_real_rom_builds_byte_exact_unchanged_and_carries_edits(zt_cotm, tmp_path):
    cotm, data = zt_cotm
    shutil.copytree(SOURCE, tmp_path / "source")
    shutil.copytree(SOURCE, tmp_path / "translation")
    assert cotm.build_rom(tmp_path, data)[0] == data
    doc = json.loads((tmp_path / "translation" / "text.json").read_text(encoding="utf-8"))
    items = {it["id"]: it for g in doc["groups"] for it in g["items"]}
    items["468"]["text"] = "UA TEST Ж"
    (tmp_path / "translation" / "text.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    font = bytearray((tmp_path / "translation" / "font" / "font.bin").read_bytes())
    font[32:64] = b"\x11" * 32                                   # 'a' becomes a filled box
    (tmp_path / "translation" / "font" / "font.bin").write_bytes(bytes(font))
    rom, texts, font_changed, sheets = cotm.build_rom(tmp_path, data)
    assert texts == ["468"] and font_changed and sheets == []
    offsets = cotm.string_offsets(rom)
    assert cotm.decode(cotm.string_bytes(rom, offsets[468])) == "UA TEST Ж"
    assert rom[cotm.FONT_AT + 8:cotm.FONT_AT + 16] == b"\xff" * 8
    table = cotm.struct.unpack_from("<I", rom, 0x60BB4)[0] - cotm.BASE      # glyph table now has the free cells
    assert table >= cotm.FREE_START and cotm.struct.unpack_from("<I", rom, 0x60AC4)[0] - cotm.BASE == table + 0x84
    same = sum(cotm.string_bytes(rom, offsets[i]) == cotm.string_bytes(data, at)
               for i, at in enumerate(cotm.string_offsets(data)))
    assert same == cotm.TEXT_COUNT - 1


def test_real_rom_sheets_pack_back_and_a_grown_one_moves(zt_cotm, tmp_path):
    cotm, data = zt_cotm
    rom = bytearray(data)
    name = "credits_1"
    (tmp_path / "s" / "gfx").mkdir(parents=True)
    (tmp_path / "t" / "gfx").mkdir(parents=True)
    raw = cotm.gfx_bytes(data, name)
    (tmp_path / "s" / "gfx" / f"{name}.bin").write_bytes(raw)
    noise = random.Random(1).randbytes(len(raw))                     # packs worse than the original
    (tmp_path / "t" / "gfx" / f"{name}.bin").write_bytes(noise)
    for other, *_ in cotm.GFX + cotm.RAW:
        if other != name:
            (tmp_path / "s" / "gfx" / f"{other}.bin").write_bytes(b"")
    assert cotm.apply_gfx(rom, data, tmp_path / "s", tmp_path / "t", [cotm.FREE_START]) == [name]
    moved = cotm.struct.unpack_from("<I", rom, 0x81E4)[0] - cotm.BASE
    assert moved >= cotm.FREE_START and cotm.lz_decompress(bytes(rom), moved)[0] == noise


@needs_source
def test_real_title_logo_takes_a_redrawn_picture():
    rules = check_loads(PLUGIN)
    logo = next(t for t in rules.get_texture_sources() if t["path"] == "gfx/title_logo.bin")
    data = (SOURCE / logo["path"]).read_bytes()
    image = texture_formats.read(logo["format"], data, logo["params"])[0].image.convert("RGBA")
    colour = next(c for _n, c in image.getcolors(1 << 16) if c[3] == 255)
    image.paste(colour, (0, 0, 16, 16))
    written = texture_formats.write(logo["format"], data, {0: image}, logo["params"])
    assert written != data and len(written) == len(data)
    again = texture_formats.read(logo["format"], written, logo["params"])[0].image.convert("RGBA")
    assert again.getpixel((5, 5)) == colour
