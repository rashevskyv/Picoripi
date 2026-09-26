"""Tests for core.reference_manager and plugins.zelda_bmg.reference."""
import json
from pathlib import Path
from core.reference_manager import ReferenceManager
from plugins.base_game_rules import BaseGameRules
from plugins.zelda_bmg.reference import _extract_bmg_messages
from plugins.zelda_bmg.rules import GameRules as ZeldaBmgRules
from bmg_tool import BMGFile, BMGMessage


def test_reference_patch_path_get_set(tmp_path: Path):
    """Test reading and writing reference_patch_path in project_settings.json."""
    project_dir = tmp_path / "test_proj"
    project_dir.mkdir()

    assert ReferenceManager.get_reference_patch_path(project_dir) is None

    patch_path = "E:/Games/Zelda/RU_patch"
    ReferenceManager.set_reference_patch_path(project_dir, patch_path)
    assert ReferenceManager.get_reference_patch_path(project_dir) == patch_path

    # Verify settings file content
    settings_file = project_dir / "project_settings.json"
    assert settings_file.exists()
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["reference_patch_path"] == patch_path


def test_extract_bmg_messages_cp1251():
    """Test extracting BMG messages with cp1251 encoding and escape tags in zelda_bmg reference."""
    bmg = BMGFile()
    # Russian text 'Привет мир' encoded in cp1251 then read as cp1252
    ru_raw_bytes = "Привет мир".encode("cp1251")
    ru_in_cp1252 = ru_raw_bytes.decode("cp1252")

    msg0 = BMGMessage(
        info=b"\x00\x00\x00\x00",
        parts=[ru_in_cp1252, {"type": "escape", "escape_type": 255, "data": "000001"}],
    )
    msg1 = BMGMessage(info=b"\x00\x00\x00\x00", is_null=True)

    bmg.messages = [msg0, msg1]

    ref_data = {}
    _extract_bmg_messages(bmg, block_idx=0, ref_data=ref_data, game_rules=None, encoding="cp1251")

    assert (0, 0) in ref_data
    assert ref_data[(0, 0)] == "Привет мир{escape:255:000001}"
    assert (0, 1) in ref_data
    assert ref_data[(0, 1)] == ""


def test_reference_manager_delegation(tmp_path: Path):
    """Test that ReferenceManager delegates loading to the active plugin."""
    class DummyRules(BaseGameRules):
        def supports_reference_patch(self) -> bool:
            return True

        def get_reference_language_label(self) -> str:
            return "German (DE)"

        def load_reference_patch(self, patch_path, block_names=None):
            return {(0, 0): "Hallo Welt"}

    patch_dir = tmp_path / "dummy_patch"
    patch_dir.mkdir()

    rules = DummyRules()
    assert ReferenceManager.get_reference_language_label(rules) == "German (DE)"

    data = ReferenceManager.load_reference(patch_dir, block_names={"0": "block0"}, game_rules=rules)
    assert data == {(0, 0): "Hallo Welt"}


def test_zelda_bmg_rules_reference_patch():
    """Test that ZeldaBmgRules declares reference patch support and label."""
    rules = ZeldaBmgRules()
    assert rules.supports_reference_patch() is True
    assert rules.get_reference_language_label() == "Russian (RU)"
