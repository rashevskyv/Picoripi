"""Metal Gear Solid (PlayStation) file formats: text codec, codec calls, GCX scripts, subtitles, program strings."""
import pytest

from plugins.metal_gear_solid_ps1 import codec, gcx, program, radio, subs
from plugins.metal_gear_solid_ps1.spans import SizeError

from .samples import gcx as gcx_file
from .samples import program as program_file
from .samples import radio as radio_file
from .samples import subtitle_block


@pytest.mark.parametrize("raw, newline, quote", [
    (b"Be careful, Snake.\x80#\x80Nwith infrared sensors.", codec.RADIO_LF, codec.QUOTE),
    (b"\x80\"Big Boss\x80\" said\x80|so.", codec.SUB_LF, codec.QUOTE),
    (b"Legendary Soldier\" Big Boss", codec.SUB_LF, codec.PLAIN_QUOTE),
    (b"\xb0\x14Rope\xd0\x15\x80|Press \x90\x1b to use.", codec.SUB_LF, codec.PLAIN_QUOTE),
    (b"\x80D\x80o\x80c\x80k\x90\x01\x80B\x801", codec.RADIO_LF, codec.QUOTE),
    (b"odd {x} \x7f", codec.RADIO_LF, codec.QUOTE),
])
def test_codec_reads_back_every_byte(raw, newline, quote):
    text = codec.decode(raw, newline, quote)
    assert codec.encode(text, newline, quote, codec.is_wide(raw)) == raw


def test_codec_shows_line_breaks_quotes_and_codes():
    assert codec.decode(b"a\x80#\x80Nb \x80\"c\x80\" \x96\x01") == 'a\nb "c" {9601}'
    assert codec.decode(b"\x80D\x80o\x90\x01\x80k") == "Do k"
    missing = set()
    assert codec.encode("Ґ", missing=missing) == b"?" and missing == {"Ґ"}
    assert codec.encode("Ґ", translation_map={"Ґ": "G"}) == b"G"


def test_radio_call_grows_and_every_size_follows():
    data = radio_file([["Snake, do you read me?", "Loud and clear."], ["What's the situation?"]])
    calls = radio.read(data)
    assert [len(c.texts) for c in calls] == [2, 1] and calls[0].voices
    longer = codec.encode("UA TEST: a much longer line\nin two rows")
    new, offsets = radio.build(data, calls, {(0, 1): longer})
    again = radio.read(new)
    assert radio.texts_of(new, again) == [[b"Snake, do you read me?", longer], [b"What's the situation?"]]
    assert offsets[1] == again[1].offset > calls[1].offset
    assert radio.build(data, calls, {})[0] == data


def test_radio_code_counts_the_sectors_it_needs():
    assert radio.sectors_code(0x47DEB, 0x529) == 0x01047DEB
    assert radio.sectors_code(0x1B1661, 0x100) == 0x001B1661


def test_gcx_string_grows_and_procs_move():
    data = gcx_file(["Press the Start Button", "RATION"], proc_strings=["Now Checking..."])
    script = gcx.read(data)
    assert gcx.strings_of(data, script) == [b"Now Checking...", b"Press the Start Button", b"RATION"]
    new = gcx.build(data, script, {0: b"UA TEST: checking the disc", 2: b"RATIONS"})
    again = gcx.read(new)
    assert gcx.strings_of(new, again) == [b"UA TEST: checking the disc", b"Press the Start Button", b"RATIONS"]
    assert gcx.build(new, again, {0: b"Now Checking...", 2: b"RATION"}) == data


def test_gcx_refuses_a_string_past_255_bytes():
    data = gcx_file(["RATION"])
    with pytest.raises(SizeError):
        gcx.build(data, gcx.read(data), {0: b"X" * 300})


def test_subtitle_block_layout():
    first = codec.encode("The nuclear weapons disposal\nfacility", codec.SUB_LF)
    raw = subtitle_block(["The nuclear weapons disposal\nfacility", "on Shadow Moses Island."])
    block = subs.Block.parse(raw)
    assert [e.text for e in block.entries] == [first, b"on Shadow Moses Island."]
    assert block.build([e.text for e in block.entries]) == raw
    longer = block.build([b"UA TEST", b"A longer second line than before."])
    assert [e.text for e in subs.Block.parse(longer).entries] == [b"UA TEST", b"A longer second line than before."]
    assert subs.Block.parse(longer).build([e.text for e in block.entries]) == raw


def test_program_strings_have_their_slot():
    data = program_file(["Data saved.", "MEMORY CARD 1", "sna_chest1", "%d error"])
    found = program.find(data)
    assert [data[s:data.index(b"\0", s)] for s, _room in found] == [b"Data saved.", b"MEMORY CARD 1"]
    assert [room for _s, room in found] == [12, 16]
