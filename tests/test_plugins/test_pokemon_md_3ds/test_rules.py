"""Pokémon Mystery Dungeon 3DS plugin: SIR0 messages, control-code tags, .img textures, .dic fonts and the real games."""
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats
from core.font_formats import pmd_font
from core.font_formats.sources import join_pair, split_pair
from core.texture_formats import pmd_img
from plugins.pokemon_md_3ds import message
from plugins.testing import check_loads, check_validator, load_rules

PLUGIN = "pokemon_md_3ds"
ROOT = Path(r"E:\Emulators\RomHacking\Pokemon")
GTI = ROOT / "Mystery Dungeon Gates to Infinity/source/romfs"
PSMD = ROOT / "Super Mystery Dungeon/source/romfs"


def make_message(units_list, hashes=None):
    """A SIR0 message file of the given unit lists (the layout ``message.File.rebuild`` writes)."""
    file = object.__new__(message.File)
    file.entries = [((hashes or {}).get(i, 0x1000 + i), 0x00DC0001, units) for i, units in enumerate(units_list)]
    file.order = list(range(len(units_list)))
    return file.rebuild([message.decode(units, "gti") for units in units_list], "gti")


def make_img(fmt, width, height, payload):
    bpp = {3: 32, 8: 8}[fmt]
    head = b"\0cte" + struct.pack("<6I", fmt, width, height, bpp, 0, 0x80)
    return head + bytes(0x80 - len(head)) + payload


def make_font():
    """A .dic of two glyphs (A, B, 6x8 boxes) and an A8 64x64 atlas."""
    dic = b"KAND" + struct.pack("<III", 0, 2, 0)
    dic += struct.pack("<HHHHHhhHI", 0x41, 2, 2, 6, 8, 0, 0, 7, 0)
    dic += struct.pack("<HHHHHhhHI", 0x42, 12, 2, 6, 8, -1, 0, 6, 0)
    return join_pair(dic, make_img(8, 64, 64, bytes(64 * 64)))


def test_the_plugin_loads_and_validates():
    check_loads(PLUGIN)
    check_validator(PLUGIN)


def test_codes_become_tags_and_back():
    units = [0xC200, ord("H"), ord("i"), 0xEB00, 0x0A, 0xDA0A, 0x000B, ord("["), 0xE402, 3, 1, 0x0009, 0xC0FE]
    text = message.decode(units, "gti")
    assert text == "[CN]Hi[K]\n[type:0A:000B][[[value:02:0003:0001][0009][M:UNUSED]"
    assert message.encode(text, "gti") == units
    # PSMD keeps its icons at U+A0xx; an unknown tag stays literal text
    assert message.decode([0xA10C], "psmd") == "[M:UNUSED]"
    assert message.encode("[nope] ]]", "gti") == [ord(c) for c in "[nope] ]"]


def test_message_file_round_trip_and_growth():
    raw = make_message([[ord(c) for c in "First"], [0xC200, ord("x")], []], {0: 0x30, 1: 0x10, 2: 0x20})
    file = message.File(raw)
    texts = file.texts("gti")
    assert texts == ["First", "[CN]x", ""]
    assert file.rebuild(texts, "gti") == raw
    grown = file.rebuild(["A much longer first line\nwith a break", "[CN]x", "new"], "gti")
    assert message.File(grown).texts("gti") == ["A much longer first line\nwith a break", "[CN]x", "new"]
    assert [e[0] for e in message.File(grown).entries] == [e[0] for e in file.entries]
    rules = load_rules(PLUGIN)
    blocks, _ = rules.load_data_from_json_obj(raw)
    assert blocks == [texts]
    assert rules.save_data_to_json_obj(blocks, {}) == raw


def test_img_reads_flipped_and_writes_back():
    data = make_img(3, 8, 8, bytes(8 * 8 * 4))
    texture = pmd_img.read(data, {})[0]
    assert texture.image.size == (8, 8) and texture.pixel_format == "RGBA8"
    red = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    red.putpixel((0, 0), (255, 0, 0, 255))
    out = pmd_img.write(data, {0: red}, {})
    assert len(out) == len(data) and out != data
    assert pmd_img.read(out, {})[0].image.getpixel((0, 0)) == (255, 0, 0, 255)
    assert pmd_img.write(out, {0: pmd_img.read(out, {})[0].image}, {}) == out


def test_font_round_trip_and_new_glyph():
    data = make_font()
    metadata, sheets = font_formats.extract("pmd_font", data)
    assert font_formats.char_map(metadata) == {"A": 0, "B": 1}
    assert font_formats.pack("pmd_font", metadata, sheets, data) == data
    metadata["MAP1"] = [font_formats.map_entries([(0x41, 0), (0x42, 1), (ord("Ж"), 2)])]
    metadata["WID1"][0]["packets"][2] = {"kerning": 0, "width": 9}
    cw, ch = metadata["GLY1"][0]["cell_width"], metadata["GLY1"][0]["cell_height"]
    sheets[0].paste((255, 255, 255, 255), (2 * cw, 0, 3 * cw, ch))
    grown = font_formats.pack("pmd_font", metadata, sheets, data)
    dic, _img = split_pair(grown)
    assert struct.unpack_from("<I", dic, 8)[0] == 3
    again, _ = font_formats.extract("pmd_font", grown)
    assert font_formats.char_map(again)["Ж"] == 2 and again["WID1"][0]["packets"][2]["width"] == 9
    metadata["MAP1"] = [font_formats.map_entries([(0x41, 0)])]
    with pytest.raises(ValueError):
        font_formats.pack("pmd_font", metadata, sheets, data)


def test_game_from_paths_and_glossary_seed(tmp_path):
    from types import SimpleNamespace
    rel = "romfs/message_en.bin/common.bin"
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_bytes(make_message([[ord(c) for c in t] for t in ("Pikachu", "Oran Berry", "It heals.")]))
    pm = SimpleNamespace(project=SimpleNamespace(blocks=[SimpleNamespace(source_file=rel)]),
                         get_absolute_path=lambda r: str(tmp_path / r))
    rules = load_rules(PLUGIN, SimpleNamespace(project_manager=pm))
    assert rules.game() == "psmd"
    assert [e["term"] for e in rules.get_glossary_seed_entries()] == ["Pikachu", "Oran Berry"]
    assert load_rules(PLUGIN).game() == "gti"


def test_c1_font_codes_keep_their_own_code():
    assert pmd_font._model_code(0x96) != pmd_font._model_code(0x2013)
    assert pmd_font._game_code(font_formats.code_char(pmd_font._model_code(0x96))) == 0x96
    assert pmd_font._game_code(font_formats.code_char(pmd_font._model_code(0x2013))) == 0x2013


# -- the real games (skipped without the unpacked workspaces) ---------------------------


@pytest.mark.parametrize("game,folder", [("gti", GTI / "message"), ("psmd", PSMD / "message_en.bin")])
def test_every_message_file_packs_back_byte_exact(game, folder):
    files = sorted(folder.glob("*.bin")) if folder.is_dir() else []
    if not files:
        pytest.skip(f"{folder} is not unpacked")
    count = 0
    for path in files:
        raw = path.read_bytes()
        file = message.File(raw)
        texts = file.texts(game)
        count += len(texts)
        assert file.rebuild(texts, game) == raw, path.name
    assert count > 50000


@pytest.mark.parametrize("root", [GTI, PSMD])
def test_every_font_packs_back_byte_exact(root):
    dics = sorted((root / "font").glob("*.dic")) if (root / "font").is_dir() else []
    if not dics:
        pytest.skip(f"{root} is not unpacked")
    for dic in dics:
        data = join_pair(dic.read_bytes(), dic.with_suffix(".img").read_bytes())
        metadata, sheets = font_formats.extract("pmd_font", data)
        assert font_formats.pack("pmd_font", metadata, sheets, data) == data, dic.name


@pytest.mark.parametrize("name", ["title01.img", "button_ok.img", "chara_shadow.img", "cursor_v_wave01.img",
                                  "surechigai_icon48.img"])
def test_gti_textures_write_back_byte_exact(name):
    path = GTI / "image_2d" / name
    if not path.is_file():
        pytest.skip(f"{path} is not unpacked")
    data = path.read_bytes()
    assert pmd_img.write(data, {0: pmd_img.read(data, {})[0].image}, {}) == data
