"""Super Paper Mario plugin: message files with their end padding, global.txt groups, HOME Menu messages; the real
files (text, fonts, textures) when the workspace is unpacked here."""
import json
from pathlib import Path

import pytest

from core.formats import SaveContext
from plugins.paper_mario_gc import msgfile
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "super_paper_mario"
PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN
SOURCE = Path(r"E:\Emulators\RomHacking\Paper Mario\Super Paper Mario\source")
MSG = SOURCE / "msg" / "UK"
real = pytest.mark.skipif(not (MSG / "global.txt").exists(), reason="Super Paper Mario not unpacked here")


def spm_file(*entries) -> bytes:
    """A message file as the game stores it: one zero byte more after the closing empty key."""
    return msgfile.build([msgfile.Entry(k, t) for k, t in entries]) + b"\0"


GLOBAL = spm_file((b"place_stg1", b"Lineland"), (b"in_kinoko", b"Mushroom"), (b"ename_000", b"Goomba"),
                  (b"ehelp_000", b"Max HP: %d\n<k>"), (b"anna_ehelp_000", b"<fairy>\nIt's a Goomba.\n<k>"),
                  (b"sys_nokey", b"<system>\n\nIt's locked.\n<k>"),
                  (b"msg_cancel", b"Select OK"), (b"msg_cancel", b"Go back"))      # the game has a key twice
HOME = "\ufeff".encode("utf-16-be") + '"ホーム"\t"HOME Menu"\t"HOME-Menü"\r\n"x"\t"Wii Remote\nSettings"\t"y"\r\n'.encode("utf-16-be")


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".txt", ".csv"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_samples_survive_load_and_save():
    check_round_trip(PLUGIN, GLOBAL)
    check_round_trip(PLUGIN, HOME)


def test_the_end_padding_is_read_and_written_back():
    assert msgfile.padding(GLOBAL) == b"\0" and msgfile.padding(msgfile.build([])) == b""
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(GLOBAL)
    assert list(names.values()) == ["Places", "Item names", "Enemy names", "Catch Cards", "Tippi's tattles",
                                    "Descriptions", "Other"]
    assert rules.save_data_to_json_obj(blocks, names) == GLOBAL
    blocks[0][0] = "Лінія"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved.endswith(b"Go back\0\0\0") and msgfile.parse(saved)[0].text != b"Lineland"
    assert [e.text for e in msgfile.parse(saved)[-2:]] == [b"Select OK", b"Go back"]


def test_home_menu_saves_only_the_english_column():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(HOME)
    assert blocks == [["HOME Menu", "Wii Remote\nSettings"]]
    rules.prepare_save_context(SaveContext(relative_path="hbm/HomeButton2_en.bin/home.csv", existing_versions=lambda: iter([HOME])))
    saved = rules.save_data_to_json_obj([["Меню HOME", "Пульт"]], names)
    assert saved.decode("utf-16") == '"ホーム"\t"Меню HOME"\t"HOME-Menü"\r\n"x"\t"Пульт"\t"y"\r\n'


@real
def test_every_message_file_and_home_menu_round_trip_byte_exact():
    files = sorted(MSG.glob("*.txt")) + [SOURCE / "hbm" / "HomeButton2_en.bin" / "home.csv"]
    total = 0
    for path in files:
        data = path.read_bytes()
        rules = load_rules(PLUGIN)
        blocks, names = rules.load_data_from_json_obj(data)
        total += sum(len(b) for b in blocks)
        rules.prepare_save_context(SaveContext(relative_path=path.name, existing_versions=lambda: iter([data])))
        assert rules.save_data_to_json_obj(blocks, names) == data, path.name
    assert total >= 8530


@real
def test_no_english_message_uses_a_slot_a_ukrainian_letter_takes():
    slots = {v for k, v in json.loads((PLUGIN_DIR / "translation_map.json").read_text(encoding="utf-8")).items()
             if not (v.isascii() or v == "’")}
    used = {msgfile.decode(e.text) for path in MSG.glob("*.txt") for e in msgfile.parse(path.read_bytes())}
    assert not {c for text in used for c in text} & slots


@real
def test_every_font_opens_and_writes_into_the_translation(tmp_path):
    from core import font_formats
    from core.font_formats import sources
    from tools.bfn_editor.bfn_engine import extract_bfn_logic, repack_bfn_logic
    descriptors = json.loads((PLUGIN_DIR / "font_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(SOURCE), "translation_path": str(tmp_path)})
    assert len(found) == 4
    for source in found:
        data = source.read_original()
        if source.format == "bfn":
            folder = tmp_path / "x" / source.name
            extract_bfn_logic(source.source_path, str(folder))
            repack_bfn_logic(str(folder), str(folder / "out.bfn"))
            assert (folder / "out.bfn").read_bytes() == data, source.name
        else:
            metadata, sheets = font_formats.extract(source.format, data, source.params)
            assert font_formats.pack(source.format, metadata, sheets, data, source.params) == data, source.name
        source.write(data)
        assert (tmp_path / Path(source.source_path).relative_to(SOURCE)).read_bytes() == data


@real
def test_texture_list_round_trips_and_an_edit_lands_in_the_translation(tmp_path):
    from PIL import ImageDraw
    from core import texture_formats
    from core.texture_formats import sources
    descriptors = json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(SOURCE), "translation_path": str(tmp_path)})
    assert len(found) >= 300
    for path in {s.source_path for s in found}:
        data = Path(path).read_bytes()
        textures = texture_formats.read("tpl", data, {})
        assert texture_formats.write("tpl", data, {i: t.image for i, t in enumerate(textures)}, {}) == data, path
    logo = next(s for s in found if s.key.startswith("lyt/title.bin.uk/arc/timg/logo_img_e.tpl"))
    image = logo.read_current().image.copy()
    ImageDraw.Draw(image).rectangle((0, 0, 31, 31), fill=(255, 0, 0, 255))
    assert logo.write(image)
    written = tmp_path / "lyt" / "title.bin.uk" / "arc" / "timg" / "logo_img_e.tpl"
    assert written.stat().st_size == Path(logo.source_path).stat().st_size
    assert logo.read_current().image.getpixel((8, 8))[:3] == (255, 0, 0)
