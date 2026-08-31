import json
from pathlib import Path
from unittest.mock import MagicMock
from ui.settings_dialog import SettingsDialog
from core.translation.config import build_default_translation_config
import PyQt6.QtWidgets

class MockMainWindow(PyQt6.QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.data_store = self
        self.active_game_plugin = "zelda_mc"
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
        
        # Plugin settings attributes
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

        # Rules
        self.current_game_rules = MagicMock()
        self.current_game_rules.get_problem_definitions.return_value = {}

def test_settings_dialog_presets_ui(qapp):
    mw = MockMainWindow()
    dialog = SettingsDialog(mw)
    
    # 1. Verify preset controls exist
    assert dialog.translation_preset_combo is not None
    assert dialog.save_preset_btn is not None
    assert dialog.delete_preset_btn is not None
    
    # 2. Verify "Default" preset is present
    assert dialog.translation_preset_combo.count() == 1
    assert dialog.translation_preset_combo.itemText(0) == "Default"
    assert dialog.translation_preset_combo.itemData(0) == "default"

def test_settings_dialog_save_and_apply_preset(qapp, monkeypatch):
    mw = MockMainWindow()
    dialog = SettingsDialog(mw)
    
    # Modify fields on UI
    dialog.translation_provider_combo.setCurrentIndex(1) # openai
    dialog.openai_api_key_edit.setText("test-key")
    dialog.openai_endpoint_edit.setText("http://test-endpoint/v1")
    dialog.openai_model_edit.setText("test-model")
    
    # Mock QInputDialog.getText to return a custom name
    def mock_get_text(*args, **kwargs):
        return "TestPreset", True
    
    monkeypatch.setattr(PyQt6.QtWidgets.QInputDialog, "getText", mock_get_text)
    
    # Click save preset
    dialog.on_save_preset_clicked()
    
    # Check that preset is saved in self.translation_presets
    assert "TestPreset" in dialog.translation_presets
    preset_config = dialog.translation_presets["TestPreset"]
    assert preset_config["provider"] == "openai"
    assert preset_config["providers"]["openai"]["api_key"] == "test-key"
    assert preset_config["providers"]["openai"]["endpoint"] == "http://test-endpoint/v1"
    assert preset_config["providers"]["openai"]["model"] == "test-model"
    
    # Check that combobox is updated
    assert dialog.translation_preset_combo.count() == 2
    assert dialog.translation_preset_combo.itemText(1) == "TestPreset"
    assert dialog.translation_preset_combo.currentIndex() == 1
    
    # Change fields again
    dialog.openai_api_key_edit.setText("another-key")
    
    # Switch back to Default preset
    dialog.translation_preset_combo.setCurrentIndex(0)
    assert dialog.openai_api_key_edit.text() == "" # Default has empty key
    
    # Switch back to TestPreset
    dialog.translation_preset_combo.setCurrentIndex(1)
    assert dialog.openai_api_key_edit.text() == "test-key"

def test_settings_dialog_delete_preset(qapp, monkeypatch):
    mw = MockMainWindow()
    # Add pre-existing preset
    mw.translation_presets = {
        "PresetToDelete": build_default_translation_config()
    }
    mw.current_translation_preset = "PresetToDelete"
    
    dialog = SettingsDialog(mw)
    assert dialog.translation_preset_combo.count() == 2
    assert dialog.translation_preset_combo.currentIndex() == 1
    
    # Mock QMessageBox.question to return Yes
    def mock_question(*args, **kwargs):
        return PyQt6.QtWidgets.QMessageBox.StandardButton.Yes
        
    monkeypatch.setattr(PyQt6.QtWidgets.QMessageBox, "question", mock_question)
    
    # Click delete preset
    dialog.on_delete_preset_clicked()
    
    # Verify it is deleted from translation_presets and combo
    assert "PresetToDelete" not in dialog.translation_presets
    assert dialog.translation_preset_combo.count() == 1
    assert dialog.translation_preset_combo.currentIndex() == 0


def test_zelda_bmg_rules_show_per_window_controls(qapp):
    mw = MockMainWindow()
    mw.active_game_plugin = "zelda_bmg"

    dialog = SettingsDialog(mw)

    # 4 header labels + 9 groups * 4 widgets
    assert dialog.zelda_window_layouts_grid.count() == 40
    assert dialog.per_window_mode_radio.isChecked()
    assert not dialog.shared_window_mode_radio.isChecked()
    assert dialog.window_rules_mode_stack.currentIndex() == 1
    assert dialog._zelda_window_layout_controls["dialog"]["max_width"].value() == 435
    assert dialog._zelda_window_layout_controls["item"]["warn_width"].value() == 340
    assert dialog._zelda_window_layout_controls["explain"]["max_width"].value() == 435
    assert dialog._zelda_window_layout_controls["subtitles"]["lines_per_page"].value() == 4
    assert dialog._zelda_window_layout_controls["kanban_talk"]["lines_per_page"].value() == 7
    assert dialog._zelda_window_layout_controls["signs"]["lines_per_page"].value() == 7

    dialog.shared_window_mode_radio.setChecked(True)
    assert dialog.window_rules_mode_stack.currentIndex() == 0
    del dialog.font_map_table
    assert dialog.get_settings()["use_per_window_layouts"] is False


def test_zelda_bmg_window_rules_save_grouped_kinds_only_on_accept(qapp, tmp_path):
    mw = MockMainWindow()
    mw.active_game_plugin = "zelda_bmg"
    dialog = SettingsDialog(mw)

    source = Path("plugins/zelda_bmg/window_layouts.json")
    document = json.loads(source.read_text(encoding="utf-8"))
    target = tmp_path / "window_layouts.json"
    target.write_text(json.dumps(document), encoding="utf-8")
    dialog._zelda_window_layouts_path = target
    dialog._zelda_window_layouts_document = document

    sign_controls = dialog._zelda_window_layout_controls["signs"]
    sign_controls["warn_width"].setValue(261)
    sign_controls["max_width"].setValue(281)
    sign_controls["lines_per_page"].setValue(5)
    kanban_controls = dialog._zelda_window_layout_controls["kanban_talk"]
    kanban_controls["warn_width"].setValue(401)
    kanban_controls["max_width"].setValue(421)
    kanban_controls["lines_per_page"].setValue(7)
    dialog.accept()

    saved = json.loads(target.read_text(encoding="utf-8"))
    for kind in ("2", "6"):
        assert saved["kinds"][kind]["warn_width"] == 261
        assert saved["kinds"][kind]["max_width"] == 281
        assert saved["kinds"][kind]["lines_per_page"] == 5
    # Kind 15 is Dialogue (kanban), not wood/stone — signs save must not touch it
    assert saved["kinds"]["15"]["warn_width"] == 401
    assert saved["kinds"]["15"]["max_width"] == 421
    assert saved["kinds"]["15"]["lines_per_page"] == 7
    assert mw.current_game_rules._window_layouts is None


def test_zelda_bmg_window_rules_cancel_does_not_write(qapp, tmp_path):
    mw = MockMainWindow()
    mw.active_game_plugin = "zelda_bmg"
    dialog = SettingsDialog(mw)

    target = tmp_path / "window_layouts.json"
    target.write_text('{"default": {"warn_width": 1, "max_width": 2}}', encoding="utf-8")
    before = target.read_text(encoding="utf-8")
    dialog._zelda_window_layouts_path = target
    dialog._zelda_window_layout_controls["dialog"]["max_width"].setValue(999)

    dialog.reject()

    assert target.read_text(encoding="utf-8") == before
