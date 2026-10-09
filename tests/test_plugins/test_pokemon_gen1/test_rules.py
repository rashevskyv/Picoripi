"""Pokémon Red / Blue / Yellow plugin: asm text units, editing and saving back, context, fonts, real files."""
import io
import json
import re
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from plugins.pokemon_gen1 import asm_text
from plugins.pokemon_gen1 import rules as gen1
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "pokemon_gen1"
SAMPLE = """_PalletTownOakItsUnsafeText::
\ttext "OAK: It's unsafe!"
\tline "Wild #MON live"
\tcont "in tall grass!"

\tpara "You need your own"
\tline "#MON for your"
\tcont "protection."
\tdone

_SSTicketReceivedText::
\ttext "<PLAYER> received"
\tline "an @"
\ttext_ram wStringBuffer
\ttext "!@"
\ttext_end

MainMenuText:
\tdb   "CONTINUE"
\tnext "NEW GAME"
\tnext "OPTION@"

TypeNames:
\tli "NORMAL"
\tli "FIGHTING"
"""
WORKSPACES = [Path(r"E:\Emulators\RomHacking\Pokemon\Red and Blue"), Path(r"E:\Emulators\RomHacking\Pokemon\Yellow")]


def test_the_plugin_loads_round_trips_and_validates():
    check_loads(PLUGIN)
    check_round_trip(PLUGIN, SAMPLE)
    check_validator(PLUGIN)


def test_units_show_breaks_paragraphs_commands_and_names():
    assert asm_text.texts(SAMPLE) == [
        "OAK: It's unsafe!\nWild #MON live\nin tall grass!\n\nYou need your own\n#MON for your\nprotection.",
        "<PLAYER> received\nan @{text_ram wStringBuffer}!@",
        "CONTINUE\nNEW GAME\nOPTION@",
        "NORMAL",
        "FIGHTING",
    ]


def test_unchanged_text_saves_the_same_bytes():
    rules = check_loads(PLUGIN)
    blocks, _ = rules.load_data_from_json_obj(SAMPLE)
    assert rules.save_data_to_json_obj(blocks, {}) == SAMPLE.encode("utf-8")


def test_edited_text_is_written_in_the_decomp_style_and_parses_back():
    texts = asm_text.texts(SAMPLE)
    texts[0] = "ОАК: Тут небезпечно!\nУ траві живуть\nдикі #MON!\n\nТобі потрібен\nсвій #MON."
    texts[1] = "{text_ram wStringBuffer}: отримано!@"      # the name moved to the front
    texts[3] = "ЗВИЧАЙНИЙ"
    saved = asm_text.apply(SAMPLE, texts)
    assert '\ttext "ОАК: Тут небезпечно!"\n\tline "У траві живуть"\n\tcont "дикі #MON!"\n\n' \
           '\tpara "Тобі потрібен"\n\tline "свій #MON."\n\tdone\n' in saved
    assert "_SSTicketReceivedText::\n\ttext_ram wStringBuffer\n\ttext \": отримано!@\"\n\ttext_end\n" in saved
    assert '\tli "ЗВИЧАЙНИЙ"\n' in saved
    assert asm_text.texts(saved) == texts
    assert saved.endswith('\tli "FIGHTING"\n')


def test_a_break_takes_the_macro_of_its_place_and_other_macros_show_as_markers():
    unit = asm_text.parse("X::\n\ttext \"a\"\n\tcont \"b\"\n\tline \"c\"\n\tdone\n")[1][0]
    assert asm_text.to_editor(unit) == "a\n{cont}b\n{line}c"
    assert asm_text.from_editor("a\nb\nc\n\nd\ne", unit) == [
        ("text", "a"), ("line", "b"), ("cont", "c"), ("para", "d"), ("line", "e")]
    dex = asm_text.parse('D::\n\ttext "a"\n\tnext "b"\n\tpage "c"\n\tdex\n')[1][0]
    assert asm_text.from_editor("a\nb\n\nc\nd", dex) == [("text", "a"), ("next", "b"), ("page", "c"), ("next", "d")]


def test_quotes_and_backslashes_are_escaped():
    saved = asm_text.apply('\tdb "A"\n', ['say "hi" \\o/'])
    assert saved == '\tdb "say \\"hi\\" \\\\o/"\n'
    assert asm_text.texts(saved) == ['say "hi" \\o/']


def test_width_counts_codes_as_the_characters_they_print():
    assert gen1.text_width("ABC") == 24
    assert gen1.text_width("<PLAYER> got #!@") == (7 + 5 + 4 + 1) * 8
    assert gen1.text_width("a{text_ram wX}\nlonger") == 6 * 8


def test_png_texture_keeps_its_mode_and_the_game_boy_greys():
    image = Image.new("L", (8, 8), 255)
    stream = io.BytesIO()
    image.save(stream, "PNG")
    data = stream.getvalue()
    texture = texture_formats.read("png", data, {})[0]
    assert texture_formats.write("png", data, {0: texture.image}, {"levels": 4}) == data
    edited = texture.image.copy()
    edited.putpixel((0, 0), (100, 100, 100, 255))
    out = Image.open(io.BytesIO(texture_formats.write("png", data, {0: edited}, {"levels": 4})))
    assert out.mode == "L" and out.getpixel((0, 0)) == 85
    one = io.BytesIO()
    Image.new("1", (8, 8), 1).save(one, "PNG")
    out = Image.open(io.BytesIO(texture_formats.write("png", one.getvalue(), {0: edited}, {})))
    assert out.mode == "1"


def test_a_grid_font_takes_a_list_of_cells_with_tokens_and_free_cells():
    stream = io.BytesIO()
    Image.new("L", (16, 8), 255).save(stream, "PNG")
    metadata, _sheets = font_formats.extract("texture_grid", stream.getvalue(),
                                             {"texture": "png", "cell": [8, 8], "chars": ["<PK>", "Б"]})
    assert font_formats.char_map(metadata) == {"Б": 1}


class _Block:
    def __init__(self, path):
        self.source_file = path


class _Project:
    def __init__(self, root, files):
        self.blocks = [_Block(path) for path in files]
        self.metadata = {"source_path": str(root)}


class _ProjectManager:
    def __init__(self, root, project_dir, files):
        self.project = _Project(root, files)
        self.project_dir = str(project_dir)
        self._root = root

    def get_absolute_path(self, path):
        return str(Path(self._root, path))


class _Window:
    def __init__(self, pm):
        self.project_manager = pm
        self.block_to_project_file_map = {}


def test_context_names_the_speaker_the_map_and_the_source_line(tmp_path):
    source = tmp_path / "source"
    (source / "text").mkdir(parents=True)
    (source / "text" / "PalletTown.asm").write_text(SAMPLE, encoding="utf-8")
    (source / "data" / "pokemon").mkdir(parents=True)
    (source / "data" / "pokemon" / "names.asm").write_text('\tdname "BULBASAUR", NAME_LENGTH\n', encoding="utf-8")
    (tmp_path / "context.json").write_text(json.dumps({"labels": {"_PalletTownOakItsUnsafeText": {
        "map": "PalletTown", "speaker": "Oak", "script": "scripts/PalletTown.asm:191"}}}), encoding="utf-8")
    rules = gen1.GameRules(_Window(_ProjectManager(source, tmp_path, ["text/PalletTown.asm"])))
    assert rules.get_speaker_for_string(0, 0) == "Oak"
    assert rules.get_speaker_for_string(0, 1) is None
    scene = rules.get_scene_context_for_string(0, 0)
    assert scene["resource"] == "text/PalletTown.asm:2" and scene["candidate_actors"] == ["Oak"]
    assert "scripts/PalletTown.asm:191" in rules.get_ai_flow_context_for_string(0, 0)
    assert rules.get_ai_flow_group_for_string(0, 0) == rules.get_ai_flow_group_for_string(0, 1)
    assert rules.get_glossary_seed_entries() == [
        {"term": "BULBASAUR", "section": "Pokémon", "source_ref": "data/pokemon/names.asm:1"}]


# -- the workspaces' real files (skipped where they are not on disk) -------------------------------

@pytest.mark.parametrize("workspace", WORKSPACES, ids=["red_blue", "yellow"])
def test_real_files_load_and_save_back_unchanged(workspace):
    source = workspace / "source"
    if not (source / "text").is_dir():
        pytest.skip("workspace not unpacked")
    rules = check_loads(PLUGIN)
    strings = 0
    for path in source.rglob("*.asm"):
        if path.relative_to(source).parts[0] == "constants":
            continue
        raw = path.read_bytes()
        blocks, _ = rules.load_data_from_json_obj(raw)
        strings += len(blocks[0])
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path
    assert strings > 3500


@pytest.mark.parametrize("workspace", WORKSPACES, ids=["red_blue", "yellow"])
def test_real_fonts_and_pictures_write_back_byte_exact(workspace):
    source = workspace / "source"
    if not (source / "gfx" / "font" / "font.png").is_file():
        pytest.skip("workspace not unpacked")
    folder = Path(gen1.__file__).parent
    for font in json.loads((folder / "font_sources.json").read_text(encoding="utf-8")):
        data = (source / font["path"]).read_bytes()
        metadata, sheets = font_formats.extract(font["format"], data, font["params"])
        assert font_formats.pack(font["format"], metadata, sheets, data, font["params"]) == data
    assert font_formats.char_map(metadata)["┌"] == 25
    pictures = 0
    for entry in json.loads((folder / "texture_sources.json").read_text(encoding="utf-8")):
        for path in source.glob(entry["path"]):
            data = path.read_bytes()
            image = texture_formats.read(entry["format"], data, entry["params"])[0].image
            assert texture_formats.write(entry["format"], data, {0: image}, entry["params"]) == data
            pictures += 1
    assert pictures >= 15


@pytest.mark.parametrize("workspace", WORKSPACES, ids=["red_blue", "yellow"])
def test_font_cells_match_the_workspace_charmap(workspace):
    charmap = workspace / "source" / "constants" / "charmap.asm"
    if not charmap.is_file():
        pytest.skip("workspace not unpacked")
    chars = json.loads((Path(gen1.__file__).parent / "font_sources.json").read_text(encoding="utf-8"))[0]
    cells = chars["params"]["chars"]
    added = charmap.read_text(encoding="utf-8").split("; Ukrainian letters", 1)[1]
    for letter, code in re.findall(r'charmap "(.)", \$([0-9a-f]{2})$', added, re.M):
        assert cells[int(code, 16) - 0x80] == letter
