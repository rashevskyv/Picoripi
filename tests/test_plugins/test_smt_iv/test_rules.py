"""Shin Megami Tensei IV plugin: MSG2 tables and executable strings (synthetic and the real games)."""
import romhacking_root
import struct

import pytest

from core.font_formats import sjis
from plugins.smt_iv import codebin, dlcinfo, mbm, tbb
from plugins.testing import check_loads, check_validator, load_rules

PLUGIN = "smt_iv"
GAMES = [romhacking_root.under('Shin Megami Tensei\\IV\\source'),
         romhacking_root.under('Shin Megami Tensei\\IV Apocalypse\\source')]
SJR = romhacking_root.under('Shin Megami Tensei\\Strange Journey Redux\\source')


def make_table(entries, gap=b"\xAA" * 12, tail=b"\0" * 8):
    """An MSG2 table of raw strings (``b""`` = empty entry), with bytes between the table and the strings."""
    table = b""
    strings = b""
    at = 0x20 + len(entries) * 16 + len(gap)
    for i, raw in enumerate(entries):
        table += struct.pack("<4I", i, len(raw), at + len(strings) if raw else 0, 0)
        strings += raw
    body = table + gap + strings
    return bytes(4) + b"MSG2" + struct.pack("<4I", 0x10000, 0x20 + len(table) + len(strings), len(entries), 0x20) + bytes(8) + body + tail


HELLO = bytes.fromhex("82 67 82 85 82 8c 82 8c 82 8f f8 01 82 60 f8 7a 01 00 ff ff")   # Hello␤A{F87A 0001}
SAMPLE = make_table([HELLO, b"", bytes.fromhex("82 78 82 85 82 93 ff ff")])


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_decode_shows_ascii_newlines_and_tags():
    assert mbm.decode(HELLO) == "Hello\nA{F87A 0001}"
    assert mbm.encode("Hello\nA{F87A 0001}") == HELLO
    assert mbm.encode("") == b"\xff\xff"


def test_ukrainian_letters_take_the_free_shift_jis_codes():
    text = "Ґалка і їжак"
    raw = mbm.encode(text)
    assert raw[:2] == bytes.fromhex("8492") and mbm.decode(raw) == text
    assert sjis.decode(sjis.encode("ї")) == "ї"
    assert sjis.encode("A") == 0x41 and sjis.decode(0x8260) == "Ａ"


def test_table_rebuilds_byte_for_byte_and_grows():
    table = mbm.Table(SAMPLE)
    texts = table.texts()
    assert texts == ["Hello\nA{F87A 0001}", "", "Yes"]
    assert table.build(texts) == SAMPLE
    texts[2] = "Yes, a longer answer"
    again = mbm.Table(table.build(texts))
    assert again.texts() == texts
    assert struct.unpack_from("<I", again.raw, 0x0C)[0] == struct.unpack_from("<I", SAMPLE, 0x0C)[0] + 34


def test_executable_strings_are_edited_in_place():
    code = b"\0" * 16 + bytes.fromhex("82 60 82 87 82 89") + b"\0\0" + bytes.fromhex("82 62 82 85 82 8c") + b"\0" * 10
    assert codebin.texts(code) == ["Agi", "Cel"]
    out = codebin.build(code, ["Ag", "Cel"])
    assert len(out) == len(code) and codebin.texts(out) == ["Ag", "Cel"]
    with pytest.raises(codebin.FormatError):
        codebin.build(code, ["Agilao", "Cel"])


def test_plugin_load_and_save_round_trip():
    rules = load_rules(PLUGIN)
    blocks, _names = rules.load_data_from_json_obj(SAMPLE)
    assert blocks == [["Hello\nA{F87A 0001}", "", "Yes"]]
    assert rules.save_data_to_json_obj(blocks, {}) == SAMPLE


@pytest.mark.parametrize("root", GAMES, ids=["smt4", "apocalypse"])
def test_every_real_table_rebuilds_byte_for_byte(root):
    if not root.is_dir():
        pytest.skip("the unpacked game is not on this machine")
    files = sorted(root.glob("**/*.mbm"))
    assert len(files) > 1000
    for path in files:
        raw = path.read_bytes()
        table = mbm.Table(raw)
        texts = table.texts()
        assert table.build(texts) == raw, path.name
        for entry, text in zip(table.entries, texts):
            assert mbm.encode(text) == entry or (text == "" and entry == b""), (path.name, text)
    code = (root / "exefs" / "code.bin").read_bytes()
    texts = codebin.texts(code)
    assert len(texts) > 500 and codebin.build(code, texts) == code



# -- Strange Journey Redux: TBB1 / FBIN containers, 0000-terminated strings, DLC info -----------------------------

def sjr_entry(text: str) -> bytes:
    return mbm.encode(text, 0)


def pad16(blob: bytes) -> bytes:
    return blob.ljust((len(blob) + 15) // 16 * 16, b"\0")


def tbb1(blocks):
    start = (0x10 + 4 * len(blocks) + 15) // 16 * 16
    offsets, at = [], start
    for block in blocks:
        offsets.append(at)
        at += len(pad16(block))
    head = b"TBB1" + struct.pack("<III", 0x10, len(blocks), at) + struct.pack(f"<{len(blocks)}I", *offsets)
    return head.ljust(start, b"\0") + b"".join(pad16(b) for b in blocks)


def fbin(members):
    first = (12 + 4 * len(members) + 15) // 16 * 16
    head = b"FBIN" + struct.pack("<II", len(members), first) + struct.pack(f"<{len(members)}I", *[len(m) for m in members])
    return head.ljust(first, b"\0") + b"".join(members)


SJR_A = make_table([sjr_entry("Medicine"), b"", sjr_entry("Life Stone\n")])
SJR_B = make_table([sjr_entry("Page {F802}")])


def test_sjr_strings_end_with_0000_and_round_trip():
    table = mbm.Table(SJR_A)
    assert table.terminator == 0
    assert table.texts() == ["Medicine", "", "Life Stone\n"]
    assert table.build(table.texts()) == SJR_A
    assert mbm.Table(SAMPLE).terminator == 0xFFFF   # SMT IV keeps FFFF


def test_tbb1_and_fbin_bundles_rebuild_and_grow():
    raw = fbin([tbb1([SJR_A, SJR_B]), tbb1([SJR_B])])
    bundle = tbb.Bundle(raw)
    assert len(bundle.tables) == 3
    assert bundle.texts() == ["Medicine", "", "Life Stone\n", "Page {F802}", "Page {F802}"]
    assert bundle.ids[0] == (0, 0) and bundle.ids[-1] == (2, 0)
    assert bundle.build(bundle.texts()) == raw
    assert tbb._lay_out(bundle.root, bundle.texts(), [0]) == raw
    edited = bundle.texts()
    edited[1] = "A new line"
    again = tbb.Bundle(bundle.build(edited))
    assert again.texts() == edited
    assert len(tbb.Bundle(tbb1([SJR_A])).ids) == 3 and tbb.Bundle(SAMPLE).ids == [0, 1, 2]


def test_content_info_archive_fields():
    def entry(title, desc):
        return title.ljust(0x40, b"\0") + desc.ljust(0x88, b"\0")
    raw = struct.pack("<II", 1, 2) + entry(b"DummyTitle", b"DummyDescription") + entry(b"Training Day", b"") + entry(b"Macca Rain", b"")
    assert dlcinfo.is_info(raw) and dlcinfo.texts(raw)[2:4] == ["Training Day", ""]
    out = dlcinfo.build(raw, [t if t != "Macca Rain" else "UA TEST" for t in dlcinfo.texts(raw)])
    assert len(out) == len(raw) and dlcinfo.texts(out)[4] == "UA TEST"
    with pytest.raises(mbm.FormatError):
        dlcinfo.build(raw, ["x" * 64 if i == 0 else t for i, t in enumerate(dlcinfo.texts(raw))])


def test_plugin_loads_a_bundle_and_saves_it_back():
    rules = load_rules(PLUGIN)
    raw = fbin([tbb1([SJR_A, SJR_B])])
    blocks, _names = rules.load_data_from_json_obj(raw)
    assert blocks == [["Medicine", "", "Life Stone\n", "Page {F802}"]]
    assert rules.save_data_to_json_obj(blocks, {}) == raw


def test_every_real_sjr_text_file_rebuilds_byte_for_byte():
    if not SJR.is_dir():
        pytest.skip("the unpacked game is not on this machine")
    files = sorted(SJR.glob("romfs/**/*.mbm")) + sorted(SJR.glob("romfs/Event/EventMessage*.bin"))
    assert len(files) == 134
    total = 0
    for path in files:
        raw = path.read_bytes()
        bundle = tbb.Bundle(raw)
        texts = bundle.texts()
        total += len(texts)
        assert bundle.build(texts) == raw, path.name
        assert tbb._lay_out(bundle.root, texts, [0]) == raw, path.name   # the layout rules give the same bytes
        for table in bundle.tables:
            for entry in table.entries:
                if entry:
                    assert mbm.encode(mbm.decode(entry, table.terminator), table.terminator) == entry, path.name
    assert total > 30000
