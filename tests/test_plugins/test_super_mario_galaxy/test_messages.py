"""Message archives of both versions on synthetic data: labels, tag byte order, writing by label, the pictures."""
import struct

from core.containers.rarc_container import RarcContainer
from plugins.super_mario_galaxy import bcsv, messages

from .fixture import message_arc, table

LABELS = ["Title_Press", "Npc_Hello", "System_Wait"]
WII = [["Press ", (3, b"\x00\x00"), " and ", (3, b"\x00\x01")],
       ["Hello ", (255, b"\x00\x00\x01\x00"), "Mario", (255, b"\x00\x00\x00\x00")],
       ["Wait", (1, b"\x00\x00\x00\x1e"), (6, b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01")]]
# The same messages as the Switch file stores them: tag numbers and the group 1, 6 and 7 numbers little-endian.
SWITCH = [["Press ", (3, b"\x49\x00")],
          ["Hello ", (255, b"\x00\x00\x01\x00"), "Mario", (255, b"\x00\x00\x00\x00")],
          ["Wait", (1, b"\x00\x00\x1e\x00"), (6, b"\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00")]]


def test_bcsv_rows_read_in_both_byte_orders():
    for little in (False, True):
        rows = bcsv.read_rows(table(LABELS, little), ["MessageId", "Index"])
        assert sorted((row["MessageId"], row["Index"]) for row in rows) == sorted((n, i) for i, n in enumerate(LABELS))


def test_both_versions_read_as_the_same_editor_text():
    wii = messages.texts_by_label(message_arc(LABELS, WII))
    switch = messages.texts_by_label(message_arc(LABELS, SWITCH, little=True))
    assert wii["Npc_Hello"] == switch["Npc_Hello"] == "Hello {escape:255:00000100}Mario{escape:255:00000000}"
    assert wii["System_Wait"] == switch["System_Wait"] == \
        "Wait{escape:1:0000001e}{escape:6:00000000000000000001}"
    assert list(wii) == LABELS   # message order


def test_an_unchanged_archive_writes_back_the_same_members():
    for data in (message_arc(LABELS, WII), message_arc(LABELS, SWITCH, little=True)):
        out = messages.apply_texts(data, messages.texts_by_label(data))
        before, after = RarcContainer(data), RarcContainer(out)
        assert after.list_files() == before.list_files()
        assert all(after.read_file(name) == before.read_file(name) for name in before.list_files())


def test_text_goes_in_by_label_in_the_target_byte_order():
    data = message_arc(LABELS, SWITCH, little=True)
    out = messages.apply_texts(data, {"System_Wait": "Чекай{escape:1:0000001e}", "Unknown": "x"})
    texts = messages.texts_by_label(out)
    assert texts["System_Wait"] == "Чекай{escape:1:0000001e}"
    assert texts["Npc_Hello"] == messages.texts_by_label(data)["Npc_Hello"]
    bmg = RarcContainer(out).read_file("message.bmg")
    assert "Чекай".encode("utf-16-le") in bmg and b"\x1a\x00\x08\x01\x00\x00\x1e\x00" in bmg
    old = RarcContainer(data).read_file("message.bmg")
    # the size field (it leaves out FLW1 on the disc) moves by as much as the file changed
    assert len(bmg) != len(old)
    assert struct.unpack_from("<I", bmg, 8)[0] - struct.unpack_from("<I", old, 8)[0] == len(bmg) - len(old)


def test_an_archive_without_a_label_table_is_labelled_by_number():
    data = message_arc([], [["One"], ["Two"]], little=True, with_table=False)
    assert messages.texts_by_label(data) == {"#0": "One", "#1": "Two"}


def test_pictures_move_between_versions_by_the_english_pairs():
    wii = {"A": "Press {escape:3:0000}", "B": "Use {escape:3:0000} or {escape:3:0001}"}
    switch = {"A": "Press {escape:3:0049}", "B": "Use {escape:3:0049} or {escape:3:004b}"}
    pairs = messages.picture_pairs(wii, switch)
    assert messages.swap_pictures("Тисни {escape:3:0000}", "A", pairs) == "Тисни {escape:3:0049}"
    assert messages.swap_pictures("{escape:3:0001}", "Other", pairs) == "{escape:3:004b}"   # the common pair
    assert messages.swap_pictures("{escape:3:004b}{escape:255:00000100}", "B", pairs, reverse=True) == \
        "{escape:3:0001}{escape:255:00000100}"


def test_a_picture_with_no_pair_takes_the_other_versions_english_picture_at_its_place():
    pairs = messages.picture_pairs({"A": "Press {escape:3:0000}"}, {"A": "Press {escape:3:0049}"})
    title_wii = "Press both {escape:3:0000} and {escape:3:0001}."
    # the Switch-only picture 0x38 has no pair anywhere: it becomes the Wii English picture at the same place
    assert messages.swap_pictures("Тисни {escape:3:0038}", "Title", pairs, reverse=True, english=title_wii) == \
        "Тисни {escape:3:0000}"
    assert messages.swap_pictures("{escape:3:0049} {escape:3:0038} {escape:3:0039}", "T", pairs, reverse=True,
                                  english=title_wii) == "{escape:3:0000} {escape:3:0001} {escape:3:0001}"
    assert messages.swap_pictures("{escape:3:0038}", "T", pairs, reverse=True) == "{escape:3:0038}"


def test_union_rows_keep_the_first_version_order_and_split_a_label_worded_differently():
    rows = messages.union_rows([("wii", {"a": "A", "b": "Point at it", "d": "Press {escape:3:0000}"}),
                                ("switch", {"b": "Touch it", "c": "C", "d": "Press  {escape:3:0049}"})])
    assert rows == [{"label": "a", "text": "A", "in": ["wii"]},
                    {"label": "b", "text": "Point at it", "in": ["wii"], "split": True},
                    {"label": "b", "text": "Touch it", "in": ["switch"], "split": True},
                    {"label": "d", "text": "Press {escape:3:0000}", "in": ["wii", "switch"]},   # pictures only
                    {"label": "c", "text": "C", "in": ["switch"]}]
    assert messages.read_document(messages.make_document(rows)) == rows
    assert messages.read_document(b'{"format": "other"}') is None and messages.read_document(b"\xff") is None
