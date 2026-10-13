"""Castlevania: Mirror of Fate plugin: the text codec (synthetic) and the real EU game files (skipped where the
workspace is not on this machine).

Real data: every localization file loads and saves back byte for byte; every font opens, packs back unchanged and
takes an edited glyph; every picture reads and writes back unchanged.
"""
import romhacking_root
import json
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.font_formats import char_map, coverage
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.castlevania_mof import text
from plugins.castlevania_mof.rules import GameRules

WS = romhacking_root.under('Castlevania\\Mirror of Fate\\3DS')
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "castlevania_mof"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_editor_form_round_trips():
    value = "Press @[A] to throw it.||Use @[$XP1] now|\xa9 caf\xe9"
    shown = text.to_editor(value)
    assert shown == "Press {A} to throw it.\n\nUse {$XP1} now\n\xa9 caf\xe9"
    assert text.from_editor(shown) == value


def test_file_keeps_keys_speakers_and_undefined_bytes():
    raw = b"HELP_A##One|two\r\ncut_1#Alucard#Hi \x81 there\r\nGUI_B##\xa9\r\n"
    parsed = text.MofText(raw)
    assert parsed.messages == [("HELP_A", "", "One|two"), ("cut_1", "Alucard", "Hi \x81 there"), ("GUI_B", "", "\xa9")]
    assert text.build_bytes(raw, [m[2] for m in parsed.messages]) == raw
    changed = text.build_bytes(raw, ["x", "y", "z"])
    assert changed == b"HELP_A##x\r\ncut_1#Alucard#y\r\nGUI_B##z\r\n"


def test_unknown_letters_are_written_as_question_marks_or_mapped():
    missing = set()
    assert text.encode("a\u0416b", missing) == b"a?b" and missing == {"\u0416"}
    rules = GameRules()
    rules.translation_map = {"\u0416": "\xc6"}
    assert text.from_editor("\u0416", rules.translation_map) == "\xc6"
    assert text.encode("\xc6") == b"\xc6"


def test_plugin_saves_a_changed_message_only():
    raw = b"A##Hello|world\r\nB#Bob#Bye @[A]\r\n"
    rules = GameRules()
    blocks, _ = rules.load_data_from_json_obj(raw)
    assert blocks == [["Hello\nworld", "Bye {A}"]]
    rules._source = raw
    assert rules.save_data_to_json_obj(blocks, {}) == raw
    blocks[0][1] = "Bye {B}"
    assert rules.save_data_to_json_obj(blocks, {}) == b"A##Hello|world\r\nB#Bob#Bye @[B]\r\n"
    rules._messages = text.MofText(raw).messages
    assert rules.get_speaker_for_string(0, 1) == "Bob" and rules.get_speaker_for_string(0, 0) is None


def test_every_localization_file_saves_back_byte_for_byte():
    folder = _need(SOURCE / "romfs" / "system" / "localization")
    raw = (folder / "english.txt").read_bytes()
    rules = GameRules()
    blocks, _names = rules.load_data_from_json_obj(raw)
    rules._source = raw
    assert len(blocks[0]) == 1522
    assert rules.save_data_to_json_obj(blocks, {}) == raw
    assert not any("{tag" in t for t in blocks[0])


def test_every_font_opens_packs_back_and_takes_a_glyph_edit():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert len(found) == 7
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract("mof_font", data)
        assert font_formats.pack("mof_font", metadata, sheets, data) == data
    data = (SOURCE / "romfs" / "system" / "fonts" / "pontif8.bfont").read_bytes()
    metadata, sheets = font_formats.extract("mof_font", data)
    glyph = char_map(metadata)["A"]
    gly = metadata["GLY1"][0]
    cw, ch, columns = gly["cell_width"], gly["cell_height"], gly["glyph_horizontal_count"]
    x, y = (glyph % columns) * cw, (glyph // columns) * ch
    sheet = sheets[0].copy()
    for px in range(x, x + cw):
        for py in range(y, y + ch):
            sheet.putpixel((px, py), (255, 255, 255, 255))
    out = font_formats.pack("mof_font", metadata, [sheet], data)
    assert len(out) == len(data) and out != data
    again, new_sheets = font_formats.extract("mof_font", out)
    assert coverage(new_sheets[0]).crop((x, y, x + cw, y + ch)).getbbox() == (0, 0, cw, ch)
    assert again["WID1"][0]["packets"][glyph]["width"] == cw


def test_every_picture_reads_and_writes_back():
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    found = texture_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    files = sorted({source.source_path for source in found})
    assert len(files) == 40
    for path in files:
        data = Path(path).read_bytes()
        textures = texture_formats.read("cgfx", data)
        assert texture_formats.write("cgfx", data, {i: t.image for i, t in enumerate(textures)}) == data, path
