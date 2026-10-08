"""Super Metroid (sm_rewrite PC port) plugin: text.json round trip, cells, context, real fonts, textures and ROM text."""
import json
import sys
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from plugins.super_metroid import rules as sm_rules
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "super_metroid"
WORKSPACE = Path(r"E:\Emulators\RomHacking\Metroid\Super Metroid")
SOURCE = WORKSPACE / "source"
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
SAMPLE = json.dumps({"format": sm_rules.FORMAT, "groups": [
    {"name": "Message boxes", "items": [{"id": "msg.01.EnergyTank", "text": "ENERGY TANK", "width": 19, "lines": 1,
                                         "symbol": "kMessageBox_1_EnergyTank"}]},
    {"name": "Intro", "items": [{"id": "intro.page1", "text": "I FIRST BATTLED\nTHE METROIDS", "width": 30, "lines": 7,
                                 "symbol": "addr_kCinematicBgObjectDef_8BCF3F"}]}]}, ensure_ascii=False, indent=1) + "\n"


def test_the_plugin_loads_round_trips_and_validates():
    check_loads(PLUGIN)
    check_round_trip(PLUGIN, SAMPLE)
    check_validator(PLUGIN)


def test_an_unchanged_save_is_the_same_file_and_texts_go_in_by_position():
    rules = check_loads(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert names == {"0": "Message boxes", "1": "Intro"}
    assert rules.save_data_to_json_obj(blocks, names) == SAMPLE
    saved = json.loads(rules.save_data_to_json_obj([["ЕНЕРГОБАК"], ["Я ВПЕРШЕ"]], names))
    item = saved["groups"][0]["items"][0]
    assert item == {"id": "msg.01.EnergyTank", "text": "ЕНЕРГОБАК", "width": 19, "lines": 1,
                    "symbol": "kMessageBox_1_EnergyTank"}


def test_a_line_is_one_cell_per_letter_and_per_tag():
    rules = check_loads(PLUGIN)
    rules.load_data_from_json_obj(SAMPLE)
    assert sm_rules.cells("[press1][press2]A B") == 5
    assert rules.calculate_string_width_override("[#304B]AB", {}) == 24
    assert rules.get_string_layout(0, 0) == {"max_width": 152, "warn_width": 152, "lines_per_page": 1}


def test_context_names_the_code_and_samus_for_the_intro():
    rules = check_loads(PLUGIN)
    rules.load_data_from_json_obj(SAMPLE)
    assert "speaker_attribution" in rules.get_capabilities()
    assert rules.get_speaker_for_string(1, 0) == "Samus"
    assert rules.get_speaker_for_string(0, 0) is None
    scene = rules.get_scene_context_for_string(0, 0)
    assert scene["resource"].startswith("src/sm_84.c:") and scene["scene"] == "Message boxes"
    assert rules.get_translation_context_for_string(1, 0)["content_role"] == "Narration"


def test_the_context_scanner_finds_symbols_and_the_plm_fallback(tmp_path):
    from plugins.super_metroid import port_context
    src = tmp_path / "src"
    src.mkdir()
    (src / "sm_84.c").write_text("void Show(void) {\n  DisplayMessageBox(kMessageBox_2_Missile);\n}\n"
                                 "void Plm(void) {\n  DisplayMessageBox(plmp[2]);\n}\n", encoding="utf-8")
    found = port_context.scan(tmp_path, [{"id": "a", "symbol": "kMessageBox_2_Missile"},
                                         {"id": "b", "symbol": "kMessageBox_7_VariaSuit"},
                                         {"id": "intro.page1", "symbol": "none"}])
    assert found["a"] == {"refs": ["src/sm_84.c:2"], "functions": ["Show"]}
    assert found["b"]["functions"] == ["Plm"]
    assert found["intro.page1"] == {"speaker": "Samus"}


def test_texture_grid_takes_a_list_of_chars_with_empty_cells():
    from PIL import Image
    data = bytes(64 * 16)              # one row of 16 4bpp tiles
    params = {"texture": "raw", "cell": [8, 8], "chars": ["", "A", "[x]", "B"],
              "texture_params": {"pixel_format": "snes:4bpp", "offset": 0, "width": 128, "height": 8}}
    metadata, sheets = font_formats.extract("texture_grid", data * 2, params)
    assert metadata["MAP1"][0]["entries"] == [65, 66, 1, 3]
    assert isinstance(sheets[0], Image.Image)
    assert font_formats.pack("texture_grid", metadata, sheets, data * 2, params) == data * 2


# -- the workspace's real files (skipped where they are not on disk) -------------------------------

needs_source = pytest.mark.skipif(not (SOURCE / "text.json").is_file(), reason="Super Metroid workspace not unpacked")


@needs_source
def test_real_text_saves_back_unchanged():
    rules = check_loads(PLUGIN)
    text = (SOURCE / "text.json").read_text(encoding="utf-8")
    blocks, names = rules.load_data_from_json_obj(text)
    assert [len(b) for b in blocks] == [27, 27, 36, 7, 6, 77]
    assert rules.save_data_to_json_obj(blocks, names) == text


@needs_source
def test_real_fonts_and_textures_open_and_pack_back_unchanged():
    rules = check_loads(PLUGIN)
    for font in rules.get_font_sources():
        data = (SOURCE / font["path"]).read_bytes()
        metadata, sheets = font_formats.extract(font["format"], data, font["params"])
        assert font_formats.pack(font["format"], metadata, sheets, data, font["params"]) == data, font["label"]
    for texture in rules.get_texture_sources():
        data = (SOURCE / texture["path"]).read_bytes()
        images = texture_formats.read(texture["format"], data, texture["params"])
        assert texture_formats.write(texture["format"], data, {0: images[0].image}, texture["params"]) == data
    bg3 = rules.get_font_sources()[0]
    assert all(ch in bg3["params"]["chars"] for ch in "БГҐДЄЖЗИЇЙЛПУФЦЧШЩЬЮЯ")


@pytest.fixture(scope="module")
def zt_sm():
    if not (SCRIPTS / "zt" / "sm.py").is_file() or not (WORKSPACE / "ISO" / "USA").is_dir():
        pytest.skip("Super Metroid workspace scripts or ROM not on disk")
    sys.path.insert(0, str(SCRIPTS))
    try:
        from zt import sm
        return sm, sm.rom_bytes(WORKSPACE)
    finally:
        sys.path.remove(str(SCRIPTS))


def test_real_rom_every_text_item_encodes_back_to_its_own_bytes(zt_sm):
    sm, data = zt_sm
    rom = sm.Rom(data)
    for item in sm.catalog(rom):
        if item.page >= 0:
            page = sm.read_page(data, item.page)
            start = sm.lo(0x8C0000 | sm.word(data, sm.lo(sm.INTRO_DEFS + 6 * item.page + 4)))
            blob = sm.page_bytes(data, page, sm.page_text(data, page), item.id)
            assert data[start:start + len(blob)] == blob, item.id
            continue
        for seg in item.segs:
            font, cells = sm.FONTS[seg.font], seg.cells(rom.buf(seg.buf))
            assert sm.encode(font, cells, sm.decode(font, cells), item.id) == cells, item.id


def test_real_rom_unchanged_text_and_sheets_build_the_same_rom(zt_sm, tmp_path):
    sm, data = zt_sm
    rom = sm.Rom(data)
    texts = {it["id"]: it["text"] for g in json.loads(sm.dump_text(rom))["groups"] for it in g["items"]}
    assert sm.apply_text(rom, texts, dict(texts)) == []
    assert bytes(rom.data) == data
    for name in sm.GFX:
        (tmp_path / "s" / "gfx").mkdir(parents=True, exist_ok=True)
        (tmp_path / "s" / "gfx" / f"{name}.bin").write_bytes(sm.gfx_source(data, name))
    assert sm.apply_gfx(rom, tmp_path / "s", tmp_path / "s") == [] and bytes(rom.data) == data


def test_real_rom_changed_texts_land_in_the_rom_and_read_back(zt_sm):
    sm, data = zt_sm
    rom = sm.Rom(data)
    texts = {it["id"]: it["text"] for g in json.loads(sm.dump_text(rom))["groups"] for it in g["items"]}
    new = dict(texts, **{"msg.01.EnergyTank": "ЕНЕРГОБАК", "menu.SamusData": "UA TEST",
                         "options.options.r06c00": "UA TEST GAME", "pause.area0": "UA TEST",
                         "credits.r000c00": "UA TEST STAFF",
                         "intro.page6": "UA TEST STATION WAS UNDER\nATTACK!! THIS IS A LONGER LINE\nTHIRD LINE"})
    assert len(sm.apply_text(rom, texts, new)) == 6
    again = {it["id"]: it["text"] for g in json.loads(sm.dump_text(sm.Rom(bytes(rom.data))))["groups"]
             for it in g["items"]}
    assert again["msg.01.EnergyTank"] == "EHEPГOБAK"          # look-alikes take the Latin tile, Г and Б their cells
    for key in ("menu.SamusData", "options.options.r06c00", "pause.area0", "credits.r000c00", "intro.page6"):
        assert again[key] == new[key], key
    assert all(again[k] == v for k, v in texts.items() if new[k] == v)
    with pytest.raises(sm.Fail):
        sm.apply_text(sm.Rom(data), texts, dict(texts, **{"menu.SamusData": "UA TEST UA TEST"}))


def test_real_rom_packed_blocks_compress_back_and_fit(zt_sm):
    sm, data = zt_sm
    for addr in [a for a, _ in sm.OPTIONS] + [sm.CREDITS, sm.GFX["intro_font"][0], sm.GFX["ending_font"][0]]:
        raw, room = sm.decompress(data, sm.lo(addr))
        packed = sm.compress(raw)
        assert sm.decompress(packed, 0)[0] == raw and len(packed) <= room, hex(addr)


def test_real_port_tables_follow_the_translated_rom(zt_sm, tmp_path):
    sm, data = zt_sm
    port_src = WORKSPACE / "port" / "sm_rewrite" / "src"
    if not port_src.is_dir():
        pytest.skip("sm_rewrite clone not on disk")
    for name in ("sm_85.h", "sm_8b.h", "ida_types.h"):
        (tmp_path / name).write_bytes((port_src / name).read_bytes())
    assert sm.patch_c_tables(port_src, tmp_path, data, data) == []
    rom = sm.Rom(data)
    texts = {it["id"]: it["text"] for g in json.loads(sm.dump_text(rom))["groups"] for it in g["items"]}
    sm.apply_text(rom, texts, dict(texts, **{"msg.01.EnergyTank": "UA TEST"}))
    assert sm.patch_c_tables(port_src, tmp_path, data, bytes(rom.data)) == ["sm_85.h:kEnergyTankMsgBoxTilemap"]
    assert "0x28f4, 0x28e0" in (tmp_path / "sm_85.h").read_text(encoding="utf-8")   # U A
