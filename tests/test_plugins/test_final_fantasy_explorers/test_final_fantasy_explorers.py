"""Final Fantasy Explorers plugin: the text codec (synthetic) and the real EUR game files (skipped where the
workspace is not on this machine).

Real data: both text tables load and save back byte for byte; both fonts open and pack back unchanged; pictures in the
layout archives read and write back unchanged.
"""
import json
import shutil
import struct
from pathlib import Path

import pytest

from core import font_formats
from core.containers.darc import DarcContainer
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.final_fantasy_explorers import textres
from plugins.final_fantasy_explorers.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Final Fantasy\Explorers")
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "final_fantasy_explorers"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _file(messages) -> bytes:
    out = bytearray(struct.pack("<I", len(messages) << 16 | 0x1000))
    for mid, text in messages:
        out += struct.pack("<I", mid) + text.encode("utf-16-le") + b"\0\0"
    return bytes(out) + b"\xff\xff\0\0"


def test_control_characters_show_as_tags_and_come_back():
    shown = textres.to_editor("\x01Hello\x05\nWorld\x0b")
    assert shown == "{c01}Hello{c05}\nWorld{c0B}"
    assert textres.from_editor(shown) == "\x01Hello\x05\nWorld\x0b"


def test_synthetic_file_round_trip_and_edit():
    raw = _file([(0xAABBCCDD, "One"), (1, "\x01Two\x05")])
    parsed = textres.TextRes(raw)
    assert parsed.ids == [0xAABBCCDD, 1] and parsed.texts == ["One", "\x01Two\x05"]
    assert parsed.build(parsed.texts) == raw
    edited = parsed.build(["Один", "\x01Two\x05"])
    assert textres.TextRes(edited).texts[0] == "Один"
    assert edited.endswith(b"\xff\xff\0\0")
    assert textres.TextRes(edited).ids == parsed.ids


def test_rules_save_keeps_unedited_messages_and_applies_edits():
    raw = _file([(5, "Yes"), (6, "\x01No\x05")])
    rules = GameRules()
    blocks, _ = rules.load_data_from_json_obj(raw)
    assert blocks == [["Yes", "{c01}No{c05}"]]
    assert rules.save_data_to_json_obj(blocks, {}) == raw
    blocks[0][1] = "{c01}Ні{c05}"
    assert textres.TextRes(rules.save_data_to_json_obj(blocks, {})).texts == ["Yes", "\x01Ні\x05"]


def test_bad_header_is_refused():
    with pytest.raises(ValueError):
        textres.TextRes(b"\x00" * 16)


def test_both_text_tables_save_back_byte_for_byte():
    counts = {}
    for name, expected in (("message_en", 6891), ("message_home_en", 5285)):
        raw = _need(SOURCE / "romfs" / "message" / f"{name}.textres").read_bytes()
        rules = GameRules()
        blocks, _ = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, {}) == raw, name
        counts[name] = len(blocks[0])
        assert counts[name] == expected
    assert counts


def test_both_fonts_open_and_pack_back_unchanged():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert [source.name for source in found] == ["font_localize.bcfnt", "font.bcfnt"]
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract("bcfnt", data)
        assert font_formats.pack("bcfnt", metadata, sheets, data) == data


def test_every_picture_kind_resolves_and_a_darc_member_writes_through(tmp_path):
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    real = _need(SOURCE) / "romfs"
    root = tmp_path / "source"            # a few files of each kind: resolving all 3,153 takes a minute
    for pattern in ("ui/*.darc", "gfx/*.cgfx", "gfx/*.ctpk"):
        for path in sorted(real.glob(pattern))[:3]:
            (root / "romfs" / path.parent.name).mkdir(parents=True, exist_ok=True)
            shutil.copy(path, root / "romfs" / path.parent.name / path.name)
    found = texture_sources.resolve(descriptors, {"source_path": str(root), "translation_path": str(tmp_path / "tr")})
    assert {"cgfx", "ctpk", "bflim"} <= {source.format for source in found}
    member = next(s for s in found if s.format == "bflim" and min(s.size) >= 16 and s.pixel_format in ("RGBA4", "ETC1A4"))
    image = member.read_original().image.copy()
    image.putpixel((0, 0), (255, 0, 0, 255))
    assert member.write(image) is True
    before = DarcContainer(Path(member.source_path).read_bytes())
    after = DarcContainer(Path(member.translation_path).read_bytes())
    assert after.list_files() == before.list_files()
    changed = [name for name in before.list_files() if after.read_file(name) != before.read_file(name)]
    assert changed == [member.member]
    assert member.read_current().image.getpixel((0, 0))[0] == 255
    for other in [s for s in found if s.source_path == member.source_path and s.key != member.key][:3]:
        assert other.read_current().image.tobytes() == other.read_original().image.tobytes()
