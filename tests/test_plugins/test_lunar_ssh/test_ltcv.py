"""Lunar: Silver Star Harmony script (LTCV) and text-table codecs on small files made here."""
import struct

from plugins.lunar_ssh import ltcv
from plugins.lunar_ssh.rules import GameRules, build_table, table_texts


def _script(labels, words):
    """``labels``: [(id, start word, end word)]; ``words``: the code."""
    head = b"LTCV" + struct.pack("<III", 2 * len(words), len(labels), 16 + 8 * len(labels))
    table = b"".join(struct.pack("<HHI", i, 2 * (e - s), 2 * s) for i, s, e in labels)
    return head + table + struct.pack(f"<{len(words)}H", *words)


def _chars(text):
    return [ord(c) for c in text]


WORDS = ([0x3E, 0, 0x29, 0xFFFF]                                                   # label 1: words 0-3
         + [0x02, 0x042E, 41] + _chars("Hi") + [0x0401] + _chars("there") + [0x0414, 0x0416]   # label 2: 4-...
         + [0x07, 0x92] + _chars("Yes") + [0xFFFF] + _chars("No") + [0xFFFF, 0xFFFF]
         + [0x38, 1, 0x0419, 0, 0x0416, 0x05])
SPLIT = 4


def _data():
    return _script([(1, 0, SPLIT), (2, SPLIT, len(WORDS))], WORDS)


def test_messages_and_choices_read_with_tags():
    script = ltcv.parse(_data())
    assert ltcv.texts(script) == ["{speaker:41}Hi\nthere{wait}", "Yes", "No"]
    assert [s.kind for s in script.spans] == ["message", "choice", "choice"]


def test_unchanged_texts_give_the_same_bytes():
    data = _data()
    assert ltcv.build(data, ltcv.texts(ltcv.parse(data))) == data
    assert ltcv.build(data, [None, None, None]) == data


def test_longer_text_moves_the_labels():
    data = _data()
    new = ltcv.build(data, ["{speaker:41}Hello\nthere, Alex{wait}{page}Bye{wait}", "Yes!", "No"])
    script = ltcv.parse(new)
    assert ltcv.texts(script) == ["{speaker:41}Hello\nthere, Alex{wait}{page}Bye{wait}", "Yes!", "No"]
    assert script.labels[0] == (1, 2 * SPLIT, 0)
    assert script.labels[1][2] == 2 * SPLIT and script.labels[1][1] == 2 * (len(script.code) - SPLIT)
    assert script.code[-6:] == [0x38, 1, 0x0419, 0, 0x0416, 0x05]


def test_characters_the_script_cannot_hold_become_question_marks():
    missing = set()
    new = ltcv.build(_data(), ["Ыэ漢", "", "No"], missing)
    assert missing == set("Ыэ漢")
    assert ltcv.texts(ltcv.parse(new)) == ["???", " ", "No"]


def test_ukrainian_letters_are_stored_with_their_cp1251_codes():
    new = ltcv.build(_data(), ["{speaker:41}Привіт, Ґанно!{wait}", "Так", "Ні"])
    script = ltcv.parse(new)
    assert ltcv.texts(script) == ["{speaker:41}Привіт, Ґанно!{wait}", "Так", "Ні"]
    assert script.code[script.spans[1].start:script.spans[1].end] == list("Так".encode("cp1251"))


def test_text_table_keeps_comments_and_end_mark():
    raw = "﻿Dummy;\t\tダミー\r\nKnife;\t\tナイフ\r\nCredits line\r\n\x1a".encode("utf-16-le")
    assert table_texts(raw) == ["Dummy", "Knife", "Credits line"]
    assert build_table(raw, table_texts(raw)) == raw
    new = build_table(raw, ["Пусто", "Ніж; гострий", "Титри"])
    expected = "﻿Пусто;\t\tダミー\r\nНіж, гострий;\t\tナイフ\r\nТитри\r\n\x1a"
    assert new == ltcv.store_letters(expected).encode("utf-16-le")
    assert table_texts(new) == ["Пусто", "Ніж, гострий", "Титри"]


def test_rules_load_and_save_both_kinds():
    for raw in (_data(), "A;x\r\nB\r\n".encode("utf-16-le")):
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw
