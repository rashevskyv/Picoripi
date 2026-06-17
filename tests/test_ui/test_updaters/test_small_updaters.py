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

    @patch.object(PreviewUpdater, 'update_text_views')
    @patch.object(PreviewUpdater, '_apply_highlights_for_block')
    def test_populate_strings_show_overrides_only(self, mock_hl, mock_ut, updater, mock_dp):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = ""
        preview_edit.document().blockCount.return_value = 3
        updater.mw.preview_text_edit = preview_edit
        
        updater.mw.data_store.data = [["line0", "line1", "line2"]]
        updater.mw.data_store.current_string_idx = 0
        updater.mw.data_store.show_overrides_only = True
        updater.mw.current_game_rules = MagicMock()
        updater.mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: x
        updater.mw.project_manager = None

        # Setup string_metadata: line 1 has custom width, line 2 has custom font, line 0 is default
        updater.mw.default_font_file = "default_font.bfn"
        updater.mw.game_dialog_max_width_pixels = 200
        
        # Meta dictionary
        updater.mw.string_metadata = {
            (0, 0): {},                                      # Default
            (0, 1): {"width": 150},                           # Custom width
            (0, 2): {"font_file": "custom_font.bfn"}          # Custom font
        }

        mock_dp.get_current_string_text.side_effect = lambda b, r: (f"line{r}", None)

        updater.populate_strings_for_block(0, force=True)

        # Only line 1 and 2 should be displayed (indices 1 and 2)
        assert updater.mw.data_store.displayed_string_indices == [1, 2]

    @patch.object(PreviewUpdater, 'update_text_views')
    @patch.object(PreviewUpdater, '_apply_highlights_for_block')
    def test_populate_strings_show_unsaved_only(self, mock_hl, mock_ut, updater, mock_dp):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = ""
        preview_edit.document().blockCount.return_value = 2
        updater.mw.preview_text_edit = preview_edit
        
        updater.mw.data_store.data = [["line0", "line1", "line2"]]
        updater.mw.data_store.current_string_idx = 0
        updater.mw.data_store.show_unsaved_only = True
        updater.mw.current_game_rules = MagicMock()
        updater.mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: x
        updater.mw.project_manager = None
        
        # Setup edited_data for line 1 (unsaved change)
        updater.mw.data_store.edited_data = {
            (0, 1): "edited_line1"
        }

        mock_dp.get_current_string_text.side_effect = lambda b, r: (f"line{r}", None)

        updater.populate_strings_for_block(0, force=True)

        # Only line 1 should be displayed since it is the only one in edited_data
        assert updater.mw.data_store.displayed_string_indices == [1]

    @patch.object(PreviewUpdater, 'update_text_views')
    @patch.object(PreviewUpdater, '_apply_highlights_for_block')
    def test_populate_strings_show_overrides_only_checkbox_visibility(self, mock_hl, mock_ut, updater, mock_dp):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = ""
        preview_edit.document().blockCount.return_value = 3
        updater.mw.preview_text_edit = preview_edit
        
        # Add checkbox mock
        checkbox = MagicMock()
        updater.mw.show_overrides_only_checkbox = checkbox
        
        updater.mw.data_store.data = [["line0", "line1", "line2"]]
        updater.mw.data_store.current_string_idx = 0
        updater.mw.current_game_rules = MagicMock()
        updater.mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: x
        updater.mw.project_manager = None
        updater.mw.default_font_file = "default_font.bfn"
        updater.mw.game_dialog_max_width_pixels = 200

        mock_dp.get_current_string_text.side_effect = lambda b, r: (f"line{r}", None)

        # Case 1: No overrides, filter is False -> Should hide checkbox
        updater.mw.data_store.show_overrides_only = False
        updater.mw.string_metadata = {}
        updater.populate_strings_for_block(0, force=True)
        checkbox.setVisible.assert_called_with(False)

        # Case 2: Has overrides, filter is False -> Should show checkbox
        checkbox.reset_mock()
        updater.mw.string_metadata = {
            (0, 1): {"width": 150}
        }
        updater.populate_strings_for_block(0, force=True)
        checkbox.setVisible.assert_called_with(True)

        # Case 3: No overrides, filter is True -> Should show checkbox
        checkbox.reset_mock()
        updater.mw.string_metadata = {}
        updater.mw.data_store.show_overrides_only = True
        updater.populate_strings_for_block(0, force=True)
        checkbox.setVisible.assert_called_with(True)

    @patch.object(PreviewUpdater, 'update_text_views')
    @patch.object(PreviewUpdater, '_apply_highlights_for_block')
    def test_populate_strings_custom_line_numbers_gutter(self, mock_hl, mock_ut, updater, mock_dp):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = ""
        preview_edit.document().blockCount.return_value = 2
        updater.mw.preview_text_edit = preview_edit
        
        updater.mw.data_store.data = [["line0", "line1", "line2"]]
        updater.mw.data_store.current_string_idx = 0
        updater.mw.data_store.show_overrides_only = True
        updater.mw.current_game_rules = MagicMock()
        updater.mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: x
        updater.mw.project_manager = None
        updater.mw.default_font_file = "default_font.bfn"
        updater.mw.game_dialog_max_width_pixels = 200

        updater.mw.string_metadata = {
            (0, 0): {},
            (0, 1): {"width": 150},
            (0, 2): {"font_file": "custom_font.bfn"}
        }
        mock_dp.get_current_string_text.side_effect = lambda b, r: (f"line{r}", None)

        updater.populate_strings_for_block(0, force=True)

        assert preview_edit.custom_line_numbers == [2, 3]

    @patch.object(PreviewUpdater, 'update_text_views')
    @patch.object(PreviewUpdater, '_apply_highlights_for_block')
    def test_populate_strings_custom_line_numbers_with_streak(self, mock_hl, mock_ut, updater, mock_dp):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = ""
        preview_edit.document().blockCount.return_value = 5
        updater.mw.preview_text_edit = preview_edit
        
        updater.mw.data_store.data = [["line" + str(i) for i in range(7)]]
        updater.mw.data_store.current_string_idx = 0
        updater.mw.data_store.hide_empty_strings = True
        updater.mw.current_game_rules = MagicMock()
        updater.mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: x
        updater.mw.project_manager = None

        def get_text_side_effect(b_idx, r_idx):
            is_empty = r_idx in [1, 2, 3]
            txt = "" if is_empty else f"line{r_idx}"
            return (txt, None)

        mock_dp.get_current_string_text.side_effect = get_text_side_effect
        mock_dp._get_string_from_source.side_effect = lambda b, s, d, mode: get_text_side_effect(b, s)[0]

        updater.populate_strings_for_block(0, force=True)

        assert preview_edit.custom_line_numbers == [1, None, 5, 6, 7]

    @patch('PyQt6.QtWidgets.QProgressDialog')
    @patch.object(PreviewUpdater, 'update_text_views')
    @patch.object(PreviewUpdater, '_apply_highlights_for_block')
    def test_populate_strings_shows_progress_dialog(self, mock_hl, mock_ut, mock_progress, updater, mock_dp):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = ""
        preview_edit.document().blockCount.return_value = 250
        updater.mw.preview_text_edit = preview_edit
        
        updater.mw.data_store.data = [["line" + str(i) for i in range(250)]]
        updater.mw.data_store.current_string_idx = 0
        updater.mw.current_game_rules = MagicMock()
        updater.mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: x
        updater.mw.project_manager = None

        mock_dp.get_current_string_text.side_effect = lambda b, r: (f"line{r}", None)

        progress_instance = MagicMock()
        progress_instance.wasCanceled.return_value = False
        mock_progress.return_value = progress_instance

        updater._force_progress_for_testing = True
        try:
            updater.populate_strings_for_block(0, force=True)
        finally:
            updater._force_progress_for_testing = False

        assert mock_progress.called
        assert progress_instance.setValue.called
        assert progress_instance.close.called


    def test_update_cached_string(self, updater):
        # Setup cache with a block having two different filter configurations
        key1 = (0, None, False, False, False, False)
        key2 = (0, None, True, False, False, False)
        
        updater._preview_cache = {
            key1: {
                'lines': ["line0", "line1", "line2"],
                'target_indices': [0, 1, 2],
                'next_index': 3
            },
            key2: {
                'lines': ["line1", "line2"],
                'target_indices': [1, 2],
                'next_index': 2
            }
        }
        
        # Update string index 1 with new text
        updater.update_cached_string(0, 1, "new_line1")
        
        # Verify both cache entries are updated
        assert updater._preview_cache[key1]['lines'] == ["line0", "new_line1", "line2"]
        assert updater._preview_cache[key2]['lines'] == ["new_line1", "line2"]

    @patch.object(PreviewUpdater, 'update_text_views')
    @patch.object(PreviewUpdater, '_apply_highlights_for_block')
    def test_populate_strings_lazy_loads_from_cache(self, mock_hl, mock_ut, updater, mock_dp):
        preview_edit = MagicMock()
        preview_edit.toPlainText.return_value = ""
        preview_edit.document().blockCount.return_value = 250
        updater.mw.preview_text_edit = preview_edit
        
        # Setup data
        updater.mw.data_store.data = [["line" + str(i) for i in range(250)]]
        updater.mw.data_store.current_string_idx = 0
        updater.mw.current_game_rules = MagicMock()
        updater.mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: x
        updater.mw.project_manager = None
        
        mock_dp.get_current_string_text.side_effect = lambda b, r: (f"line{r}", None)
        
        # Pre-populate cache
        key = (0, None, False, False, False, False)
        cached_lines = [f"line{i}" for i in range(250)]
        updater._preview_cache = {
            key: {
                'lines': cached_lines,
                'target_indices': list(range(250)),
                'next_index': 250
            }
        }
        
        # Mock timer
        timer_mock = MagicMock()
        updater._lazy_load_timer = timer_mock
        
        # Trigger population
        updater.populate_strings_for_block(0)
        
        # Since use_cache is True and len > initial_chunk_size (200), it should start the lazy load timer
        assert timer_mock.start.called
        # The text set in plain text edit should have only first 200 lines and the rest should be empty strings
        set_text_call = preview_edit.setPlainText.call_args[0][0]
        lines_set = set_text_call.split('\n')
        assert len(lines_set) == 250
        assert lines_set[0] == "line0"
        assert lines_set[199] == "line199"
        assert lines_set[200] == ""
        assert lines_set[249] == ""




