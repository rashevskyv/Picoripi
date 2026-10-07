"""Hyrule Warriors DE: XL tables, offset containers, control-code tags and the 12-language text file."""
import struct

import pytest

from plugins.zelda_hwde import ktbin, tags
from plugins.zelda_hwde.textfile import LANGUAGES, TextFile

SJIS = "こんにちは".encode("cp932") + b"\0"


def xl(types, rows):
    return ktbin.build_xl(ktbin.XlTable(0x13, list(types), [list(r) for r in rows]))


def section(lang: int) -> bytes:
    """Three tables: messages, a 3-form name table and a UTF-16 table."""
    en = lang in (1, 6)
    say = (b"Defeat \x1bA0%1s\x1bF2\x1bR!\0" if en else b"Besiege \x1bA0%1s\x1bF2\x1bR!\0")
    messages = xl([3, 3, 3, 0], [
        [1, 0, 0, say],
        [1, 2, 0, b"\0"],                      # empty: not a string
        [0, 0, 0, SJIS],                        # Japanese leftover, identical in every section
        [0, 1, 0, b"Caf\xe9 \x1bPH {x}\0"],
    ])
    names = xl([0, 0, 0], [[b"Link\0", b"Links\0", b"Link\0"], [b"Zelda\0", b"\0", b"Zelda\0"]])
    wide = xl([0], [["Mr. Fairy".encode("utf-16-le") + b"\0" * 4]])
    return ktbin.build_container([messages, names, wide])


def sample_file() -> bytes:
    return ktbin.build_container([section(i) for i in range(len(LANGUAGES))])


# -- ktbin --------------------------------------------------------------------

def test_xl_header_and_string_pool_round_trip():
    data = xl([2, 0, 3], [[-5, b"ab\0", 7], [3, b"\0\0\0\0", 1]])
    _magic, version, size, ncols, nrows, rowsize, rows_off = struct.unpack_from("<2sHHHHHI", data)
    assert (version, size, ncols, nrows, rowsize, rows_off) == (0x13, len(data), 3, 2, 7, 0x14)
    assert data[0x10:0x14] == b"\x02\x00\x03\xff"
    table = ktbin.parse_xl(data)
    assert table.rows == [[-5, b"ab\0", 7], [3, b"\0\0\0\0", 1]]
    assert ktbin.build_xl(table) == data


def test_xl_rejects_shared_strings():
    data = bytearray(xl([0, 0], [[b"a\0", b"b\0"]]))
    struct.pack_into("<I", data, 0x14 + 4, 8)  # second cell points at the first string
    with pytest.raises(ktbin.FormatError):
        ktbin.parse_xl(bytes(data))


def test_container_pads_payloads_to_four_bytes():
    built = ktbin.build_container([b"abc", b"defgh"])
    assert struct.unpack_from("<IIIII", built) == (2, 20, 3, 24, 5)
    assert built[20:] == b"abc\0defgh\0\0\0"
    payloads, gaps = ktbin.split_container(built)
    assert payloads == [b"abc", b"defgh"] and ktbin.build_container(payloads) == built


# -- tags ---------------------------------------------------------------------

@pytest.mark.parametrize("raw, editor", [
    (b"\x1bA0%1s\x1bF1\x1bR control!", "{c:0}%1s{form:1}{/c} control!"),
    (b"\x1bPH Skip \x1bP0", "{btn:H} Skip {btn:0}"),
    (b"\x1bK!\x1bL?\x1bN11/2\x1bN0", "{K:!}{L:?}{N:1}1/2{N:0}"),
    (b"\x1bT\x1bZ\x1bQ{a}\x01", "{ruby}{/ruby}{esc:Q}{lb}a{rb}{x:01}"),
    (b"\x1bK:", "{K:#3A}"),
    (b"line\nnext \xe9\x92", "line\nnext é’"),
    (b"\xfa\xfb\xfd\xda", "зйсЧ"),
])
def test_tags_round_trip(raw, editor):
    assert tags.to_editor(list(raw)) == editor
    assert bytes(tags.from_editor(editor)) == raw


def test_ukrainian_letters_use_cp1251_slots():
    units = tags.from_editor("Ґанон їжак Є №")
    assert bytes(units) == "Ґанон їжак Є №".encode("cp1251")


def test_latin_letters_the_game_shows_keep_their_slots():
    """× ç é ñ (English text, the language list) stay; Ч з й с use the free slots of Ъ ъ ы э."""
    assert bytes(tags.from_editor("×çéñ")) == b"\xd7\xe7\xe9\xf1"
    assert bytes(tags.from_editor("Чзйс")) == b"\xda\xfa\xfb\xfd"
    assert tags.to_editor(list(b"Fran\xe7ais Espa\xf1ol")) == "Français Español"


def test_unknown_tag_is_refused():
    with pytest.raises(ValueError):
        tags.parse_tag("{colour:1}")
    with pytest.raises(ValueError):
        tags.parse_tag("{c}")


# -- text file ----------------------------------------------------------------

def test_exposes_english_text_only():
    f = TextFile(sample_file())
    assert [b.name for b in f.blocks] == ["000 Messages", "001 Table", "002 Text"]
    texts = f.texts()
    assert texts[0] == ["Defeat {c:0}%1s{form:2}{/c}!", "Café {btn:H} {lb}x{rb}"]
    assert texts[1] == ["Link", "Links", "Link", "Zelda", "Zelda"]
    assert texts[2] == ["Mr. Fairy"]


def test_unchanged_save_is_byte_exact():
    data = sample_file()
    f = TextFile(data)
    assert f.build(f.texts()) == data


def test_translation_survives_reload_and_reaches_the_mirror():
    data = sample_file()
    f = TextFile(data)
    texts = f.texts()
    texts[0][0] = "Здолай {c:0}%1s{form:2}{/c}!"
    texts[2][0] = "Пан Фея"
    out = TextFile(data).build(texts)
    again = TextFile(out)
    assert again.texts() == texts
    sections = again.sections
    assert sections[6][0].rows[0][3] == sections[1][0].rows[0][3]
    assert sections[6][2].rows[0][0] == "Пан Фея".encode("cp1251").decode("cp1252").encode("utf-16-le") + b"\0" * 4
    assert sections[3][0].rows[0][3] == b"Besiege \x1bA0%1s\x1bF2\x1bR!\0"   # German untouched


def test_empty_translation_keeps_the_original():
    data = sample_file()
    texts = TextFile(data).texts()
    texts[1][0] = ""
    assert TextFile(data).build(texts) == data


def test_characters_without_a_byte_become_question_marks():
    data = sample_file()
    texts = TextFile(data).texts()
    texts[1][0] = "Link★"
    missing = set()
    out = TextFile(data).build(texts, missing)
    assert missing == {"★"}
    assert TextFile(out).texts()[1][0] == "Link?"


def test_not_a_text_file():
    from plugins.zelda_hwde.textfile import FormatError
    with pytest.raises(FormatError):
        TextFile(ktbin.build_container([b"abcd"] * 12))


def test_verify_rejects_a_file_that_would_not_rebuild_byte_exact():
    from plugins.zelda_hwde.textfile import FormatError
    odd = sample_file() + b"\0" * 8                 # a tail the container builder would not write back
    assert TextFile(odd).texts() == TextFile(sample_file()).texts()      # reading does not rebuild
    TextFile(sample_file(), verify=True)
    with pytest.raises(FormatError):
        TextFile(odd, verify=True)
