"""Xenoblade Chronicles (Wii / 3DS) plugin: big-endian legacy BDAT tables (a hand-made file: read, unchanged =
same bytes, a longer text, hidden tables), the Nintendo Huffman codec of the RFNA fonts, and the real
workspace files when they are unpacked here."""
import random
import struct
from pathlib import Path

import pytest

from core import font_formats
from core.font_formats import bcfnt
from core.formats import SaveContext
from plugins.common import bdat_wii
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "xenoblade_wii"
SOURCE = Path(r"E:\Emulators\RomHacking\Xenoblade\Chronicles\Wii\source")
real = pytest.mark.skipif(not (SOURCE / "bdat" / "bdat_common.bin").exists(), reason="Xenoblade Wii not unpacked here")


def table(name: str, columns: list, rows: list, e: str = ">") -> bytes:
    """A scrambled table: ``columns`` = (name, value type), ``rows`` = lists of cell values (str or int)."""
    infos = b"".join(struct.pack(e + "BBH", 1, kind, 4 * i) for i, (_n, kind) in enumerate(columns))
    names_off = 0x20 + len(infos)
    names = bytearray(name.encode() + b"\0")
    names += bytes(len(names) % 2)
    for i, (cname, _k) in enumerate(columns):
        names += struct.pack(e + "HH", 0x20 + 4 * i, 0) + cname.encode() + b"\0"
        names += bytes(len(names) % 2)
    hash_off = names_off + len(names)
    rows_off = (hash_off + 2 + 15) & ~15
    row_len = 4 * len(columns)
    str_off = (rows_off + row_len * len(rows) + 15) & ~15
    body = bytearray(str_off)
    strings, where = bytearray(), {}
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            at = rows_off + r * row_len + 4 * c
            if columns[c][1] == bdat_wii.STRING:
                if value and value not in where:
                    where[value] = str_off + len(strings)
                    strings += value.encode("utf-8") + b"\0"
                    strings += bytes(len(strings) % 2)
                struct.pack_into(e + "I", body, at, where[value] if value else 0)
            else:
                struct.pack_into(e + "I", body, at, value)
    strings += bytes(-(str_off + len(strings)) % 16)
    body[0x20:0x20 + len(infos)] = infos
    body[names_off:hash_off] = names
    struct.pack_into(e + "4sBBHHHHHHHHHII", body, 0, b"BDAT", 3, 0, names_off, row_len, hash_off, 1, rows_off,
                     len(rows), 1, 2, 0, str_off, len(strings))
    plain = bytes(body) + bytes(strings)
    checksum = bdat_wii.checksum_of(plain)
    out = bytearray(plain)
    struct.pack_into(e + "H", out, 0x16, checksum)
    out[names_off:hash_off] = bdat_wii._scramble(plain[names_off:hash_off], checksum)
    out[str_off:] = bdat_wii._scramble(plain[str_off:], checksum)
    return bytes(out)


def bdat_file(*tables: bytes, e: str = ">") -> bytes:
    head = 8 + 4 * len(tables)
    offsets, at = [], head
    for part in tables:
        offsets.append(at)
        at += len(part)
    return struct.pack(e + "II", len(tables), at) + struct.pack(f"{e}{len(tables)}I", *offsets) + b"".join(tables)


SAMPLE = bdat_file(
    table("MNU_sysmes", [("name", bdat_wii.STRING), ("help", bdat_wii.STRING)],
          [["Obtained Items", ""], ["Yes", "Confirm the choice.@Second line"]]),
    table("BTL_growlist", [("value", 3)], [[7], [9]]),
    table("FLD_npclist", [("name", bdat_wii.STRING), ("resource", bdat_wii.STRING)], [["Reyn", "pc02"]]))


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".bdat", ".bin", ".csv"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_tables_read_write_and_hide_the_ones_without_text():
    assert bdat_wii.endian_of(SAMPLE) == ">"
    assert bdat_wii.read(SAMPLE) == [("MNU_sysmes", ["Obtained Items", "", "Yes", "Confirm the choice.@Second line"]),
                                     ("BTL_growlist", []), ("FLD_npclist", ["Reyn"])]
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert names == {"0": "MNU_sysmes", "1": "FLD_npclist"} and blocks[1] == ["Reyn"]
    rules.prepare_save_context(SaveContext(relative_path="bdat/x.bdat", existing_versions=lambda: iter([SAMPLE])))
    assert rules.save_data_to_json_obj(blocks, names) == SAMPLE
    blocks[0][0] = "Отримані речі, Їжак та Ґанок " * 3
    blocks[1][0] = "Райн"
    saved = rules.save_data_to_json_obj(blocks, names)
    again, _names = rules.load_data_from_json_obj(saved)
    assert again == blocks
    spans = bdat_wii._tables(saved, ">")
    assert saved[spans[1][0]:spans[1][1]] == SAMPLE[bdat_wii._tables(SAMPLE, ">")[1][0]:bdat_wii._tables(SAMPLE, ">")[1][1]]
    assert bdat_wii.read(saved)[2] == ("FLD_npclist", ["Райн"])           # the resource column stays, unlisted
    assert struct.unpack_from(">I", saved, 4)[0] == len(saved)


def test_a_little_endian_file_is_the_3ds_layout():
    little = bdat_file(table("MNU_sysmes", [("name", bdat_wii.STRING)], [["Yes"]], e="<"), e="<")
    assert bdat_wii.endian_of(little) == "<" and bdat_wii.read(little) == [("MNU_sysmes", ["Yes"])]
    assert bdat_wii.write(little, [["Так"]]) != little and bdat_wii.read(bdat_wii.write(little, [["Так"]])) == [("MNU_sysmes", ["Так"])]


def test_huffman_4_bit_streams_decode_to_their_input():
    rng = random.Random(7)
    for _ in range(10):
        raw = bytes(rng.choice([0, 0, 0x11, 0xFF, rng.randrange(256)]) for _ in range(rng.randrange(1, 700)))
        stream = bcfnt.huffman_encode4(raw)
        assert stream[0] == 0x24 and bcfnt.huffman_decode(stream) == raw
    assert bcfnt.huffman_decode(bcfnt.huffman_encode4(b"\0" * 64)) == b"\0" * 64


@real
def test_the_real_tables_and_fonts_round_trip():
    rules = load_rules(PLUGIN)
    total = 0
    for path in sorted(SOURCE.glob("bdat/**/*.b*")):
        raw = path.read_bytes()
        blocks, names = rules.load_data_from_json_obj(raw)
        rules.prepare_save_context(SaveContext(relative_path=path.name, existing_versions=lambda r=raw: iter([r])))
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
        total += sum(len(b) for b in blocks)
    assert total > 38000
    font = (SOURCE / "font" / "00_0000.brfna").read_bytes()
    assert font_formats.detect(font) == "brfnt"
    meta, sheets = font_formats.extract("brfnt", font)
    assert font_formats.pack("brfnt", meta, sheets, font) == font
    plain, glgr = bcfnt.rfna_to_rfnt(font)
    again = bcfnt.rfnt_to_rfna(plain, glgr)
    assert again[:4] == b"RFNA" and bcfnt.rfna_to_rfnt(again)[0] == plain
