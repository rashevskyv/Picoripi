"""Skyward Sword on the user's own dumps (skipped without them): every English MSBT of HD 1.0.1 and Wii USA
saves back byte for byte, every archive repacks byte for byte, every font packs back unchanged and takes a
new letter, and the HD's official Russian fills a Wii project by label."""
from pathlib import Path

import pytest

from core import font_formats
from core.containers.u8_container import U8Container
from core.font_formats import bcfnt
from plugins.common.msbt import Msbt
from plugins.zelda_sshd import reference
from plugins.zelda_sshd.rules import GameRules

HD = Path(r"E:\Emulators\RomHacking\ZELDA\SSHD_UA")
WII = Path(r"E:\Emulators\RomHacking\ZELDA\SS_UA")


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} not found")
    return path


@pytest.mark.parametrize("workspace", [HD, WII], ids=["hd", "wii"])
def test_every_english_message_file_saves_back_byte_for_byte(workspace):
    files = sorted(_need(workspace / "source").rglob("*.msbt"))
    assert len(files) > 100
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path


def test_every_archive_repacks_byte_for_byte():
    archives = sorted(_need(HD / "romfs").rglob("*.arc"))
    for path in archives:
        raw = path.read_bytes()
        container = U8Container(raw)
        for member in container.list_files():
            container.write_file(member, container.read_file(member))
        assert container.pack() == raw, path


def test_every_font_packs_back_and_takes_a_new_letter():
    fonts = sorted(_need(HD / "romfs" / "US" / "Font").rglob("*.brfnt"))
    fonts += sorted(p for p in (WII / "source").rglob("*.brfnt")) if WII.exists() else []
    for path in fonts:
        raw = path.read_bytes()
        assert font_formats.detect(raw) == "brfnt"
        metadata, sheets = font_formats.extract("brfnt", raw, {"min_sheets": 1})
        assert font_formats.pack("brfnt", metadata, sheets, raw) == raw, path
    raw = (HD / "romfs" / "US" / "Font" / "en_US" / "special_00.brfnt").read_bytes()
    metadata, sheets = font_formats.extract("brfnt", raw, {"min_sheets": 2})
    chars = font_formats.char_map(metadata)
    gly = metadata["GLY1"][0]
    per_sheet = gly["glyph_horizontal_count"] * gly["glyph_vertical_count"]
    glyph = per_sheet            # the first cell of the blank sheet
    sheets[1].paste((255, 255, 255, 255), (2, 2, 20, 40))
    metadata["WID1"][0]["packets"][glyph] = {"kerning": 0, "width": 22}
    pairs = [(font_formats.char_code(c), g) for c, g in chars.items()] + [(ord("Ґ"), glyph)]
    metadata["MAP1"] = [font_formats.map_entries(pairs)]
    packed = font_formats.pack("brfnt", metadata, sheets, raw, {"min_sheets": 2})
    info = bcfnt._info(packed)
    assert info["sheets"] == 2
    assert bcfnt._codes(bcfnt._cmap_blocks(packed, info))[ord("Ґ")] == glyph
    assert bcfnt._widths(packed, info)[glyph] == (0, 20, 22)
    again, again_sheets = font_formats.extract("brfnt", packed)
    assert again_sheets[0].tobytes() == sheets[0].tobytes()


def test_the_hd_russian_fills_a_wii_project_by_label():
    romfs = _need(HD / "romfs")
    story = sorted(_need(WII / "source" / "US" / "Object" / "en_US").rglob("*.msbt"))
    blocks = {index: (path.relative_to(WII / "source").as_posix(), Msbt(path.read_bytes()).labels)
              for index, path in enumerate(story)}
    found = reference.load_languages(romfs, blocks)
    assert next(iter(found)) == "Russian (RU)"
    lines = sum(len(labels) for _path, labels in blocks.values())
    assert len(found["Russian (RU)"]) / lines > 0.99
