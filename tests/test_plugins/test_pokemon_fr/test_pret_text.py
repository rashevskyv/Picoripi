"""Pokémon generation III (pret decompilations): finding, showing and writing back the text of ``.inc`` / ``.s`` /
``.c`` / ``.h`` files; the plugin's load and save of such a file; real-data round trips of the workspaces."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from plugins.pokemon_fr import pret_context, pret_text
from plugins.pokemon_fr.rules import GameRules

ASM = (
    "LittlerootTown_EventScript_Boy::\n"
    "\tmsgbox LittlerootTown_Text_Boy, MSGBOX_NPC\n"
    "\tend\n"
    "\n"
    "LittlerootTown_Text_Boy:\n"
    '\t.string "Hello there!\\n"\n'
    '\t.string "I\'m {PLAYER}.\\p"\n'
    '\t.string "Bye!$"\n'
    "\n"
    "Name_Text: .string \"BOY$\"\n"
)
C_FILE = (
    '#include "global.h"\n'
    'static const u8 sName[] = _("BULBASAUR");\n'
    "static const u8 sText[] = _(\n"
    '    "First line\\n"\n'
    '    "second line$");\n'
    "static const struct Thing sThing = {\n"
    '    .name = _("OAK"),\n'
    "};\n"
    'static const u8 sAscii[] = __("COLOR WHITE");\n'
)
MAP_JSON = json.dumps({"object_events": [{"graphics_id": "OBJ_EVENT_GFX_BOY_2", "script": "LittlerootTown_EventScript_Boy"}],
                       "bg_events": [{"type": "sign", "script": "LittlerootTown_EventScript_Sign"}]})


def test_asm_units_are_one_message_per_label():
    units = pret_text.parse(ASM, True)
    assert [u.content for u in units] == ["Hello there!\\nI'm {PLAYER}.\\pBye!", "BOY"]
    assert [u.label for u in units] == ["LittlerootTown_Text_Boy", "Name_Text"]
    assert all(u.hidden_end for u in units)


def test_c_units_are_the_charmap_calls_only():
    units = pret_text.parse(C_FILE, False)
    assert [u.content for u in units] == ["BULBASAUR", "First line\\nsecond line", "OAK"]
    assert [u.label for u in units] == ["sName", "sText", "name"]


@pytest.mark.parametrize("text,asm", [(ASM, True), (C_FILE, False)])
def test_an_unchanged_file_is_written_back_as_it_was(text, asm):
    assert pret_text.write(text, asm, [u.content for u in pret_text.parse(text, asm)]) == text


def test_a_changed_asm_message_is_written_in_pret_style_in_place():
    new = pret_text.write(ASM, True, ["Привіт!\\nЯ {PLAYER}.\\pБувай \"друже\"!", None])
    assert new.endswith('Name_Text: .string "BOY$"\n')
    assert '\t.string "Привіт!\\n"\n\t.string "Я {PLAYER}.\\p"\n\t.string "Бувай \\"друже\\"!$"\n' in new
    assert [u.content for u in pret_text.parse(new, True)] == ['Привіт!\\nЯ {PLAYER}.\\pБувай \\"друже\\"!', "BOY"]


def test_a_changed_c_literal_keeps_its_shape():
    new = pret_text.write(C_FILE, False, [None, "Перший рядок\\nдругий рядок", "ОАК"])
    assert '_(\n    "Перший рядок\\n"\n    "другий рядок$")' in new and '.name = _("ОАК")' in new
    assert 'sName[] = _("BULBASAUR")' in new


def test_scripts_and_speakers_come_from_the_map_files():
    assert pret_text.references(ASM) == {"LittlerootTown_Text_Boy": ["LittlerootTown_EventScript_Boy"]}
    assert pret_context.speakers_of_scripts(MAP_JSON) == {"LittlerootTown_EventScript_Boy": ["Boy 2"],
                                                          "LittlerootTown_EventScript_Sign": ["Sign"]}


def test_the_plugin_loads_and_saves_a_decompilation_file(qapp):
    rules = GameRules(SimpleNamespace(show_multiple_spaces_as_dots=False, newline_display_symbol="↵"))
    blocks, names = rules.load_data_from_json_obj(ASM)
    assert names == {"0": "Text"} and blocks[0][1] == "BOY"
    assert rules.save_data_to_json_obj(blocks, names) == ASM
    blocks[0][1] = "ХЛОПЕЦЬ"
    context = SimpleNamespace(relative_path="data/maps/X/scripts.inc", existing_versions=lambda: iter([ASM.encode()]),
                              block_indices=[0], runtime_state=[])
    rules.prepare_save_context(context)
    assert rules.save_data_to_json_obj(blocks, names).endswith('Name_Text: .string "ХЛОПЕЦЬ$"\n')
    assert pret_text.SUFFIXES == (".inc", ".s", ".c", ".h")
    assert any(fmt.mode == "text" and ".inc" in fmt.extensions for fmt in rules.get_file_formats())


WORKSPACES = {"Ruby and Sapphire": "pokeruby", "FireRed and LeafGreen": "pokefirered", "Emerald": "pokeemerald"}


@pytest.mark.parametrize("game", list(WORKSPACES))
def test_every_text_file_of_the_decompilation_writes_back_and_edits_cleanly(game):
    root = Path(r"E:\Emulators\RomHacking\Pokemon") / game / "source"
    if not root.is_dir():
        pytest.skip(f"{root} is not on this machine")
    count = 0
    for path in root.rglob("*"):
        if path.suffix.lower() not in pret_text.SUFFIXES or not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", "surrogateescape")
        asm = pret_text.is_asm(path.name)
        units = pret_text.parse(text, asm)
        if not units:
            continue
        count += 1
        assert pret_text.write(text, asm, [u.content for u in units]) == text, path
        edited = [u.content + "x" for u in units]
        assert [u.content for u in pret_text.parse(pret_text.write(text, asm, edited), asm)] == edited, path
    assert count > 100


@pytest.mark.parametrize("game", list(WORKSPACES))
def test_the_font_and_picture_descriptors_resolve_in_a_decompilation_project(game):
    from core import font_formats, texture_formats
    from core.font_formats import sources as font_sources
    from core.texture_formats import sources as texture_sources

    root = Path(r"E:\Emulators\RomHacking\Pokemon") / game / "source"
    if not root.is_dir():
        pytest.skip(f"{root} is not on this machine")
    meta = {"source_path": str(root), "translation_path": str(root.parent / "translation"), "is_directory_mode": True}
    mw = SimpleNamespace(project_manager=SimpleNamespace(project=SimpleNamespace(metadata=meta)))
    rules = GameRules(mw)
    fonts = font_sources.resolve(rules.get_font_sources(), meta)
    assert len(fonts) >= 6
    for font in fonts:
        data = font.read_current()
        metadata, sheets = font_formats.extract(font.format, data, font.params)
        assert font_formats.pack(font.format, metadata, sheets, data, font.params) == data
    pictures = texture_sources.resolve(rules.get_texture_sources(), meta)
    assert len(pictures) > 200
    for picture in pictures[:40]:
        data = Path(picture.source_path).read_bytes()
        assert texture_formats.write(picture.format, data, {0: picture.read_current().image}, picture.params) == data
