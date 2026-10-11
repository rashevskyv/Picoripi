"""Paper Mario (N64) message codec: tags, the end code and padding, and the real ROM's messages (skipped
where the workspace is not on this machine)."""
import re
from pathlib import Path

import pytest

from plugins.paper_mario_64.msg_codec import decode_message, encode_message

WORKSPACE = Path(r"E:\Emulators\RomHacking\Paper Mario\Paper Mario 64\N64-PC-port with ISO")
MESSAGES = WORKSPACE / "source" / "text" / "paper_mario_64_messages.txt"
ROM = WORKSPACE / "ISO" / "Paper Mario (U) [!].z64"
ROM_SEGMENT = 0x1B83000
MESSAGES_YML = WORKSPACE / "source" / "text" / "messages.yml"


def test_decodes_letters_and_tags():
    raw = bytes.fromhex("ff299f344f4441590e0e0efd")
    assert decode_message(raw) == "[@FF][@29][@9F]Today..."


def test_encode_round_trips_a_tagged_message_with_padding():
    text = "[@FF][@29][@9F]Today..."
    assert encode_message(text) == bytes.fromhex("ff299f344f4441590e0e0efd")


def test_a_raw_bracket_is_a_tag_and_survives():
    raw = bytes.fromhex("3b41fd000000")
    text = decode_message(raw)
    assert text == "[@3B]a"
    assert encode_message(text) == bytes.fromhex("3b41fd00")


def test_bytes_after_the_end_code_are_padding_only():
    assert decode_message(bytes.fromhex("2122fd00")) == "AB"


def test_unknown_character_is_refused():
    with pytest.raises(ValueError):
        encode_message("Ї")


def test_encode_pads_to_four_bytes():
    assert len(encode_message("A")) % 4 == 0


def _real_messages():
    if not MESSAGES_YML.is_file() or not ROM.is_file():
        pytest.skip("the Paper Mario workspace is not on this machine")
    text = MESSAGES_YML.read_text(encoding="utf-8")
    entries = re.findall(r"^(\w+):\s*\n\s*\{ type: BLOB, offset: (0x[0-9A-Fa-f]+), size: (0x[0-9A-Fa-f]+) \}",
                         text, re.M)
    rom = ROM.read_bytes()
    return [(name, rom[ROM_SEGMENT + int(off, 16):ROM_SEGMENT + int(off, 16) + int(size, 16)])
            for name, off, size in entries]


def test_real_rom_messages_round_trip_byte_exact():
    messages = _real_messages()
    assert len(messages) == 8009
    bad = [name for name, raw in messages if encode_message(decode_message(raw)) != raw]
    assert bad == []
