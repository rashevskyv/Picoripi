"""Dragon Quest VII, VIII and Monsters: Joker 3 (3DS) plugins: packs, tables and the real games' files."""
import struct
from pathlib import Path

import pytest

from core.containers.darc import DarcContainer
from core.texture_formats import dmp
from plugins.dq_monsters_joker3 import mes
from plugins.dq_monsters_joker3 import rules as j3_rules
from plugins.dragon_quest_vii import fpt
from plugins.dragon_quest_vii import rules as dq7_rules
from plugins.dragon_quest_viii import bine
from plugins.testing import check_loads, check_validator, load_rules

ROOT = Path(r"E:\Emulators\RomHacking\Dragon Quest")
DQ7 = ROOT / "Dragon Quest VII/3DS/source/romfs"
DQ8 = ROOT / "Dragon Quest VIII/3DS/source/romfs"
J3 = ROOT / "Monsters Joker 3/source/romfs"


def make_fpt(entries, kind=1):
    """An FPT0 pack of ``{name: bytes}``."""
    head = b"FPT0" + struct.pack("<III", 0, len(entries), kind)
    table, body = b"", b""
    for name, data in entries.items():
        table += name.encode().ljust(16, b"\0") + struct.pack("<IIII", 0x1234, len(body), len(data), 0)
        body += data
    return head + table + bytes(128 if kind == 2 else 64) + body


@pytest.mark.parametrize("name", ["dragon_quest_vii", "dragon_quest_viii", "dq_monsters_joker3"])
def test_the_plugins_load_and_validate(name):
    check_loads(name)
    check_validator(name)


def test_fpt_messages_keep_headers_and_line_breaks():
    text = b"#3,Prince {KEAFA}\r\nRight, you know.\r\nSecond line.\r\n#9999\r\nSong \xe2\x99\xaa\nmore\r\n#5"
    pack = make_fpt({"#000004.txt": text, "#000005.txt": b"lead\r\n#2\r\nHi\r\n"})
    texts = fpt.texts(fpt.Pack(pack))
    assert texts == ["Right, you know.\nSecond line.", "Song \u266a{LF}more", "", "Hi"]
    assert fpt.rebuild(fpt.Pack(pack), texts) == pack
    texts[0] = "UA TEST\nlonger text"
    again = fpt.Pack(fpt.rebuild(fpt.Pack(pack), texts))
    assert fpt.texts(again) == texts
    assert again.data["#000004.txt"].startswith(b"#3,Prince {KEAFA}\r\nUA TEST\r\nlonger text\r\n#9999")
    rules = load_rules("dragon_quest_vii")
    blocks, _ = rules.load_data_from_json_obj(pack)
    assert blocks == [["Right, you know.\nSecond line.", "Song \u266a{LF}more", "", "Hi"]]
    assert rules.save_data_to_json_obj(blocks, {}) == pack


def test_fpt_texture_pack_container():
    pack = make_fpt({"tex000.dmp": b"DMP\x03" + b"8888" + bytes(8) + bytes(16), "size.dat": b"64,64\r\n"}, kind=2)
    container = fpt.FptContainer(pack)
    assert container.list_files() == ["tex000.dmp", "size.dat"]
    assert container.pack() == pack
    container.write_file("size.dat", b"128,128\r\n")
    assert fpt.FptContainer(container.pack()).read_file("size.dat") == b"128,128\r\n"


def test_menu_lines_round_trip():
    raw = b"#1,,Fight,,,,,,,\r\n#2,,Tactics,,,,,,,\r\n"
    lines, trailing = dq7_rules.menu_lines(raw)
    assert lines == ["#1,,Fight,,,,,,,", "#2,,Tactics,,,,,,,"] and trailing
    assert dq7_rules.menu_build(raw, lines) == raw


def test_dmp_texture_reads_and_writes():
    from PIL import Image
    data = b"DMP\x03" + b"8888" + struct.pack("<HHHH", 6, 5, 8, 8) + bytes(8 * 8 * 4)
    texture = dmp.read(data, {})[0]
    assert texture.image.size == (6, 5) and texture.pixel_format == "RGBA8"
    image = Image.new("RGBA", (6, 5), (255, 0, 0, 255))
    out = dmp.write(data, {0: image}, {})
    assert len(out) == len(data) and dmp.read(out, {})[0].image.getpixel((0, 0)) == (255, 0, 0, 255)


def test_darc_lists_members_and_repacks():
    names = ".\0blyt\0a.bclyt\0font\0b.bcfnt\0".encode("utf-16-le")
    table = struct.pack("<III", 0x01000000, 0, 5)                 # "." root directory, 5 entries
    table += struct.pack("<III", 0x01000000 | 4, 0, 3) + struct.pack("<III", 14, 0x100, 4)    # blyt/a.bclyt
    table += struct.pack("<III", 0x01000000 | 30, 0, 5) + struct.pack("<III", 40, 0x110, 4)   # font/b.bcfnt
    table_len = len(table) + len(names)
    data = b"darc" + struct.pack("<HHIIIII", 0xFEFF, 0x1C, 0x01000000, 0x120, 0x1C, table_len, 0x100)
    data += table + names
    data += bytes(0x100 - len(data)) + b"LYT!" + bytes(12) + b"FNT!" + bytes(12)
    assert len(data) == 0x120
    archive = DarcContainer(data)
    assert archive.list_files() == ["blyt/a.bclyt", "font/b.bcfnt"]
    assert archive.read_file("font/b.bcfnt") == b"FNT!" and archive.pack() == data
    archive.write_file("font/b.bcfnt", b"FONT-LONGER")
    again = DarcContainer(archive.pack())
    assert again.read_file("font/b.bcfnt") == b"FONT-LONGER" and again.read_file("blyt/a.bclyt") == b"LYT!"


def test_bine_table_grows_and_keeps_ids():
    raw = struct.pack("<II", 2, 3) + struct.pack("<3I", 10, 11, 12) + struct.pack("<2I", 2, 1)
    offsets = 8 + 12 + 8 + 12
    texts = [b"None[end]", b"Attack[end]", b"Frizz[end]"]
    raw += struct.pack("<3I", offsets, offsets + 9, offsets + 20) + b"".join(texts)
    table = bine.Table(raw)
    assert table.texts() == ["None", "Attack", "Frizz"] and table.ids == [10, 11, 12]
    assert table.build(table.texts()) == raw
    again = bine.Table(table.build(["None", "Attack UA TEST", "Frizz"]))
    assert again.texts()[1] == "Attack UA TEST" and again.ids == [10, 11, 12]
    assert bine.Table(b"").texts() == [] and bine.Table(b"").build([]) == b""


def test_mes_table_keeps_labels_and_control_codes():
    def entry(label, text_off):
        name = label.encode() + b"\0"
        return struct.pack("<I", text_off) + name + bytes(-len(name) % 4)
    entries_at = 4 + 2 * 8
    e0 = entry("I0000", 0)
    e1 = entry("I0001", 0)
    text_at = entries_at + len(e0) + len(e1)
    t0 = "Herb\x01x".encode("utf-16-le") + b"\0\0"
    t0 += bytes(-len(t0) % 4)
    t1 = "Stone".encode("utf-16-le") + b"\0\0"
    raw = struct.pack("<I", 2) + struct.pack("<II", 1, entries_at) + struct.pack("<II", 1, entries_at + len(e0))
    raw += entry("I0000", text_at) + entry("I0001", text_at + len(t0)) + t0 + t1
    table = mes.Table(raw)
    assert table.labels == ["I0000", "I0001"] and table.texts() == ["Herb\x01x", "Stone"]
    assert table.build(table.texts()) == raw
    rules = load_rules("dq_monsters_joker3")
    blocks, _ = rules.load_data_from_json_obj(raw)
    assert blocks == [["Herb{01}x", "Stone"]]
    assert rules.save_data_to_json_obj(blocks, {}) == raw
    blocks[0][1] = "Stone UA TEST"
    assert mes.Table(rules.save_data_to_json_obj(blocks, {})).texts() == ["Herb\x01x", "Stone UA TEST"]


def test_nut_quoted_strings_round_trip():
    raw = b'// credits\r\nlocal a = "MONSTERS CAST";\r\nx("say \\"hi\\"", 3);\r\n'
    strings = j3_rules.nut_strings(raw)
    assert strings == ["MONSTERS CAST", 'say \\"hi\\"']
    assert j3_rules.nut_build(raw, strings) == raw
    assert j3_rules.nut_build(raw, ["UA TEST", strings[1]]).startswith(b'// credits\r\nlocal a = "UA TEST";')


@pytest.mark.skipif(not DQ7.is_dir(), reason="the unpacked game is not on this machine")
def test_every_real_dq7_pack_rebuilds_byte_for_byte():
    packs = sorted((DQ7 / "MESS/EN").glob("*.fpt"))
    assert len(packs) > 300
    messages = 0
    for path in packs:
        raw = path.read_bytes()
        texts = fpt.texts(fpt.Pack(raw))
        messages += len(texts)
        assert fpt.rebuild(fpt.Pack(raw), texts) == raw, path.name
    assert messages > 50000
    for path in list((DQ7 / "SCREENTEX").rglob("*.fpt"))[:40] + list((DQ7 / "LAYOUTTEX").glob("*.fpt")):
        raw = path.read_bytes()
        assert fpt.FptContainer(raw).pack() == raw, path.name
    for path in sorted((DQ7 / "LAYOUT").glob("*.arc")):
        raw = path.read_bytes()
        assert DarcContainer(raw).pack() == raw, path.name


@pytest.mark.skipif(not DQ8.is_dir(), reason="the unpacked game is not on this machine")
def test_every_real_dq8_table_rebuilds_byte_for_byte():
    files = sorted(DQ8.rglob("*.binE"))
    assert len(files) > 500
    texts = 0
    for path in files:
        raw = path.read_bytes()
        table = bine.Table(raw)
        texts += len(table.entries)
        assert table.build(table.texts()) == raw, path.name
    assert texts > 35000


@pytest.mark.skipif(not J3.is_dir(), reason="the unpacked game is not on this machine")
def test_every_real_joker3_table_rebuilds_byte_for_byte():
    files = sorted(J3.rglob("*.mes"))
    assert len(files) > 400
    texts = 0
    for path in files:
        raw = path.read_bytes()
        table = mes.Table(raw)
        texts += len(table.entries)
        assert table.build(table.texts()) == raw, path.name
        for text in table.texts():
            assert j3_rules.encode_text(j3_rules.decode_text(text)) == text
    assert texts > 15000
    for path in sorted(J3.glob("data/Menu/EndRoll/*.nut")):
        raw = path.read_bytes()
        assert j3_rules.nut_build(raw, j3_rules.nut_strings(raw)) == raw, path.name
