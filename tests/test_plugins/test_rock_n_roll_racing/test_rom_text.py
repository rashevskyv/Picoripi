"""Rock N' Roll Racing (SNES): the string codec, the fixed-budget writer and the IPS patch, on a small synthetic ROM."""
import pytest

from plugins.rock_n_roll_racing import rom_text as rt


def _rom(strings, region_byte=rt.REGION_USA):
    """A 1 MB ROM whose text table is zero bytes (terminators) with ``strings`` (offset -> bytes) written in."""
    data = bytearray(rt.ROM_SIZE)
    data[rt.HEADER:rt.HEADER + len(rt.TITLE)] = rt.TITLE
    data[rt.REGION_OFFSET] = region_byte
    for offset, raw in strings.items():
        data[offset:offset + len(raw)] = raw
    return bytes(data)


def _checksum_ok(rom: bytes) -> bool:
    total = sum(rom) & 0xFFFF
    field = int.from_bytes(rom[rt.CHECKSUM_OFFSET:rt.CHECKSUM_OFFSET + 4], "little")
    return field & 0xFFFF == total ^ 0xFFFF and field >> 16 == total


def _apply_ips(original: bytes, patch: bytes) -> bytes:
    assert patch[:5] == b"PATCH"
    out, i = bytearray(original), 5
    while patch[i:i + 3] != b"EOF":
        offset = int.from_bytes(patch[i:i + 3], "big")
        size = int.from_bytes(patch[i + 3:i + 5], "big")
        i += 5
        out[offset:offset + size] = patch[i:i + size]
        i += size
    return bytes(out)


def test_usa_header_is_recognised_and_other_regions_are_not():
    assert rt.is_usa_rom(_rom({}))
    assert not rt.is_usa_rom(_rom({}, region_byte=0x02))
    assert not rt.is_usa_rom(_rom({})[:-1])


def test_string_slots_give_the_room_of_each_string():
    rom = _rom({rt.TEXT_START: b"PLAYER", rt.TEXT_START + 0x10: b"AB\rCD"})
    slots = rt.string_slots(rom)
    assert (rt.TEXT_START, 6) in slots
    assert (rt.TEXT_START + 0x10, 5) in slots


def test_codec_round_trips_lines_and_tags_and_refuses_what_the_game_cannot_draw():
    raw = b"A\rB[C\x80"
    text = rt.decode(raw)
    assert text == "A\nB[5B]C[80]"
    assert rt.encode(text) == raw
    with pytest.raises(rt.EncodeError) as error:
        rt.encode("Ї")                     # Cyrillic Yi: no code in the font
    assert error.value.char == "Ї"
    with pytest.raises(rt.EncodeError):
        rt.encode("[00]")                       # a 00 byte would end the string


def test_build_pads_a_shorter_string_with_spaces_and_fixes_the_checksum():
    rom = _rom({rt.TEXT_START: b"PLAYER"})
    bank = rt.extract(rom)
    string = bank["blocks"][0]["strings"][0]
    string["raw"] = rt.encode("UA").hex()
    patched = rt.build(rom, bank)
    assert patched[rt.TEXT_START:rt.TEXT_START + 6] == b"UA    "
    assert _checksum_ok(patched)


def test_build_refuses_a_string_longer_than_its_room():
    rom = _rom({rt.TEXT_START: b"PLAYER"})
    bank = rt.extract(rom)
    bank["blocks"][0]["strings"][0]["raw"] = b"TOO LONG".hex()
    with pytest.raises(ValueError, match="room is 6"):
        rt.build(rom, bank)


def test_ips_patch_turns_the_original_into_the_patched_rom():
    original = _rom({rt.TEXT_START: b"PLAYER"})
    patched = bytearray(original)
    patched[rt.TEXT_START + 2] = 0x55
    patched[rt.TEXT_START + 3] = 0x56
    patched[rt.HEADER + 40] = 0x01
    patch = rt.create_ips(original, bytes(patched))
    assert _apply_ips(original, patch) == bytes(patched)
    assert rt.create_ips(original, original) == b"PATCHEOF"
