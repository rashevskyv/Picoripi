"""Pokémon Black / White and Black 2 / White 2 (DS): the generation V message codec (packing, tags, flags), the
plugin's load and save, and real-data round trips of every text bank of the workspaces."""
from pathlib import Path

import pytest

from plugins.common import gen5msg
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "pokemon_gen5"
GAMES = {name: Path(r"E:\Emulators\RomHacking\Pokemon") / name / "source" / "text"
         for name in ("Black and White", "Black 2 and White 2")}


def _units(text: str):
    return gen5msg.from_editor(text)


SAMPLE = gen5msg.write([
    gen5msg.Line(_units("Delete all saved data?"), 0xE8),
    gen5msg.Line(_units("Once the saved data has been deleted,\nthere is no way to recover it.{PAGE}\nReally?{SCROLL}"), 0xE8),
    gen5msg.Line(_units("Cheren"), 0x3C, packed=True),
    gen5msg.Line(_units("{VAR 0101 0000} used {VAR 0102 0001}!{CHAR E447}"), 0x76),
])


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_tags_read_like_the_other_game_freak_text():
    texts = [gen5msg.to_editor(line.units) for line in gen5msg.read(SAMPLE)]
    assert texts[1] == "Once the saved data has been deleted,\nthere is no way to recover it.{PAGE}\nReally?{SCROLL}"
    assert texts[3] == "{VAR 0101 0000} used {VAR 0102 0001}!{CHAR E447}"
    assert gen5msg.from_editor(texts[3]) == [0xF000, 0x101, 1, 0] + _units(" used ")[0:6] + \
        [0xF000, 0x102, 1, 1] + _units("!")  + [0xE447]


def test_a_packed_line_is_packed_again_and_a_name_fits_its_words():
    lines = gen5msg.read(SAMPLE)
    assert lines[2].packed and gen5msg.to_editor(lines[2].units) == "Cheren"
    assert gen5msg.pack9([ord(c) for c in "Chili"]) == [0xD043, 0x61A4, 0xE693]       # the end mark is cut short
    assert gen5msg.unpack9([0xD043, 0x9194, 0xC653, 0x7FCD]) == [ord(c) for c in "Cheren"]
    assert gen5msg.write(lines) == SAMPLE


def test_a_changed_line_keeps_the_flags_the_packing_and_the_other_lines():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert names == {"0": "Text"}
    blocks[0][2] = "Bianca"
    blocks[0][1] = blocks[0][1] + "{WAIT 0010}"
    saved = rules.save_data_to_json_obj(blocks, names)
    again = gen5msg.read(saved)
    assert [gen5msg.to_editor(line.units) for line in again] == blocks[0]
    assert [line.flags for line in again] == [0xE8, 0xE8, 0x3C, 0x76] and again[2].packed
    assert gen5msg.read(SAMPLE)[0] == again[0]


def test_an_unchanged_file_is_returned_as_it_was():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE + b"\xaa\xaa")        # padding bytes behind the lines
    assert not gen5msg.is_gen5msg(SAMPLE + b"\xaa\xaa") or rules.save_data_to_json_obj(blocks, names) is not None
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert rules.save_data_to_json_obj(blocks, names) == SAMPLE


def test_a_letter_the_packing_cannot_hold_leaves_the_line_plain():
    line = gen5msg.Line(_units("Черен"), 0x3C, packed=True)
    assert gen5msg.encode(line)[0] != gen5msg.PACKED and gen5msg.encode(line)[-1] == gen5msg.END


def test_a_wrong_line_count_is_refused():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    with pytest.raises(ValueError):
        rules.save_data_to_json_obj([blocks[0][:-1]], names)


def test_a_name_table_is_known_by_its_first_lines():
    names = gen5msg.write([gen5msg.Line(_units(text)) for text in ("-----", "Bulbasaur", "Ivysaur")])
    assert load_rules(PLUGIN)._table(names)[0] == "Pokémon name"
    assert load_rules(PLUGIN)._table(SAMPLE) is None


@pytest.mark.parametrize("game", list(GAMES))
def test_every_text_bank_of_the_game_saves_back_unchanged(game):
    root = GAMES[game]
    if not root.is_dir():
        pytest.skip(f"{root} is not on this machine")
    rules = load_rules(PLUGIN)
    files = sorted(root.glob("*/*.msg"))
    assert files
    for path in files:
        raw = path.read_bytes()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path.name
        lines = gen5msg.read(raw)
        # the editor text is lossless: every line comes back as the same units
        assert [gen5msg.from_editor(text) for text in blocks[0]] == [line.units for line in lines], path.name
        # and a rebuilt file differs from the original at most in the two padding bytes at its end
        rebuilt = gen5msg.write(lines)
        assert rebuilt[:-4] == raw[:-4] and len(rebuilt) == len(raw), path.name


@pytest.mark.parametrize("game", list(GAMES))
def test_the_font_and_picture_descriptors_resolve_in_a_project(game):
    """The Font Editor and the Textures window resolve the plugin's descriptors: NARC members, byte-exact."""
    from types import SimpleNamespace

    from core import font_formats, texture_formats
    from core.font_formats import sources as font_sources
    from core.texture_formats import sources as texture_sources

    root = GAMES[game].parent
    if not root.is_dir():
        pytest.skip(f"{root} is not on this machine")
    meta = {"source_path": str(root), "translation_path": str(root.parent / "translation"), "is_directory_mode": True}
    mw = SimpleNamespace(project_manager=SimpleNamespace(project=SimpleNamespace(metadata=meta)))
    rules = load_rules(PLUGIN, mw)
    fonts = font_sources.resolve(rules.get_font_sources(), meta)
    assert len(fonts) == 5
    for font in fonts:
        data = font.read_current()
        metadata, sheets = font_formats.extract(font.format, data, font.params)
        assert font_formats.pack(font.format, metadata, sheets, data, font.params) == data
    pictures = texture_sources.resolve(rules.get_texture_sources(), meta)
    assert len(pictures) > 1000
    for picture in pictures[:50]:
        data, _rewrap = texture_sources.unwrap(Path(picture._current_path()).read_bytes(), picture.member, picture.params)
        image = picture.read_current().image
        assert texture_formats.write(picture.format, data, {picture.index: image}, picture.params) == data
