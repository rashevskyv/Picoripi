"""Metal Gear Solid: Snake Eater 3D plugin: the subtitle file model (synthetic) and the real EU game files
(skipped where the workspace is not on this machine)."""
import json
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.font_formats import sources as font_sources
from core.texture_formats import sources as texture_sources
from plugins.metal_gear_solid_3d.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Metal Gear\Metal Gear Solid 3\3DS")
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "metal_gear_solid_3d"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _model(*lines: bytes) -> bytes:
    record = {"offset": 2048, "slot": 2048, "frame": 0,
              "lines": [{"start": i * 10, "end": i * 10 + 9, "speaker": 0, "hex": line.hex()} for i, line in enumerate(lines)]}
    return json.dumps({"format": "mgs3d-subtitles", "records": [record]}, indent=1).encode("utf-8")


def test_lines_decode_with_accents_and_line_breaks():
    raw = _model(b"Snake! Respond!\x80|SNAKE!!", b"Du wei\x1f`t", b"")
    rules = GameRules()
    blocks, _ = rules.load_data_from_json_obj(raw)
    assert blocks == [["Snake! Respond!\nSNAKE!!", "Du wei\xdft", ""]]


def test_unedited_file_is_written_back_unchanged_and_an_edit_keeps_the_line_break_style():
    raw = _model(b"Hello\x80|World", b"Plain")
    rules = GameRules()
    blocks, _ = rules.load_data_from_json_obj(raw)
    rules._model = json.loads(raw)
    assert rules.save_data_to_json_obj(blocks, {}) == raw
    blocks[0][0] = "Hi\nThere"
    saved = json.loads(rules.save_data_to_json_obj(blocks, {}))
    assert bytes.fromhex(saved["records"][0]["lines"][0]["hex"]) == b"Hi\x80|There"
    assert saved["records"][0]["lines"][1]["hex"] == b"Plain".hex()
    assert saved["records"][0]["lines"][0]["start"] == 0


def test_every_subtitle_file_loads_and_saves_back_byte_for_byte():
    folder = _need(SOURCE / "text")
    total = 0
    for name, count in (("vox", 3935), ("movie", 689), ("demo", 2254)):
        raw = (folder / f"{name}.mgssubs").read_bytes()
        rules = GameRules()
        blocks, _ = rules.load_data_from_json_obj(raw)
        rules._model = json.loads(raw)
        assert len(blocks[0]) == count, name
        assert rules.save_data_to_json_obj(blocks, {}) == raw, name
        total += count
    assert total == 6878


def test_every_font_opens_and_packs_back_unchanged():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    found = font_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    assert len(found) == 43
    for source in found:
        data = source.read_original()
        metadata, sheets = font_formats.extract("bcfnt", data)
        assert font_formats.pack("bcfnt", metadata, sheets, data) == data


def test_pictures_read_and_write_back():
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    found = texture_sources.resolve(descriptors, {"source_path": str(_need(SOURCE)), "translation_path": ""})
    files = sorted({source.source_path for source in found})
    assert len(files) >= 1000
    formats = set()
    for path in files[::12]:   # a full sweep of the 1,064 files is byte-exact (40 s)
        data = Path(path).read_bytes()
        textures = texture_formats.read("bflim", data)
        formats.update(texture.pixel_format for texture in textures)
        assert texture_formats.write("bflim", data, {i: t.image for i, t in enumerate(textures)}) == data, path
    assert formats
