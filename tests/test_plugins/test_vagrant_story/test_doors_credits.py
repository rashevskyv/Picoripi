"""Vagrant Story text outside the room script: door scripts, the chest's weapon name, the staff roll."""
import struct
from pathlib import Path

import pytest

from core.formats import SaveContext
from plugins.testing import load_rules
from plugins.vagrant_story import codec, formats
from plugins.vagrant_story import doc as docs

from .samples import script

SOURCE = Path(r"E:\Emulators\RomHacking\Vagrant Story\source")


def door_room(room_lines, doors, weapon="Seventh Heaven", slack_check=True) -> bytes:
    """A room: geometry, cleared, script, a door section (16 offsets + scripts), enemies, a 544-byte treasure."""
    room = script(room_lines)
    door_bytes, offsets = b"", []
    for lines in doors:
        offsets.append(32 + len(door_bytes))
        door_bytes += script(lines)
    end = 32 + len(door_bytes)
    door_section = struct.pack("<16H", *(offsets + [end] * (16 - len(offsets)))) + door_bytes
    treasure = bytearray(formats.TREASURE_SIZE)
    name = (weapon if isinstance(weapon, bytes) else codec.encode(weapon)) + bytes((codec.END,))
    treasure[formats.TREASURE_NAME:formats.TREASURE_NAME + len(name)] = name
    bodies = [b"\x5a" * 0x40, b"\x01" * 4, room, door_section, b"\x0e" * 8, bytes(treasure)]
    header, at = [], 0x30
    for body in bodies:
        header += [at, len(body)]
        at += len(body)
    return struct.pack("<12I", *header) + b"".join(bodies)


def save(rules, data, blocks, names):
    rules.prepare_save_context(SaveContext(relative_path="MAP/MAP999.MPD", existing_versions=lambda: iter([data])))
    return rules.save_data_to_json_obj(blocks, names)


def test_room_shows_its_door_scripts_and_the_weapon_in_its_chest():
    data = door_room(["Who goes there?"], [["The door is locked!"], ["Room cleared!", "Unlatched the door!"]])
    rules = load_rules("vagrant_story")
    blocks, names = rules.load_data_from_json_obj(data)
    assert list(names.values()) == ["Room dialog", "Door 0 dialog", "Door 1 dialog", "Treasure"]
    assert blocks == [["Who goes there?"], ["The door is locked!"], ["Room cleared!", "Unlatched the door!"],
                      ["Seventh Heaven"]]
    assert save(rules, data, blocks, names) == data


def test_growing_room_and_door_scripts_move_what_follows():
    data = door_room(["Who goes there?"], [["The door is locked!"], ["Room cleared!"]])
    rules = load_rules("vagrant_story")
    blocks, names = rules.load_data_from_json_obj(data)
    blocks[0][0] = "Who goes there? " * 3
    blocks[1][0] = "The door is locked, it will not open, not today, not ever!"
    blocks[3][0] = "Сьоме небо"
    out = save(rules, data, blocks, names)
    assert len(out) > len(data)
    again, _ = load_rules("vagrant_story").load_data_from_json_obj(out)
    assert again == blocks
    sections = formats.mpd_header(out)
    assert [s for s, _l in sections] == sorted(s for s, _l in sections)     # still back to back


def test_empty_treasure_slot_is_not_shown():
    data = door_room(["Hello."], [], weapon=docs.NOTHING)     # the game writes the space as FA 06
    blocks, names = load_rules("vagrant_story").load_data_from_json_obj(data)
    assert list(names.values()) == ["Room dialog"]


def credits_file(names) -> bytes:
    stream = bytearray(b"\x08\x0d\xa0\x05")
    for index, name in enumerate(names):
        body = bytes((2 + index % 2,)) + name.encode("latin-1")
        stream += b"\x01\x0c\x01\x10\x02" + bytes((len(body),)) + body
    return bytes(stream) + b"\x01\x3c\xff" + bytes(64)


def test_staff_roll_is_ascii_in_place():
    people = [f"Person Number {i:03d}" for i in range(formats.CREDIT_MIN)] + ["Fran>ois Hermellin"]
    data = credits_file(people)
    rules = load_rules("vagrant_story")
    blocks, names = rules.load_data_from_json_obj(data)
    assert list(names.values()) == ["Staff roll"] and blocks[0] == people
    blocks[0][0] = "Short"
    out = save(rules, data, blocks, names)
    assert len(out) == len(data)
    again, _ = load_rules("vagrant_story").load_data_from_json_obj(out)
    assert again[0][0] == "Short" + " " * (len(people[0]) - 5) and again[0][1:] == people[1:]
    blocks[0][0] = people[0] + "!"
    with pytest.raises(formats.FormatError):
        save(rules, data, blocks, names)
    blocks[0][0] = "Ґава"
    with pytest.raises(formats.FormatError):
        save(rules, data, blocks, names)


def test_credits_bytes_keep_codes():
    assert docs.credits_bytes("Minagaw{x1F}a") == b"Minagaw\x1fa"
    line = docs.Line(b"M\x7fllenkamp", docs.CREDITS, "", 0, 10)
    assert docs.text_of(line) == "M{x7F}llenkamp"


needs_disc = pytest.mark.skipif(not (SOURCE / "ENDING" / "ENDING.PRG").exists(), reason="Vagrant Story not unpacked here")


@needs_disc
@pytest.mark.parametrize("rel,groups", [("ENDING/ENDING.PRG", ["Staff roll"]),
                                        ("MAP/MAP018.MPD", ["Room dialog", "Door 1 dialog", "Door 2 dialog",
                                                            "Treasure"])])
def test_real_doors_and_staff_roll_round_trip(rel, groups):
    data = (SOURCE / rel).read_bytes()
    rules = load_rules("vagrant_story")
    blocks, names = rules.load_data_from_json_obj(data)
    assert list(names.values()) == groups
    assert save(rules, data, blocks, names) == data
    if rel.startswith("ENDING"):
        assert len(blocks[0]) == 300 and "Yasumi Matsuno" in blocks[0]
