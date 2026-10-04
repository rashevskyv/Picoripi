"""Tingle Tuner plugin hooks: load/save, limits, the client's own strings, the font source; the real disc
files when they are on the developer's disk."""
from pathlib import Path

import pytest

from core import font_formats
from core.font_formats import sources
from core.formats import SaveContext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.zelda_tingle import tuner

from .samples import message_file

GBA = Path(r"E:\Emulators\RomHacking\ZELDA\WW_UA\source\files\res\Gba")
PAL_GBA = Path(r"E:\Emulators\RomHacking\ZELDA\WW_UA\ISO\PAL\files\res\Gba")
needs_disc = pytest.mark.skipif(not (GBA / "msg_LZ.bin").is_file(), reason="Wind Waker disc files not on this disk")


def _save(rules, blocks, names, source, name="msg_LZ.bin"):
    rules.prepare_save_context(SaveContext(existing_versions=lambda: iter([source]), relative_path=f"res/Gba/{name}"))
    return rules.save_data_to_json_obj(blocks, names)


def test_plugin_loads_and_validates():
    rules = check_loads("zelda_tingle")
    assert ".bin" in {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator("zelda_tingle")


def test_sample_round_trip_and_unchanged_save_is_the_source():
    check_round_trip("zelda_tingle", message_file())
    rules = load_rules("zelda_tingle")
    data = message_file(True)
    blocks, names = rules.load_data_from_json_obj(data)
    assert names == {"0": "Tingle Tuner"} and blocks[0][1] == "Kooloo-limpah!"
    assert _save(rules, blocks, names, data) == data


def test_ukrainian_save_and_reload():
    rules = load_rules("zelda_tingle")
    data = message_file()
    blocks, names = rules.load_data_from_json_obj(data)
    blocks[0][1] = "Кулу-лімпа! Пане Феє, їжак ґанок"
    out = _save(rules, blocks, names, data)
    assert out != data
    assert load_rules("zelda_tingle").load_data_from_json_obj(out)[0][0][1] == blocks[0][1]


def test_other_files_give_one_empty_block():
    rules = load_rules("zelda_tingle")
    assert rules.load_data_from_json_obj(b"\x01\x02\x03\x04" * 8) == ([[]], {})
    assert _save(rules, [[]], {}, b"\x01\x02\x03\x04" * 8) == b"\x01\x02\x03\x04" * 8


def test_layout_and_widths():
    rules = load_rules("zelda_tingle")
    assert rules.get_string_layout(0, 0) == {"max_width": 96, "warn_width": 96, "lines_per_page": 6}
    assert rules.calculate_string_width_override("{color:2}Tingle{color:0}", {}) == 36
    assert "Text colour" in rules.get_tag_tooltip("{color:2}")
    assert rules.get_translation_context_for_string(0, 0)["content_role"].startswith("Tingle Tuner")


@needs_disc
def test_real_usa_messages_load_and_save():
    raw = (GBA / "msg_LZ.bin").read_bytes()
    rules = load_rules("zelda_tingle")
    blocks, names = rules.load_data_from_json_obj(raw)
    assert len(blocks[0]) == 1086
    assert blocks[0][1].startswith("{anim:13}{color:4}Tingle Bomb\n")
    assert not any("{x" in text for text in blocks[0])          # every USA glyph has a character
    assert _save(rules, blocks, names, raw) == raw
    blocks[0][1] = "{anim:13}{color:4}Бомба Тінгла\nТінгл {color:0}підірве\nдля вас бомбу!"
    out = _save(rules, blocks, names, raw)
    again = load_rules("zelda_tingle").load_data_from_json_obj(out)[0][0]
    assert again[1] == blocks[0][1] and again[2:] == blocks[0][2:]
    blocks[0] = [text + " довший рядок" * 3 for text in blocks[0]]
    with pytest.raises(ValueError, match="too long"):
        _save(rules, blocks, names, raw)


@needs_disc
@pytest.mark.parametrize("index", range(5))
def test_real_european_messages_round_trip(index):
    path = PAL_GBA / f"msg_LZ{index}.bin"
    if not path.is_file():
        pytest.skip("European disc files not on this disk")
    raw = path.read_bytes()
    rules = load_rules("zelda_tingle")
    blocks, names = rules.load_data_from_json_obj(raw)
    assert len(blocks[0]) == 1086 and tuner.parse(raw).halfword_offsets
    assert _save(rules, blocks, names, raw, path.name) == raw
    blocks[0][0] += " "
    assert load_rules("zelda_tingle").load_data_from_json_obj(_save(rules, blocks, names, raw, path.name))[0] == blocks


@needs_disc
def test_real_client_program_text_and_font():
    raw = (GBA / "client_u.bin").read_bytes()
    rules = load_rules("zelda_tingle")
    blocks, names = rules.load_data_from_json_obj(raw)
    assert names == {"0": "Tingle Tuner program text"}
    assert blocks[0] == ["Calling...", "Unable to link to the Nintendo GameCube.\nPlease turn off your Game Boy Advance."]
    assert _save(rules, blocks, names, raw, "client_u.bin") == raw
    blocks[0][0] = "Дзвоню..."
    out = _save(rules, blocks, names, raw, "client_u.bin")
    assert load_rules("zelda_tingle").load_data_from_json_obj(out)[0][0][0] == "Дзвоню..."
    assert load_rules("zelda_tingle").load_data_from_json_obj((GBA / "client_ud.bin").read_bytes()) == ([[]], {})

    found = sources.resolve(rules.get_font_sources(), {"source_path": str(GBA), "translation_path": "",
                                                       "is_directory_mode": True})
    assert [s.name for s in found] == ["client_u.bin"]
    params = found[0].params
    metadata, sheets = font_formats.extract("gba_tiles", raw, params)
    chars = font_formats.char_map(metadata)
    assert chars["A"] == 1 and chars["z"] == 0x34 and chars["б"] == 0x40 and chars["Б"] == 0x78
    assert font_formats.pack("gba_tiles", metadata, sheets, raw, params) == raw
    # the text save keeps a font drawn in the Font Editor (the host carries it over)
    sheet = sheets[0]
    sheet.paste((255, 255, 255, 255), (0x78 % 16 * 8 + 1, 0x78 // 16 * 8, 0x78 % 16 * 8 + 5, 0x78 // 16 * 8 + 7))
    with_font = font_formats.pack("gba_tiles", metadata, [sheet], raw, params)
    kept = font_formats.carry_over("gba_tiles", with_font, out, params)
    assert load_rules("zelda_tingle").load_data_from_json_obj(kept)[0][0][0] == "Дзвоню..."
    assert font_formats.extract("gba_tiles", kept, params)[1][0].tobytes() == \
        font_formats.extract("gba_tiles", with_font, params)[1][0].tobytes()
