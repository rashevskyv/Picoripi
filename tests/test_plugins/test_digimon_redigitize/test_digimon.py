"""Digimon World: Re:Digitize Decode plugin: KCAP / BTX text containers on synthetic data, then on the real game files
(skipped where the workspace is not on this machine)."""
import json
import struct
from pathlib import Path

import pytest

from plugins.digimon_redigitize.btxt import DigiText, FormatError, decode, encode
from plugins.digimon_redigitize.rules import GameRules


def _btx(strings, header=0x10, prefixed=False, tail=b"", short=()):
    """A BTX table; the offsets count from their own pair; strings listed in ``short`` end with one NUL unit,
    the others with two. ``prefixed``: the story-text item with a size field before the table."""
    heap, offsets, pos = b"", [], 8 * len(strings)
    for i, text in enumerate(strings):
        piece = text.encode("utf-16-le") + bytes(2 if i in short else 4)
        offsets.append(pos - 8 * i)
        heap += piece
        pos += len(piece)
    head = b"BTX " + struct.pack("<II", 1, header) + bytes(header - 12) + struct.pack("<II", 1, len(strings))
    table = b"".join(struct.pack("<II", 100 * (i + 1), off) for i, off in enumerate(offsets))
    body = head + table + heap
    if prefixed:
        body = struct.pack("<I", len(body) + 4) + body
    return body + tail


def _kcap(items):
    """A KCAP of raw items: items back to back at multiples of 0x10, the size table behind the header."""
    n = len(items)
    first = (0x24 + 8 * n - 4 + 0xF) & ~0xF
    offs, pos = [], first
    for item in items:
        offs.append(pos)
        pos = (pos + len(item) + 0xF) & ~0xF
    total = offs[-1] + len(items[-1])
    head = bytearray(first)
    head[:4] = b"KCAP"
    struct.pack_into("<IIIIIII", head, 4, 1, total, 0x10000, n, 0, 0x20, 0)
    struct.pack_into("<I", head, 0x20, first)
    for i, item in enumerate(items):
        struct.pack_into("<I", head, 0x24 + 8 * i, len(item))
        if i + 1 < n:
            struct.pack_into("<I", head, 0x28 + 8 * i, offs[i + 1])
    out = bytearray(head)
    for off, item in zip(offs, items):
        out += bytes(off - len(out)) + item
    return bytes(out)


def test_text_codec():
    assert decode("Hi\n{c:0001}!".encode("utf-16-le")) == "Hi\n{c:0001}!"
    text = "Line\nFull-width！{c:0003}"
    assert decode(encode(text)) == text


def test_reads_blocks_of_both_kinds_and_round_trips():
    inner = _kcap([_btx(["One", "Two"]), b"RAW-DATA!", _btx(["Story line"], header=0x0C, prefixed=True, tail=bytes(20))])
    data = _kcap([b"head-item", inner, _btx(["Last"])])
    f = DigiText(data)
    assert f.strings == [["One", "Two"], ["Story line"], ["Last"]]
    assert [b.prefixed for b in f.blocks] == [False, True, False] and all(f.exact)
    assert f.build(f.strings) == data


def test_offsets_follow_a_string_that_changes_its_length():
    data = _kcap([_btx(["One", "Two", "Three", "Four"], short={1, 3})])
    f = DigiText(data)
    assert f.strings == [["One", "Two", "Three", "Four"]]
    out = f.build([["One", "Twenty-two", "Three", "Four"]])           # grows: the later pairs move their offsets
    g = DigiText(out)
    assert g.strings == [["One", "Twenty-two", "Three", "Four"]]
    # the gap of every string (one or two NUL units) is kept
    assert [len(x) for x in g.blocks[0].gaps] == [4, 2, 4, 2]
    shorter = g.build([["One", "Two", "Three", "Four"]])
    assert shorter == data


def test_same_length_edit_stays_in_place():
    data = _kcap([_btx(["One", "Two"]), _btx(["Three"])])
    f = DigiText(data)
    out = f.build([["Uno", "Two"], ["Three"]])
    assert len(out) == len(data) and DigiText(out).strings == [["Uno", "Two"], ["Three"]]


def test_growth_rebuilds_the_container_tree():
    inner = _kcap([_btx(["One", "Two"]), b"RAW-DATA!", _btx(["Story line"], header=0x0C, prefixed=True, tail=bytes(20))])
    data = _kcap([b"head-item", inner, _btx(["Last"])])
    f = DigiText(data)
    new = [["One is now much longer than before", "Two"], ["Short"], ["Last and a longer one too"]]
    out = f.build(new)
    g = DigiText(out)
    assert g.strings == new and len(out) != len(data)
    assert struct.unpack_from("<I", out, 8)[0] == len(out)
    # the item behind the grown one moved and keeps its content
    assert b"RAW-DATA!" in out and b"head-item" in out
    # the size field of the story item follows its table; the extra bytes behind it are kept
    block = g.blocks[1]
    assert struct.unpack_from("<I", out, block.item_at)[0] == block.heap_end - block.item_at
    assert DigiText(g.build(g.strings)).strings == new


def test_file_with_data_behind_the_container_keeps_lengths():
    data = _kcap([_btx(["One"])]) + b"\x01\x02" * 20
    f = DigiText(data)
    assert f.build([["Uno"]])[-40:] == b"\x01\x02" * 20
    with pytest.raises(FormatError):
        f.build([["One is longer"]])


def test_wrong_shape_is_refused():
    f = DigiText(_kcap([_btx(["One"])]))
    with pytest.raises(FormatError):
        f.build([["One", "extra"]])
    with pytest.raises(FormatError):
        DigiText(b"\0" * 64)
    with pytest.raises(FormatError):
        DigiText(_kcap([b"no text here"]))


def test_rules_load_and_save():
    data = _kcap([_btx(["Alpha", "Beta"]), _btx(["Gamma"])])
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(data)
    assert blocks == [["Alpha", "Beta"], ["Gamma"]] and names == {"0": "Table 1", "1": "Table 2"}
    assert rules.save_data_to_json_obj(blocks, {}) == data
    out = rules.save_data_to_json_obj([["Альфа"], ["Gamma"]], {})            # a missing string keeps its old text
    assert DigiText(out).strings == [["Альфа", "Beta"], ["Gamma"]]


WS = Path(r"E:\Emulators\RomHacking\Digimon World Re Digitize Decode")
SOURCE = WS / "source" / "romfs" / "ARCV"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "digimon_redigitize"


def test_real_files_round_trip_and_grow():
    if not SOURCE.exists():
        pytest.skip(f"{SOURCE} is not on this machine")
    files = sorted(SOURCE.rglob("*.btxt"))
    assert len(files) > 100
    strings = 0
    for path in files[::5]:
        raw = path.read_bytes()
        f = DigiText(raw)
        assert f.build(f.strings) == raw, path.name
        assert all(f.exact)
        strings += sum(b.count for b in f.blocks)
    assert strings > 5000
    keep = SOURCE / "Keep" / "LanguageKeep_jp.res.btxt"
    if keep.exists():
        f = DigiText(keep.read_bytes())
        new = f.strings
        new[0][0] += " (longer)"
        assert DigiText(f.build(new)).strings == new


def _gmio(kind, bits, width=16, height=8, fill=0x55):
    head = bytearray(0x80)
    head[:4] = b"GMIO"
    struct.pack_into("<I", head, 4, 6)
    struct.pack_into("<HH", head, 0x14, width, height)
    head[0x1A], head[0x1B], head[0x1E] = kind[0], kind[1], bits
    struct.pack_into("<HH", head, 0x24, width, height)
    return bytes(head) + bytes([fill]) * (width * height * bits // 8)


def test_gmio_reads_and_writes_each_pixel_format():
    from PIL import Image

    from core import texture_formats
    for kind, bits, name in (((1, 0x10), 32, "RGBA8"), ((2, 0x10), 24, "RGB8"), ((3, 0x10), 16, "RGB565"),
                             ((2, 0x11), 8, "L8")):
        data = _gmio(kind, bits)
        texture = texture_formats.read("gmio", data)[0]
        assert texture.pixel_format == name and texture.image.size == (16, 8)
        assert texture_formats.write("gmio", data, {0: texture.image}) == data
        out = texture_formats.write("gmio", data, {0: Image.new("RGBA", (16, 8), (255, 0, 0, 255))})
        assert len(out) == len(data) and out != data and out[:0x80] == data[:0x80]
    with pytest.raises(ValueError):
        texture_formats.read("gmio", _gmio((9, 9), 32))
    with pytest.raises(ValueError):
        texture_formats.read("gmio", _gmio((1, 0x10), 32)[:-4])


def test_real_gmio_files_round_trip():
    from core import texture_formats
    files = sorted(SOURCE.rglob("*.gmio")) if SOURCE.exists() else []
    if not files:
        pytest.skip("no unpacked GMIO files on this machine")
    for path in files[::17]:
        raw = path.read_bytes()
        texture = texture_formats.read("gmio", raw)[0]
        assert texture_formats.write("gmio", raw, {0: texture.image}) == raw, path.name


def test_descriptors_are_valid_json():
    assert json.loads((PLUGIN / "config.json").read_text(encoding="utf-8"))["display_name"]
    assert "translation" in json.loads((PLUGIN / "translation_prompts" / "prompts.json").read_text(encoding="utf-8"))
    assert isinstance(json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8")), list)
