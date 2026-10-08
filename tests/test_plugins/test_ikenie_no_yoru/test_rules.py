"""Ikenie no Yoru plugin: MES0 message tables (control codes, layout, the first-number field), layout text boxes,
main.dol slots, the HOME Menu's Japanese column; the real files (text, fonts, textures) when the workspace is
unpacked here."""
import json
import struct
from pathlib import Path

import pytest

from core.formats import SaveContext
from plugins.common.wii_home_menu import JAPANESE, HomeCsv
from plugins.ikenie_no_yoru import brlyt, dol, mes, rules
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "ikenie_no_yoru"
PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN
SOURCE = Path(r"E:\Emulators\RomHacking\Ikenie no Yoru\source")
real = pytest.mark.skipif(not (SOURCE / "sys" / "main.dol").exists(), reason="Ikenie no Yoru not unpacked here")

NAME, PAGE, NEWLINE = [0x0001, 0x0003], 0x000C, 0x000A
SAMPLE = mes.build([
    [*NAME, ord(":"), *map(ord, "Hi"), NEWLINE, *map(ord, "there"), PAGE, ord("{")],
    [0x0007, 0xFF00, 0x00FF, 0x0003, 0x4000, 0x0000, *map(ord, "Curse"), 0x0001],     # a code at the very end
    list(map(ord, "※未使用枠")),
    list(map(ord, "学a")),
], first=605)


def layout(*texts: str) -> bytes:
    """A layout: header, one pane, then a text box per text."""
    sections = [b"pan1" + struct.pack(">I", 0x4C) + bytes(0x44)]
    for n, text in enumerate(texts):
        data = text.encode("utf-16-be") + b"\0\0"
        box = bytearray(0x74)
        box[0:4] = b"txt1"
        box[0x0C:0x0C + 5] = f"T_{n:03}".encode()
        struct.pack_into(">HH", box, 0x4C, len(data), len(data))
        struct.pack_into(">I", box, 0x58, 0x74)
        box += data + bytes(-len(data) % 4)
        struct.pack_into(">I", box, 4, len(box))
        sections.append(bytes(box))
    body = b"".join(sections)
    return b"RLYT\xfe\xff\x00\x08" + struct.pack(">IHH", 0x10 + len(body), 0x10, len(sections)) + body


def test_the_plugin_loads_and_validates():
    plugin = check_loads(PLUGIN)
    assert {".mes", ".brlyt", ".dol", ".csv"} <= {e for f in plugin.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)
    check_round_trip(PLUGIN, layout("Screen", "iiii", "追加された！"))


def test_control_codes_become_tags_and_come_back_unit_for_unit():
    texts = rules.texts_of(SAMPLE)
    assert texts[0] == "{NAME:3}:Hi\nthere{PAGE}{U007B}"
    assert texts[1] == "{COLOR:FF0000FF}{SIZE:40000000}Curse{U0001}"
    assert [mes.from_editor(t) for t in texts] == mes.units(SAMPLE)
    assert rules.TagManager().is_tag_legitimate("{NAME:3}") and rules.TagManager().is_tag_legitimate("{CR}")


def test_a_table_keeps_its_first_number_and_layout_when_edited():
    edited = rules.build(SAMPLE, ["{NAME:1}: Привіт", "x", "※未使用枠", "学a"])
    assert mes.first_number(edited) == 605 and len(edited) % 0x20 == 0
    assert mes.units(edited)[0] == [*NAME[:1], 1, *map(ord, ": Привіт")]
    offsets = struct.unpack_from(">4H", edited, 8)
    assert offsets[0] == 0x10 and all(o % 4 == 0 for o in offsets)
    assert rules.build(SAMPLE, rules.texts_of(SAMPLE)) == SAMPLE          # unchanged: the same bytes


def test_japanese_lines_are_found_but_not_the_unused_mark_or_the_d_pad_icon():
    assert [mes.is_japanese(t) for t in rules.texts_of(SAMPLE)] == [False, False, False, True]
    assert not mes.is_japanese("Use 十 to activate【Note】") and mes.is_japanese("追加された！")


def test_layout_text_boxes_skip_placeholders_and_grow():
    raw = layout("Screen", "iiii\niiii", "追加された！")
    assert [t for _p, t in brlyt.boxes(raw)] == ["Screen", "追加された！"]
    assert brlyt.build(raw, ["Screen", "追加された！"]) == raw
    grown = brlyt.build(raw, ["Яскравість екрана", "Додано!"])
    assert [t for _p, t in brlyt.boxes(grown)] == ["Яскравість екрана", "Додано!"]
    assert struct.unpack_from(">I", grown, 8)[0] == len(grown)


def test_home_menu_csv_edits_the_japanese_column():
    raw = '\ufeff"ホーム"\t"Home"\r\n"戻る"\t"Back"\r\n'.encode("utf-16-be")
    table = HomeCsv(raw, JAPANESE)
    assert table.messages == ["ホーム", "戻る"] and HomeCsv(raw).messages == ["Home", "Back"]
    assert HomeCsv(table.build(["Дім", "戻る"]), JAPANESE).messages == ["Дім", "戻る"]
    plugin = load_rules(PLUGIN)
    blocks, _names = plugin.load_data_from_json_obj(raw)
    assert blocks == [["ホーム", "戻る"]]


@real
def test_every_real_message_table_and_layout_round_trips():
    tables = sorted(SOURCE.rglob("*.mes"))
    assert len(tables) == 88
    lines = japanese = 0
    for path in tables:
        raw = path.read_bytes()
        texts = rules.texts_of(raw)
        assert [mes.from_editor(t) for t in texts] == mes.units(raw), path
        assert rules.build(raw, texts) == raw
        again = mes.build([mes.from_editor(t) for t in texts], mes.first_number(raw))
        assert rules.texts_of(again) == texts
        lines, japanese = lines + len(texts), japanese + sum(mes.is_japanese(t) for t in texts)
    assert (lines, japanese) == (1944, 3)
    layouts = sorted(SOURCE.rglob("*.brlyt"))
    assert len(layouts) == 28
    for path in layouts:
        raw = path.read_bytes()
        texts = rules.texts_of(raw)
        assert texts and brlyt.build(raw, texts) == raw, path


@real
def test_the_real_main_dol_strings_fit_their_slots():
    raw = (SOURCE / "sys" / "main.dol").read_bytes()
    texts = rules.texts_of(raw)
    assert len(texts) == len(dol.SLOTS) == 34 and texts[0] == "Ikenie" and texts[-1] == "Coal"
    assert dol.build(raw, texts) == raw
    edited = dol.build(raw, ["Ікеніє"] + texts[1:])
    assert rules.texts_of(edited)[0] == "Ікеніє" and len(edited) == len(raw)
    with pytest.raises(ValueError):
        dol.build(raw, ["far too long for the banner title slot"] + texts[1:])
    plugin = load_rules(PLUGIN)
    plugin.load_data_from_json_obj(raw)
    plugin.prepare_save_context(SaveContext(relative_path="sys/main.dol", existing_versions=lambda: iter([raw])))
    assert plugin.save_data_to_json_obj([texts], {}) == raw


@real
def test_every_font_opens_packs_byte_exact_and_writes_into_the_translation(tmp_path):
    from core import font_formats
    from core.font_formats import sources
    descriptors = json.loads((PLUGIN_DIR / "font_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(SOURCE), "translation_path": str(tmp_path)})
    assert len(found) == 6
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract(source.format, data, source.params)
        assert font_formats.pack(source.format, metadata, sheets, data, source.params) == data, source.name
        assert not any("\u0400" <= c < "\u0500" for c in font_formats.char_map(metadata))   # no Cyrillic yet
        source.write(data)
        assert (tmp_path / Path(source.source_path).relative_to(SOURCE)).read_bytes() == data


@real
def test_every_texture_reads_and_an_edit_lands_in_the_translation(tmp_path):
    from PIL import ImageDraw
    from core import texture_formats
    from core.texture_formats import sources
    descriptors = json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(SOURCE), "translation_path": str(tmp_path)})
    assert len({s.source_path for s in found}) == 481
    formats = set()
    for path in {s.source_path for s in found}:
        data = Path(path).read_bytes()
        textures = texture_formats.read("tpl", data, {})
        formats |= {t.pixel_format for t in textures}
        assert texture_formats.write("tpl", data, {i: t.image for i, t in enumerate(textures)}, {}) == data, path
    assert formats == {"C8", "I4", "RGB5A3", "CMPR", "IA8", "IA4", "C4", "C14X2", "RGBA8", "RGB565"}
    logo = sources.resolve([{"format": "tpl", "path": "package/menu_title/005f/title/timg/copyright.tpl"}],
                           {"source_path": str(SOURCE), "translation_path": str(tmp_path)})[0]
    image = logo.read_current().image.copy()
    ImageDraw.Draw(image).rectangle((0, 0, 15, 15), fill=(255, 0, 0, 255))
    assert logo.write(image)
    assert logo.read_current().image.getpixel((8, 8))[:3] == (255, 0, 0)
