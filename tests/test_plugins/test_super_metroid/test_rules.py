"""Super Metroid (sm_rewrite PC port) plugin: text.json round trip, cells, context, real fonts, textures and ROM text."""
import hashlib
import json
import shutil
import sys

import pytest

import romhacking_root
from core import font_formats, texture_formats
from plugins.super_metroid import rules as sm_rules
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "super_metroid"
# Under the RomHacking root. The real-file checks are verified against one ROM dump and one sm.py: a changed
# input skips its checks with the reason (re-verify, then update the pin).
SM = ("Metroid", "Super Metroid")
SCRIPT_FILE = ("_shared", "scripts", "zt", "sm.py")
ROM_SHA256 = "12b77c4bc9c1832cee8881244659065ee1d84c70c3d29e6eaf92e6798cc2ca72"   # Super Metroid (Japan, USA) (En,Ja)
SM_PY_SHA256 = "d2e0cf99e85d46d4d362836978879164c3f709a471d65646b017da6c90d471d4"
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

needs_source = romhacking_root.needs((*SM, "source", "text.json"))


@needs_source
def test_real_text_saves_back_unchanged(tmp_path):
    copy = tmp_path / "text.json"                  # the test reads its own copy: the workspace file may be edited meanwhile
    shutil.copy(romhacking_root.path(*SM, "source", "text.json"), copy)
    rules = check_loads(PLUGIN)
    text = copy.read_text(encoding="utf-8")
    blocks, names = rules.load_data_from_json_obj(text)
    assert any(blocks)
    assert rules.save_data_to_json_obj(blocks, names) == text


@needs_source
def test_real_fonts_and_textures_open_and_pack_back_unchanged():
    rules = check_loads(PLUGIN)
    for font in rules.get_font_sources():
        data = romhacking_root.path(*SM, "source", font["path"]).read_bytes()
        metadata, sheets = font_formats.extract(font["format"], data, font["params"])
        assert font_formats.pack(font["format"], metadata, sheets, data, font["params"]) == data, font["label"]
    for texture in rules.get_texture_sources():
        data = romhacking_root.path(*SM, "source", texture["path"]).read_bytes()
        images = texture_formats.read(texture["format"], data, texture["params"])
        assert texture_formats.write(texture["format"], data, {0: images[0].image}, texture["params"]) == data
    bg3 = rules.get_font_sources()[0]
    assert all(ch in bg3["params"]["chars"] for ch in "БГҐДЄЖЗИЇЙЛПУФЦЧШЩЬЮЯ")


def _sm_py_pinned() -> None:
    """Skip when sm.py is not the file these checks were verified against."""
    if hashlib.sha256(romhacking_root.path(*SCRIPT_FILE).read_bytes()).hexdigest() != SM_PY_SHA256:
        pytest.skip("sm.py changed since these checks were verified: re-verify, then update SM_PY_SHA256")


@pytest.fixture(scope="module")
def zt_sm():
    reason = romhacking_root.missing(*SCRIPT_FILE) or romhacking_root.missing(*SM, "ISO", "USA")
    if reason:
        pytest.skip(reason)
    scripts = romhacking_root.path("_shared", "scripts")
    sys.path.insert(0, str(scripts))
    try:
        from zt import sm
        data = sm.rom_bytes(romhacking_root.path(*SM))
    finally:
        sys.path.remove(str(scripts))
    if hashlib.sha256(data).hexdigest() != ROM_SHA256:
        pytest.skip("the Super Metroid ROM is not the dump these checks were verified with")
    return sm, data


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
    for addr in [a for a, _ in sm.OPTIONS] + [sm.CREDITS, sm.PROLOGUE, sm.GFX["intro_font"][0], sm.GFX["ending_font"][0]]:
        raw, room = sm.decompress(data, sm.lo(addr))
        packed = sm.compress(raw)
        assert sm.decompress(packed, 0)[0] == raw and len(packed) <= room, hex(addr)


def test_real_port_tables_follow_the_translated_rom(zt_sm, tmp_path):
    sm, data = zt_sm
    port_src = romhacking_root.path(*SM, "port", "sm_rewrite", "src")
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


# -- the intro fonts: story pages (green, 8x8) and the first screen (white, 8x16) share intro_font.bin -------------

def _font(rules, part: str) -> dict:
    return next(f for f in rules.get_font_sources() if part in f["label"])


def _tile_image(data: bytes, tile: int):
    """One 8x8 tile of intro_font.bin as the texture reader draws it."""
    params = {"pixel_format": "snes:2bpp", "offset": 0, "width": 128, "height": 8 * (len(data) // 16 // 16)}
    sheet = texture_formats.read("raw", data, params)[0].image.convert("RGBA")
    x, y = tile % 16 * 8, tile // 16 * 8
    return sheet.crop((x, y, x + 8, y + 8))


def test_the_game_fonts_are_listed_one_by_one_and_intro_is_two_fonts():
    rules = check_loads(PLUGIN)
    labels = [f["label"] for f in rules.get_font_sources()]
    assert len(labels) == len(set(labels)) == 9
    assert [part for part in ("Message boxes", "HUD numbers", "small letters", "big letters (top",
                              "Pause screen", "Intro story", "Intro first screen", "Credits: job", "Credits: names")
            if not any(part in label for label in labels)] == []
    story, prologue = _font(rules, "Intro story"), _font(rules, "Intro first screen")
    assert story["path"] == prologue["path"] == "gfx/intro_font.bin"
    assert story["font_map"] != prologue["font_map"]
    # the big letters start at tile 0x30 (offset 0x300), their top and bottom tiles are 16 cells apart
    assert prologue["params"]["cell"] == [8, 16] and prologue["params"]["texture_params"]["offset"] == 0x30 * 16
    assert story["params"]["cell"] == [8, 8] and story["params"]["texture_params"]["offset"] == 0
    assert story["params"]["texture_params"]["height"] // 8 * 16 == 0x30   # tiles 0..0x2F only


def test_real_intro_fonts_show_every_letter_the_text_uses_as_a_whole_glyph(zt_sm):
    sm, data = zt_sm
    _sm_py_pinned()
    rules = check_loads(PLUGIN)
    raw = sm.gfx_source(data, "intro_font")
    story, prologue = _font(rules, "Intro story"), _font(rules, "Intro first screen")
    _meta, (s_sheet,) = font_formats.extract(story["format"], raw, story["params"])
    _meta, (p_sheet,) = font_formats.extract(prologue["format"], raw, prologue["params"])
    for tile, ch in sm.FONTS["intro"].chars.items():
        if ch != " ":
            assert story["params"]["chars"][tile] == ch
            assert s_sheet.convert("RGBA").crop((tile % 16 * 8, tile // 16 * 8, tile % 16 * 8 + 8, tile // 16 * 8 + 8)
                                                ).tobytes() == _tile_image(raw, tile).tobytes()
    letters = prologue["params"]["chars"]
    for (top, bottom), ch in sm.FONTS["prologue"].chars.items():
        if ch in " .":
            continue
        cell = letters.index(ch)
        box = (cell % 16 * 8, cell // 16 * 16)
        glyph = p_sheet.convert("RGBA").crop((box[0], box[1], box[0] + 8, box[1] + 16))
        assert glyph.crop((0, 0, 8, 8)).tobytes() == _tile_image(raw, top).tobytes(), ch
        assert glyph.crop((0, 8, 8, 16)).tobytes() == _tile_image(raw, bottom).tobytes(), ch


def test_an_edited_intro_glyph_lands_in_the_built_rom_and_the_other_intro_font_keeps_its_edit(zt_sm, tmp_path):
    sm, data = zt_sm
    _sm_py_pinned()
    rules = check_loads(PLUGIN)
    ws = tmp_path / "ws"
    (ws / "source" / "gfx").mkdir(parents=True)
    (ws / "translation" / "gfx").mkdir(parents=True)
    (ws / "source" / "text.json").write_text(sm.dump_text(sm.Rom(data)), encoding="utf-8")
    for name in sm.GFX:
        (ws / "source" / "gfx" / f"{name}.bin").write_bytes(sm.gfx_source(data, name))
    target = ws / "translation" / "gfx" / "intro_font.bin"
    raw = (ws / "source" / "gfx" / "intro_font.bin").read_bytes()
    story, prologue = _font(rules, "Intro story"), _font(rules, "Intro first screen")

    def edit(entry: dict, current: bytes, copy_from: str, onto: str, width: int, height: int) -> bytes:
        """The font editor's save: copy the shape of one existing glyph onto another cell, pack back."""
        chars = entry["params"]["chars"]
        meta, (sheet,) = font_formats.extract(entry["format"], current, entry["params"])
        src, dst = chars.index(copy_from), chars.index(onto)
        cols = 16

        def box(cell):
            return (cell % cols * width, cell // cols * height, cell % cols * width + width, cell // cols * height + height)
        sheet = sheet.copy()
        sheet.paste(sheet.crop(box(src)), box(dst))
        return font_formats.pack(entry["format"], meta, [sheet], current, entry["params"])

    after_prologue = edit(prologue, raw, "B", "A", 8, 16)         # "A" of the first screen now looks like "B"
    target.write_bytes(after_prologue)
    after_both = edit(story, target.read_bytes(), "B", "A", 8, 8)  # the story font's "A", on top of the saved file
    assert after_both != after_prologue != raw
    target.write_bytes(after_both)
    rom, _texts, sheets = sm.build_rom(ws, data)
    assert sheets == ["intro_font"]
    built, _ = sm.decompress(rom, sm.lo(0x95D089))
    original = sm.gfx_bytes(data, "intro_font")
    tile = lambda blob, n: blob[n * 16:(n + 1) * 16]       # noqa: E731
    assert tile(built, 0x30) == tile(original, 0x31) and tile(built, 0x40) == tile(original, 0x41)   # first screen A
    assert tile(built, 0x00) == tile(original, 0x01)                                                  # story A
    assert tile(built, 0x01) == tile(original, 0x01) and tile(built, 0x31) == tile(original, 0x31)
    assert built[0x50 * 16:] == original[0x50 * 16:] and len(built) == len(original)


def test_real_rom_the_first_screen_text_is_an_item_and_moves_to_free_space_when_it_no_longer_fits(zt_sm, tmp_path):
    sm, data = zt_sm
    rom = sm.Rom(data)
    texts = {it["id"]: it["text"] for g in json.loads(sm.dump_text(rom))["groups"] for it in g["items"]}
    assert texts["intro.prologue"] == "THE LAST METROID IS IN\nCAPTIVITY. THE GALAXY\nIS AT PEACE..."
    names = [it["id"] for g in json.loads(sm.dump_text(rom))["groups"] if g["name"] == "Intro" for it in g["items"]]
    assert names == [f"intro.page{n}" for n in range(1, 7)] + ["intro.prologue"]   # appended: old positions kept
    assert sm.prologue_address(data) == sm.PROLOGUE
    # a text that packs into the original 226 bytes stays where it is
    same_size = "THE LAST METROID IS IN\nCAPTIVITY. THE GALAXY\nIS AT PEACE.."
    assert sm.apply_text(rom, texts, dict(texts, **{"intro.prologue": same_size})) == ["intro.prologue"]
    assert sm.prologue_address(rom.data) == sm.PROLOGUE
    # a text with more distinct letters does not: the block goes to bank 8C and the ROM code follows it
    rom = sm.Rom(data)
    new = "UA TEST IS A LONGER LINE\nCAPTIVITY. THE GALAXY\nIS AT PEACE..."
    assert sm.apply_text(rom, texts, dict(texts, **{"intro.prologue": new})) == ["intro.prologue"]
    moved = bytes(rom.data)
    assert len(moved) == len(data) and sm.prologue_address(moved) == sm.PROLOGUE_SPACE[0]
    again = {it["id"]: it["text"] for g in json.loads(sm.dump_text(sm.Rom(moved)))["groups"] for it in g["items"]}
    assert again["intro.prologue"] == new
    assert all(again[k] == v for k, v in texts.items() if k != "intro.prologue")
    raw, room = sm.decompress(data, sm.lo(sm.PROLOGUE))
    assert len(sm.compress(raw)) <= room                      # the unchanged block still fits as it was
    diff = [i for i in range(len(data)) if data[i] != moved[i]]
    spaces = [sm.lo(a) for a in sm.PROLOGUE_SPACE]
    assert all(spaces[0] <= i < spaces[1] or sm.PROLOGUE_CODE <= i < sm.PROLOGUE_CODE + 8 or sm.lo(sm.PROLOGUE) <= i
               < sm.lo(sm.PROLOGUE) + 226 for i in diff)
    # the port's C literal follows the moved block
    c_file = tmp_path / "sm_8b.c"
    c_file.write_text("a;\n  DecompressToMem(0x978d12, g_ram + 0x1e000);\n  DecompressToMem(0x978ADB, g_ram);\n",
                      encoding="utf-8")
    assert sm.patch_prologue_pointer(c_file, data, data) is False
    assert sm.patch_prologue_pointer(c_file, data, moved) is True
    assert c_file.read_text(encoding="utf-8").count(f"DecompressToMem(0x{sm.PROLOGUE_SPACE[0]:06x}, g_ram + 0x1e000)") == 1
    assert "0x978ADB" in c_file.read_text(encoding="utf-8")
