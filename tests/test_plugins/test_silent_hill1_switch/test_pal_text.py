"""Silent Hill 1 (PAL disc, Ukrainian English slot): the glyph text codec and the PAL overlay round trip."""
import pytest

import romhacking_root
from plugins.silent_hill_ps1 import doc, pal_text


def test_ukrainian_word_decodes_from_glyph_bytes():
    raw = bytes([0x4D, 0x6F, 0x8B, 0x90, 0x8D, 0x88, 0x6F, 0x2C])   # "Можливо,"
    assert pal_text.decode_message(raw) == "Можливо,"
    assert pal_text.encode_message("Можливо,", raw) == raw


def test_control_code_is_ascii_inside_angle_brackets():
    raw = bytes([0x7B, 0x43, 0x32, 0x7D, 0x86])                      # {C2} then а
    assert pal_text.decode_message(raw) == "⟨C2⟩а"
    assert pal_text.encode_message("⟨C2⟩а", raw) == raw


def test_english_message_stays_ascii():
    raw = bytes(b"these bizarre events")
    assert pal_text.decode_message(raw) == "these bizarre events"
    assert pal_text.encode_message("these bizarre events", raw) == raw


def test_translation_only_codes_round_trip_as_bytes():
    raw = bytes([0xA4, 0xFE, 0xFF, 0x0A, 0x09])                      # я х ц {0A}{09}
    text = pal_text.decode_message(raw)
    assert text == "яхц{0A}{09}"
    assert pal_text.encode_message(text, raw) == raw


def test_new_text_uses_the_written_cells():
    assert pal_text.encode_message("аі", bytes([0x86, 0x80])) == bytes(
        [pal_text._BYTE_OF["а"], pal_text._BYTE_OF["і"]])
    with pytest.raises(ValueError):
        pal_text.encode_message("Ї", bytes([0x86]))   # no capital Ї on this sheet


def test_real_overlays_build_back_unchanged():
    folder = romhacking_root.under(r"Silent Hill\Silent Hill\Switch\translation\VIN")
    if not folder.is_dir():
        pytest.skip("Silent Hill PAL translation not here")
    checked = 0
    for path in sorted(folder.glob("MAP*.BIN"))[:12]:
        data = path.read_bytes()
        texts = doc.texts(data, pal=True)
        out, problems = doc.build(data, texts, pal=True)
        assert problems == [], path.name
        assert out == data, path.name
        checked += 1
    assert checked
