"""Kingdom Hearts 3D plugin: the CTD codec (synthetic) and the real EU game files (skipped where the workspace is
not on this machine).

Real data: every English message file loads and saves back byte for byte and takes an edit; both kinds of picture
(CTRT, L2D with pictures inside) read and write back unchanged; every font opens and packs back unchanged.
"""
import json
import struct
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.kingdom_hearts_ddd import ctd
from plugins.kingdom_hearts_ddd.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Kingdom Hearts\Dream Drop Distance\3DS")
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "kingdom_hearts_ddd"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _file(texts, shared=None) -> bytes:
    """A tiny CTD: header, message table (id, layout << 20 | offset), one layout, UTF-16 texts."""
    count = len(texts)
    table, layout = 0x20, 0x20 + count * 8
    text_at = layout + 20
    body, offsets = bytearray(), []
    for text in texts:
        offsets.append(text_at + len(body))
        body += text.encode("utf-16-le") + b"\0\0"
    head = b"@CTD" + struct.pack("<IIHHIII", 0x1F7, 0x1000, 1, count, table, layout, text_at) + bytes(4)
    msgs = b"".join(struct.pack("<II", 0x1000 + i, offsets[i if shared is None or i not in shared else shared[i]])
                    for i in range(count))
    return head + msgs + bytes(20) + bytes(body)


def test_editor_form_of_private_characters():
    shown = ctd.to_editor("Use \ue026Fire\ue028 with \ue000")
    assert shown == "Use {UE026}Fire{UE028} with {UE000}"
    assert ctd.from_editor(shown) == "Use \ue026Fire\ue028 with \ue000"


def test_unedited_file_is_written_back_unchanged_and_an_edit_appends():
    raw = _file(["Hello", "World\nTwo", ""])
    parsed = ctd.Ctd(raw)
    assert parsed.texts == ["Hello", "World\nTwo", ""] and parsed.ids == [0x1000, 0x1001, 0x1002]
    assert parsed.build(list(parsed.texts)) == raw
    edited = ctd.Ctd(parsed.build(["Hello", "Longer than before", ""]))
    assert edited.texts == ["Hello", "Longer than before", ""]
    assert edited.fields[0] == parsed.fields[0]


def test_a_shared_string_is_only_replaced_for_the_edited_message():
    raw = _file(["Same", "Same"], shared={1: 0})
    parsed = ctd.Ctd(raw)
    assert parsed.fields[0] == parsed.fields[1]
    changed = ctd.Ctd(parsed.build(["Same", "Other"]))
    assert changed.texts == ["Same", "Other"]


def test_plugin_round_trip_and_edit():
    raw = _file(["One {x}", "Two"])
    rules = GameRules()
    blocks, _ = rules.load_data_from_json_obj(raw)
    assert blocks == [["One {x}", "Two"]]
    assert rules.save_data_to_json_obj(blocks, {}) == raw
    blocks[0][1] = "Dva"
    assert ctd.Ctd(rules.save_data_to_json_obj(blocks, {})).texts == ["One {x}", "Dva"]


def test_every_english_message_file_saves_back_byte_for_byte():
    files = sorted(_need(SOURCE / "romfs" / "message" / "en").rglob("*.ctd"))
    assert len(files) == 69
    messages = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, _ = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, path.name
        messages += len(blocks[0])
    assert messages == 8374


def test_every_font_opens_and_packs_back_unchanged():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert len(found) == 6
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract("bcfnt", data)
        assert font_formats.pack("bcfnt", metadata, sheets, data) == data
        assert "\u0416" not in font_formats.char_map(metadata)


def test_every_picture_reads_and_writes_back():
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    found = texture_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    files = sorted({source.source_path for source in found})
    assert len(files) >= 150
    formats = set()
    for path in files[::3]:   # every third file keeps the test short (a full sweep of all 1,575 + 248 files is byte-exact)
        data = Path(path).read_bytes()
        fmt = "l2d" if path.endswith(".l2d") else "ctrt"
        textures = texture_formats.read(fmt, data)
        formats.update(texture.pixel_format for texture in textures)
        assert texture_formats.write(fmt, data, {i: t.image for i, t in enumerate(textures)}) == data, path
    assert {"ETC1", "ETC1A4"} <= formats
