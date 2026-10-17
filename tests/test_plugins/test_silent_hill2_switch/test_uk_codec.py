"""Silent Hill 2 Switch: the Ukrainian glyph table of the message codec and the translation save path."""
import pytest

from plugins.silent_hill2_pc import mes


def test_ukrainian_words_decode_to_their_letters():
    # "Надто" (н is cell 0x6D), "Ні" (і is cell 0xCC), "цієї" (є 0x9D, ї 0xCF), "темно," (comma is 0x0C)
    assert mes.decode_uk(bytes([0x6D, 0x80, 0x84, 0x92, 0x8E])) == "Надто"
    assert mes.decode_uk(bytes([0x6D, 0xCC])) == "Ні"
    assert mes.decode_uk(bytes([0x96, 0xCC, 0x9D, 0xCF])) == "цієї"
    assert mes.decode_uk(bytes([0x92, 0x85, 0x8C, 0x8D, 0x8E, 0x0C])) == "темно,"
    assert mes.decode_uk(bytes([0x0E])) == "."


def test_codes_stay_tags_and_round_trip():
    raw = bytes([0x8E, 0xFD, 0x7F, 0x00, 0xFF, 0xFA])
    text = mes.decode_uk(raw)
    assert text == "о{FD}Я {FF}{FA}"
    assert mes.encode_uk(text) == raw


def test_letter_without_glyph_is_refused():
    with pytest.raises(ValueError):
        mes.encode_uk("Їжа")  # the atlas has no capital Ї


def test_ukrainian_message_files_round_trip_byte_exact():
    import romhacking_root
    folder = romhacking_root.under(r"Silent Hill\Silent Hill 2\Switch\translation\data\etc\message")
    if not folder.is_dir():
        pytest.skip("Silent Hill 2 Switch translation not here")
    files = sorted(folder.glob("*.mes"))
    assert files
    for path in files:
        raw = path.read_bytes()
        parts = mes.split(raw)
        assert mes.build(parts) == raw, path.name
        for part in parts:
            assert mes.encode_uk(mes.decode_uk(part)) == part, path.name
