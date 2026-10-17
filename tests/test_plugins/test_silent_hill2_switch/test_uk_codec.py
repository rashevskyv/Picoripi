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


UKRAINIAN_CAPITALS = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"  # the 33 letters of the Ukrainian alphabet


def test_capital_yi_is_the_spare_cell_of_the_atlas():
    assert mes.UK_CELLS[0x7A] == "Ї"
    assert mes.decode_uk(bytes([0x7A, 0x86, 0x80])) == "Їжа"
    assert mes.encode_uk("Їжа") == bytes([0x7A, 0x86, 0x80])


def test_russian_only_letter_is_refused():
    with pytest.raises(ValueError):
        mes.encode_uk("Ъ")  # Russian only: the atlas has no cell for it any more


def test_every_ukrainian_letter_has_one_cell():
    letters = UKRAINIAN_CAPITALS + UKRAINIAN_CAPITALS.lower()
    assert len(letters) == 66
    assert all(0x400 <= ord(ch) <= 0x4FF for ch in letters)  # Cyrillic, no Latin look-alikes
    for ch in letters:
        raw = mes.encode_uk(ch)
        assert len(raw) == 1, ch
        assert mes.decode_uk(raw) == ch, ch


def test_every_byte_round_trips_through_the_table():
    for b in range(256):
        raw = bytes([b])
        assert mes.encode_uk(mes.decode_uk(raw)) == raw, hex(b)


def test_font_sheet_labels_match_the_codec_table():
    import json
    from pathlib import Path

    import plugins.silent_hill2_switch as switch

    sheet = json.loads((Path(switch.__file__).parent / "font_sources.json").read_text(encoding="utf-8"))
    labels = sheet[0]["params"]["chars"]
    for b in range(223):
        assert labels[b] == (mes.UK_CELLS[b] or "\u0000"), hex(b)


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
