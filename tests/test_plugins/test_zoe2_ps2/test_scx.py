"""The stage script text layer: strings found by their pointers, written in place or moved to the end."""
import struct

from plugins.zoe2_ps2 import scx

from .helpers import make_scx

STRINGS = [b"Save game.", b"Press the \x83\x02 button|to fire.", b"Yes", b"Fire rod-like lasers while|pressing it."]


def _pointers(data):
    return [struct.unpack_from("<I", data, m.start(1))[0] for m in scx.POINTER.finditer(data)]


def test_text_strings_are_found_by_pointer_and_labels_are_left_out():
    data = make_scx(STRINGS)
    assert scx.read_texts(data) == ["Save game.", "Press the {83:02} button\nto fire.", "Yes",
                                    "Fire rod-like lasers while\npressing it."]


def test_text_class_keeps_one_word_labels_and_drops_resource_names():
    assert scx.is_text(b"Saved.") and scx.is_text(b"NORMAL") and scx.is_text(b"geme initialize start")
    assert not scx.is_text(b"fa_sky_01_RP.tex") and not scx.is_text(b"s131c1") and not scx.is_text(b"AumCore_Settle")
    assert not scx.is_text(b"\x82\x08\x82-code") and not scx.is_text(b"----")


def test_tags_round_trip_through_text():
    raw = b"A\x80\x7c b\x83\x04 c\x0a"
    text = scx.decode(raw)
    assert text == "A{80:7C} b{83:04} c{0A}"
    assert scx.encode(text) == (raw, [])
    assert scx.encode("Line\nbreak") == (b"Line|break", [])


def test_unchanged_texts_write_back_the_same_bytes():
    data = make_scx(STRINGS)
    assert scx.write_texts(data, scx.read_texts(data)) == (data, [])


def test_a_shorter_string_is_written_in_place():
    data = make_scx(STRINGS)
    texts = scx.read_texts(data)
    texts[0] = "Save."
    out, problems = scx.write_texts(data, texts)
    assert problems == [] and len(out) == len(data)
    assert scx.read_texts(out) == texts
    assert _pointers(out) == _pointers(data)


def test_a_longer_string_moves_to_the_end_and_its_pointer_follows():
    data = make_scx(STRINGS)
    texts = scx.read_texts(data)
    texts[2] = "Yes, I really want to do that now"
    out, problems = scx.write_texts(data, texts)
    assert problems == [] and len(out) > len(data) and len(out) % 16 == 0
    assert out[:len(data)].count(b"Yes") == 1                      # the old place is untouched
    assert scx.read_texts(out) == texts                           # same strings, same order
    changed = [(a, b) for a, b in zip(_pointers(data), _pointers(out)) if a != b]
    assert len(changed) == 1 and changed[0][1] >= len(data)
    again, _ = scx.write_texts(out, scx.read_texts(out))
    assert again == out


def test_an_edit_that_would_look_like_a_resource_name_still_reads_back():
    data = make_scx(STRINGS)
    texts = scx.read_texts(data)
    texts[2] = "obj1"
    out, problems = scx.write_texts(data, texts)
    assert problems == [] and scx.read_texts(out)[2] == "obj1 "


def test_a_character_the_font_lacks_is_reported_and_written_as_a_question_mark():
    data = make_scx(STRINGS)
    texts = scx.read_texts(data)
    texts[2] = "Так так"
    out, problems = scx.write_texts(data, texts)
    assert len(problems) == 1 and scx.read_texts(out)[2] == "??? ???"
