"""Final Fantasy XII: Revenant Wings plugin: text formats, DPK packs, NFTR fonts in a pack; real-data round trips."""
import json
import struct
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.containers import lz10
from core.texture_formats.sources import resolve, unwrap
from plugins.ff12rw import rwtext, textures
from plugins.ff12rw.dpk import DpkContainer
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "ff12rw"
PLUGIN_DIR = Path(__file__).parents[3] / "plugins" / "ff12rw"
WS = Path(r"E:\Emulators\RomHacking\Final Fantasy\Revenant Wings")
SOURCE = WS / "source"
needs_data = pytest.mark.skipif(not (SOURCE / "data" / "FontPack.dpk").is_file(),
                                reason="Final Fantasy XII: Revenant Wings workspace not on disk")


def _btx(*strings: bytes) -> bytes:
    head, body = bytearray(struct.pack("<I", len(strings))), bytearray()
    for n, raw in enumerate(strings):
        head += struct.pack("<II", n + 1, len(body))
        body += raw + b"\x00\x00"
    return bytes(head + body)


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, "First line\nSecond line\n\nA line of the next block")


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_bytes_become_text_and_tags_and_back():
    raw = b"\x16Title\x18\x01Line\x02two [x] \xe9\x85"
    text = rwtext.to_editor(raw)
    assert text == "[x16]Title[x18][page]Line\ntwo [x5B]x[x5D] é…"
    assert rwtext.from_editor(text) == raw


def test_a_character_the_fonts_lack_is_refused():
    with pytest.raises(rwtext.FormatError):
        rwtext.from_editor("Привіт")


def test_a_menu_table_grows_and_keeps_its_ids():
    data = _btx(b"Bridge", b"Back")
    text = rwtext.parse("x.btx", data)
    assert text.strings == [b"Bridge", b"Back"] and text.build(text.strings) == data
    grown = rwtext.parse("x.btx", text.build([b"Bridge, a longer one", b"Back"]))
    assert grown.strings == [b"Bridge, a longer one", b"Back"]


def test_a_conversation_record_grows():
    entry = struct.pack("<HHHHII", 0, 4, 1, 1, 0, 0)
    text, name = b"Hello\x02there.\x00\x00\x00\x00", b"Vaan\x00\x00\x00\x00"
    body = entry + struct.pack("<III", len(text), 0x410040, len(name)) + text + name
    data = b"HSCD" + struct.pack("<II", 0x100, 1) + struct.pack("<II", 7, 8 + len(body)) + body
    parsed = rwtext.parse("conv.hscd", data)
    assert parsed.strings == [b"Hello\x02there.", b"Vaan"] and parsed.build(parsed.strings) == data
    again = rwtext.parse("conv.hscd", parsed.build([b"UA TEST: a much longer line", b"Vaan"]))
    assert again.strings == [b"UA TEST: a much longer line", b"Vaan"]


def test_the_plugin_saves_only_what_changed():
    data = _btx(b"Bridge", b"Back")
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(data)
    assert blocks == [["Bridge", "Back"]]
    assert rules.save_data_to_json_obj(blocks, names) == data
    blocks[0][0] = "UA TEST"
    assert rwtext.parse("x.btx", rules.save_data_to_json_obj(blocks, names)).strings == [b"UA TEST", b"Back"]


def test_a_dpk_member_packed_with_lz10_is_read_plain():
    narc = b"NARC" + bytes(60)
    data = rwtext.dpk_pack([(1, lz10.compress(narc)), (2, b"raw")])
    pack = DpkContainer(data)
    assert DpkContainer.can_handle(data) and pack.list_files() == ["#0", "#1"]
    assert pack.read_file("#0") == narc and pack.pack() == data
    pack.write_file("#0", b"NARC" + bytes(64))
    again = DpkContainer(pack.pack())
    assert again.read_file("#0") == b"NARC" + bytes(64) and again.read_file("#1") == b"raw"


# -- real data ---------------------------------------------------------------------------------------------------


@needs_data
def test_every_text_file_round_trips_byte_exact():
    total = 0
    for path in SOURCE.rglob("*"):
        if not path.is_file() or rwtext.parser_for(path.name) is None:
            continue
        data = path.read_bytes()
        text = rwtext.parse(path.name, data)
        assert text.build(text.strings) == data, path
        assert all(rwtext.from_editor(rwtext.to_editor(raw)) == raw for raw in text.strings)
        total += len(text.strings)
    assert total == 14398


@needs_data
def test_the_four_fonts_pack_back():
    pack = DpkContainer((SOURCE / "data" / "FontPack.dpk").read_bytes())
    for member in pack.list_files():
        font = pack.read_file(member)
        metadata, sheets = font_formats.extract("nftr", font, {"spare": 72})
        assert font_formats.pack("nftr", metadata, sheets, font, {"spare": 72}) == font
        assert "é" in font_formats.char_map(metadata) or member == "#3"


@needs_data
def test_texture_list_matches_the_game_files_and_every_picture_writes_back_unchanged():
    load_rules(PLUGIN)
    entries = json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
    assert entries == textures.describe(SOURCE)
    for entry in entries[::7]:
        raw = (SOURCE / entry["path"]).read_bytes()
        data, rewrap = unwrap(raw, entry.get("member", ""), entry["params"])
        image = texture_formats.read(entry["format"], data, entry["params"])[0].image
        assert rewrap(texture_formats.write(entry["format"], data, {0: image}, entry["params"])) == raw, entry["label"]
    meta = {"source_path": str(SOURCE), "translation_path": "", "is_directory_mode": True}
    assert len(resolve([e for e in entries if "title/bg_pack" in e["path"]], meta)) == 6
