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
    mw.data_store.current_category_name = None
    mw.data_store.current_chapter_id = None
    mw.string_metadata = {}
    mw.show_multiple_spaces_as_dots = False
    mw.newline_display_symbol = "↵"
    mw.current_game_rules = None
    mw.data_store.data = []
    mw.line_width_warning_threshold_pixels = 100
    mw.game_dialog_max_width_pixels = 200
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
        updater.mw.game_dialog_max_width_pixels = 200

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
        updater.mw.game_dialog_max_width_pixels = 200

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

        def get_text_side_effect(b_idx, r_idx):
            if r_idx == 0:
                return ("Hello", None)
            return ("World", None)
            
        mock_dp.get_current_string_text.side_effect = get_text_side_effect

        updater.populate_strings_for_block(0, force=True)

        preview_edit.setPlainText.assert_called_once_with("Hello\nWorld")

    @patch('ui.updaters.preview_updater.QTextCursor')
    @patch.object(PreviewUpdater, 'update_text_views')
    @patch.object(PreviewUpdater, '_apply_highlights_for_block')
    def test_populate_strings_chunked(self, mock_hl, mock_ut, mock_cursor, updater, mock_dp):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = ""
        preview_edit.document().blockCount.return_value = 250
        
        # Mock document structure for findBlockByNumber
        mock_blocks = {}
        def mock_find_block(num):
            block = MagicMock()
            block.isValid.return_value = True
            block.position.return_value = num * 10
            block.text.return_value = ""
            mock_blocks[num] = block
            return block
        
        preview_edit.document().findBlockByNumber.side_effect = mock_find_block
        updater.mw.preview_text_edit = preview_edit
        
        updater.mw.data_store.data = [["line" + str(i) for i in range(300)]]
        updater.mw.data_store.current_string_idx = 0
        updater.mw.current_game_rules = MagicMock()
        updater.mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: x
        updater.mw.project_manager = None
        updater.mw.data_store.current_category_name = None

        mock_dp.get_current_string_text.side_effect = lambda b, r: (f"Hello {r}", None)

        updater.populate_strings_for_block(0, force=True)

        assert preview_edit.setPlainText.called
        called_arg = preview_edit.setPlainText.call_args[0][0]
        lines = called_arg.split('\n')
        assert len(lines) == 300
        assert lines[0] == "Hello 0"
        assert lines[199] == "Hello 199"
        assert lines[200] == ""

        assert hasattr(updater, '_lazy_load_timer')
        assert updater._lazy_load_timer.isActive()

        # Mock the cursor instance returned by QTextCursor constructor
        cursor_instance = MagicMock()
        mock_cursor.return_value = cursor_instance

        updater._load_next_preview_chunk()

        assert cursor_instance.beginEditBlock.called
        assert cursor_instance.endEditBlock.called
        assert cursor_instance.insertText.called
        
        # First insertion in this chunk should be Hello 200
        first_insert_arg = cursor_instance.insertText.call_args_list[0][0][0]
        assert first_insert_arg == "Hello 200"

        assert not updater._lazy_load_timer.isActive()

    def test_populate_strings_syncs_subline_asterisks(self, updater):
        edited_edit = MagicMock()
        edited_edit.toPlainText.return_value = "new text"
        updater.mw.edited_text_edit = edited_edit
        
        updater.mw.data_store.current_block_idx = 0
        updater.mw.data_store.current_string_idx = 0
        
        # Mock get_current_string_text to return different texts so update triggers
        updater.data_processor.get_current_string_text.return_value = ("different text", None)
        
        # Mock text_operation_handler
        toh = MagicMock()
        updater.mw.text_operation_handler = toh
        
        # Trigger update_text_views
        updater.update_text_views()
        
        # Verify sync_subline_asterisks was called
        toh.sync_subline_asterisks.assert_called_once_with(0, 0, "different text")

    @patch.object(PreviewUpdater, 'update_text_views')
    @patch.object(PreviewUpdater, '_apply_highlights_for_block')
    def test_populate_strings_hide_translated(self, mock_hl, mock_ut, updater, mock_dp):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = ""
        preview_edit.document().blockCount.return_value = 2
        updater.mw.preview_text_edit = preview_edit
        updater.mw.data_store.data = [["line0", "line1", "line2"]]
        updater.mw.data_store.current_string_idx = 0
        updater.mw.data_store.hide_translated = True
        updater.mw.current_game_rules = MagicMock()
        updater.mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: x
        updater.mw.project_manager = None

        mock_dp.is_string_translated.side_effect = lambda b, s: s == 0

        def get_text_side_effect(b_idx, r_idx):
            if r_idx == 0:
                return ("Hello Translated", None)
            elif r_idx == 1:
                return ("World Untranslated", None)
            return ("Another Untranslated", None)
            
        mock_dp.get_current_string_text.side_effect = get_text_side_effect

        updater.populate_strings_for_block(0, force=True)

        preview_edit.setPlainText.assert_called_once_with("World Untranslated\nAnother Untranslated")
        assert updater.mw.data_store.displayed_string_indices == [1, 2]

    @patch.object(PreviewUpdater, 'update_text_views')
    @patch.object(PreviewUpdater, '_apply_highlights_for_block')
    def test_populate_strings_hide_empty_strings(self, mock_hl, mock_ut, updater, mock_dp):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = ""
        preview_edit.document().blockCount.return_value = 8
        updater.mw.preview_text_edit = preview_edit
        
        # 10 lines: 
        # 0: non-empty
        # 1: empty
        # 2: non-empty
        # 3: empty
        # 4: empty
        # 5: non-empty
        # 6: empty
        # 7: empty
        # 8: empty
        # 9: non-empty
        updater.mw.data_store.data = [["line" + str(i) for i in range(10)]]
        updater.mw.data_store.current_string_idx = 0
        updater.mw.data_store.hide_empty_strings = True
        updater.mw.current_game_rules = MagicMock()
        updater.mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: x
        updater.mw.project_manager = None

        def get_text_side_effect(b_idx, r_idx):
            is_empty = r_idx in [1, 3, 4, 6, 7, 8]
            txt = "" if is_empty else f"line{r_idx}"
            return (txt, None)

        mock_dp.get_current_string_text.side_effect = get_text_side_effect
        mock_dp._get_string_from_source.side_effect = lambda b, s, d, mode: get_text_side_effect(b, s)[0]

        updater.populate_strings_for_block(0, force=True)

        expected_indices = [0, 1, 2, 3, 4, 5, -1, 9]
        assert updater.mw.data_store.displayed_string_indices == expected_indices
        assert updater._placeholder_texts[6] == "[6-8] 3 empty line(s)"


