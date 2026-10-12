"""Family plan of Link's Awakening DX: members, stable ids and recognition by content."""
import os
from pathlib import Path

import pytest

from plugins.zelda_ladx_hd import lng
from plugins.zelda_ladx_hd.rules import SEED_FILE, GameRules


def _translated_gbc(path: Path) -> Path:
    rom = bytearray(0x100000)
    rom[0x134:0x139] = b"ZELDA"
    rom[0x143] = 0x80
    path.write_bytes(bytes(rom))
    return path


def test_unknown_files_are_no_family(tmp_path):
    (tmp_path / "eng.lng").write_bytes(b"menu_start Start Game\r\n")
    (tmp_path / "other.gbc").write_bytes(bytes(0x100000))
    assert GameRules().family_plan([str(tmp_path / "eng.lng"), str(tmp_path / "other.gbc")]) is None
    assert GameRules().family_plan([str(tmp_path)]) is None


def test_translated_gbc_rom_is_the_base_member(tmp_path):
    rom = _translated_gbc(tmp_path / "game.gbc")
    plan = GameRules().family_plan([str(rom)], str(tmp_path))
    assert plan.base == "dx_gbc"
    assert [m.key for m in plan.members] == ["dx_gbc"]
    assert plan.link_method == "scene key match"
    assert plan.seed_path == str(tmp_path / SEED_FILE)


def _real_hd_folder() -> Path:
    root = os.environ.get("PICORIPI_ROMHACKING", "").strip()
    folder = Path(root) / "_new" / "Links Awakening DX HD" / "Data" / "Languages" if root else None
    if folder is None or not folder.is_dir():
        pytest.skip("PICORIPI_ROMHACKING is not set or the Links Awakening DX HD folder is missing")
    return folder


def test_real_hd_folder_is_the_hd_member():
    folder = _real_hd_folder()
    plan = GameRules().family_plan([str(folder)])
    assert plan.base == "dx_hd"
    assert [m.key for m in plan.members] == ["dx_hd"]
    expected = sum(len(lng.parse((folder / name).read_bytes()).entries()) for name in ("eng.lng", "dialog_eng.lng"))
    assert len(plan.read("dx_hd")) == expected
