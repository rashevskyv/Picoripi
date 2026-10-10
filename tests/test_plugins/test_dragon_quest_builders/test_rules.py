"""Dragon Quest Builders plugin: excel string tables (self-relative offsets, number columns, key columns),
byte-exact when unedited, appended texts and footer when edited."""
import struct

import pytest

from core.formats import SaveContext
from plugins.dragon_quest_builders import excel
from plugins.dragon_quest_builders.rules import TAG_RE
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "dragon_quest_builders"


def make_table(rows, columns, pool_texts, cells):
    """``cells``: list of (row, column, value) where value is a text, an int (a number column) or None."""
    base = excel.HEADER + 4 * rows
    pool_at = base + 4 * rows * columns
    pool = bytearray()
    where = {}
    for row, column, value in cells:
        if isinstance(value, str) and value not in where:
            where[value] = len(pool)
            pool += value.encode("utf-8") + b"\0"
    cell_array = [0] * (rows * columns)
    for row, column, value in cells:
        index = row * columns + column
        if isinstance(value, str):
            cell_array[index] = pool_at + where[value] - (base + 4 * index)
        elif value is not None:
            cell_array[index] = value
    head = struct.pack("<I", rows) + bytes(excel.HEADER - 4)
    ids = struct.pack(f"<{rows}I", *range(rows))
    return head + ids + struct.pack(f"<{rows * columns}I", *cell_array) + bytes(pool)


SAMPLE = make_table(4, 3, None, [
    (0, 0, "<speaker(Rollo)>Hello!<key>"), (0, 1, 7), (0, 2, ""),
    (1, 0, "Open the <color(0xFFFC9016)>door</color>."), (1, 1, 1001), (1, 2, "second"),
    (2, 0, ""), (2, 1, 0), (2, 2, "<pname>, wait!<key>"),
    (3, 0, "Hello!"), (3, 1, 9), (3, 2, None),
])


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".bin"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_columns_and_texts_are_found_and_number_columns_skipped():
    table = excel.parse(SAMPLE)
    assert table is not None and table.columns == 3
    assert table.texts() == ["<speaker(Rollo)>Hello!<key>", "Open the <color(0xFFFC9016)>door</color>.", "second",
                             "<pname>, wait!<key>", "Hello!"]


def test_sample_survives_load_and_save_and_the_unedited_file_is_returned_as_is():
    check_round_trip(PLUGIN, SAMPLE)
    table = excel.parse(SAMPLE)
    assert excel.write(table, table.texts()) == SAMPLE


def test_edited_texts_are_appended_and_read_back_with_the_same_columns():
    table = excel.parse(SAMPLE)
    texts = table.texts()
    texts[1] = "Відчини <color(0xFFFC9016)>двері</color>."
    texts[4] = "Привіт!"
    out = excel.write(table, texts)
    pool_at = excel.HEADER + 4 * 4 + 4 * 12
    assert out[:pool_at - 4 * 12] == SAMPLE[:pool_at - 4 * 12] and out[pool_at:].startswith(SAMPLE[pool_at:])  # old pool kept
    again = excel.parse(out)
    assert again.columns == 3 and again.texts() == texts
    assert excel.write(again, texts) == out                                   # a second save is stable
    twice = excel.write(again, [t + "!" for t in texts])
    assert excel.parse(twice).texts() == [t + "!" for t in texts]
    assert twice.count(excel.FOOTER) == 1


def test_japanese_key_column_is_not_shown_and_not_rewritten():
    data = make_table(3, 2, None, [(0, 0, "やくそう"), (0, 1, "<icon(427)>medicinal herb"),
                                   (1, 0, "土"), (1, 1, "<icon(1)>earth"),
                                   (2, 0, "たいまつ"), (2, 1, "<icon(157)>torch")])
    table = excel.parse(data)
    assert table.texts() == ["<icon(427)>medicinal herb", "<icon(1)>earth", "<icon(157)>torch"]
    out = excel.write(table, ["a", "b", "c"])
    assert b"\xe3\x82\x84" in out and excel.parse(out).texts() == ["a", "b", "c"]


def test_things_that_are_not_tables_are_refused():
    assert excel.parse(b"") is None
    assert excel.parse(bytes(0x80)) is None
    assert excel.parse(struct.pack("<I", 2) + bytes(0x3c) + struct.pack("<2I", 0, 1) + struct.pack("<2I", 5, 6)) is None


def test_a_save_writes_over_the_newest_file_and_checks_the_line_count():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    rules.prepare_save_context(SaveContext(relative_path="text/Text.en.bin", existing_versions=lambda: iter([SAMPLE])))
    blocks[0][0] = "Привіт<key>"
    assert excel.parse(rules.save_data_to_json_obj(blocks, names)).texts()[0] == "Привіт<key>"
    with pytest.raises(ValueError):
        rules.save_data_to_json_obj([blocks[0][:-1]], names)


def test_tags_are_the_angle_codes():
    for tag in ("<key>", "<br>", "<pname>", "<speaker(Rollo)>", "<color(0xFFFC9016)>", "</color>", "<icon(427)>", "<nbsp>"):
        assert TAG_RE.fullmatch(tag), tag
    assert not TAG_RE.fullmatch("a < b")
