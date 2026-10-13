"""Monster Hunter Stories (Switch) plugin: GMD v2 tables (synthetic and the real game's archive when it is unpacked here)."""
import romhacking_root
import struct

import pytest

from plugins.monster_hunter_stories_nx import gmd
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "monster_hunter_stories_nx"
SOURCE = romhacking_root.under('Monster Hunter\\Stories\\Switch\\source\\romfs\\nativeNXx64\\archive\\message_R\\message_all_eng.arc\\message_R')


def make_gmd(strings, labels=None) -> bytes:
    labels = labels or [f"MSG_TEST_{i:03d}" for i in range(len(strings))]
    name = b"test_eng"
    label_area = b"".join(label.encode() + b"\0" for label in labels)
    pool = b"".join(s.encode("utf-8") + b"\0" for s in strings)
    head = struct.pack("<4sIIIIIIIII", b"GMD\0", 0x10302, 1, 0x1234, 0, len(labels), len(strings), len(label_area),
                       len(pool), len(name)) + name + b"\0"
    items, at = b"", 0
    for i, label in enumerate(labels):
        items += struct.pack("<IIIIQQ", i, 0xAAAA0000 + i, 0xBBBB0000 + i, 0xCDCDCDCD, at, 0)
        at += len(label) + 1
    return head + items + bytes(0x800) + label_area + pool


SAMPLE = make_gmd(["<COL F00000FF>Rathalos<COL>\r\nlives here.<PAGE>Go on!", "Hero", ""])


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert ".gmd" in {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_gmd_texts_ids_and_rebuild():
    table = gmd.Table(SAMPLE)
    assert table.texts()[0].startswith("<COL F00000FF>Rathalos<COL>")
    assert table.ids() == ["MSG_TEST_000", "MSG_TEST_001", "MSG_TEST_002"]
    assert table.build(table.texts()) == SAMPLE
    changed = gmd.Table(table.build(["short", "A much longer replacement line of text", "now filled"]))
    assert changed.texts() == ["short", "A much longer replacement line of text", "now filled"]
    assert changed.ids() == table.ids()
    with pytest.raises(ValueError):
        table.build(["too few"])
    with pytest.raises(ValueError):
        gmd.Table(SAMPLE[:-3])


def test_markup_is_tags():
    from plugins.monster_hunter_stories_nx.tag_manager import TAG_RE
    assert TAG_RE.findall("<COL F00000FF>Rathalos<COL> <SPNM NAVI>: <PAGE>") == [
        "<COL F00000FF>", "<COL>", "<SPNM NAVI>", "<PAGE>"]


@pytest.mark.skipif(not SOURCE.is_dir(), reason="Monster Hunter Stories (Switch) is not unpacked here")
def test_every_english_table_of_the_game_round_trips_byte_for_byte():
    files = sorted(SOURCE.rglob("*.gmd"))
    assert len(files) >= 600
    total = 0
    for path in files:
        raw = path.read_bytes()
        table = gmd.Table(raw)
        assert table.build(table.texts()) == raw, path
        total += len(table.texts())
    assert total > 36000


def make_tex(width=16, height=16, fmt=7, total=1024) -> bytes:
    """A Switch TEX with one mip level (RGBA8) whose data is zeros (a block-linear surface of ``total`` bytes)."""
    head = b"TEX\0" + struct.pack("<III", 0x2000B0A3, 1 | width << 6 | height << 19, 0x10001 | fmt << 8)
    return head + struct.pack("<II", total, 0) + bytes(total)


def make_gfd() -> bytes:
    name = b"gui\font\test"
    head = struct.pack("<10I", 0x00444647, 0x21108, 8, 3, 0, 50, 1, 2, 0, 1) + struct.pack("<5f", 57, 65, 50.75, 14.25, 14.25)
    head += struct.pack("<I", len(name)) + name + b"\0"
    rec = struct.pack("<I6fII", 0x41, 6.0, 8.0, 0.5, 7.0, 7.5, 10.0, 0 | 0 << 8 | 0 << 20, 0xFFFF1400)
    rec += struct.pack("<I6fII", 0x42, 5.0, 8.0, 0.5, 7.0, 6.5, 10.0, 0 | 8 << 8 | 0 << 20, 0xFFFF1400)
    return head + rec


def test_switch_tex_reads_and_writes_in_place():
    from core import texture_formats
    data = make_tex()
    textures = texture_formats.read("mt_tex", data, {})
    assert textures[0].image.size == (16, 16)
    assert texture_formats.write("mt_tex", data, {0: textures[0].image}, {}) == data
    painted = textures[0].image.copy()
    painted.paste((10, 200, 30, 255), (0, 0, 5, 5))
    changed = texture_formats.write("mt_tex", data, {0: painted}, {})
    assert changed != data and len(changed) == len(data)
    assert texture_formats.read("mt_tex", changed, {})[0].image.getpixel((2, 2))[:3] == (10, 200, 30)


def test_switch_gfd_font_model_and_pack():
    from core import font_formats
    from core.font_formats.sources import join_pair
    data = join_pair(make_gfd(), make_tex())
    metadata, sheets = font_formats.extract("mt_font", data, {"page": 0})
    assert [p["width"] for p in metadata["WID1"][0]["packets"][:2]] == [8, 6]      # round(7.5), round(6.5): 8 and 6
    assert font_formats.pack("mt_font", metadata, sheets, data, {"page": 0}) == data
    sheet = sheets[0].convert("RGBA")
    sheet.paste((255, 255, 255, 255), (0, 0, 3, 3))
    edited = font_formats.pack("mt_font", metadata, [sheet], data, {"page": 0})
    assert edited != data and len(edited) == len(data)
    assert font_formats.extract("mt_font", edited, {"page": 0})[1][0].convert("L").getpixel((1, 1)) == 255
