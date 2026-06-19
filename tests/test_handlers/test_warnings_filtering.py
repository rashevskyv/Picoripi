# tests/test_handlers/test_warnings_filtering.py
import pytest
from unittest.mock import MagicMock, patch
from handlers.list_selection_handler import ListSelectionHandler
from ui.updaters.preview_updater import PreviewUpdater

def test_warnings_filter_handler_calls(qapp, mock_mw):
    """Test handler toggling and signal triggering for warnings filters."""
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_category_name = None
    mock_mw.ui_updater = MagicMock()

    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)

    # Toggle show warnings only
    handler.toggle_show_warnings_only(True)
    assert mock_mw.data_store.show_warnings_only is True
    mock_mw.ui_updater.populate_strings_for_block.assert_called_with(0, None)
    mock_mw.data_processor.schedule_autosave.assert_called_once()

    # Change active warning filters
    mock_mw.data_processor.schedule_autosave.reset_mock()
    mock_mw.ui_updater.populate_strings_for_block.reset_mock()
    mock_mw.data_store.show_warnings_only = True

    handler.warnings_filter_changed(["width_exceeded"])
    assert mock_mw.data_store.active_warning_filters == ["width_exceeded"]
    mock_mw.ui_updater.populate_strings_for_block.assert_called_with(0, None)
    mock_mw.data_processor.schedule_autosave.assert_called_once()

def test_preview_updater_warnings_filtering(qapp, mock_mw):
    """Test preview populated strings filtering logic based on warnings active filters."""
    from PyQt6.QtWidgets import QTextEdit
    preview_edit = QTextEdit()
    preview_edit.reset_selection_state = MagicMock()
    preview_edit.updateLineNumberAreaWidth = MagicMock()
    mock_mw.preview_text_edit = preview_edit
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: x

    mock_mw.data = [["Line 1", "Line 2", "Line 3"]]
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.data = [["Line 1", "Line 2", "Line 3"]]
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_string_idx = -1
    mock_mw.data_store.current_chapter_id = None
    mock_mw.data_store.current_speaker_name = None
    mock_mw.data_store.current_category_name = None
    mock_mw.data_store.hide_translated = False
    mock_mw.data_store.hide_categorized = False
    mock_mw.data_store.show_unsaved_only = False
    mock_mw.data_store.show_warnings_only = True
    mock_mw.data_store.hide_empty_strings = False
    mock_mw.data_store.show_overrides_only = False

    # Setup data_processor mocks to return text correctly
    mock_mw.data_processor.get_current_string_text.return_value = ("some text", False)
    mock_mw.data_processor._get_string_from_source.return_value = "some text"

    # Mock problem analyzer/definitions
    mock_mw.current_game_rules.get_problem_definitions.return_value = {
        "width_exceeded": {"name": "Width Exceeded"},
        "tag_spacing": {"name": "Tag Spacing"}
    }

    mock_mw.data_store.problems_per_subline = {
        (0, 0, 0): {"width_exceeded"},
        (0, 1, 0): {"tag_spacing"}
    }

    def get_warnings_matching_set(block_idx, active_filters, detection_config):
        matching = set()
        problems_dict = mock_mw.data_store.problems_per_subline
        for (b_idx, s_idx, subline_idx), problems in problems_dict.items():
            if b_idx == block_idx:
                if active_filters:
                    if any(p_id in active_filters for p_id in problems):
                        matching.add(s_idx)
                else:
                    if any(detection_config.get(p_id, True) for p_id in problems):
                        matching.add(s_idx)
        return matching

    mock_mw.data_processor.get_warnings_matching_set.side_effect = get_warnings_matching_set

    updater = PreviewUpdater(mock_mw, mock_mw.data_processor)

    # Case 1: active_warning_filters = ["width_exceeded"]
    mock_mw.data_store.active_warning_filters = ["width_exceeded"]
    updater._do_populate_strings_for_block(0)
    assert mock_mw.data_store.displayed_string_indices == [0]

    # Case 2: active_warning_filters = ["width_exceeded", "tag_spacing"]
    mock_mw.data_store.active_warning_filters = ["width_exceeded", "tag_spacing"]
    updater._do_populate_strings_for_block(0)
    assert mock_mw.data_store.displayed_string_indices == [0, 1]

    # Case 3: active_warning_filters = []
    mock_mw.data_store.active_warning_filters = []
    updater._do_populate_strings_for_block(0)
    assert mock_mw.data_store.displayed_string_indices == [0, 1]

def test_open_warnings_filter_dialog(qapp, mock_mw):
    """Test open_warnings_filter_dialog triggers dialog and updates button."""
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_category_name = None
    mock_mw.ui_updater = MagicMock()

    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.get_problem_definitions.return_value = {
        "width_exceeded": {"name": "Width Exceeded"}
    }
    mock_mw.detection_enabled = {"width_exceeded": True}
    mock_mw.data_store.active_warning_filters = []

    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)

    with patch("ui.warnings_filter_dialog.WarningsFilterDialog") as MockDialog:
        dialog_inst = MockDialog.return_value
        dialog_inst.exec.return_value = True
        dialog_inst.get_selected_pids.return_value = ["width_exceeded"]

        handler.open_warnings_filter_dialog()

        MockDialog.assert_called_once()
        assert mock_mw.data_store.active_warning_filters == ["width_exceeded"]
        mock_mw.plugin_handler.update_warnings_filter_button.assert_called_once()
