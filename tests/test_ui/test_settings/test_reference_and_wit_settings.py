"""Tests for reference path in project settings and wit_tool_path in global settings."""
import json
from unittest.mock import MagicMock, patch
import pytest
from PyQt6.QtWidgets import QMainWindow
from ui.settings_dialog import SettingsDialog
from ui.builders.menu_builder import MenuBuilder
from plugins.zelda_bmg.reference import _try_extract_iso_messages
from core.translation.config import build_default_translation_config


class MockMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data_store = self
        self.active_game_plugin = "zelda_bmg"
        self.current_font_size = 10
        self.theme = "auto"
        self.restore_unsaved_on_startup = False
        self.show_multiple_spaces_as_dots = True
        self.space_dot_color_hex = "#BBBBBB"
        self.window_was_maximized_on_close = False
        self.window_normal_geometry_on_close = None
        self.prompt_editor_enabled = True
        self.recent_projects = []
        self.translation_ai = {}
        self.glossary_ai = {}
        self.spellchecker_enabled = False
        self.spellchecker_language = 'uk'
        self.spellchecker_manager = MagicMock()
        self.spellchecker_manager.language = "uk"
        self.spellchecker_manager.enabled = False
        self.last_browse_dir = ""
        self.enable_console_logging = True
        self.enable_file_logging = True
        self.settings_window_width = 800
        self.log_file_path = ""
        self.enabled_log_categories = []
        self.edited_data = {}
        self.json_path = None
        self.edited_json_path = None
        self.main_splitter = None
        self.right_splitter = None
        self.bottom_right_splitter = None
        self.ui_updater = MagicMock()
        self.statusBar = MagicMock()
        self.default_tag_mappings = {}
        self.block_names = {}
        self.block_color_markers = {}
        self.string_metadata = {}
        self.default_font_file = ""
        self.newline_display_symbol = "↵"
        self.preview_wrap_lines = True
        self.editors_wrap_lines = False
        self.game_dialog_max_width_pixels = 208
        self.line_width_warning_threshold_pixels = 208
        self.lines_per_page = 4
        self.last_cursor_position_in_edited = 0
        self.last_selected_block_index = -1
        self.last_selected_string_index = -1
        self.last_edited_text_edit_scroll_value_v = 0
        self.last_edited_text_edit_scroll_value_h = 0
        self.last_preview_text_edit_scroll_value_v = 0
        self.last_original_text_edit_scroll_value_v = 0
        self.last_original_text_edit_scroll_value_h = 0
        self.search_history_to_save = []
        self.autofix_enabled = {}
        self.detection_enabled = {}
        self.translation_config = build_default_translation_config()
        self.translation_presets = {}
        self.current_translation_preset = "default"
        self.context_menu_tags = {"single_tags": [], "wrap_tags": []}
        self.current_game_rules = MagicMock()
        self.current_game_rules.get_problem_definitions.return_value = {}
        self.show_width_guideline = True
        self.preview_enabled = True
        self.warnings_enabled = True
        self.glossary_enabled = True
        self.show_archive_size_warnings = True
        self.auto_sleep_idle_delay_seconds = 300
        self.log_ai_traffic = False
        self.newline_color_rgba = "#A020F0"
        self.newline_bold = True
        self.newline_italic = False
        self.newline_underline = False
        self.tag_bold = True
        self.tag_italic = False
        self.tag_underline = False


@pytest.fixture
def fake_main_window(qtbot):
    """Fixture providing a mock MainWindow for SettingsDialog."""
    mw = MockMainWindow()
    qtbot.addWidget(mw)
    mw.reference_patch_path = "D:/games/zelda/PAL_RU"
    mw.wit_tool_path = "D:/tools/wit.exe"
    mw.fonts_dir_path = ""
    mw.orig_fonts_dir_path = ""

    # Setup mock project
    proj = MagicMock()
    proj.metadata = {
        "source_path": "D:/proj/src",
        "translation_path": "D:/proj/dst",
        "is_directory_mode": True,
        "auto_generate_translation_path": False,
    }
    mw.project_manager = MagicMock()
    mw.project_manager.project = proj
    mw.project_manager.current_project = proj
    return mw


def test_file_menu_does_not_contain_reference_load_actions(qtbot):
    """File menu should not contain Load Reference Patch or Load Unpacked ROM actions."""
    window = QMainWindow()
    qtbot.addWidget(window)
    builder = MenuBuilder(window)
    builder.build_all()

    menubar = window.menuBar()
    file_action = next((a for a in menubar.actions() if "File" in a.text()), None)
    assert file_action is not None
    file_menu = file_action.menu()
    assert file_menu is not None

    menu_action_texts = [a.text() for a in file_menu.actions()]
    assert not any("Reference Patch" in t for t in menu_action_texts)
    assert not any("Unpacked ROM" in t for t in menu_action_texts)


def test_settings_dialog_initializes_and_saves_wit_tool_path(fake_main_window, qtbot):
    """SettingsDialog Global tab should expose wit_tool_path_edit and save its value."""
    dialog = SettingsDialog(fake_main_window)
    qtbot.addWidget(dialog)

    assert hasattr(dialog, "wit_tool_path_edit")
    assert dialog.wit_tool_path_edit.text() == "D:/tools/wit.exe"

    dialog.wit_tool_path_edit.setText("E:/custom_wit/bin/wit.exe")
    settings = dialog.get_settings()
    assert settings.get("wit_tool_path") == "E:/custom_wit/bin/wit.exe"


def test_settings_dialog_initializes_and_saves_reference_patch_path(fake_main_window, qtbot):
    """SettingsDialog Project paths subtab should expose reference_path_edit and save its value."""
    dialog = SettingsDialog(fake_main_window)
    qtbot.addWidget(dialog)

    assert hasattr(dialog, "reference_path_edit")
    assert dialog.reference_path_edit.text() == "D:/games/zelda/PAL_RU"
    assert dialog.reference_path_selector.isEnabled()

    dialog.reference_path_edit.setText("D:/games/zelda/Zelda_PAL.iso")
    settings = dialog.get_settings()
    assert settings.get("reference_patch_path") == "D:/games/zelda/Zelda_PAL.iso"


def test_try_extract_iso_messages_uses_configured_wit_tool(tmp_path):
    """_try_extract_iso_messages should prioritize configured wit_tool_path from settings."""
    iso_file = tmp_path / "game.iso"
    iso_file.touch()

    custom_wit = tmp_path / "wit.exe"
    custom_wit.touch()

    settings_file = tmp_path / "settings.json"
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({"wit_tool_path": str(custom_wit)}, f)

    with patch("utils.constants.SETTINGS_FILE_PATH", settings_file):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            dest = _try_extract_iso_messages(iso_file)
            assert dest is not None
            # Check that mock_run was called with custom_wit as command executable
            assert mock_run.call_args[0][0][0] == str(custom_wit)


def test_provider_ids_stay_english_in_a_translated_interface(fake_main_window, qtbot):
    """The combo's data is the provider id the settings store; only the label is translated."""
    from core import i18n

    i18n.init("uk")      # conftest's english_interface puts English back afterwards
    dialog = SettingsDialog(fake_main_window)
    qtbot.addWidget(dialog)
    combo = dialog.translation_provider_combo

    assert [combo.itemData(i) for i in range(combo.count())] == ["disabled", "openai", "ollama_chat", "gemini", "perplexity"]
