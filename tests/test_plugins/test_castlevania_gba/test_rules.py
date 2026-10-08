"""Castlevania GBA plugin (Harmony of Dissonance, Aria of Sorrow): text codes, strings bank, 1-bit fonts; real data."""
import json
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats, texture_formats
from core.font_formats import cv_gba
from core.font_formats.sources import join_pair, split_pair
from core.texture_formats.sources import resolve as resolve_textures
from plugins.castlevania_gba import codec
from plugins.castlevania_gba.rules import BLOCKS, TEXT_FORMAT, font_descriptors
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "castlevania_gba"
ROOT = Path(r"E:\Emulators\RomHacking\Castlevania")
WORKSPACES = {"aos": ROOT / "Aria of Sorrow", "hod": ROOT / "Harmony of Dissonance"}


def _bank(game: str, strings) -> dict:
    return {"format": TEXT_FORMAT, "version": 1, "game": game, "strings": [s.hex() for s in strings]}


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, [["First line", "Second line"], ["A line of the next block"]])


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_aos_codes_become_text_and_tags_and_back():
    data = bytes([0x05, 0x04, 0x03, 0x00, 0x07, 0x01]) + b"Hi" + bytes([0x06]) + b"[x]" + bytes([0x05, 0x09, 0x0B, 0xE9, 0x81])
    text = codec.AOS.decode(data)
    assert text == "[box]\n[face:00][name:01]Hi\n［x］[page]\n[A]é[x81]"
    assert codec.AOS.encode(text) == data


def test_aos_ukrainian_letters_have_their_own_free_cells():
    assert len(codec.AOS_UA_SLOTS) == 66 and len(set(codec.AOS_UA_SLOTS.values())) == 66
    assert codec.AOS.encode("Їжак") == bytes(codec.AOS_UA_SLOTS[c] for c in "Їжак")
    assert codec.AOS.decode(codec.AOS.encode("ґанок")) == "ґанок"


def test_hod_narrow_letters_and_shift_jis_capitals():
    data = b"".join(code.to_bytes(2, "little") for code in (0xF003, 0x0001, 0x8269, 0x855C, 0x8540, 0x824F, 0xF006,
                                                          0xF005, 0x8440, 0x8492, 0xF004))
    text = codec.HOD.decode(data)
    assert text == "[face:0001]Ju 0\n[wait]АҐ[clear]"
    assert codec.HOD.encode(text) == data


def test_unknown_characters_are_reported_and_written_as_question_marks():
    assert codec.HOD.unknown_chars("Hi 🙂[wait]") == ["🙂"]
    with pytest.raises(codec.EncodeError):
        codec.AOS.encode("Ω")
    assert codec.AOS.encode("aΩ", strict=False) == b"a?"


def test_the_bank_loads_in_blocks_and_saves_only_the_edited_string():
    strings = [b"Name %d" % i for i in range(965)]
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(_bank("aos", strings))
    assert len(blocks) == len(BLOCKS["aos"]) and names["1"].startswith("Story")
    assert rules.get_message_attributes(1, 2) == {"id": 13}
    blocks[1][2] = "Привіт"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved["strings"][13] == codec.AOS.encode("Привіт").hex()
    assert [s for i, s in enumerate(saved["strings"]) if i != 13] == [s.hex() for i, s in enumerate(strings) if i != 13]
    assert rules.get_string_layout(1, 0)["font_file"] == "aos_text.json"


def _font(count=3, rows=4, record=6):
    data = bytearray()
    for glyph in range(count):
        data += glyph.to_bytes(2, "big") + bytes([0x81, 0x41, 0x01, 0xC1][:rows])
    return bytes(data), {"glyphs": count, "record": record, "rows": rows, "keep_mask": 1,
                         "widths": {"stride": 4, "byte": 1}, "chars": {"A": 1}}


def test_cv_gba_font_round_trip_keeps_hidden_bits_and_writes_glyphs_and_widths():
    glyphs, params = _font()
    widths = bytes([0, 5, 0, 0] * 3)
    data = join_pair(glyphs, widths)
    metadata, sheets = cv_gba.extract(data, params)
    assert font_formats.char_map(metadata) == {"A": 1}
    assert cv_gba.pack(metadata, sheets, data, params) == data
    ImageDraw.Draw(sheets[0]).rectangle((8, 0, 15, 3), fill=(255, 255, 255, 255))
    metadata["WID1"][0]["packets"][1]["width"] = 7
    new_glyphs, new_widths = split_pair(cv_gba.pack(metadata, sheets, data, params))
    assert new_glyphs[6:8] == b"\x00\x01" and new_glyphs[8:12] == b"\xff\xff\xff\xff"   # bit 0 kept as it was
    assert new_glyphs[:6] == glyphs[:6] and new_widths[5] == 7 and new_widths[1] == 5


# -- real data (skipped when the workspaces are not on disk) ---------------------------------------------------


@pytest.mark.parametrize("game", ["aos", "hod"])
def test_real_strings_decode_and_encode_to_the_same_bytes(game):
    bank_path = WORKSPACES[game] / "source" / "text" / "strings.cvtext"
    if not bank_path.is_file():
        pytest.skip("Castlevania GBA workspace not on disk")
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    for raw in bank["strings"]:
        data = bytes.fromhex(raw)
        assert codec.CODECS[game].encode(codec.CODECS[game].decode(data)) == data
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(bank)
    assert sum(len(b) for b in blocks) == len(bank["strings"])
    assert rules.save_data_to_json_obj(blocks, names)["strings"] == bank["strings"]


@pytest.mark.parametrize("game", ["aos", "hod"])
def test_real_fonts_and_pictures_read_and_write_back_unchanged(game):
    source = WORKSPACES[game] / "source"
    if not (source / "fonts").is_dir():
        pytest.skip("Castlevania GBA workspace not on disk")
    fonts = [d for d in font_descriptors() if (source / d["path"]).is_file()]
    assert len(fonts) == 2
    for descriptor in fonts:
        data = (source / descriptor["path"]).read_bytes()
        if descriptor.get("companion"):
            data = join_pair(data, (source / descriptor["companion"]).read_bytes())
        metadata, sheets = font_formats.extract("cv_gba", data, descriptor["params"])
        assert font_formats.pack("cv_gba", metadata, sheets, data, descriptor["params"]) == data
    descriptors = json.loads((Path(__file__).parents[3] / "plugins" / PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    textures = resolve_textures(descriptors, {"source_path": str(source), "translation_path": str(source.parent / "_no_translation"),
                                              "is_directory_mode": True})
    assert len(textures) == len(list((source / "gfx").glob("*.bin")))
    for texture in textures:
        image = texture.read_original().image
        raw = Path(texture.source_path).read_bytes()
        assert texture_formats.write("tiles", raw, {0: image}, texture.params) == raw
