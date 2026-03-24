import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from ui.updaters.title_status_bar_updater import TitleStatusBarUpdater
from ui.updaters.string_settings_updater import StringSettingsUpdater
from ui.updaters.preview_updater import PreviewUpdater


@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.data_store = mw
    mw.data_store.json_path = None
    mw.data_store.edited_json_path = None
    mw.data_store.unsaved_changes = False
    mw.project_manager = None
    mw.active_game_plugin = None
    mw.default_font_file = None
    mw.data_store.current_block_idx = -1
    mw.data_store.current_string_idx = -1
    mw.string_metadata = {}
    mw.show_multiple_spaces_as_dots = False
    mw.newline_display_symbol = "↵"
    mw.current_game_rules = None
    mw.data_store.data = []
    mw.line_width_warning_threshold_pixels = 100
    return mw


@pytest.fixture
def mock_dp():
    dp = MagicMock()
    dp.get_current_string_text.return_value = ("Some text", None)
    return dp


# ── TitleStatusBarUpdater ─────────────────────────────────────────────────────

class TestTitleStatusBarUpdater:
    @pytest.fixture
    def updater(self, mock_mw, mock_dp):
        return TitleStatusBarUpdater(mock_mw, mock_dp)

    def test_title_no_file_open(self, updater):
        from utils.constants import APP_VERSION
        updater.mw.data_store.json_path = None
        updater.mw.project_manager = None
        updater.update_title()
        updater.mw.setWindowTitle.assert_called_once_with(f"Picoripi v{APP_VERSION} - [No File Open]")

    def test_title_with_json_path(self, updater):
        from utils.constants import APP_VERSION
        updater.mw.data_store.json_path = "/some/path/myfile.json"
        updater.mw.project_manager = None
        updater.update_title()
        updater.mw.setWindowTitle.assert_called_once_with(f"Picoripi v{APP_VERSION} - [myfile.json]")

    def test_title_with_project(self, updater):
        from utils.constants import APP_VERSION
        pm = MagicMock()
        pm.project.name = "MyProject"
        updater.mw.project_manager = pm
        updater.update_title()
        updater.mw.setWindowTitle.assert_called_once_with(f"Picoripi v{APP_VERSION} - [MyProject]")

    def test_title_with_unsaved_changes(self, updater):
        from utils.constants import APP_VERSION
        updater.mw.data_store.json_path = "/path/file.json"
        updater.mw.project_manager = None
        updater.mw.data_store.unsaved_changes = True
        updater.update_title()
        updater.mw.setWindowTitle.assert_called_once_with(f"Picoripi v{APP_VERSION} - [file.json] *")

    def test_update_statusbar_paths_with_both_paths(self, updater):
        updater.mw.data_store.json_path = "/path/to/src.json"
        updater.mw.data_store.edited_json_path = "/path/to/edit.json"
        updater.update_statusbar_paths()
        updater.mw.original_path_label.setText.assert_called_once_with("Original: src.json")
        updater.mw.edited_path_label.setText.assert_called_once_with("Changes: edit.json")

    def test_update_statusbar_paths_no_paths(self, updater):
        updater.mw.data_store.json_path = None
        updater.mw.data_store.edited_json_path = None
        updater.update_statusbar_paths()
        updater.mw.original_path_label.setText.assert_called_once_with("Original: [not specified]")
        updater.mw.edited_path_label.setText.assert_called_once_with("Changes: [not specified]")


# ── StringSettingsUpdater ────────────────────────────────────────────────────

class TestStringSettingsUpdater:
    @pytest.fixture
    def updater(self, mock_mw, mock_dp):
        return StringSettingsUpdater(mock_mw, mock_dp)

    def test_update_string_settings_panel_no_selection(self, updater):
        updater.mw.data_store.current_block_idx = -1
        updater.mw.data_store.current_string_idx = -1
        updater.update_string_settings_panel()

        updater.mw.font_combobox.setEnabled.assert_called_with(False)
        updater.mw.width_spinbox.setEnabled.assert_called_with(False)

    def test_update_string_settings_panel_default_meta(self, updater):
        updater.mw.data_store.current_block_idx = 0
        updater.mw.data_store.current_string_idx = 0
        updater.mw.string_metadata = {}  # No custom meta
        updater.mw.line_width_warning_threshold_pixels = 200

        updater.update_string_settings_panel()

        updater.mw.font_combobox.setEnabled.assert_called_with(True)
        updater.mw.width_spinbox.setEnabled.assert_called_with(True)
        # Width should be default
        updater.mw.width_spinbox.setValue.assert_called_with(200)
        updater.mw.width_spinbox.setStyleSheet.assert_called_with("")

    def test_update_string_settings_panel_custom_width(self, updater):
        updater.mw.data_store.current_block_idx = 0
        updater.mw.data_store.current_string_idx = 0
        updater.mw.string_metadata = {(0, 0): {"width": 150}}
        updater.mw.line_width_warning_threshold_pixels = 200

        updater.update_string_settings_panel()

        updater.mw.width_spinbox.setValue.assert_called_with(150)
        updater.mw.width_spinbox.setStyleSheet.assert_called_with(updater.highlight_style)


# ── PreviewUpdater ────────────────────────────────────────────────────────────

class TestPreviewUpdater:
    @pytest.fixture
    def updater(self, mock_mw, mock_dp):
        return PreviewUpdater(mock_mw, mock_dp)

    def test_populate_strings_no_preview_edit(self, updater):
        updater.mw.preview_text_edit = None
        # Should not raise
        updater.populate_strings_for_block(0)

    def test_populate_strings_negative_block_idx(self, updater):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = "old"
        updater.mw.preview_text_edit = preview_edit
        updater.mw.original_text_edit = MagicMock()
        updater.mw.edited_text_edit = MagicMock()
        updater.mw.current_game_rules = MagicMock()
        
        updater.populate_strings_for_block(-1)
        preview_edit.setPlainText.assert_called_with("")

    def test_populate_strings_no_data(self, updater):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = ""
        updater.mw.preview_text_edit = preview_edit
        updater.mw.data_store.data = []
        updater.mw.current_game_rules = MagicMock()
        
        updater.populate_strings_for_block(0)
        # Should not crash, and not set any text (already empty)
        preview_edit.setPlainText.assert_not_called()

    @patch.object(PreviewUpdater, 'update_text_views')
    @patch.object(PreviewUpdater, '_apply_highlights_for_block')
    def test_populate_strings_basic(self, mock_hl, mock_ut, updater, mock_dp):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = ""
        preview_edit.document().blockCount.return_value = 2
        updater.mw.preview_text_edit = preview_edit
        updater.mw.data_store.data = [["line0", "line1"]]
        updater.mw.data_store.current_string_idx = 0
        updater.mw.current_game_rules = MagicMock()
        updater.mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: x
        updater.mw.project_manager = None

        mock_dp.get_current_string_text.side_effect = [
            ("Hello", None),
            ("World", None),
        ]

        updater.populate_strings_for_block(0, force=True)

        preview_edit.setPlainText.assert_called_once_with("Hello\nWorld")
