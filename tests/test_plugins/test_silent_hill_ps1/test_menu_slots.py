"""Silent Hill (PlayStation) menu overlays: strings sit at fixed offsets, edited in place, room kept.

Synthetic bytes only: a zero-filled overlay of the real size with a few strings placed at their offsets.
"""
from plugins.silent_hill_ps1 import doc
from plugins.silent_hill_ps1.menu_slots import OPTION_SIZE, SAVELOAD_SIZE, pack_key


def overlay(size, placed):
    out = bytearray(size)
    for offset, text in placed:
        raw = text.encode("latin-1") + b"\x00"
        out[offset:offset + len(raw)] = raw
    return bytes(out)


def option_overlay():
    # Exit at 404 (room up to Brightness_Level at 412), Weapon_Control at 224, Blood_Color at 240
    return overlay(OPTION_SIZE, [(404, "Exit"), (224, "Weapon_Control"), (240, "Blood_Color")])


def test_option_overlay_opens_its_strings_at_their_offsets():
    groups = doc.parse(option_overlay())
    assert [g.label for g in groups] == ["options"]
    # menu order: Exit, then Weapon_Control, then Blood_Color
    assert [slot.text for slot in groups[0].slots] == ["Exit", "Weapon_Control", "Blood_Color"]


def test_edit_fits_room_and_keeps_its_slot():
    data = option_overlay()
    out, problems = doc.build(data, [["UA", "Weapon_Control", "Blood_Color"]])
    assert problems == []
    assert len(out) == len(data)
    # the translated string is still a slot after the write
    assert doc.texts(out) == [["UA", "Weapon_Control", "Blood_Color"]]


def test_edit_longer_than_room_is_not_written():
    data = option_overlay()
    out, problems = doc.build(data, [["TOO_LONG_TEXT", "Weapon_Control", "Blood_Color"]])
    assert out == data
    assert len(problems) == 1 and "room" in problems[0]


def test_save_load_overlay_is_a_separate_block():
    data = overlay(SAVELOAD_SIZE, [(4, "Next_fear"), (32, "Nowhere"), (272, "SLOT1")])
    groups = doc.parse(data)
    assert [g.label for g in groups] == ["save and load"]
    assert [s.text for s in groups[0].slots] == ["Next_fear", "Nowhere", "SLOT1"]


def test_other_sizes_are_not_menu_overlays():
    assert doc.parse(bytes(1000)) == []


def test_pack_key_writes_equals_as_dash():
    assert pack_key("Exit") == "MENU.Exit"
    assert pack_key("A=B") == "MENU.A-B"
