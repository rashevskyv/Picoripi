"""Pokémon Sun / Moon and Ultra Sun / Ultra Moon (3DS) plugin: the shared gfmsg codec on gen 7 tables, block names;
real-data round trips of the English tables, fonts and pictures of the workspaces (skipped when the data is missing)."""
import romhacking_root

import pytest

from core import font_formats, texture_formats
from plugins.common import gfmsg
from plugins.pokemon_gen7.rules import locate, table_name
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "pokemon_gen7"
ROOTS = {name: romhacking_root.under('Pokemon') / name / "source" / "romfs"
         for name in ("Sun and Moon", "Ultra Sun and Ultra Moon")}
TEXT = ("a/0/3/2", "a/0/4/2")
TABLES = {"Sun and Moon": 898, "Ultra Sun and Ultra Moon": 1251}
FONTS = "a/0/2/5"
PICTURES = ("a/0/6/1", "a/0/6/2", "a/1/5/4", "a/1/5/9", "a/2/6/0", "a/2/6/9", "a/2/8/1", "a/2/9/1")
SAMPLE = gfmsg.write([([ord(c) for c in "Rowlet"], 0), ([0x10, 2, 0xBDFF, 2], 0)])


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_a_sample_table_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_block_names_and_locate_follow_the_gen7_paths():
    assert locate("romfs/a/0/3/2/035.dat") == ("sm", "game", 35)
    assert locate("romfs/a/0/4/2/004.dat") == ("sm", "battle", 4)
    assert table_name("romfs/a/0/3/2/035.dat") == "035 Game text"
    assert locate("romfs/a/0/2/5/000.bcfnt") is None


@pytest.mark.parametrize("game", list(ROOTS))
def test_every_english_table_saves_back_byte_exact(game):
    root = ROOTS[game]
    if not root.is_dir():
        pytest.skip(f"{root} is not on this machine")
    rules = load_rules(PLUGIN)
    tables = 0
    for garc in TEXT:
        files = sorted((root / garc).glob("*.dat"))
        assert files, f"{root / garc} has no tables"
        for path in files:
            data = path.read_bytes()
            blocks, names = rules.load_data_from_json_obj(data)
            assert rules.save_data_to_json_obj(blocks, names) == data, path
            tables += 1
    assert tables == TABLES[game]          # the v1.2 overlay adds tables to the Ultra games


@pytest.mark.parametrize("game", list(ROOTS))
def test_every_font_round_trips(game):
    root = ROOTS[game]
    if not root.is_dir():
        pytest.skip(f"{root} is not on this machine")
    fonts = sorted((root / FONTS).glob("*.bcfnt")) + sorted((root / FONTS).glob("*.bffnt"))
    if not fonts:
        pytest.skip(f"{root / FONTS} has no fonts")
    for path in fonts:
        data = path.read_bytes()
        metadata, sheets = font_formats.extract("bcfnt", data, {})
        assert font_formats.pack("bcfnt", metadata, sheets, data, {}) == data, path


@pytest.mark.parametrize("game", list(ROOTS))
def test_every_picture_round_trips(game):
    root = ROOTS[game]
    if not root.is_dir():
        pytest.skip(f"{root} is not on this machine")
    pictures = [p for rel in PICTURES for p in sorted((root / rel).glob("*.bflim"))][::40]  # every 40th: all 3754 take minutes
    if not pictures:
        pytest.skip(f"{root} has no pictures")
    for path in pictures:
        data = path.read_bytes()
        textures = texture_formats.read("bflim", data)
        assert texture_formats.write("bflim", data, {0: textures[0].image}) == data, path
