"""Spore Hero plugin: the LOCBIN package (strings, histogram bytes, stream layout), main.dol messages; the real files
(text, fonts, UI textures) when the workspace is unpacked here."""
import json
import struct
from pathlib import Path

import pytest

from core.formats import SaveContext
from plugins.spore_hero import locbin
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "spore_hero"
PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN
SOURCE = Path(r"E:\Emulators\RomHacking\Spore Hero\source")
TEXT = SOURCE / "game" / "localization" / "localization" / "ENG_US.rpk"
real = pytest.mark.skipif(not TEXT.exists(), reason="Spore Hero not unpacked here")


def _text_asset(strings) -> bytes:
    """A LOCBIN text asset: header, (hash, offset) table sorted by hash, pool in the given order."""
    pool, table = bytearray(), {}
    for key, text in strings:
        table[key] = len(pool)
        pool += text + b"\0"
    pool += bytes(-(36 + 8 * len(strings) + len(pool)) % 4)
    head = struct.pack("<5I", locbin.TEXT_ID, 0, len(strings), 0x1C, 0x1C + 8 * len(strings)) + b"Global".ljust(16, b"\0")
    body = b"".join(struct.pack("<II", key, table[key]) for key in sorted(table))
    out = bytearray(head + body + pool)
    struct.pack_into("<I", out, 4, len(out) - 8)
    return bytes(out)


def _map_asset(codes) -> bytes:
    table = [0] * 256
    table[0x80] = 2
    for byte, code in codes.items():
        table[byte] = code
    return struct.pack("<3I", locbin.MAP_ID, 0x1804, 256) + struct.pack("<256H", *table) + bytes(0x1600)


def _package(*blobs) -> bytes:
    """A STRM package with one LOCBIN group (alignment 0x10) holding ``blobs``, laid out as the game's tools do:
    AGRP (GHDR, ASET per asset), STRS (type name, asset names), DATA (assets at multiples of 0x10)."""
    names = [f"asset{i}.BIN".encode() + b"\0" for i in range(len(blobs))]
    strings = b"LOCBIN\0\0" + b"".join(names)
    strings += bytes(-len(strings) % 4)
    group = 8 + 0x14 + 0x28 * len(blobs)
    strs_body = 8 + group + 8
    pos = strs_body + len(strings) + 8                 # the DATA body
    out = bytearray(b"STRM\0\0\0\0" + b"AGRP" + struct.pack(">I", group))
    out += b"GHDR" + struct.pack(">IIII", 0x14, 0x10, strs_body, 0x10)
    body, name_at = bytearray(), strs_body + 8
    for blob, name in zip(blobs, names):
        at = -(-pos // 0x10) * 0x10
        body += bytes(at - pos) + blob
        out += b"ASET" + struct.pack(">I8I", 0x28, 0x1234, 0x856E9D81, 0, 0, at, len(blob), name_at, 0)
        name_at += len(name)
        pos = at + len(blob)
    body += bytes(-pos % 4)
    out += b"STRS" + struct.pack(">I", 8 + len(strings)) + strings
    out += b"DATA" + struct.pack(">I", 8 + len(body)) + body
    struct.pack_into(">I", out, 4, len(out))
    return bytes(out)


SAMPLE = _package(_text_asset([(0x30, b"New Game"), (0x10, b"Spore\x81 Hero"), (0x20, b"Fran\xe7ais <c>x</c> &")]),
                  _map_asset({0x81: 0x2122, 0xE7: 0xE7}))


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".rpk", ".dol", ".csv"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    assert locbin.replace_assets(SAMPLE, {}) == SAMPLE
    check_round_trip(PLUGIN, SAMPLE)


def test_strings_show_in_pool_order_through_the_histogram():
    assert locbin.texts(SAMPLE) == ["New Game", "Spore™ Hero", "Français <c>x</c> &"]


def test_a_new_letter_gets_a_free_byte_and_its_histogram_entry():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    blocks[0][0] = "Нова гра™"
    rules.prepare_save_context(SaveContext(relative_path="ENG_US.rpk", existing_versions=lambda: iter([SAMPLE])))
    saved = rules.save_data_to_json_obj(blocks, names)
    assert locbin.texts(saved) == ["Нова гра™", "Spore™ Hero", "Français <c>x</c> &"]
    parts = locbin._parts(saved)
    table = locbin.char_table(parts[locbin.MAP_ID][1])
    assert table[0x81] == 0x2122 and table[0x80] == 2 and ord("Н") in table
    raw_first = locbin.strings(parts[locbin.TEXT_ID][1])[0][1]
    assert all(b >= locbin.FIRST_FREE for b in raw_first if b > 0x7F) and len(raw_first) == len("Нова гра™")
    # the stream stays packed: every asset at the next multiple of 0x10 after the one before it
    items = locbin.assets(saved)
    assert items[1]["off"] == -(-(items[0]["off"] + items[0]["size"]) // 0x10) * 0x10
    assert struct.unpack_from(">I", saved, 4)[0] == len(saved) and len(saved) % 4 == 0


def test_a_translation_map_writes_letters_as_their_glyph_slots():
    slots = {"Ж": "Æ", "А": "A"}
    shown = {"Æ": "Ж"}                                  # a Latin look-alike slot is never shown as Cyrillic
    saved = locbin.build(SAMPLE, ["ЖАba", "Spore™ Hero", "Français <c>x</c> &"], slots, shown)
    parts = locbin._parts(saved)
    raw = locbin.strings(parts[locbin.TEXT_ID][1])[0][1]
    assert raw == b"\xc6Aba" and locbin.char_table(parts[locbin.MAP_ID][1])[0xC6] == 0xC6
    assert locbin.texts(saved, shown)[0] == "ЖAba"
    assert locbin.build(saved, locbin.texts(saved, shown), slots, shown) == saved


def test_a_byte_used_by_another_string_is_never_given_out():
    table = [0] * 256
    assert locbin.encode("é", table, frozenset({0xE9})) != b"\xe9"


def test_main_dol_messages_are_edited_in_their_own_bytes():
    raw = bytearray(0x573000)
    start, second = locbin.DOL_SETS[0][0], locbin.DOL_SETS[1][0]
    text = b"Please insert the\0Abc\0\0\0Long\0"
    raw[start:start + len(text)] = text
    raw[second:second + 2] = b"y\0"
    raw = bytes(raw)
    assert locbin.is_dol(raw)
    groups = locbin.dol_texts(raw)
    assert groups == [["Please insert the", "Abc", "Long"], ["y"]]
    groups[0][1] = "Abcde"                             # its bytes: 3 letters and the zeros up to "Long" but one
    out = locbin.build_dol(raw, groups)
    assert out[start + 18:start + 24] == b"Abcde\0" and len(out) == len(raw) and out[start + 24:start + 28] == b"Long"
    groups[0][1] = "Abcdef"
    with pytest.raises(ValueError):
        locbin.build_dol(raw, groups)


@real
def test_the_real_text_round_trips_byte_exact_and_an_edit_lands():
    raw = TEXT.read_bytes()
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(raw)
    assert sum(len(b) for b in blocks) == 2285 and len(blocks) == 23
    rules.prepare_save_context(SaveContext(relative_path="ENG_US.rpk", existing_versions=lambda: iter([raw])))
    assert rules.save_data_to_json_obj(blocks, names) == raw
    blocks[20][2] = "UA TEST Ґанок"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert locbin.texts(saved)[2002] == "UA TEST Ґанок"


@real
def test_the_real_main_dol_and_home_menu_round_trip():
    for rel, count in (("sys/main.dol", 37), ("Game.rpk/home.csv", 4), ("Game.rpk/home_nosave.csv", 4)):
        raw = (SOURCE / rel).read_bytes()
        rules = load_rules(PLUGIN)
        blocks, names = rules.load_data_from_json_obj(raw)
        assert sum(len(b) for b in blocks) == count, rel
        rules.prepare_save_context(SaveContext(relative_path=rel, existing_versions=lambda: iter([raw])))
        assert rules.save_data_to_json_obj(blocks, names) == raw, rel


@real
def test_every_font_opens_and_packs_byte_exact(tmp_path):
    from core import font_formats
    from core.font_formats import sources
    descriptors = json.loads((PLUGIN_DIR / "font_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(SOURCE), "translation_path": str(tmp_path)})
    assert [s.format for s in found] == ["fntg", "fntg", "fntg", "brfnt"]
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract(source.format, data, source.params)
        assert font_formats.pack(source.format, metadata, sheets, data, source.params) == data, source.name


@real
def test_every_ui_texture_reads_and_an_unchanged_write_changes_nothing(tmp_path):
    from core.texture_formats import sources
    descriptors = json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(SOURCE), "translation_path": str(tmp_path)})
    assert len(found) == 2126
    assert {s.pixel_format for s in found} >= {"C8", "CMPR", "RGB5A3", "I4", "IA8"}
    for source in found[::25]:
        assert not source.write(source.read_original().image), source.key
    assert not list(tmp_path.rglob("*"))
