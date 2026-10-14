"""The preview and Settings learn about a game's message windows through hooks (WP5 5.7)."""
import hashlib
import importlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from plugins.base_game_rules import BaseGameRules
from plugins.zelda_bmg.rules import GameRules as ZeldaBmgRules
from plugins.zelda_bmg.window_frame_loader import textbox_height_center
from plugins.zelda_bmg.window_kinds import EXPLAIN_PRESET_KEY, PREVIEW_WINDOW_PRESETS
from ui.components.bfn_preview.paint_mixin import BfnPreviewPaintMixin

HOST = ("core", "handlers", "ui", "components", "utils")
# What the host may import from the plugins package: the platform, never a game.
PLATFORM = ("plugins.base_game_rules", "plugins.common", "plugins.spec", "plugins.validate", "plugins.testing")


def test_no_host_module_imports_a_game_plugin():
    pattern = re.compile(r"^\s*(?:from|import)\s+(plugins\.[\w.]+)", re.MULTILINE)
    offenders = {}
    for root in HOST:
        for path in Path(root).rglob("*.py"):
            for module in pattern.findall(path.read_text(encoding="utf-8")):
                if not module.startswith(PLATFORM):
                    offenders.setdefault(path.as_posix(), set()).add(module)
    assert offenders == {}


class TestBaseDefaults:
    def test_a_plugin_without_message_windows_answers_harmlessly(self):
        rules = BaseGameRules()

        assert rules.get_window_presets() == [None]
        assert rules.get_window_preset_label(None) == "Auto" and rules.get_window_preset_label(7) == "7"
        assert rules.get_window_preset_labels() == ["Auto"]
        assert rules.get_window_style_for_preset(3) is None
        assert rules.get_window_frame({"fuki_kind": 0}) is None
        assert rules.get_window_item_icon(0, 0) is None
        assert rules.get_window_text_offset_y(100, 20, 22, 4, 2) == 0.0
        assert rules.get_window_layout_groups() == []
        assert rules.get_window_layouts_document() is None
        rules.save_window_layouts_document({})


class TestZeldaBmg:
    def test_presets_and_labels(self):
        rules = ZeldaBmgRules()

        presets = rules.get_window_presets()
        assert presets == list(PREVIEW_WINDOW_PRESETS) and presets[0] is None
        assert rules.get_window_preset_label(EXPLAIN_PRESET_KEY) == "Explain"
        assert rules.get_window_preset_label(None, {"kind_name": "Item"}).endswith("Item")
        labels = rules.get_window_preset_labels()
        assert len(labels) > len(presets) and all(isinstance(label, str) and label for label in labels)

    def test_a_forced_preset_gives_a_paintable_style(self):
        rules = ZeldaBmgRules()

        explain = rules.get_window_style_for_preset(EXPLAIN_PRESET_KEY)
        item = rules.get_window_style_for_preset(9)

        assert explain["preset_key"] == EXPLAIN_PRESET_KEY and explain["lines_per_page"] > 0
        assert item["fuki_kind"] == 9 and isinstance(item.get("geometry"), dict)

    def test_the_text_offset_is_the_game_s_vertical_centring(self):
        assert ZeldaBmgRules().get_window_text_offset_y(118, 22, 23, 4, 2) == textbox_height_center(118, 22, 23, 4, 2)

    def test_no_item_icon_without_a_loaded_message(self):
        assert ZeldaBmgRules().get_window_item_icon(0, 0) is None

    def test_the_settings_rows_and_the_stored_limits(self, tmp_path):
        source = Path("plugins/zelda_bmg/window_layouts.json")
        target = tmp_path / "window_layouts.json"
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        rules = ZeldaBmgRules()
        rules.window_layouts_path = str(target)

        groups = rules.get_window_layout_groups()
        document = rules.get_window_layouts_document()
        assert [key for key, _label, _kinds in groups][:3] == ["dialog", "signs", "kanban_talk"]
        assert groups[0][2] is None and groups[1][2] == ("2", "6")
        assert document == json.loads(source.read_text(encoding="utf-8"))

        rules._get_window_layouts()                                  # cached
        document["default"]["max_width"] = 123
        rules.save_window_layouts_document(document)

        assert json.loads(target.read_text(encoding="utf-8"))["default"]["max_width"] == 123
        assert rules._get_window_layouts()["default"]["max_width"] == 123      # the cache was dropped
        assert not list(tmp_path.glob("*.tmp"))

    def test_a_missing_limits_file_gives_the_shipped_document_else_an_empty_one(self, tmp_path):
        rules = ZeldaBmgRules()
        rules.window_layouts_path = str(tmp_path / "absent.json")
        shipped = json.loads(Path("plugins/zelda_bmg/window_layouts.json").read_text(encoding="utf-8"))

        assert rules.get_window_layouts_document() == shipped
        rules.data_dir = str(tmp_path)                 # a plugin that ships no limits file (zelda_tww, SMS)
        assert rules.get_window_layouts_document() == {"default": {}, "kinds": {}}


def _folder_state(folder: Path) -> dict:
    """Every file of ``folder`` (no bytecode caches) with its time stamp and SHA-256."""
    return {str(path.relative_to(folder)): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in folder.rglob("*") if path.is_file() and "__pycache__" not in path.parts}


@pytest.mark.parametrize("plugin", ["zelda_bmg", "zelda_tww", "super_mario_sunshine"])
def test_settings_limits_go_to_the_user_folder_atomically_never_into_plugins(plugin, tmp_path, monkeypatch):
    """Rule 8: the plugin's shipped limits stay a read-only default; Settings writes the user's copy (rule 9: atomic)."""
    import utils.constants as constants
    monkeypatch.setattr(constants, "SETTINGS_DIR", tmp_path)
    plugin_dir = constants.plugins_root() / plugin
    before = _folder_state(plugin_dir)
    rules = importlib.import_module(f"plugins.{plugin}.rules").GameRules()

    document = rules.get_window_layouts_document()
    document.setdefault("default", {})["max_width"] = 123
    rules.save_window_layouts_document(document)

    user_copy = tmp_path / "plugins" / plugin / "window_layouts.json"
    assert json.loads(user_copy.read_text(encoding="utf-8"))["default"]["max_width"] == 123
    assert rules.get_window_layouts_document()["default"]["max_width"] == 123     # the user's copy is read first
    assert _folder_state(plugin_dir) == before

    def refuse(_source, _target):
        raise OSError("disk full")

    monkeypatch.setattr("utils.atomic_io.os.replace", refuse)
    document["default"]["max_width"] = 456
    with pytest.raises(OSError, match="disk full"):
        rules.save_window_layouts_document(document)
    assert json.loads(user_copy.read_text(encoding="utf-8"))["default"]["max_width"] == 123
    assert [path.name for path in user_copy.parent.iterdir()] == ["window_layouts.json"]   # no temporary file left


class _Preview(BfnPreviewPaintMixin):
    """Just enough of the preview widget to exercise the style resolution."""

    def __init__(self, rules, **window):
        self.mw = SimpleNamespace(current_game_rules=rules, data_store=None, **window)
        self._window_preset_override = None
        self._window_frame_image = None

    def _sync_window_preset_scope(self):
        pass


class _WindowRules(BaseGameRules):
    def __init__(self, frame=None):
        super().__init__()
        self.frame = frame

    def get_preview_window_style(self, block_idx=None, string_idx=None):
        return {"kind_name": "Dialogue", "halo": {"alpha": 200}, "geometry": {"box": [0, 0, 1, 1]}}

    def get_window_style_for_preset(self, preset):
        return {"kind_name": f"Forced {preset}", "lines_per_page": 6} if preset == "sign" else None

    def get_window_frame(self, style):
        return self.frame


class TestPreviewUsesTheHooks:
    def test_auto_follows_the_message(self):
        preview = _Preview(_WindowRules())

        assert preview._get_game_window_style()["kind_name"] == "Dialogue"
        assert preview._window_frame_image is None

    def test_a_forced_preset_comes_from_the_plugin_and_obeys_the_shared_limits_switch(self):
        preview = _Preview(_WindowRules(), use_per_window_layouts=False, lines_per_page=3)
        preview._window_preset_override = "sign"

        style = preview._get_game_window_style()

        assert style["kind_name"] == "Forced sign" and style["lines_per_page"] == 3

    def test_an_unknown_preset_falls_back_to_the_message(self):
        preview = _Preview(_WindowRules())
        preview._window_preset_override = "no such preset"

        assert preview._get_game_window_style()["kind_name"] == "Dialogue"

    def test_the_game_s_own_frame_replaces_the_geometry_and_softens_the_halo(self):
        image = object()
        preview = _Preview(_WindowRules(frame={"geometry": {"box": [10, 20, 300, 100]}, "image": image}))

        style = preview._get_game_window_style()

        assert style["geometry"] == {"box": [10, 20, 300, 100]} and style["halo"]["alpha"] == 80
        assert preview._window_frame_image is image

    @pytest.mark.parametrize("rules", [None, BaseGameRules(), object()])
    def test_a_plugin_that_knows_nothing_about_windows_draws_no_window(self, rules):
        preview = _Preview(rules)

        assert preview._get_game_window_style() is None and preview._window_frame_image is None

    def test_a_failing_hook_does_not_break_painting(self):
        class Broken(_WindowRules):
            def get_window_frame(self, style):
                raise OSError("dump folder is gone")

        preview = _Preview(Broken())

        assert preview._get_game_window_style()["kind_name"] == "Dialogue"
