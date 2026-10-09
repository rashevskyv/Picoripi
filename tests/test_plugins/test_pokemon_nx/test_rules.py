"""Pokémon Sword/Shield + Legends: Arceus plugin: gfmsg codec, translation map; real-data round trips."""
import json
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats
from core.containers.sarc import Sarc
from core.texture_formats import sources as texture_sources
from plugins.pokemon_nx import gfmsg
from plugins.pokemon_nx.tags import describe
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "pokemon_nx"
PLUGIN_DIR = Path(__file__).parents[3] / "plugins" / PLUGIN
GAMES = {name: Path(r"E:\Emulators\RomHacking\Pokemon") / name / "source" for name in ("Sword and Shield", "Legends Arceus")}
LINES = {"Sword and Shield": (1106, 60588), "Legends Arceus": (322, 43704)}


def _dat(lines, flags=None) -> bytes:
    """A message file of ``lines`` (lists of UTF-16 words without the terminator), laid out as the game's."""
    table, body = bytearray(), bytearray()
    start = 4 + 8 * len(lines)
    for index, words in enumerate(lines):
        table += struct.pack("<iHH", start + len(body), len(words) + 1, (flags or [0] * len(lines))[index])
        key = (gfmsg.KEY_BASE + gfmsg.KEY_ADVANCE * index) & 0xFFFF
        body += struct.pack(f"<{len(words) + 1}H", *gfmsg._crypt([*words, 0], key))
        body += b"\0" * (-len(body) % 4)
    section = struct.pack("<I", start + len(body)) + table + body
    return struct.pack("<HHIII", 1, len(lines), len(section), 0, 0x10) + section


def _words(text: str):
    return list(struct.unpack(f"<{len(text)}H", text.encode("utf-16-le")))


SAMPLE = _dat([_words("Hello, ") + [0x10, 2, 0x0100, 0] + _words("!") + [0x10, 1, 0xBE01] + _words("\nBye"),
               [0xE305] + _words(" [x]"), [0x10, 2, 0xBDFF, 2]], flags=[4, 0, 0])


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_commands_icons_and_brackets_become_tags_and_back():
    message = gfmsg.MessageFile(SAMPLE)
    assert message.texts() == ["Hello, [VAR 0100(0000)]![VAR BE01]\nBye", "[E305] [005B]x[005D]", "[VAR BDFF(0002)]"]
    assert message.pack(message.words) == SAMPLE and message.build(message.texts()) == SAMPLE
    assert describe("[VAR BE01]").startswith("Next text box") and describe("[E305]")


def test_a_longer_line_moves_the_lines_after_it_and_keeps_the_flags():
    message = gfmsg.MessageFile(SAMPLE)
    texts = message.texts()
    texts[0] = texts[0].replace("Bye", "Goodbye, see you soon")
    again = gfmsg.MessageFile(message.build(texts))
    assert again.texts() == texts and again.flags == [4, 0, 0]


def test_other_files_are_not_taken_for_messages():
    with pytest.raises(gfmsg.FormatError):
        gfmsg.MessageFile(b"\x04\x00\x00\x00" + bytes(32))
    rules = load_rules(PLUGIN)
    assert rules.load_data_from_json_obj(b"AHTB" + bytes(16)) == ([[]], {})


def test_labels_come_from_the_tbl():
    table = b"AHTB" + struct.pack("<I", 2)
    for name in (b"msg_a", b"msg_bc"):
        table += struct.pack("<QH", 0x1234, len(name) + 1) + name + b"\0"
    assert gfmsg.read_labels(table) == ["msg_a", "msg_bc"] and gfmsg.read_labels(b"nope") == []


def test_letters_the_fonts_lack_are_saved_as_their_font_slots():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    blocks[0][1] = "Їжак і Ґава: Є, ґ, є"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert gfmsg.MessageFile(saved).texts()[1] == "Ïжак i Ъава: Э, ъ, э"
    again, _ = rules.load_data_from_json_obj(saved)
    assert again[0][1] == "Ïжак i Ґава: Є, ґ, є"       # look-alike Latin letters stay Latin when read back


# -- real data (the workspaces of both games) ---------------------------------------------------------


def _need(game: str) -> Path:
    if not (GAMES[game] / "bin" / "message" / "English").is_dir():
        pytest.skip(f"{game} workspace not on disk")
    return GAMES[game]


@pytest.mark.parametrize("game", list(GAMES))
def test_every_english_message_file_rebuilds_byte_exact(game):
    source = _need(game)
    files = sorted((source / "bin" / "message" / "English").rglob("*.dat"))
    rules = load_rules(PLUGIN)
    lines = 0
    for path in files:
        raw = path.read_bytes()
        message = gfmsg.MessageFile(raw)
        assert message.pack(message.words) == raw, path.name
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path.name
        assert len(gfmsg.read_labels(path.with_suffix(".tbl").read_bytes())) >= len(message.words)
        lines += len(message.words)
    assert (len(files), lines) == LINES[game]


@pytest.mark.parametrize("game", list(GAMES))
def test_every_font_packs_back_and_a_glyph_edit_reads_back(game):
    source = _need(game)
    entries = json.loads((PLUGIN_DIR / "font_sources.json").read_text(encoding="utf-8"))
    present = [e for e in entries if (source / e["path"]).is_file()]
    assert len(present) == {"Sword and Shield": 7, "Legends Arceus": 4}[game]
    for entry in present:
        data = (source / entry["path"]).read_bytes()
        params = entry.get("params", {})
        metadata, sheets = font_formats.extract(entry["format"], data, params)
        assert font_formats.pack(entry["format"], metadata, sheets, data, params) == data, entry["label"]
        grid = metadata["GLY1"][0]
        cell = (0, 0, grid["cell_width"], grid["cell_height"])
        before = sheets[0].crop(cell).tobytes()
        sheets[0].paste(Image.new("RGBA", (grid["cell_width"] - 4, grid["cell_height"] - 4), (255, 255, 255, 255)), (2, 2))
        packed = font_formats.pack(entry["format"], metadata, sheets, data, params)
        assert packed != data, entry["label"]
        assert font_formats.extract(entry["format"], packed, params)[1][0].crop(cell).tobytes() != before, entry["label"]


@pytest.mark.parametrize("game", list(GAMES))
def test_every_english_layout_texture_writes_back_and_a_logo_edit_lands_in_the_archive(game, tmp_path):
    source = _need(game)
    entries = json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
    found = texture_sources.resolve(entries, {"source_path": str(source), "translation_path": str(tmp_path),
                                              "is_directory_mode": True})
    assert len(found) == {"Sword and Shield": 1250, "Legends Arceus": 211}[game]
    assert all("not supported" not in item.pixel_format for item in found)
    for item in found[::25]:
        assert not item.write(item.read_current().image)            # an unchanged picture writes nothing
    logo = next(item for item in found if item.kind == "title_screen" and "_logo_" in item.name and "mask" not in item.name)
    image = logo.read_current().image.copy()
    image.paste(Image.new("RGBA", (64, 64), (255, 0, 0, 255)), (0, 0))
    assert logo.write(image)
    edited, original = Sarc(Path(logo.translation_path).read_bytes()), Sarc(Path(logo.source_path).read_bytes())
    changed = [name for name in original.files if edited.files[name] != original.files[name]]
    assert changed == [n for n in original.files if n.endswith(".bntx")]
    assert logo.read_current().image.getpixel((8, 8)) != logo.read_original().image.getpixel((8, 8))
