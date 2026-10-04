"""Age of Calamity: text tables with self-relative string offsets, AOCT bundles, the [es] tag form."""
import struct

import pytest

from plugins.zelda_aoc import tags
from plugins.zelda_aoc.aoctext import FormatError, Table, TextBundle, build_bundle, read_bundle


def table(rows, extra=b""):
    """A text table: each row is a list of strings (None = no string) followed by ``extra`` bytes."""
    row_size = 4 * len(rows[0]) + len(extra)
    pool_start = 16 + row_size * len(rows)
    head = bytearray()
    pool = bytearray()
    for row in rows:
        for column, text in enumerate(row):
            position = 16 + len(head)
            if text is None:
                head += b"\0\0\0\0"
            else:
                head += struct.pack("<I", pool_start + len(pool) - position)
                pool += text.encode("utf-8") + b"\0"
        head += extra
    return struct.pack("<IIQ", len(rows), len(pool), 0) + bytes(head) + bytes(pool)


def dialogue(rows):
    """Battle dialogue rows: (text, seconds, speaker)."""
    pool_start = 16 + 12 * len(rows)
    head, pool = bytearray(), bytearray()
    for text, seconds, speaker in rows:
        head += struct.pack("<IfBBH", pool_start + len(pool) - (16 + len(head)), seconds, speaker, 1, 0)
        pool += text.encode("utf-8") + b"\0"
    return struct.pack("<IIQ", len(rows), len(pool), 0) + bytes(head) + bytes(pool)


def bundle(tables, key=0x1000):
    return build_bundle([(0xBE097869, key + i, t) for i, t in enumerate(tables)])


ITEMS_EN = table([["Tree Branch", "Wooden branches such as this\n[cdb]are common."], ["0", "0"],
                  ["[cs][es]1_1_1______Link[cm][es]5_5_1______Links[ce]", None]])
ITEMS_FR = table([["Branche", "Une branche."], ["0", "0"], ["Link", None]])


def sample_text() -> bytes:
    return bundle([ITEMS_EN] + [ITEMS_FR] * 11)


def sample_battle() -> bytes:
    en = dialogue([("Mipha and Daruk are in danger.", 26.5, 2), ("Hurry!", 3.0, 70), ("0", 1.0, 0)])
    en2 = dialogue([("Mipha and Daruk are in danger.", 26.5, 2), ("", 3.0, 70), ("0", 1.0, 0)])
    other = dialogue([("Mipha et Daruk sont en danger.", 26.5, 2), ("Vite !", 3.0, 70), ("0", 1.0, 0)])
    return bundle([en, en2] + [other] * 11, key=0x2000)


def test_table_columns_and_byte_exact_rebuild():
    parsed = Table.parse(ITEMS_EN)
    assert (parsed.rows, parsed.row_size, parsed.columns) == (3, 8, [0, 4])
    assert parsed.text(0, 4) == "Wooden branches such as this\n[cdb]are common." and parsed.raw(2, 4) == b""
    assert parsed.build({}) == ITEMS_EN
    grown = Table.parse(parsed.build({(0, 0): "Гілка дерева".encode()}))
    assert grown.text(0, 0) == "Гілка дерева" and grown.text(2, 0).startswith("[cs]")
    numbers = Table.parse(table([["a"], ["b"]], extra=struct.pack("<I", 0x40)))
    assert numbers.columns == [0]                       # a number column is not taken for strings


def test_bundle_header_and_refusals():
    data = sample_text()
    assert struct.unpack_from("<4sHH", data) == (b"AOCT", 1, 12)
    assert [key for _kind, key, _p in read_bundle(data)] == list(range(0x1000, 0x100C))
    with pytest.raises(FormatError):
        TextBundle(b"AOCT" + bytes(4))
    with pytest.raises(FormatError):
        TextBundle(bundle([ITEMS_EN] * 3))


def test_english_cells_exposed_and_written_back():
    text = TextBundle(sample_text())
    assert text.texts() == ["Tree Branch", "Wooden branches such as this\n[cdb]are common.",
                            "[cs][es:1_1_1]Link[cm][es:5_5_1]Links[ce]"]
    assert text.build(text.texts()) == sample_text()
    edited = text.build(["Гілка", None, "[cs][es:1_1_1]Лінк[cm][es:5_5_1]Лінки[ce]"])
    again = TextBundle(edited)
    assert again.texts()[0] == "Гілка" and again.texts()[2].startswith("[cs][es:1_1_1]Лінк")
    assert Table.parse(again.slots[0][2]).text(2, 0) == "[cs][es]1_1_1______Лінк[cm][es]5_5_1______Лінки[ce]"
    assert [s[2] for s in again.slots[1:]] == [s[2] for s in TextBundle(sample_text()).slots[1:]]


def test_hidden_values_are_never_written():
    text = TextBundle(sample_text())
    assert TextBundle(text.build(["", "0", None])).texts() == text.texts()


def test_battle_dialogue_mirrors_into_en2_where_it_was_the_same():
    text = TextBundle(sample_battle())
    assert text.is_battle_dialogue and text.texts() == ["Mipha and Daruk are in danger.", "Hurry!"]
    edited = TextBundle(text.build(["Міфа й Дарук у небезпеці.", "Швидше!"]))
    en2 = Table.parse(edited.slots[1][2])
    assert en2.text(0, 0) == "Міфа й Дарук у небезпеці." and en2.text(1, 0) == ""
    assert edited.slots[2][2] == text.slots[2][2]
    assert edited.table.value(0, 8, "B") == 2 and edited.table.value(0, 4, "f") == 26.5


def test_es_tag_round_trip():
    raw = "[es]2_5_1______monster and [es]x"
    assert tags.to_editor(raw) == "[es:2_5_1]monster and [es]x"
    assert tags.from_editor(tags.to_editor(raw)) == raw
    assert tags.describe("[s0]").startswith("Which") and tags.describe("[$0003]").startswith("Controller")
    assert tags.KNOWN_TAG_RE.fullmatch("[es:1_5_1]") and not tags.KNOWN_TAG_RE.fullmatch("[zz]")
