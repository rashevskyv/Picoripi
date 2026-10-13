"""Layton's Mystery Journey: Deluxe Edition (Switch) keeps loose RomFS files in the 3DS formats (IMGN pictures, XF fonts)."""
import romhacking_root
import json
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from plugins.layton_3ds import xscr
from plugins.layton_3ds.rules import folder_of

PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "layton_3ds"
SOURCE = romhacking_root.under('Professor Layton\\Mystery Journey\\Switch\\source')


def test_us_spelling_folder_is_the_chapter():
    assert folder_of("_us/txt/en/40/40_000001.xs") == "40"
    assert folder_of("txt/en/18/18_180101.xs") == "18"
    assert folder_of("res/lt6_def.xs") == "res"


def test_switch_fonts_and_pictures_are_listed():
    fonts = [entry["path"] for entry in json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))]
    assert {"fnt/[na]/nrm.xf", "fnt/[eu]/lrg.xf"} <= set(fonts)
    pictures = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    paths = {p for entry in pictures for p in ([entry["path"]] if isinstance(entry["path"], str) else entry["path"])}
    assert {"menu/en/nx/*.xa", "_us/menu/en/*.xa", "_us/chr/en/*.xi"} <= paths


def _files(pattern):
    return sorted(SOURCE.glob(pattern))[:6] if SOURCE.is_dir() else []


def test_real_switch_scripts_save_back_unchanged():
    files = _files("txt/en/0*/*.xs") + _files("_us/txt/en/*/*.xs") + _files("res/lt6_def.xs")
    if not files:
        pytest.skip("the Switch workspace is not unpacked")
    for path in files:
        raw = path.read_bytes()
        script = xscr.parse(raw, "utf-8")
        assert script.build(script.texts()) == raw, path


def test_real_switch_pictures_and_fonts_round_trip():
    pictures = _files("chr/en/*.xi") + _files("menu/en/nx/*.xi")
    fonts = _files("fnt/[[]eu[]]/*.xf") + _files("fnt/[[]na[]]/*.xf")
    if not pictures or not fonts:
        pytest.skip("the Switch workspace is not unpacked")
    for path in pictures:
        raw = path.read_bytes()
        textures = texture_formats.read("imgc", raw)
        assert texture_formats.write("imgc", raw, {i: t.image for i, t in enumerate(textures)}) == raw, path
    for path in fonts:
        raw = path.read_bytes()
        meta, sheets = font_formats.extract("xf", raw, {})
        assert font_formats.pack("xf", meta, sheets, raw, {}) == raw, path
