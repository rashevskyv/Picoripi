"""Link's Awakening DX dialog codec on synthetic bytes (no game data): table, text spans and in-place writes."""
import pytest

from plugins.zelda_ladx import rom, text
from plugins.zelda_ladx.rom import DIALOG_COUNT, POINTER_TABLE, BANK_TABLE, ROM_SIZE


def _build_rom(dialogs):
    """A 1 MB ROM where dialog i holds ``dialogs[i]`` (bytes, without the end code) in bank 0x14."""
    data = bytearray(ROM_SIZE)
    base = 0x14 * 0x4000
    cursor = 0x0000
    for i in range(DIALOG_COUNT):
        run = dialogs[i] if i < len(dialogs) else b"\x20"
        pointer = 0x4000 + cursor
        at = POINTER_TABLE + 2 * i
        data[at] = pointer & 0xFF
        data[at + 1] = pointer >> 8
        data[BANK_TABLE + i] = 0x14
        start = base + cursor
        data[start : start + len(run)] = run
        data[start + len(run)] = 0xFF
        cursor += len(run) + 1
    return data


def test_identify_rejects_other_bytes():
    with pytest.raises(rom.UnknownRom):
        rom.identify(b"\x00" * 16)
    with pytest.raises(rom.UnknownRom):
        rom.identify(bytes(ROM_SIZE))


def test_dialog_names_match_the_disassembly_labels():
    assert rom.dialog_name(0) == "Dialog000"
    assert rom.dialog_name(0x24E) == "Dialog24E"
    assert rom.dialog_name(0x2AF) == "Dialog2AF"


def test_refs_resolve_bank_and_offset():
    data = _build_rom([b"HI"])
    refs = rom.read_dialog_refs(data)
    assert len(refs) == DIALOG_COUNT
    assert refs[0].bank == 0x14
    assert refs[0].rom == 0x14 * 0x4000
    assert refs[0].name == "Dialog000"
    assert text.read_text(data, refs[0]) == "HI"


def test_bank_byte_keeps_high_bits_and_masks_on_read():
    data = _build_rom([b"A"])
    data[BANK_TABLE] = 0x94
    ref = rom.read_dialog_refs(data)[0]
    assert ref.bank_byte == 0x94
    assert ref.bank == 0x14


def test_encode_decode_round_trip_for_tokens_and_escapes():
    sample = "Hi <skull>, it's 5 o'clock? Aé {03}"
    assert text.decode_bytes(text.encode_text(sample)) == sample


def test_unknown_character_is_refused():
    with pytest.raises(text.TextError):
        text.encode_text("Ukr: І")


def test_unchanged_rom_rebuilds_byte_for_byte():
    dialogs = [b"Whoa, boy!", b"<skull>\xfe Yes" + b"  ", b"x" * 20]
    data = _build_rom(dialogs)
    original = bytes(data)
    out = bytearray(data)
    for ref in rom.read_dialog_refs(original):
        run = original[ref.rom : ref.rom + text.span_length(original, ref.rom)]
        text.write_text(out, ref, text.to_markup(run))
    assert bytes(out) == original


def test_write_pads_short_text_with_spaces_and_keeps_the_end_code():
    data = _build_rom([b"Whoa, boy!"])
    ref = rom.read_dialog_refs(data)[0]
    out = bytearray(data)
    text.write_text(out, ref, "UA TEST")
    assert text.read_text(bytes(out), ref) == "UA TEST" + " " * 3
    assert out[ref.rom + 10] == 0xFF


def test_write_refuses_text_longer_than_the_run():
    data = _build_rom([b"Hi"])
    ref = rom.read_dialog_refs(data)[0]
    with pytest.raises(text.TextTooLong):
        text.write_text(bytearray(data), ref, "Hello!")


def test_span_without_end_code_is_an_error():
    data = bytearray(ROM_SIZE)
    with pytest.raises(text.TextError):
        text.span_length(bytes(data), 0x4000 * 0x14)
