"""Tests of the Castlevania: Symphony of the Night (PlayStation) plugin: codecs, scripts, saving, pictures.

Real-data tests read the workspace's ``source`` folder (``1_unpack.bat`` of the SotN PS1 workspace) and
skip when it is not on this machine.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from core import font_formats, texture_formats
from core.texture_formats import sotn as sotn_pictures
from plugins.castlevania_sotn import codec, doc, script
from plugins.castlevania_sotn.rules import GameRules
from plugins.testing import check_loads, check_validator

PLUGIN = "castlevania_sotn"
PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN
SOURCE = Path(r"E:\Emulators\RomHacking\Castlevania\Symphony of the Night\PS1\source")
needs_data = pytest.mark.skipif(not (SOURCE / "DRA.BIN").is_file(), reason="SotN workspace source not on disk")


def _sources(name):
    return json.loads((PLUGIN_DIR / name).read_text(encoding="utf-8"))


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_validator_passes():
    check_validator(PLUGIN)


# ---------------------------------------------------------------- codecs

def test_menu_strings_use_the_cell_numbers_and_keep_escapes():
    raw = bytes([0x21, 0x4C, 0x55, 0x43, 0x41, 0x52, 0x54, 0x00, 0x53]) + b"\xff\xff"
    text = codec.decode(raw, "s8")
    assert text == "Alucart s{FFFF}"
    assert codec.encode(text, "s8") == raw + codec.S8_END


def test_a_ukrainian_letter_goes_to_its_free_cell():
    assert codec.encode("Б", "s8", mapping={"Б": "ア"}) == bytes([codec.CELL_OF["ア"]]) + codec.S8_END
    missing = set()
    assert codec.encode("Ж", "s8", missing=missing)[:1] == bytes([codec.CELL_OF["?"]])
    assert missing == {"Ж"}


def test_the_shipped_map_gives_every_ukrainian_letter_a_cell():
    mapping = _sources("translation_map.json")
    letters = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
    for letter in letters + letters.lower():
        assert mapping.get(letter) in codec.CELL_OF, letter
    own = [v for k, v in mapping.items() if not v.isascii()]
    assert len(own) == len(set(own))


def test_shift_jis_text_keeps_quotes_line_breaks_and_unknown_codes():
    raw = b"Summons " + codec.QUOTE_SJ + b"Bat" + codec.QUOTE_SJ + b" @\x81\x44" + b"\xeb\x40"
    text = codec.decode(raw, "sj", newline="@")
    assert text == "Summons ”Bat” \n．{EB40}"
    assert codec.encode(text, "sj", newline="@") == raw + b"\x00"


def test_cyrillic_goes_to_the_bios_font_and_i_to_latin():
    assert codec.encode("Ліс", "sj") == "Л".encode("cp932") + b"i" + "с".encode("cp932") + b"\x00"
    missing = set()
    codec.encode("Є", "sj", missing=missing)
    assert missing == {"Є"}


# ---------------------------------------------------------------- scripts

def _script(base):
    """A script: a switch to page two, page one, page two."""
    page_one = b"\x05\x01\x00" + b"Hello" + b"\x01" + b"\x03\x10" + b"you" + b"\x06"
    page_two = b"\x05\x00\x01" + b"Bye" + b"\x06\x00"
    target = base + 9 + len(page_one)
    head = bytes([script.SWITCH]) + script.write_pointer(base + 0x7777) + script.write_pointer(target)
    return head + page_one + page_two


def test_script_lines_read_with_tags_and_speakers():
    data = _script(0x80180000) + bytes(16)
    ops = script.parse_ops(data, 0, len(data))
    lines = script.lines_of(ops)
    assert [script.line_text(ops, line) for line in lines] == ["Hello\n{WAIT 10}you", "Bye"]
    assert [line.speaker for line in lines] == [1, 0]


def test_a_longer_line_moves_the_pointers_into_the_script():
    base = 0x80180000
    data = _script(base) + bytes(16)
    new = script.build(data, 0, len(data), {0: script.encode_line("Hello there\n{WAIT 10}you")}, base)
    assert len(new) == len(data)
    ops = script.parse_ops(new, 0, len(new))
    lines = script.lines_of(ops)
    assert script.line_text(ops, lines[0]) == "Hello there\n{WAIT 10}you"
    switch = ops[0]
    assert script.read_pointer(switch.raw[1:5]) == base + 0x7777                       # outside: kept
    page_two = ops[lines[1].first - 1].at                                              # its portrait op
    assert script.read_pointer(switch.raw[5:9]) == base + page_two


def test_a_script_does_not_grow_past_its_room():
    base = 0x80180000
    data = _script(base)
    with pytest.raises(script.ScriptError):
        script.build(data, 0, len(data), {0: script.encode_line("Hello, a much longer line")}, base)


def test_staff_roll_entries_round_trip():
    data = b"\x01\x16CASTLEVANIA\x02\x10ROBERT\x00\x00\x00\x00"
    entries = [e for e in script.credit_entries(data, 0, len(data)) if e[1]]
    assert [script.credit_text(op, x, raw) for _at, op, x, raw in entries] == \
        ["{SUBTEXT 16}CASTLEVANIA", "{ENTRY 10}ROBERT"]
    new = script.build_credits(data, 0, len(data), {1: script.encode_credit("{ENTRY 10}ROB")})
    assert new == b"\x01\x16CASTLEVANIA\x02\x10ROB" + bytes(len(data) - 18)


# ---------------------------------------------------------------- pictures

def test_the_nibble_coder_round_trips():
    rows = bytearray(64 * 32)
    for y in range(32):
        for x in range(10, 50):
            rows[y * 64 + x] = 0x11 if (x + y) % 7 else 0xF1
    dictionary = bytes([0x11, 0x21, 0x61, 0x6F, 0x1F, 0x2F, 0x10, 0x20])
    packed = sotn_pictures.deflate(bytes(rows), dictionary)
    unpacked, size = sotn_pictures.inflate(packed + bytes(4), 0)
    assert unpacked == bytes(rows)
    assert size == len(packed)


def test_tile_blocks_are_placed_like_the_game_places_them():
    data = bytearray(4 * sotn_pictures.BLOCK)
    data[3 * sotn_pictures.BLOCK] = 0x0F             # block 3: second column, second row
    image = texture_formats.read("sotn_blocks", bytes(data), {"bpp": 4})[0].image
    assert image.size == (256, 256)
    assert image.getpixel((128, 128))[:3] == (255, 255, 255)
    assert texture_formats.write("sotn_blocks", bytes(data), {0: image}, {"bpp": 4}) == bytes(data)


# ---------------------------------------------------------------- real data

@needs_data
def test_every_program_file_reads_and_saves_back_byte_for_byte():
    for path in doc.layout()["files"]:
        data = (SOURCE / path).read_bytes()
        assert doc.build(data, doc.parse(data).texts()) == data, path


@needs_data
def test_a_longer_item_name_is_moved_and_read_back():
    data = (SOURCE / "DRA.BIN").read_bytes()
    parsed = doc.parse(data)
    texts = parsed.texts()
    names = {v: int(k) for k, v in parsed.names.items()}
    texts[names["Equipment names"]][1] += " of the long name"
    texts[names["Equipment descriptions"]] = [t[:10] for t in texts[names["Equipment descriptions"]]]
    out = doc.build(data, texts)
    assert len(out) == len(data)
    assert doc.parse(out).texts() == texts


@needs_data
def test_saving_keeps_pictures_edited_in_the_translation_copy():
    data = (SOURCE / "ST/NO0/NO0.BIN").read_bytes()
    rules = GameRules(None)
    blocks, names = rules.load_data_from_json_obj(data)
    picture = next(e for e in _sources("texture_sources.json") if e["path"] == "ST/NO0/NO0.BIN")
    image = texture_formats.read(picture["format"], data, picture["params"])[0].image
    image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    current = texture_formats.write(picture["format"], data, {0: image}, picture["params"])
    assert current != data
    blocks[0][0] += "!"
    rules.prepare_save_context(SimpleNamespace(existing_versions=lambda: iter([current, data])))
    out = rules.save_data_to_json_obj(blocks, names)
    assert GameRules(None).load_data_from_json_obj(out)[0][0][0] == blocks[0][0]
    offset = int(picture["params"]["offset"], 16)
    assert out[offset:offset + 256] == current[offset:offset + 256]


@needs_data
def test_every_picture_and_the_font_write_back_unchanged():
    for entry in _sources("texture_sources.json"):
        data = (SOURCE / entry["path"]).read_bytes()
        image = texture_formats.read(entry["format"], data, entry["params"])[0].image
        assert texture_formats.write(entry["format"], data, {0: image}, entry["params"]) == data, entry["label"]
    font = _sources("font_sources.json")[0]
    data = (SOURCE / font["path"]).read_bytes()
    metadata, sheets = font_formats.extract(font["format"], data, font["params"])
    assert font_formats.pack(font["format"], metadata, sheets, data, font["params"]) == data


@needs_data
def test_a_redrawn_area_name_packs_into_its_room():
    entry = next(e for e in _sources("texture_sources.json") if e["label"] == "Area name (NO0)")
    data = (SOURCE / entry["path"]).read_bytes()
    image = texture_formats.read(entry["format"], data, entry["params"])[0].image
    image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    out = texture_formats.write(entry["format"], data, {0: image}, entry["params"])
    assert len(out) == len(data)
    back = texture_formats.read(entry["format"], out, entry["params"])[0].image
    assert back.tobytes() == image.convert("RGBA").tobytes()


def test_a_script_that_outgrows_its_room_continues_in_free_space():
    base = 0x80180000
    data = bytearray(_script(base) + bytes(64))
    room = len(_script(base))
    spare = script.Spare([[room + 8, room + 64]])
    region = script.build(bytes(data), 0, room, {0: script.encode_line("Hello, a much longer line")}, base,
                          spare=spare)
    assert len(region) == room
    data[:room] = region
    for at, raw in spare.writes:
        data[at:at + len(raw)] = raw
    jump = next(op for op in script.parse_ops(bytes(data), 0, room) if op.code == script.JUMP)
    target = script.read_pointer(jump.raw[1:5]) - base
    assert room + 8 <= target < room + 64
    chars, at = bytearray(), 0                       # follow the script as the game does
    while data[at] != 6:                             # until the end of page one
        op = script.parse_ops(bytes(data), at, len(data))[0]
        if op.code == script.JUMP:
            at = script.read_pointer(op.raw[1:5]) - base
            continue
        if op.is_char:
            chars += op.raw
        at += len(op.raw)
    assert bytes(chars).decode("ascii").endswith("Hello, a much longer line")


@needs_data
def test_a_longer_cutscene_continues_in_free_space_and_reads_back():
    data = (SOURCE / "ST/NZ0/NZ0.BIN").read_bytes()
    parsed = doc.parse(data)
    texts = parsed.texts()
    number = next(int(k) for k, v in parsed.names.items() if v.startswith("Cutscene"))
    texts[number] = [t + " and more" for t in texts[number]]
    out = doc.build(data, texts)
    assert len(out) == len(data)
    assert doc.parse(out).texts() == texts
