"""Lunar 2 Remastered dialogue scripts: the message reader on a small synthetic stream (no game data)."""
import struct

from core.containers.lunar_scn import EN_GLYPHS, read_messages


def _words(*values):
    return struct.pack("<%dH" % len(values), *values)


def test_english_glyph_table_spells_dialogue():
    # "Hi" + line break + "ok." + message end, after a voice cue 0xB2C1.
    data = _words(0x2000, 0xB2C1, 0x702F, 0x7050, 0x1000, 0x7056, 0x7052, 0x7015, 0x2000)
    msgs = read_messages(data, english=True)
    assert len(msgs) == 1
    assert msgs[0].offset == 4  # the first text word, after the message end and the cue
    assert msgs[0].cues == (0xB2C1,)
    assert msgs[0].lines == ["Hi", "ok."]
    assert EN_GLYPHS[0x07] == " " and EN_GLYPHS[0x48] == "a" and EN_GLYPHS[0x28] == "A"


def test_junk_before_a_message_is_not_part_of_it():
    # Five control words in a row end the open message; the text after them is a new message.
    data = _words(0x7028, 0x0001, 0x0002, 0x0003, 0x0004, 0x0005, 0x7028, 0x2000)
    msgs = read_messages(data, english=True)
    assert [m.lines for m in msgs] == [["A"]]
    assert msgs[0].offset == 2 * 6


def test_japanese_shift_jis_words_and_unclosed_text_is_dropped():
    # Hiragana A and I (SJIS 0x82A0 and 0x82A2) on two lines, then a message end; trailing text without an end mark.
    data = _words(0x82A0, 0x1000, 0x82A2, 0x2000, 0x82A0)
    msgs = read_messages(data, english=False)
    assert [m.lines for m in msgs] == [["あ", "い"]]
    assert msgs[0].offset == 0
