"""sh23ds build of the Silent Hill 2 Ukrainian translation: messages, MSG1 layout, LA4 tiles, font records, the tree.

All inputs are synthetic (built here), so no game data is needed.
"""
import struct

import numpy as np
import pytest
from PIL import Image

from plugins.silent_hill2_switch import sh23ds
from plugins.silent_hill2_switch.rules import GameRules


def _mes(*messages):
    """A message file in the packer's layout: the count word, one offset word per message, then the messages."""
    padded = [m + b"\0" if len(m) % 2 else m for m in messages]
    count = len(padded)
    position = 2 + 2 * count
    offsets = []
    for m in padded:
        offsets.append(position // 2)
        position += len(m)
    return struct.pack(f"<H{count}H", count, *offsets) + b"".join(padded)


def test_message_text_follows_the_packer_rules():
    # 6D CC: two cells; FF FD: line break; 21: a cell; 0E: a dot; FF FF: end of page; then the end marker 00 90
    page_one = bytes([0x6D, 0xCC, 0xFF, 0xFD, 0x21, 0x0E, 0xFF, 0xFF, 0x00, 0x90])
    # FF E1 inserted value 2; FF F6 yes/no marker; the 00 pad is skipped: a second page starts on a 16-bit boundary
    values = bytes([0x41, 0xFF, 0xE1, 0x42, 0xFF, 0xF6, 0x43, 0xFF, 0xFF, 0x00, 0x44, 0xFF, 0xFF])
    texts = sh23ds.load_texts(_mes(page_one, values))
    assert texts == ["\x8d\xec\nA.", "a\x02b\x05c\fd"]


def test_control_word_at_the_start_is_skipped():
    texts = sh23ds.load_texts(_mes(bytes([0x00, 0x80, 0x6D, 0xFF, 0xFF])))
    assert texts == ["\x8d"]


def test_strip_keeps_cells_that_look_like_spaces():
    # 0x65 is the cell chr(0x85) and 0x60 is chr(0x80): Python's str.strip() would drop them, the cells must stay
    texts = sh23ds.load_texts(_mes(bytes([0x65, 0xFF, 0xFF]), bytes([0x60, 0xFF, 0xFF])))
    assert texts == ["\x85", "\x80"]


def test_count_zero_is_an_empty_file_and_bad_table_is_refused():
    assert sh23ds.load_texts(b"\x00\x00") == []
    with pytest.raises(ValueError):
        sh23ds.load_texts(b"\x05\x00\x04\x00")


def test_msg_file_is_msg1_with_nul_terminated_latin1():
    data = sh23ds.msg_file(["AB\n", "\x8d"])
    assert data[:4] == b"MSG1"
    count, first, second = struct.unpack_from("<III", data, 4)
    assert count == 2
    assert data[first:second] == b"AB\n\0"
    assert data[second:] == b"\x8d\0"


def test_la4_texels_use_the_3ds_tile_order_and_luminance_rule():
    alpha = np.zeros((8, 8), np.uint8)
    alpha[0, 0] = 0xFF   # texel (u 0, row 0): index 0 in the tile
    alpha[0, 1] = 0x30   # (u 1, row 0): index 1
    alpha[1, 0] = 0x70   # (u 0, row 1): index 2
    alpha[0, 2] = 0x20   # (u 2, row 0): index 4
    texels = sh23ds.la4_levels(alpha)
    assert texels[0] == 0xFF
    assert texels[1] == 0xF3
    assert texels[2] == 0xF7
    assert texels[4] == 0xF2
    assert texels[3] == 0x00            # transparent texel: no luminance
    assert len(texels) == 64


def test_t3x_has_the_tex3ds_header_and_size_word():
    alpha = np.full((8, 8), 0x80, np.uint8)
    data = sh23ds.t3x_la4(alpha)
    count, dims, fmt, mips = struct.unpack_from("<HBBB", data, 0)
    assert (count, dims, fmt, mips) == (1, 0, 0x09, 0)
    width, height, left, top, right, bottom = struct.unpack_from("<HH4H", data, 5)
    assert (width, height, left, top, right, bottom) == (8, 8, 0, 1024, 1024, 0)
    assert data[17:21] == bytes([0, 64, 0, 0])
    assert len(data) == 21 + 64


def _tga(path, width, rows_ink):
    """A 44-wide cell atlas with the given ink pixels per cell code: {code: [(col, row), ...]}."""
    img = np.zeros((64 * 3, width, 4), np.uint8)
    for code, pixels in rows_ink.items():
        col, row = code % 100, code // 100
        for x, y in pixels:
            img[row * 64 + y, col * 44 + x] = (255, 255, 255, 255)
    Image.fromarray(img, "RGBA").save(path)


def _widths(path, table):
    values = [0] * 224
    for code, width in table.items():
        values[code] = width
    path.write_bytes(struct.pack("<224H", *values))


def _font_dir(tmp_path, ink, widths):
    font = tmp_path / sh23ds.FONT_SOURCE
    font.mkdir(parents=True)
    _tga(font / sh23ds.TGA_NAME, 4400, ink)
    _widths(font / sh23ds.WIDTH_NAME, widths)
    return tmp_path


def test_font_records_follow_the_pc_width_and_the_3ds_scale(tmp_path):
    ink = {1: [(5, y) for y in range(10, 40)] + [(6, 20)], 2: [(10, 2), (20, 60)]}
    _font_dir(tmp_path, ink, {1: 7, 2: 0})
    font_bin, alpha = sh23ds.font_pack(str(tmp_path))
    assert font_bin[:4] == b"FNT1"
    assert struct.unpack_from("<H", font_bin, 4)[0] == 2
    cw, ch, count = struct.unpack_from("<HHH", font_bin, 6)
    assert (cw, ch, count) == (20, 30, 224)
    records = {}
    pos = 12
    for index in range(count):
        records[index] = struct.unpack_from("<HHHBBBB", font_bin, pos)
        pos += 10
    code, x, y, w, h, advance, _ = records[1]
    assert code == 1 and (x, y) == (0, 0)
    assert (w, h) == (round(7 * sh23ds.PC_TO_3DS[0]), round(30 * sh23ds.PC_TO_3DS[1]))
    assert advance == 9
    assert records[0][5] == sh23ds.SPACE_ADVANCE
    # code 2 has ink and a 0 width in the table: the ink width (11 atlas px, 4 PC units) is used
    assert records[2][3:6] == (3, 14, 6)
    assert alpha.shape[1] == sh23ds.ATLAS_WIDTH and alpha.shape[0] >= 64


def test_build_writes_the_overlay_tree(tmp_path):
    source = tmp_path / "source"
    message_dir = source / "data" / "etc" / "message"
    message_dir.mkdir(parents=True)
    (message_dir / "common_msg_e.mes").write_bytes(_mes(bytes([0x6D, 0xFF, 0xFF])))
    _font_dir(source, {1: [(5, 5)]}, {1: 5})
    out = tmp_path / "out"
    out.mkdir()
    root = sh23ds.build(str(source), str(out), lambda p, t: None, lambda: False)
    assert root == str(out / "3ds" / "sh23ds")
    assert (out / "3ds" / "sh23ds" / "events" / "common.msg").read_bytes()[:4] == b"MSG1"
    assert (out / "3ds" / "sh23ds" / "ui" / "font.bin").read_bytes()[:4] == b"FNT1"
    assert (out / "3ds" / "sh23ds" / "ui" / "font.t3x").read_bytes()[:2] == b"\x01\x00"
    assert not (out / "3ds" / "sh23ds" / "events" / "s17.msg").exists()


def test_build_refuses_a_translation_without_the_font_or_messages(tmp_path):
    with pytest.raises(ValueError):
        sh23ds.build(str(tmp_path), str(tmp_path / "no_messages"), lambda p, t: None, lambda: False)
    message_dir = tmp_path / "data" / "etc" / "message"
    message_dir.mkdir(parents=True)
    (message_dir / "common_msg_e.mes").write_bytes(_mes(bytes([0x6D, 0xFF, 0xFF])))
    with pytest.raises(ValueError):
        sh23ds.build(str(tmp_path), str(tmp_path / "no_font"), lambda p, t: None, lambda: False)


def test_stage_message_names_map_to_the_packer_file_names():
    jobs = dict(sh23ds.message_jobs())
    assert jobs["s17.msg"] == "stage_heaven_night_msg_e.mes"
    assert jobs["s49.msg"] == "stage_end_maria_msg_e.mes"
    assert jobs["s58.msg"] == "stage_x_apart_msg_e.mes"
    assert jobs["memo.msg"] == "memo_x_msg_e.mes"
    assert jobs["s01.msg"] == "stage_tgs_trial_msg_e.mes"
    assert "s00.msg" not in jobs              # stage 0 is Stg_null: no stage, no file


def test_sh23ds_is_a_files_target_for_3ds():
    targets = GameRules().get_build_targets()
    assert [(t["id"], t["platforms"], t["kind"]) for t in targets] == [("sh23ds", ["3ds"], "files")]
