"""Tests for multi-language unpacked ROM reference loading in core and zelda_bmg plugin."""
from pathlib import Path
from typing import List, Optional

from bmg_tool import BMGFile, BMGMessage
from core.reference_manager import ReferenceManager
from plugins.base_game_rules import BaseGameRules
from plugins.zelda_bmg.reference import (
    load_zelda_bmg_multi_reference,
)
from plugins.zelda_bmg.rules import GameRules as ZeldaBmgRules


def _create_mock_bmg_file(path: Path, messages: List[str], encoding: str = "cp1252"):
    """Helper to write a mock BMG file."""
    bmg = BMGFile()
    bmg_messages = []
    for text in messages:
        # BMG tool expects text in cp1252 parts
        if encoding == "cp1251":
            # Russian text packed as cp1251 bytes into cp1252 string
            raw_bytes = text.encode("cp1251")
            part = raw_bytes.decode("cp1252")
        else:
            part = text
        msg = BMGMessage(info=b"\x00\x00\x00\x00", parts=[part])
        bmg_messages.append(msg)
    bmg.messages = bmg_messages
    bmg.encoding = "cp1252"
    path.write_bytes(bmg.save())


def test_zelda_bmg_multi_reference_unpacked_rom(tmp_path: Path):
    """Test detecting Msguk as Russian (cp1251) and Msgde as German (cp1252)."""
    # Structure: tmp_path / root / res / Msguk, Msgde
    res_dir = tmp_path / "root" / "res"
    msg_uk = res_dir / "Msguk"
    msg_de = res_dir / "Msgde"
    msg_fr = res_dir / "Msgfr"
    msg_uk.mkdir(parents=True)
    msg_de.mkdir(parents=True)
    msg_fr.mkdir(parents=True)

    _create_mock_bmg_file(msg_uk / "zel_00.bmg", ["Привет мир", "Линк, проснись!"], encoding="cp1251")
    _create_mock_bmg_file(msg_de / "zel_00.bmg", ["Hallo Welt", "Aufwachen, Link!"], encoding="cp1252")
    _create_mock_bmg_file(msg_fr / "zel_00.bmg", ["Bonjour le monde", "Réveille-toi, Link !"], encoding="cp1252")

    rules = ZeldaBmgRules()
    block_names = {"0": "zel_00"}

    multi_data = load_zelda_bmg_multi_reference(tmp_path, block_names=block_names, game_rules=rules)

    assert "Russian (RU)" in multi_data
    assert "German (DE)" in multi_data
    assert "French (FR)" in multi_data

    assert multi_data["Russian (RU)"][(0, 0)] == "Привет мир"
    assert multi_data["Russian (RU)"][(0, 1)] == "Линк, проснись!"

    assert multi_data["German (DE)"][(0, 0)] == "Hallo Welt"
    assert multi_data["German (DE)"][(0, 1)] == "Aufwachen, Link!"

    assert multi_data["French (FR)"][(0, 0)] == "Bonjour le monde"
    assert multi_data["French (FR)"][(0, 1)] == "Réveille-toi, Link !"


def test_zelda_bmg_multi_reference_msg_folder_and_siblings(tmp_path: Path):
    """Test pointing directly to Msg folder detects Russian (cp1251) and sibling European languages."""
    res_dir = tmp_path / "files" / "res"
    msg_ru = res_dir / "Msg"
    msg_de = res_dir / "Msgde"
    msg_fr = res_dir / "Msgfr"
    msg_it = res_dir / "Msgit"
    msg_sp = res_dir / "Msgsp"
    for d in (msg_ru, msg_de, msg_fr, msg_it, msg_sp):
        d.mkdir(parents=True)

    _create_mock_bmg_file(
        msg_ru / "zel_00.bmg",
        ["Но уже всё, поздно, хватит болтать.", "Я направил несколько воронов"],
        encoding="cp1251",
    )
    _create_mock_bmg_file(msg_de / "zel_00.bmg", ["Es ist zu spät.", "Ich habe Krähen geschickt."], encoding="cp1252")
    _create_mock_bmg_file(msg_fr / "zel_00.bmg", ["Il est trop tard.", "J'ai envoyé des corbeaux."], encoding="cp1252")
    _create_mock_bmg_file(msg_it / "zel_00.bmg", ["Ormai è tardi.", "Ho mandato dei corvi."], encoding="cp1252")
    _create_mock_bmg_file(msg_sp / "zel_00.bmg", ["Ya es tarde.", "Envié unos cuervos."], encoding="cp1252")

    rules = ZeldaBmgRules()
    block_names = {"0": "zel_00"}

    # Pass msg_ru (the Msg folder directly) as patch_path
    multi_data = load_zelda_bmg_multi_reference(msg_ru, block_names=block_names, game_rules=rules)

    assert "Russian (RU)" in multi_data
    assert "German (DE)" in multi_data
    assert "French (FR)" in multi_data
    assert "Italian (IT)" in multi_data
    assert "Spanish (ES)" in multi_data

    # Ensure no mojibake
    assert multi_data["Russian (RU)"][(0, 0)] == "Но уже всё, поздно, хватит болтать."
    assert multi_data["Russian (RU)"][(0, 1)] == "Я направил несколько воронов"
    assert multi_data["German (DE)"][(0, 0)] == "Es ist zu spät."
    assert multi_data["Italian (IT)"][(0, 0)] == "Ormai è tardi."
    assert multi_data["Spanish (ES)"][(0, 0)] == "Ya es tarde."


def test_bmg_file_load_override_encoding(tmp_path: Path):
    """Test that BMGFile.load with override_encoding parses cp1251 directly without mojibake."""
    bmg_path = tmp_path / "test.bmg"
    _create_mock_bmg_file(bmg_path, ["Но уже всё, поздно, хватит болтать."], encoding="cp1251")

    # Load with override_encoding="cp1251"
    bmg = BMGFile()
    bmg.load(bmg_path.read_bytes(), override_encoding="cp1251")
    assert bmg.encoding == "cp1251"
    assert len(bmg.messages) == 1
    assert bmg.messages[0].parts[0] == "Но уже всё, поздно, хватит болтать."


def test_reference_manager_load_multi_reference_delegation(tmp_path: Path):
    """Test ReferenceManager delegating multi-reference loading to rules."""
    class DummyMultiRules(BaseGameRules):
        def supports_reference_patch(self) -> bool:
            return True

        def load_multi_reference(self, patch_path: str, block_names: Optional[List[str]] = None):
            return {
                "Russian (RU)": {(0, 0): "Привет"},
                "German (DE)": {(0, 0): "Hallo"},
            }

    rules = DummyMultiRules()
    res = ReferenceManager.load_multi_reference(tmp_path, block_names={"0": "zel_00"}, game_rules=rules)
    assert "Russian (RU)" in res
    assert "German (DE)" in res
    assert res["Russian (RU)"] == {(0, 0): "Привет"}

    # Also test load_reference returning primary Russian (RU)
    primary = ReferenceManager.load_reference(tmp_path, block_names={"0": "zel_00"}, game_rules=rules)
    assert primary == {(0, 0): "Привет"}


def test_base_game_rules_fallback_to_single_reference(tmp_path: Path):
    """Test that BaseGameRules wraps single reference in dict when load_multi_reference is not overridden."""
    class DummySingleRules(BaseGameRules):
        def supports_reference_patch(self) -> bool:
            return True

        def get_reference_language_label(self) -> str:
            return "Italian (IT)"

        def load_reference_patch(self, patch_path: str, block_names: Optional[List[str]] = None):
            return {(0, 0): "Ciao mondo"}

    rules = DummySingleRules()
    res = ReferenceManager.load_multi_reference(tmp_path, block_names={"0": "zel_00"}, game_rules=rules)
    assert "Italian (IT)" in res
    assert res["Italian (IT)"] == {(0, 0): "Ciao mondo"}

    primary = ReferenceManager.load_reference(tmp_path, block_names={"0": "zel_00"}, game_rules=rules)
    assert primary == {(0, 0): "Ciao mondo"}


def test_zelda_bmg_multi_reference_deep_nested_scan(tmp_path: Path):
    """Test discovering Msg folders placed arbitrarily deep inside subdirectories (e.g. PAL_RU/P-GZ2P/files/res)."""
    deep_res = tmp_path / "EUR_PAL" / "P-GZ2P" / "files" / "res"
    msg_uk = deep_res / "Msguk"
    msg_de = deep_res / "Msgde"
    msg_uk.mkdir(parents=True)
    msg_de.mkdir(parents=True)

    # Also have an unrelated Msgus at another branch to test Msguk priority for PAL Russian
    other_branch = tmp_path / "ENG_NTSC" / "root" / "res" / "Msgus"
    other_branch.mkdir(parents=True)

    _create_mock_bmg_file(msg_uk / "zel_00.bmg", ["PAL Російський текст"], encoding="cp1251")
    _create_mock_bmg_file(other_branch / "zel_00.bmg", ["NTSC Російський текст"], encoding="cp1251")
    _create_mock_bmg_file(msg_de / "zel_00.bmg", ["Deutscher Text"], encoding="cp1252")

    rules = ZeldaBmgRules()
    block_names = {"0": "zel_00"}

    # Pass the top-level tmp_path (parent of both EUR_PAL and ENG_NTSC)
    multi_data = load_zelda_bmg_multi_reference(tmp_path, block_names=block_names, game_rules=rules)

    assert "Russian (RU)" in multi_data
    assert "German (DE)" in multi_data
    # Msguk should take precedence over Msgus in PAL multi-language context
    assert multi_data["Russian (RU)"][(0, 0)] == "PAL Російський текст"
    assert multi_data["German (DE)"][(0, 0)] == "Deutscher Text"
