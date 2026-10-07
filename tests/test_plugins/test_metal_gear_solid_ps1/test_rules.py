"""Metal Gear Solid (PlayStation) plugin hooks: load and save every kind of file; the real workspace when present."""
import json
from pathlib import Path

import pytest

from core import font_formats
from core.formats import SaveContext
from core.texture_formats import pcx
from core.texture_formats import sources as texture_sources
from plugins.metal_gear_solid_ps1 import doc as docs
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

from .samples import gcx, program, radio, subs_file

WS = Path(r"E:\Emulators\RomHacking\Metal Gear\Metal Gear Solid\PS1")
SOURCE = WS / "source"
real = pytest.mark.skipif(not (SOURCE / "RADIO.DAT").is_file(), reason="the unpacked workspace is not on this machine")


def test_plugin_loads_and_validates():
    rules = check_loads("metal_gear_solid_ps1")
    assert {".dat", ".gcx", ".subs", ".94", ".bin"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator("metal_gear_solid_ps1")


@pytest.mark.parametrize("sample", [
    radio([["Snake, do you read me?", "Loud and clear."]]),
    gcx(["Press the Start Button"]),
    subs_file([["He'll be through here...\nI know it."]]),
    program(["Data saved.", "MEMORY CARD 1"]),
])
def test_samples_round_trip(sample):
    check_round_trip("metal_gear_solid_ps1", sample)


def test_letters_without_a_glyph_become_question_marks():
    rules = load_rules("metal_gear_solid_ps1")
    source = radio([["Snake, do you read me?", "Loud and clear."]])
    blocks, names = rules.load_data_from_json_obj(source)
    blocks[0][1] = 'Чути "добре".'
    out = rules.save_data_to_json_obj(blocks, names)
    again, _ = load_rules("metal_gear_solid_ps1").load_data_from_json_obj(out)
    assert again[0] == ["Snake, do you read me?", '???? "?????".']


def test_program_line_longer_than_its_slot_is_refused():
    rules = load_rules("metal_gear_solid_ps1")
    source = program(["Data saved.", "MEMORY CARD 1"])
    blocks, names = rules.load_data_from_json_obj(source)
    blocks[0][0] = "A much longer message than the slot"
    rules.prepare_save_context(SaveContext(relative_path="SLUS_005.94", existing_versions=lambda: iter([source])))
    with pytest.raises(docs.FormatError, match="SLUS_005.94"):
        rules.save_data_to_json_obj(blocks, names)


def test_program_translation_is_read_with_the_source_layout():
    rules = load_rules("metal_gear_solid_ps1")
    source = program(["Data saved.", "MEMORY CARD 1"])
    blocks, names = rules.load_data_from_json_obj(source)
    blocks[0][1] = "UA TEST 1"
    out = rules.save_data_to_json_obj(blocks, names)
    fresh = load_rules("metal_gear_solid_ps1")
    fresh.restore_runtime_state(json.loads(json.dumps(rules.export_runtime_state())))
    assert fresh.load_data_from_json_obj(out)[0] == [["Data saved.", "UA TEST 1"]]


def test_subtitle_block_too_long_for_its_room_is_refused():
    rules = load_rules("metal_gear_solid_ps1")
    source = subs_file([["Short."]], room=64)
    blocks, names = rules.load_data_from_json_obj(source)
    blocks[0][0] = "A line far too long for the little room this subtitle block has in its stream"
    with pytest.raises(docs.FormatError, match="too long"):
        rules.save_data_to_json_obj(blocks, names)


# -- the real workspace ----------------------------------------------------------------------


def _text_files():
    return sorted(p for p in SOURCE.rglob("*") if p.suffix.lower() in (".dat", ".gcx", ".subs", ".94", ".bin"))


@real
def test_every_real_text_file_loads_and_saves_byte_exact():
    lines = 0
    for path in _text_files():
        rules = load_rules("metal_gear_solid_ps1")
        data = path.read_bytes()
        blocks, names = rules.load_data_from_json_obj(data)
        lines += sum(len(b) for b in blocks)
        assert rules.save_data_to_json_obj(blocks, names) == data, path
    assert lines > 28000


@real
@pytest.mark.parametrize("rel, block, line", [("RADIO.DAT", 24, 3), ("subs/demo.subs", 3, 1),
                                              ("stage/title/ea54.gcx", 0, 1), ("SLUS_005.94", 0, 2)])
def test_real_edit_survives_save_and_reload(rel, block, line):
    rules = load_rules("metal_gear_solid_ps1")
    data = (SOURCE / rel).read_bytes()
    blocks, names = rules.load_data_from_json_obj(data)
    blocks[block][line] = "UA TEST"
    out = rules.save_data_to_json_obj(blocks, names)
    fresh = load_rules("metal_gear_solid_ps1")
    fresh.restore_runtime_state(rules.export_runtime_state())
    again, _ = fresh.load_data_from_json_obj(out)
    assert again[block][line] == "UA TEST"
    assert sum(len(b) for b in again) == sum(len(b) for b in blocks)


@real
def test_real_font_and_textures_open_and_pack_back_unchanged():
    font = (SOURCE / "font/font.res").read_bytes()
    metadata, sheets = font_formats.extract("mgs1", font)
    assert font_formats.pack("mgs1", metadata, sheets, font) == font
    rules = load_rules("metal_gear_solid_ps1")
    found = texture_sources.resolve(rules.get_texture_sources(), {"source_path": str(SOURCE), "translation_path": "",
                                                                 "is_directory_mode": True})
    assert len(found) > 500
    for source in found[::25]:
        data = Path(source.source_path).read_bytes()
        assert pcx.write(data, {0: source.read_original().image}, {}) == data
