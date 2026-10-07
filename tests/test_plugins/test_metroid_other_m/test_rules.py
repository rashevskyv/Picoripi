"""Metroid: Other M plugin: the tdpack message file (tables, control codes, line breaks), HOME Menu messages; the real
files (text, fonts, layout textures) when the workspace is unpacked here."""
import json
import struct
from pathlib import Path

import pytest

from core.formats import SaveContext
from plugins.metroid_other_m import msgdat
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "metroid_other_m"
PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN
SOURCE = Path(r"E:\Emulators\RomHacking\Metroid\Other M\source")
MESSAGES = SOURCE / "message" / "message_all.dat"
real = pytest.mark.skipif(not MESSAGES.exists(), reason="Metroid: Other M not unpacked here")


def tdpack(*tables) -> bytes:
    """A message file as the game stores it: header, offset and size lists, tables on 0x20 bytes."""
    head = bytearray(b"tdpack\0\0" + struct.pack(">IIIIIIIII", 0xFF000100, 0x30, 0, len(tables), len(tables), 0,
                                                0x30, 0x50, 0))
    head += bytes(0x80 - len(head))
    struct.pack_into(">I", head, 0x30, 0x80)                            # the first table starts at 0x80
    return msgdat.build(bytes(head), [msgdat.table(list(t)) for t in tables])


SAMPLE = tdpack(["#FONT_SYSTEMはい"], ["", "#FONT_SYSTEMPress #ICON_ONE.^#COLOR_YELLOWSUPER MISSILE#COLOR_WHITE ok",
                                      "#IMG_ADAMAdam#IMG_MB"] + ["x"] * 600)


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".dat", ".csv"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_control_codes_become_named_tags_and_the_longest_name_wins():
    assert msgdat.to_editor("#COLOR_YELLOWSUPER^#ICON_CROSS #ICON_C") == "{COLOR_YELLOW}SUPER\n{ICON_CROSS} {ICON_C}"
    assert msgdat.to_editor("#COLOR_FUMEI x") == "#COLOR_FUMEI x"          # not a colour of the game: plain text
    assert msgdat.from_editor("{COLOR_YELLOW}SUPER\n{ICON_CROSS} {NOPE}") == "#COLOR_YELLOWSUPER^#ICON_CROSS {NOPE}"


def test_only_the_english_table_is_shown_and_written():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert names["0"] == "Title, save and menu messages" and len(blocks) == 7
    assert blocks[0][:3] == ["", "{FONT_SYSTEM}Press {ICON_ONE}.\n{COLOR_YELLOW}SUPER MISSILE{COLOR_WHITE} ok",
                             "{IMG_ADAM}Adam{IMG_MB}"]
    rules.prepare_save_context(SaveContext(relative_path="message/message_all.dat", existing_versions=lambda: iter([SAMPLE])))
    assert rules.save_data_to_json_obj(blocks, names) == SAMPLE
    blocks[0][2] = "Адам {IMG_ADAM}\nдовший рядок"
    saved = rules.save_data_to_json_obj(blocks, names)
    tables = msgdat.tables(saved)
    assert tables[0] == msgdat.tables(SAMPLE)[0]
    assert msgdat.messages(tables[1])[2] == "Адам #IMG_ADAM^довший рядок"
    assert struct.unpack_from(">I", saved, 0x10)[0] == len(saved) and len(saved) % 0x20 == 0


@real
def test_the_real_message_file_round_trips_byte_exact_and_an_edit_lands():
    raw = MESSAGES.read_bytes()
    assert msgdat.build(raw, msgdat.tables(raw)) == raw
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(raw)
    assert sum(len(b) for b in blocks) == 1899 and len(blocks[6]) == 1393      # 1393 voice and cutscene subtitles
    rules.prepare_save_context(SaveContext(relative_path="message/message_all.dat", existing_versions=lambda: iter([raw])))
    assert rules.save_data_to_json_obj(blocks, names) == raw
    blocks[6][0] = "UA TEST"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert msgdat.messages(msgdat.tables(saved)[1])[506] == "UA TEST"
    assert [t for i, t in enumerate(msgdat.tables(saved)) if i != 1] == [t for i, t in enumerate(msgdat.tables(raw)) if i != 1]


@real
def test_the_real_home_menu_messages_round_trip():
    for name in ("home.csv", "home_nosave.csv"):
        raw = (SOURCE / "hbm" / "HomeButton2" / name).read_bytes()
        rules = load_rules(PLUGIN)
        blocks, names = rules.load_data_from_json_obj(raw)
        assert len(blocks[0]) == 4
        rules.prepare_save_context(SaveContext(relative_path=name, existing_versions=lambda: iter([raw])))
        assert rules.save_data_to_json_obj(blocks, names) == raw


@real
def test_every_font_opens_packs_byte_exact_and_writes_into_the_translation(tmp_path):
    from core import font_formats
    from core.font_formats import sources
    descriptors = json.loads((PLUGIN_DIR / "font_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(SOURCE), "translation_path": str(tmp_path)})
    assert len(found) == 5
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract(source.format, data, source.params)
        assert font_formats.pack(source.format, metadata, sheets, data, source.params) == data, source.name
        source.write(data)
        assert (tmp_path / Path(source.source_path).relative_to(SOURCE)).read_bytes() == data


@real
def test_layout_textures_round_trip_and_an_edit_lands_in_the_translation(tmp_path):
    from PIL import ImageDraw
    from core import texture_formats
    from core.texture_formats import sources
    descriptors = json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
    assert len(descriptors) > 850
    found = sources.resolve(descriptors[:6] + descriptors[6::40], {"source_path": str(SOURCE),
                                                                     "translation_path": str(tmp_path)})
    assert len(found) >= 150
    for path in {s.source_path for s in found}:
        data = Path(path).read_bytes()
        textures = texture_formats.read("tpl", data, {})
        assert texture_formats.write("tpl", data, {i: t.image for i, t in enumerate(textures)}, {}) == data, path
    press = sources.resolve([{"format": "tpl", "path": "3492/title_01/timg/please_press_2.tpl"}],
                            {"source_path": str(SOURCE), "translation_path": str(tmp_path)})[0]
    image = press.read_current().image.copy()
    ImageDraw.Draw(image).rectangle((0, 0, 15, 15), fill=(255, 0, 0, 255))
    assert press.write(image)
    written = tmp_path / "3492" / "title_01" / "timg" / "please_press_2.tpl"
    assert written.stat().st_size == Path(press.source_path).stat().st_size
    assert press.read_current().image.getpixel((8, 8))[:3] == (255, 0, 0)
