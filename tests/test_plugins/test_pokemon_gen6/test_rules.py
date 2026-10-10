"""Pokémon X/Y + Omega Ruby/Alpha Sapphire (3DS) plugin: the shared gfmsg codec on gen 6 tables, keyboard rows, block
names; real-data round trips of every English table, font and layout picture of the workspaces."""
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from plugins.common import gfmsg
from plugins.pokemon_gen6.rules import is_keyboard, keyboard_header, locate, table_name
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "pokemon_gen6"
GAMES = {name: Path(r"E:\Emulators\RomHacking\Pokemon") / name / "source" / "romfs"
         for name in ("X and Y", "Omega Ruby and Alpha Sapphire")}
TABLES = {"X and Y": ("a/0/7/4", "a/0/8/2", 151, 424, 27605 + 7607), "Omega Ruby and Alpha Sapphire": ("a/0/7/3", "a/0/8/1", 175, 637, 33909 + 11538)}
FONTS = {"X and Y": "a/1/8/5", "Omega Ruby and Alpha Sapphire": "a/1/6/7"}


def _words(text: str):
    return list(struct.unpack(f"<{len(text)}H", text.encode("utf-16-le")))


SAMPLE = gfmsg.write([(_words("Master Ball") + [0x10, 3, 0x1101, 0x00FE, 0x0100] + _words("s"), 4),
                      (_words("Select language"), 0), ([0x10, 2, 0xBDFF, 2], 0)])
KEYBOARD = struct.pack("<HH", 13, 5) + "ABCDEFGHIJ ,.KLMNOPQRST \ue08e".encode("utf-16-le")


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)
    check_round_trip(PLUGIN, KEYBOARD)


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_gen6_tags_read_like_the_switch_games():
    texts = [gfmsg.to_editor(units) for units, _flags in gfmsg.read(SAMPLE)]
    assert texts == ["Master Ball{PLURAL 00FE||s}", "Select language", "{NULL 0002}"]


def test_a_keyboard_row_is_one_line_and_keeps_its_header():
    rules = load_rules(PLUGIN)
    assert keyboard_header(KEYBOARD) == 4 and not is_keyboard(SAMPLE) and not is_keyboard(b"\x00\x00")
    blocks, names = rules.load_data_from_json_obj(KEYBOARD)
    assert blocks == [["ABCDEFGHIJ ,.KLMNOPQRST \ue08e"]] and names == {"0": "Keyboard row"}
    blocks[0][0] = "АБВГҐДЕЄЖЗ ,.ИІЇЙКЛМНОП \ue08e"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved[:4] == KEYBOARD[:4] and rules.load_data_from_json_obj(saved)[0] == blocks


def test_a_longer_line_moves_the_lines_after_it_and_keeps_the_flags():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    blocks[0][1] = "Оберіть мову гри, будь ласка"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert rules.load_data_from_json_obj(saved)[0] == blocks
    assert [f for _u, f in gfmsg.read(saved)] == [4, 0, 0]


def test_block_names_follow_the_table():
    assert table_name("romfs/a/0/7/4/080.dat") == "080 Species names"
    assert table_name("romfs\\a\\0\\7\\3\\098.dat") == "098 Species names"
    assert table_name("romfs/a/0/8/2/012.dat") == "Story 012" and table_name("romfs/a/0/2/0/004.2.bin") == "Keyboard 004"
    assert table_name("romfs/a/0/7/4/049.dat") == "049 Game text" and locate("romfs/a/1/8/5/000.bcfnt") is None


@pytest.mark.parametrize("game", list(GAMES))
def test_every_english_table_of_the_game_saves_back_byte_exact(game):
    root = GAMES[game]
    if not root.is_dir():
        pytest.skip(f"{root} is not on this machine")
    game_garc, story_garc, game_count, story_count, _lines = TABLES[game]
    rules = load_rules(PLUGIN)
    counts, lines = [], 0
    for garc in (game_garc, story_garc):
        files = sorted((root / garc).glob("*.dat"))
        counts.append(len(files))
        for path in files:
            data = path.read_bytes()
            blocks, names = rules.load_data_from_json_obj(data)
            lines += len(blocks[0])
            assert rules.save_data_to_json_obj(blocks, names) == data, path
    assert counts == [game_count, story_count]
    rows = sorted((root / "a/0/2/0").glob("*.bin"))
    assert len(rows) == 9 and all(rules.save_data_to_json_obj(*rules.load_data_from_json_obj(r.read_bytes())) == r.read_bytes()
                                  for r in rows if is_keyboard(r.read_bytes()))
    if TABLES[game][4]:
        assert lines == TABLES[game][4]


@pytest.mark.parametrize("game", list(GAMES))
def test_every_font_and_layout_picture_of_the_game_round_trips(game):
    root = GAMES[game]
    if not root.is_dir():
        pytest.skip(f"{root} is not on this machine")
    fonts = sorted((root / FONTS[game]).glob("*.bcfnt"))
    assert len(fonts) == (4 if game == "X and Y" else 5)
    for path in fonts:
        data = path.read_bytes()
        metadata, sheets = font_formats.extract("bcfnt", data, {"min_sheets": len(sheets_of(data)) + 2})
        assert font_formats.pack("bcfnt", metadata, sheets, data, {}) == data, path
    pictures = sorted(root.glob("a/*/*/*/*/timg/*.bclim"))
    assert len(pictures) > 100
    for path in pictures:
        data = path.read_bytes()
        textures = texture_formats.read("bflim", data)
        assert texture_formats.write("bflim", data, {0: textures[0].image}) == data, path


def sheets_of(data: bytes):
    return font_formats.extract("bcfnt", data, {})[1]


def test_a_3ds_font_grows_by_a_sheet_for_a_new_letter():
    root = GAMES["X and Y"]
    path = root / "a/1/8/5/002.bcfnt"
    if not path.is_file():
        pytest.skip(f"{path} is not on this machine")
    data = path.read_bytes()
    metadata, sheets = font_formats.extract("bcfnt", data, {"min_sheets": 6})
    assert len(sheets) == 6 and font_formats.pack("bcfnt", metadata, sheets, data, {}) == data
    glyphs = metadata["GLY1"][0]
    per_sheet = glyphs["glyph_horizontal_count"] * glyphs["glyph_vertical_count"]
    glyph = 5 * per_sheet + 3
    pairs = [(font_formats.char_code(c), g) for c, g in font_formats.char_map(metadata).items()] + [(0x0404, glyph)]
    metadata["MAP1"] = [font_formats.map_entries(pairs)]
    box = Image.new("RGBA", (8, 12), (255, 255, 255, 255))
    sheets[5].paste(box, ((glyph - 5 * per_sheet) % glyphs["glyph_horizontal_count"] * glyphs["cell_width"] + 1, 1))
    grown = font_formats.pack("bcfnt", metadata, sheets, data, {})
    again, new_sheets = font_formats.extract("bcfnt", grown, {})
    assert len(grown) > len(data) and len(new_sheets) == 6 and font_formats.char_map(again)["Є"] == glyph
