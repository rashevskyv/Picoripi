"""Metal Gear Solid Master Collection plugin: M2's PSB text, fonts and pictures; the real workspaces when present."""
import json
from pathlib import Path

import pytest

from core import font_formats, m2_psb
from core import texture_formats as textures
from core.font_formats import char_map
from core.texture_formats import pcx
from plugins.testing import check_loads, check_validator, load_rules

BASE = Path(r"E:\Emulators\RomHacking\Metal Gear\Metal Gear Solid")
WORKSPACES = [BASE / "PC - Steam" / "source", BASE / "Switch" / "source"]
PRESENT = [ws for ws in WORKSPACES if (ws / "mgsmc_members.idx").is_file()]
real = pytest.mark.skipif(not PRESENT, reason="the unpacked workspaces are not on this machine")


def _message_file() -> bytes:
    tree = {"message": {"NoticeMsg__SAVED": {"eng": ["Data saved."], "jpn": ["セーブしました。"], "fra": ["Data saved."]},
                        "MenuItemText__BACK": {"eng": ["Back"], "jpn": ["戻る"]}},
            "credits": ["DIRECTOR Hideo Kojima", "id_value"]}
    return m2_psb.dump(tree, version=2)


def test_plugin_loads_and_validates():
    rules = check_loads("metal_gear_solid_mc")
    assert {".dat", ".psb", ".94"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator("metal_gear_solid_mc")


def test_psb_dump_reads_back_its_tree():
    data = _message_file()
    root, psb = m2_psb.load(data)
    assert root["message"]["MenuItemText__BACK"]["jpn"] == ["戻る"]
    assert m2_psb.dump(root, psb.chunks, psb.version, psb.names, psb.strings) == data


def test_message_file_shows_english_lines_and_saves_one_place():
    rules = load_rules("metal_gear_solid_mc")
    source = _message_file()
    blocks, names = rules.load_data_from_json_obj(source)
    assert blocks == [["DIRECTOR Hideo Kojima", "Back", "Data saved."]]      # keys in name order
    assert rules.save_data_to_json_obj(blocks, names) == source
    blocks[0][2] = "Дані збережено."
    out = rules.save_data_to_json_obj(blocks, names)
    root = m2_psb.load(out)[0]
    assert root["message"]["NoticeMsg__SAVED"]["eng"] == ["Дані збережено."]
    assert root["message"]["NoticeMsg__SAVED"]["fra"] == ["Data saved."]       # the shared string stays elsewhere
    again, _ = load_rules("metal_gear_solid_mc").load_data_from_json_obj(out)
    assert again[0][2] == "Дані збережено."


def test_playstation_files_still_go_to_the_playstation_rules():
    from ..test_metal_gear_solid_ps1.samples import radio
    rules = load_rules("metal_gear_solid_mc")
    source = radio([["Snake, do you read me?", "Loud and clear."]])
    blocks, names = rules.load_data_from_json_obj(source)
    assert blocks[0] == ["Snake, do you read me?", "Loud and clear."]
    assert rules.save_data_to_json_obj(blocks, names) == source


def test_hd_font_round_trip_and_edit():
    glyph = bytes([0x55] * 576)
    data = b"".join(bytes([w, 0]) + (glyph if w else bytes(576)) for w in [16] + [24] * 111)
    meta, sheets = font_formats.extract("mgs1_hd", data)
    assert font_formats.pack("mgs1_hd", meta, sheets, data) == data
    assert char_map(meta)["A"] == ord("A") - 0x20
    sheet = sheets[0].copy()
    sheet.paste((0, 0, 0, 0), (0, 0, sheet.width, sheet.height))
    out = font_formats.pack("mgs1_hd", meta, [sheet], data)
    assert len(out) == len(data) and out[2:578] == bytes(576)


def test_plain_pcx_8_bit_round_trip():
    width, height = 4, 2
    head = bytearray(128)
    head[0:4] = bytes((0x0A, 5, 1, 8))
    head[8:12] = bytes((width - 1, 0, height - 1, 0))
    head[0x41], head[0x42] = 1, width
    pixels = bytes([1, 1, 2, 2, 3, 3, 3, 3])
    palette = bytes(3) + bytes((255, 0, 0, 0, 255, 0, 0, 0, 255)) + bytes(756)
    data = bytes(head) + pixels + b"\x0c" + palette
    image = pcx.read(data, {})[0].image
    assert image.getpixel((0, 0)) == (255, 0, 0, 255)
    assert pcx.write(data, {0: image}, {}) == data
    image.putpixel((0, 0), (0, 0, 255, 255))
    assert pcx.read(pcx.write(data, {0: image}, {}), {})[0].image.getpixel((0, 0)) == (0, 0, 255, 255)


# ---------------------------------------------------------------- the real workspaces

@real
@pytest.mark.parametrize("source", PRESENT)
def test_real_text_files_round_trip_and_take_an_edit(source):
    rules = load_rules("metal_gear_solid_mc")
    files = sorted((source / "m2" / "text").rglob("*.psb"))
    assert len(files) >= 20
    for path in files:
        data = path.read_bytes()
        blocks, names = rules.load_data_from_json_obj(data)
        assert blocks[0], path
        assert rules.save_data_to_json_obj(blocks, names) == data, path
    data = (source / "m2" / "text" / "system" / "config" / "notice.psb").read_bytes()
    blocks, names = rules.load_data_from_json_obj(data)
    blocks[0][0] = "UA TEST " + blocks[0][0]
    again, _ = rules.load_data_from_json_obj(rules.save_data_to_json_obj(blocks, names))
    assert again == blocks


@real
@pytest.mark.parametrize("source", PRESENT)
def test_real_fonts_round_trip_byte_exact(source):
    for path in sorted((source / "m2" / "font").glob("*.m2font")) + [source / "font" / "font.res"]:
        data = path.read_bytes()
        fmt = "mgs1" if path.name == "font.res" else "mgs1_hd" if path.name.startswith("us_") else "m2"
        if fmt == "m2":
            assert font_formats.detect(data) == "m2"
        meta, sheets = font_formats.extract(fmt, data)
        assert font_formats.pack(fmt, meta, sheets, data) == data, path


@real
@pytest.mark.parametrize("source", PRESENT)
def test_real_m2_font_takes_a_glyph_edit(source):
    data = (source / "m2" / "font" / "title_mgsrodin_db_24pt.m2font").read_bytes()
    meta, sheets = font_formats.extract("m2", data)
    g = meta["GLY1"][0]
    i = char_map(meta)["A"]
    x, y = i % g["glyph_horizontal_count"] * g["cell_width"], i // g["glyph_horizontal_count"] * g["cell_height"]
    sheet = sheets[0].copy()
    sheet.paste((255, 255, 255, 255), (x, y, x + g["cell_width"], y + g["cell_height"]))
    out = font_formats.pack("m2", meta, [sheet], data)
    assert len(out) == len(data) and out != data
    again, again_sheets = font_formats.extract("m2", out)
    box = again_sheets[0].crop((x, y, x + g["cell_width"], y + g["cell_height"]))
    assert box.getextrema()[3][1] == 255


@real
@pytest.mark.parametrize("source", PRESENT)
def test_real_pictures_round_trip_byte_exact(source):
    for path in sorted((source / "m2" / "image").glob("*.m2tex")) + sorted((source / "m2" / "texture").glob("*.pcx")):
        data = path.read_bytes()
        fmt = textures.detect(data, path.name)
        found = textures.read(fmt, data)
        assert found, path
        assert textures.write(fmt, data, {i: t.image for i, t in enumerate(found)}) == data, path
    data = (source / "m2" / "image" / "txt_en.m2tex").read_bytes()
    image = textures.read("m2", data)[0].image.copy()
    image.paste((255, 0, 0, 255), (0, 0, 16, 16))
    out = textures.write("m2", data, {0: image})
    assert textures.read("m2", out)[0].image.getpixel((4, 4)) == (255, 0, 0, 255)


@real
def test_real_sources_point_at_files():
    rules = load_rules("metal_gear_solid_mc")
    entries = rules.get_font_sources() + rules.get_texture_sources()
    for entry in entries:               # a few M2 files are on one platform only (a PC font, the PC keyboard help)
        assert any(list(source.glob(entry["path"])) for source in PRESENT), entry
    for source in PRESENT:
        assert sum(1 for entry in entries if list(source.glob(entry["path"]))) >= len(entries) - 2
        members = json.loads((source / "mgsmc_members.idx").read_text(encoding="utf-8"))
        assert all((source / rel).is_file() for rel in members)
