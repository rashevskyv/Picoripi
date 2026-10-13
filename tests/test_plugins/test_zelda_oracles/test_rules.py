"""The Oracles rules on the USA ROM (skipped where the ROM is not on this machine): the blocks come from the
text groups, an unchanged save gives the same bytes, an edit lands in its own string and a longer one is refused.
Ukrainian letter cells are unique and avoid the English button codes."""
from pathlib import Path

import pytest

from plugins.zelda_oracles import text
from plugins.zelda_oracles.rules import GameRules, load_letters

AGES = Path(r"D:\Emulators\roms\roms\gbc\Legend of Zelda,The-Oracle of Ages.gbc")


def _ages():
    if not AGES.is_file():
        pytest.skip("the USA Oracle of Ages ROM is not on this machine")
    return AGES.read_bytes()


def test_ukrainian_letter_cells_are_unique_and_avoid_english_buttons():
    letters, back = load_letters()
    codes = list(letters.values())
    assert len(codes) == len(set(codes))
    assert not set(codes) & {0xB8, 0xB9, 0xBA, 0xBB}   # abtn / bbtn in the English text
    assert letters["А"] == 0xC0 and letters["я"] == 0xFF
    assert back[0xA5] == "Ґ"
    assert {"І", "і", "Ї", "ї", "Є", "є", "Ґ", "ґ"} <= set(letters)


def test_blocks_are_text_groups_with_named_strings():
    blocks, names = GameRules().load_data_from_json_obj(_ages())
    assert len(blocks) > 20
    assert sum(len(block) for block in blocks) > 1500
    assert all(name.startswith("Group 0x") for name in names.values())


def test_unchanged_save_gives_the_same_bytes():
    raw = _ages()
    rules = GameRules()
    blocks, _names = rules.load_data_from_json_obj(raw)
    assert rules.save_data_to_json_obj(blocks, {}) == raw


def test_edit_lands_in_its_own_string_and_reloads():
    raw = _ages()
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    # TX_0104 is "Oh! That's it!": a short replacement fits.
    block_index, string_index = rules._names["TX_0104"]
    blocks[block_index][string_index] = "UA TEST"
    saved = rules.save_data_to_json_obj(blocks, names)
    diff = [i for i in range(len(raw)) if raw[i] != saved[i]]
    assert diff and diff[-1] - diff[0] < 16
    reloaded, _ = GameRules().load_data_from_json_obj(saved)
    assert reloaded[block_index][string_index] == "UA TEST"


def test_too_long_edit_is_refused_with_the_string_name():
    raw = _ages()
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    block_index, string_index = rules._names["TX_0104"]
    blocks[block_index][string_index] = "This line is far longer than the old text was allowed to be"
    with pytest.raises(ValueError, match="TX_0104"):
        rules.save_data_to_json_obj(blocks, names)


def test_markup_of_a_ukrainian_letter_round_trips_through_its_cell():
    letters, back = load_letters()
    data = text.from_markup("Ї\u0456", 0, letters)
    assert data == bytes([0xAF, 0xB3, 0x00])
    assert text.to_markup(data[:-1], 0, lambda b: back.get(b)) == "Ї\u0456"
