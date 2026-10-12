"""Ocarina of Time 3D: the translator's sheet written into the English slot of eu.qm (synthetic fixtures; the real
package is checked when its files are on disk)."""
import json
import struct

import pytest

import romhacking_root
from plugins.zelda_oot3d import qm, sheet_import as si

# Under the RomHacking root: the game's source package, and the translator's sheet and its shipped package
# (copy the oot3d_ua folder there to run that check).
OOT3D_SOURCE_QM = ("Zelda", "Ocarina of Time", "3D - 3DS", "source", "romfs", "message", "eu", "eu.qm")
OOT3D_SHEET = ("oot3d_ua", "source", "current_translation.json")
OOT3D_PACKAGE_QM = ("oot3d_ua", "build", "rev1_stage6", "romfs", "message", "eu", "eu.qm")
EU_ENGLISH = 2          # language index of the English slot in the table row
GERMAN = 3


def make_qm(messages):
    """A minimal eu.qm: ``messages`` is ``[(id, {language index: raw text}), ...]`` (languages 2..9)."""
    table, body = bytearray(), bytearray()
    start = 16 + len(messages) * qm.ENTRY
    for message_id, texts in messages:
        values = [message_id, 0, 2, 3, 0, 0, 0, 0]
        for language in range(2, 10):
            raw = texts.get(language, b"")
            while (start + len(body)) % 4:
                body.append(0)
            if raw:
                values += [start + len(body), len(raw)]
                body += raw
            else:
                values += [0, 0]
        table += struct.pack("<24I", *values)
    return struct.pack("<4sIII", b"QM\0\0", 4, len(messages), 0) + bytes(table) + bytes(body)


def sheet_row(message_id, english, ukrainian):
    return [str(message_id), hex(message_id), str(message_id), "2", "0;0", english, ukrainian] + [""] * 8


def make_sheet(rows):
    header = ["№", "ID (hex)", "ID", "Тип", "Службове", "English (EU)", "Українська"] + [""] * 8
    return {"sheet": "test", "values": [header] + rows}


def test_encodes_named_codes_and_plain_text():
    assert si.encode_message("⟦NL⟧A⟦COLOR:RED⟧b⟦COLOR:WHITE⟧") == b"\x7f\x1cA\x7f\x1d\x41b\x7f\x1d\x00"
    assert si.encode_message("⟦ITEM:2D⟧") == b"\x7f\x0f\x2d"
    assert si.encode_message("⟦SOUND:00010002F2⟧") == b"\x7f\x0e\x00\x01\x00\x02\xf2"
    assert si.encode_message("⟦CHOICE_2:FFFFFFFF⟧") == b"\x7f\x1a\xff\xff\xff\xff"


def test_plain_text_loses_newlines_and_combining_accents():
    assert si.encode_message("a\u0301\nb\r") == b"ab"


def test_unknown_tag_and_wrong_argument_size_are_refused():
    with pytest.raises(si.SheetError, match="Unknown tag"):
        si.encode_message("⟦NO_SUCH_TAG⟧")
    with pytest.raises(si.SheetError, match="argument bytes"):
        si.encode_message("⟦ITEM:2D2D⟧")


def test_text_after_end_moves_before_the_end_code():
    assert si.repair_terminal_text("x⟦END⟧y") == ("xy⟦END⟧", True)
    assert si.repair_terminal_text("x⟦END⟧  ") == ("x⟦END⟧  ", False)
    assert si.repair_terminal_text("no end") == ("no end", False)


def test_control_codes_stop_at_the_end_code():
    assert si.control_codes(b"\x7f\x1cA\x7f\x00junk") == [(0x1C, b"")]


def test_build_replaces_the_english_slot_and_keeps_other_languages():
    source = make_qm([
        (1, {EU_ENGLISH: b"Hello\x7f\x00", GERMAN: b"Hallo\x7f\x00"}),
        (2, {EU_ENGLISH: b"Bye\x7f\x00"}),
        (3, {EU_ENGLISH: b"Ok\x7f\x00"}),
    ])
    sheet = make_sheet([
        sheet_row(1, "Hello⟦END⟧", "Привіт⟦NL⟧Світ⟦END⟧"),
        sheet_row(2, "Bye⟦END⟧", ""),                 # empty Ukrainian cell: English text
        sheet_row(3, None, ""),                       # no English either: the game's own bytes stay
    ])
    result = si.build_eu_qm(source, sheet)
    assert result.translated == 1
    assert result.fallback_ids == [2, 3]
    assert [c["id"] for c in result.code_changes] == ["0x00000001"]
    file = qm.Qm(result.data)
    assert file.ids == [1, 2, 3]
    assert file.texts[0][0] == "Привіт".encode() + b"\x7f\x1c" + "Світ".encode() + b"\x7f\x00"
    assert file.texts[1][0] == b"Bye\x7f\x00"
    assert file.texts[2][0] == b"Ok\x7f\x00"
    assert file.texts[0][1] == b"Hallo\x7f\x00"      # German slot untouched
    assert si.check_editor_readable(result.data) == []


def test_row_count_and_id_must_match_the_game_file():
    source = make_qm([(1, {EU_ENGLISH: b"A\x7f\x00"})])
    with pytest.raises(si.SheetError, match="messages"):
        si.build_eu_qm(source, make_sheet([]))
    with pytest.raises(si.SheetError, match="ID"):
        si.build_eu_qm(source, make_sheet([sheet_row(9, "A", "B")]))


@romhacking_root.needs(OOT3D_SOURCE_QM, OOT3D_SHEET, OOT3D_PACKAGE_QM)
def test_real_sheet_reproduces_the_translators_shipped_eu_qm():
    source = romhacking_root.path(*OOT3D_SOURCE_QM).read_bytes()
    sheet = json.loads(romhacking_root.path(*OOT3D_SHEET).read_text(encoding="utf-8"))
    result = si.build_eu_qm(source, sheet)
    assert result.data == romhacking_root.path(*OOT3D_PACKAGE_QM).read_bytes()
    assert result.translated == 2508
    assert result.fallback_ids == [1371, 1373]
    assert si.check_editor_readable(result.data) == []
