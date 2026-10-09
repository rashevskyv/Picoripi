"""Raving Rabbids: Party Collection plugin: Jade text lists, TV Party TextPackages, executable messages, HOME Menu;
the real files, fonts and textures when the workspace is unpacked here."""
import json
import struct
from pathlib import Path

import pytest

from core.formats import SaveContext
from plugins.rabbids_party import dol_text, jade_text, text_packages
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "rabbids_party"
PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN
SOURCE = Path(r"E:\Emulators\RomHacking\Raving Rabbids Party Collection\source")
real = pytest.mark.skipif(not (SOURCE / "rrr1.bf").is_dir(), reason="Raving Rabbids Party Collection not unpacked here")


def txl(texts) -> bytes:
    """A text list: version-1 entries (24 bytes), None = a text without a string."""
    head, buf = struct.pack("<I", len(texts)), b""
    for i, text in enumerate(texts):
        offset = -1 if text is None else len(buf)
        head += struct.pack("<IIiI4sI", 0x49000000 + i, 0xFFFFFFFF, offset, 0x10028, b"\x01\x02\0\0", 0x38)
        if text is not None:
            buf += text + b"\0"
    return head + buf


JTXT = jade_text.write({0x4902D48F: txl([b"Yes", b"No", None, b"Press \\p16\\a to\ncontinue", b""]),
                        0x61020799: txl([b"Caf\xe9 \\cFF7FFF\\www\\cFFFFFF\\"])})


def packages(rows) -> bytes:
    out = struct.pack("<II", 3, len(rows))
    for ident, values in rows:
        for text in [ident] + values:
            data = (text + "\0").encode("utf-16-le")
            out += struct.pack("<H", len(data)) + data
    return out


TV = packages([("ID_BUTTON_NEXT", ["Next", "Suivant", "Siguiente"]),
               ("ID_BRIEF", ["<font color='#FFCC00'>Do</font> it", "Fais-le", ""])])


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".jtxt", ".bin", ".dol", ".csv"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_samples_survive_load_and_save():
    check_round_trip(PLUGIN, JTXT)
    check_round_trip(PLUGIN, TV)


def test_a_jade_text_list_rebuilds_byte_exact_and_lays_out_new_strings():
    item = txl([b"Yes", None, b"Off"])
    assert jade_text.build(item, jade_text.parse(item)[1]) == item
    new = jade_text.build(item, [b"\xc0\xc1", None, b"Off"])
    assert jade_text.parse(new)[1] == [b"\xc0\xc1", None, b"Off"]
    assert struct.unpack_from("<i", new, 4 + 24 + 8)[0] == -1


def test_jade_text_blocks_show_lists_and_write_letters_through_the_translation_map(monkeypatch):
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(JTXT)
    assert blocks[0] == ["Yes", "No", "", "Press \\p16\\a to\ncontinue", ""] and names["1"].startswith("61020799 Caf")
    rules.prepare_save_context(SaveContext(relative_path="rrr1.bf/text_english.jtxt", existing_versions=lambda: iter([JTXT])))
    assert rules.save_data_to_json_obj(blocks, names) == JTXT
    monkeypatch.setattr(type(rules), "load_translation_map",
                        lambda self: setattr(self, "translation_map", {"Т": "T", "Б": "\xc1"}))
    blocks[0][0] = "ТБ"
    blocks[0][1] = "Ж"
    saved = rules.save_data_to_json_obj(blocks, names)
    lists = jade_text.read(saved)
    assert jade_text.parse(lists[0x4902D48F])[1][:3] == [b"T\xc1", b"?", None]
    assert lists[0x61020799] == jade_text.read(JTXT)[0x61020799]


def test_tv_party_text_edits_only_the_english_column():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(TV)
    assert blocks == [["Next", "<font color='#FFCC00'>Do</font> it"]]
    blocks[0][0] = "Далі"
    saved = rules.save_data_to_json_obj(blocks, names)
    rows = text_packages.rows(saved)
    assert rows[0] == ("ID_BUTTON_NEXT", ["Далі", "Suivant", "Siguiente"]) and rows[1] == text_packages.rows(TV)[1]


def test_executable_messages_are_written_in_place_within_their_bytes():
    raw = bytearray(1108032)
    struct.pack_into(">I", raw, 0, 0x100)
    for at, room in dol_text.SLOTS[len(raw)][1]:
        raw[at:at + 3] = b"Abc"
    raw = bytes(raw)
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(raw)
    assert names == {"0": "Menu (RRRTExec_R.dol)"} and blocks[0][:2] == ["Abc", "Abc"]
    blocks[0][4] = "UA TEST: Press A"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved[0xded98:0xded98 + 17] == b"UA TEST: Press A\0" and len(saved) == len(raw)
    blocks[0][4] = "x" * 40
    with pytest.raises(ValueError):
        rules.save_data_to_json_obj(blocks, names)


@real
def test_every_real_text_file_round_trips_byte_exact_and_an_edit_lands():
    files = {"rrr1.bf/text_english.jtxt": 4046, "rrr2.bf/text_english.jtxt": 3149,
             "rrr3_bin_wii.bf/TextPackages.bin": 1116, "files/RRRTExec_R.dol": 18, "files/rrr1_f.dol": 12,
             "files/rrr2_eu.dol": 13, "files/rrr3_noe.dol": 13, "files/HomeButton2/home.csv": 4}
    for rel, count in files.items():
        raw = (SOURCE / rel).read_bytes()
        rules = load_rules(PLUGIN)
        blocks, names = rules.load_data_from_json_obj(raw)
        assert sum(len(b) for b in blocks) == count, rel
        rules.prepare_save_context(SaveContext(relative_path=rel, existing_versions=lambda: iter([raw])))
        assert rules.save_data_to_json_obj(blocks, names) == raw, rel
        blocks[-1][0] = "UA TEST"
        again, _ = load_rules(PLUGIN).load_data_from_json_obj(rules.save_data_to_json_obj(blocks, names))
        assert again[-1][0] == "UA TEST", rel


@real
def test_every_listed_font_opens_and_packs_byte_exact(tmp_path):
    from core import font_formats
    from core.font_formats import sources
    descriptors = json.loads((PLUGIN_DIR / "font_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve([d for d in descriptors if d["format"] != "brfna"],
                            {"source_path": str(SOURCE), "translation_path": str(tmp_path)})
    assert len(found) >= 19
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract(source.format, data, source.params)
        assert font_formats.pack(source.format, metadata, sheets, data, source.params) == data, source.name


@real
def test_every_listed_texture_path_resolves_and_a_menu_picture_round_trips(tmp_path):
    from core import texture_formats
    from core.texture_formats import sources
    descriptors = json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
    for descriptor in descriptors:
        found = sources.resolve([descriptor], {"source_path": str(SOURCE), "translation_path": str(tmp_path)})
        assert found, descriptor["label"]
    data = (SOURCE / "files" / "M_RRR1_0.tpl").read_bytes()
    textures = texture_formats.read("tpl", data, {})
    assert texture_formats.write("tpl", data, {i: t.image for i, t in enumerate(textures)}, {}) == data
