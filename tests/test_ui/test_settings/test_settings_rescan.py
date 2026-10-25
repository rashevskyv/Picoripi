"""Settings-dialog rescans follow effective issue-scan inputs."""
from types import SimpleNamespace

import pytest

from ui.main_window.actions import settings_mixin
from ui.main_window.actions.settings_mixin import MainWindowSettingsActionsMixin


class FakeSettingsDialog:
    scenario = {}

    def __init__(self, mw):
        self._mw = mw
        self.plugin_changed_requires_restart = False
        self.theme_changed_requires_restart = False
        self.rules_changed_requires_rescan = True  # UI interaction signals may be transient.
        self.font_map_changed_requires_rescan = self.scenario.get("_font_map_changed", False)
        self._initial_font_map = self.scenario.get("_initial_font_map", getattr(mw, "current_font_map", {}))

    def exec(self):
        return 1

    def get_settings(self):
        result = {
            "theme": "auto",
            "preview_enabled": True,
            "restore_unsaved_on_startup": False,
            "game_dialog_max_width_pixels": 300,
            "line_width_warning_threshold_pixels": 280,
            "lines_per_page": 4,
            "detection_enabled": {"width": True},
            "default_tag_mappings": {},
            "default_font_file": "",
            "fonts_dir_path": "",
            "use_per_window_layouts": True,
            "original_file_path": None,
            "edited_file_path": None,
            "is_directory_mode": False,
            "auto_generate_translation_path": False,
            "spellchecker_enabled": False,
            "spellchecker_language": "uk",
            "show_width_guideline": True,
            "autofix_enabled": {"width": False},
            "translation_config": {"provider": "openai", "endpoint": "https://example.invalid"},
        }
        font_map_after = self.scenario.get("_font_map_after")
        if font_map_after is not None:
            self._mw.current_font_map = font_map_after
        result.update(self.scenario)
        result.pop("_initial_font_map", None)
        result.pop("_font_map_after", None)
        result.pop("_font_map_changed", None)
        return result


class SettingsActionHarness(MainWindowSettingsActionsMixin):
    def __init__(self, settings):
        calls = {"rescans": 0}
        self.mw = SimpleNamespace(
            game_dialog_max_width_pixels=300,
            line_width_warning_threshold_pixels=280,
            lines_per_page=4,
            detection_enabled={},  # Missing IDs mean enabled by default.
            default_tag_mappings={},
            current_font_map={"A": {"width": 8}},
            use_per_window_layouts=True,
            fonts_dir_path="",
            default_font_file="",
            current_game_rules=SimpleNamespace(
                get_window_layout_groups=lambda: [],
                get_problem_definitions=lambda: {"width": {}},
            ),
            spellchecker_manager=SimpleNamespace(language="uk", enabled=False),
            restore_unsaved_on_startup=False,
            preview_enabled=True,
            data_store=SimpleNamespace(json_path=None, edited_json_path=None, unsaved_changes=False),
            settings_manager=SimpleNamespace(
                set=lambda *_args: None,
                save_settings=lambda: None,
                load_all_font_maps=lambda: None,
            ),
            ui_updater=SimpleNamespace(update_preview_visibility=lambda *_args, **_kwargs: None),
            string_settings_updater=SimpleNamespace(
                update_font_combobox=lambda: None,
                update_string_settings_panel=lambda: None,
            ),
            ui_handler=SimpleNamespace(
                apply_font_size=lambda: None,
                update_editor_rules_properties=lambda: None,
            ),
            helper=SimpleNamespace(
                reconfigure_all_highlighters=lambda: None,
                apply_text_wrap_settings=lambda: None,
            ),
            text_operation_handler=SimpleNamespace(
                _update_preview_content=lambda: None,
                text_edited=lambda: None,
            ),
            plugin_handler=None,
            project_manager=None,
            is_directory_mode=False,
            auto_generate_translation_path=False,
        )
        self.mw.app_action_handler = SimpleNamespace(
            rescan_all_tags=lambda: calls.__setitem__("rescans", calls["rescans"] + 1)
        )
        self.helper = SimpleNamespace(restart_application=lambda: None)
        self.calls = calls
        FakeSettingsDialog.scenario = settings


@pytest.mark.parametrize(
    "changes, expected_rescans",
    [
        ({}, 0),  # No-op OK.
        ({"show_width_guideline": False}, 0),  # Appearance-only setting.
        ({"autofix_enabled": {"width": True}}, 0),  # Auto-fix-only setting.
        ({"translation_config": {"provider": "ollama_chat", "endpoint": "http://localhost"}}, 0),
        ({"line_width_warning_threshold_pixels": 281}, 1),
        ({"detection_enabled": {"width": False}}, 1),
    ],
)
def test_settings_dialog_rescans_only_when_effective_scan_input_changes(monkeypatch, changes, expected_rescans):
    monkeypatch.setattr(settings_mixin, "SettingsDialog", FakeSettingsDialog)
    monkeypatch.setattr(settings_mixin.QMessageBox, "information", lambda *_args, **_kwargs: None)
    action = SettingsActionHarness(changes)

    action.open_settings_dialog()

    assert action.calls["rescans"] == expected_rescans


def test_settings_change_then_revert_does_not_rescan(monkeypatch):
    monkeypatch.setattr(settings_mixin, "SettingsDialog", FakeSettingsDialog)
    action = SettingsActionHarness({"line_width_warning_threshold_pixels": 280})

    action.open_settings_dialog()

    assert action.calls["rescans"] == 0


def test_clearing_inherited_font_map_entries_triggers_rescan(monkeypatch):
    monkeypatch.setattr(settings_mixin, "SettingsDialog", FakeSettingsDialog)
    monkeypatch.setattr(settings_mixin.QMessageBox, "information", lambda *_args, **_kwargs: None)
    action = SettingsActionHarness({
        "_font_map_changed": True,
    })
    del action.mw.current_font_map

    action.open_settings_dialog()

    assert action.calls["rescans"] == 1


def test_unchanged_inherited_font_map_with_no_runtime_attribute_does_not_rescan(monkeypatch):
    monkeypatch.setattr(settings_mixin, "SettingsDialog", FakeSettingsDialog)
    action = SettingsActionHarness({})
    del action.mw.current_font_map

    action.open_settings_dialog()

    assert action.calls["rescans"] == 0
