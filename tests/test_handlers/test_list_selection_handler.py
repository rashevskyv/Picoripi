import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItem, QMessageBox
from handlers.list_selection_handler import ListSelectionHandler

@pytest.fixture
def handler(mock_mw):
    # Ensure a clean, predictable mock_mw state for every test
    mock_mw.is_loading_data = False
    mock_mw.is_programmatically_changing_text = False
    mock_mw._restoring_session_state = False
    mock_mw.current_block_idx = -1
    mock_mw.current_string_idx = -1
    mock_mw.current_category_name = None
    mock_mw.data = [["L0", "L1", "L2"]]
    mock_mw.displayed_string_indices = [0, 1, 2]
    mock_mw.block_names = {"0": "Block 0"}
    mock_mw.settings_manager = MagicMock()
    mock_mw.project_manager = MagicMock()
    
    # Setup project structure
    p = mock_mw.project_manager.project
    mock_block = MagicMock()
    mock_block.last_selected_string_idx = -1
    mock_block.categories = []
    p.blocks = [mock_block]
    p.virtual_folders = []
    
    mock_mw.block_to_project_file_map = {0: 0}
    mock_mw.problems_per_subline = {}
    mock_mw.detection_enabled = {}
    mock_mw.undo_manager = MagicMock()
    mock_mw.edited_sublines = set()
    
    # Mock UI
    mock_mw.ui_updater = MagicMock()
    mock_mw.preview_text_edit = MagicMock()
    
    return ListSelectionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)

def test_ListSelectionHandler_init(handler):
    assert handler._restoring_selection is False

def test_ListSelectionHandler_navigate_between_blocks(handler):
    handler.mw.block_list_widget = MagicMock()
    handler.navigate_between_blocks(True)
    handler.mw.block_list_widget.navigate_blocks.assert_called_with(1)

def test_ListSelectionHandler_navigate_between_folders(handler):
    handler.mw.block_list_widget = MagicMock()
    handler.navigate_between_folders(False)
    handler.mw.block_list_widget.navigate_folders.assert_called_with(-1)

def test_ListSelectionHandler_block_selected(handler):
    mock_item = MagicMock()
    # Return block_index=0, category=None
    mock_item.data.side_effect = lambda col, role: 0 if role == Qt.UserRole else None

    # Setup what we want to "restore"
    handler.mw.project_manager.project.blocks[0].last_selected_string_idx = 42
    
    handler.block_selected(mock_item, None)

    assert handler.mw.data_store.current_block_idx == 0
    assert handler.mw.data_store.current_string_idx == 42
    handler.data_processor.schedule_autosave.assert_called_once()

def test_ListSelectionHandler_cleanup_stops_owned_timers(handler):
    handler._cursor_visible_timer.start(1000)
    handler._schedule_string_selection(7)
    assert handler._cursor_visible_timer.isActive()
    assert handler._selection_timer.isActive()
    assert handler._pending_selection_line == 7

    handler.cleanup()

    assert not handler._cursor_visible_timer.isActive()
    assert not handler._selection_timer.isActive()
    assert handler._pending_selection_line is None

def test_ListSelectionHandler_restore_block_selection(handler):
    mock_item = MagicMock()
    mock_item.data.return_value = 0
    handler.mw.data_store.current_block_idx = 0
    handler.mw.block_list_widget = MagicMock()
    
    with patch('handlers.list_selection_handler.QTreeWidgetItemIterator') as mock_iter_class:
        mock_iter = MagicMock()
        mock_iter_class.return_value = mock_iter
        vals = [mock_item, None]
        v_idx = 0
        mock_iter.value.side_effect = lambda: vals[v_idx] if v_idx < len(vals) else None
        def advance(other):
            nonlocal v_idx
            v_idx += 1
            return mock_iter
        mock_iter.__iadd__.side_effect = advance
        
        handler._restore_block_selection()
        handler.mw.block_list_widget.setCurrentItem.assert_called_with(mock_item)

def test_ListSelectionHandler_update_block_toolbar_button_states(handler):
    handler.mw.project_manager.project = MagicMock()
    mock_item = MagicMock()
    mock_parent = mock_item.parent.return_value
    mock_parent.indexOfChild.return_value = 0
    mock_parent.childCount.return_value = 2
    handler.mw.block_list_widget.currentItem.return_value = mock_item
    
    handler._update_block_toolbar_button_states(0)
    handler.mw.delete_block_button.setEnabled.assert_called_with(True)

def test_ListSelectionHandler_select_string_by_absolute_index(handler):
    handler.mw.data_store.displayed_string_indices = [10, 20]
    handler.string_selected_from_preview = MagicMock()
    handler.select_string_by_absolute_index(20)
    handler.string_selected_from_preview.assert_called_with(1)

def test_ListSelectionHandler_string_selected_from_preview(handler):
    handler.mw.data_store.displayed_string_indices = [5, 6, 7]
    handler.mw.data_store.current_block_idx = 0
    handler.mw.data_store.data = [["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7"]]
    
    with patch('handlers.list_selection_handler.QTextCursor') as mock_cursor:
        # Selecting preview line 1 corresponds to abs index 6
        handler.string_selected_from_preview(1)
        assert handler.mw.data_store.current_string_idx == 6
        handler.mw.ui_updater.update_text_views.assert_called()

def test_ListSelectionHandler_rename_block(handler):
    handler.rename_block(MagicMock())
    handler.mw.block_list_widget.editItem.assert_called_once()

def test_ListSelectionHandler_handle_block_item_text_changed(handler):
    mock_item = MagicMock()
    mock_item.text.return_value = "NewName"
    mock_item.data.side_effect = lambda col, role: 0 if role == Qt.UserRole else None
    
    handler.handle_block_item_text_changed(mock_item, 0)
    assert handler.mw.data_store.block_names["0"] == "NewName"
    handler.mw.settings_manager.save_block_names.assert_called_once()

def test_ListSelectionHandler_data_string_has_any_problem(handler):
    handler.mw.current_game_rules = MagicMock()
    handler.mw.detection_enabled = {"p": True}
    handler.mw.data_store.problems_per_subline = {(0, 0, 0): ["p"]}
    handler.data_processor.get_current_string_text.return_value = ("T", None)
    
    assert handler._data_string_has_any_problem(0, 0) is True

def test_ListSelectionHandler_navigate_to_problem_string(handler):
    handler.mw.data_store.current_block_idx = 0
    handler.mw.data_store.data = [["S0", "S1"]]
    handler._data_string_has_any_problem = MagicMock(side_effect=[False, True])
    handler.string_selected_from_preview = MagicMock()
    
    handler.navigate_to_problem_string(True)
    handler.string_selected_from_preview.assert_called_with(1)

def test_ListSelectionHandler_handle_preview_selection_changed(handler):
    mock_preview = handler.mw.preview_text_edit
    mock_preview.hasFocus.return_value = True
    mock_cursor = mock_preview.textCursor.return_value
    mock_cursor.hasSelection.return_value = False
    handler.mw.data_store.current_block_idx = 0
    handler.mw.data_store.current_string_idx = 1
    handler.mw.data_store.displayed_string_indices = [0, 1]
    handler.handle_preview_selection_changed(None)
    mock_preview.set_selected_lines.assert_called_with([1])

@pytest.mark.parametrize("virtual_block_idx", [-3, -2])
def test_ListSelectionHandler_preview_selection_keeps_virtual_folder(handler, virtual_block_idx):
    handler.mw.data_store.current_block_idx = virtual_block_idx
    handler.mw.data_store.physical_block_idx = 5
    handler.mw.data_store.current_string_idx = 0
    handler.mw.data_store.displayed_string_indices = [(5, 0), (7, 2)]
    handler.mw.data_store.data = [[], [], [], [], [], ["S0"], [], ["S0", "S1", "S2"]]

    handler.handle_preview_selection_changed([1])

    assert handler.mw.data_store.current_block_idx == virtual_block_idx
    assert handler.mw.data_store.physical_block_idx == 7
    assert handler.mw.data_store.current_string_idx == 2
    assert handler.mw.data_store.selected_string_indices == [(7, 2)]

def test_ListSelectionHandler_preview_selection_updates_block_in_normal_mode(handler):
    handler.mw.data_store.current_block_idx = 0
    handler.mw.data_store.physical_block_idx = 0
    handler.mw.data_store.current_string_idx = 0
    handler.mw.data_store.displayed_string_indices = [(1, 3)]
    handler.mw.data_store.data = [["S0"], ["S0", "S1", "S2", "S3"]]

    handler.handle_preview_selection_changed([0])

    assert handler.mw.data_store.current_block_idx == 1
    assert handler.mw.data_store.physical_block_idx == 1
    assert handler.mw.data_store.current_string_idx == 3

@pytest.mark.parametrize("virtual_block_idx", [-3, -2])
def test_ListSelectionHandler_string_selected_from_preview_uses_physical_tuple_in_virtual_folder(handler, virtual_block_idx):
    handler.mw.data_store.current_block_idx = virtual_block_idx
    handler.mw.data_store.physical_block_idx = 5
    handler.mw.data_store.current_string_idx = 0
    handler.mw.data_store.displayed_string_indices = [(5, 0), (7, 2)]
    handler.mw.data_store.data = [[], [], [], [], [], ["S0"], [], ["S0", "S1", "S2"]]

    with patch('handlers.list_selection_handler.QTextCursor'):
        handler.string_selected_from_preview(1)

    assert handler.mw.data_store.current_block_idx == virtual_block_idx
    assert handler.mw.data_store.physical_block_idx == 7
    assert handler.mw.data_store.current_string_idx == 2
    handler.mw.preview_text_edit.set_selected_lines.assert_called_with([1])

@patch('PyQt6.QtWidgets.QInputDialog.getText')
def test_ListSelectionHandler_move_selection_to_category(mock_get_text, handler):
    handler.mw.data_store.selected_string_indices = [1]
    handler.mw.data_store.current_block_idx = 0
    mock_get_text.return_value = ("NewCat", True)
    handler.move_selection_to_category()
    handler.mw.project_manager.move_strings_to_category.assert_called_with(0, [1], "NewCat")

@patch('PyQt6.QtWidgets.QInputDialog.getText')
def test_ListSelectionHandler_rename_category(mock_get_text, handler):
    mock_cat = MagicMock()
    mock_cat.name = "Old"
    handler.mw.project_manager.project.blocks[0].categories = [mock_cat]
    mock_get_text.return_value = ("NewCat", True)
    handler.rename_category(0, "Old")
    assert mock_cat.name == "NewCat"

@patch('PyQt6.QtWidgets.QMessageBox.question')
def test_ListSelectionHandler_delete_category(mock_question, handler):
    mock_cat = MagicMock()
    mock_cat.name = "Del"
    handler.mw.project_manager.project.blocks[0].categories = [mock_cat]
    mock_question.return_value = QMessageBox.StandardButton.Yes
    handler.delete_category(0, "Del")
    assert handler.mw.project_manager.project.blocks[0].categories == []

def test_ListSelectionHandler_toggles(handler):
    handler.toggle_highlight_categorized(True)
    assert handler.mw.data_store.highlight_categorized is True
    handler.toggle_hide_categorized(False)
    assert handler.mw.data_store.hide_categorized is False
    handler.toggle_hide_translated(True)
    assert handler.mw.data_store.hide_translated is True
    handler.toggle_show_unsaved_only(True)
    assert handler.mw.data_store.show_unsaved_only is True

# --- New missing coverage tests ---

def test_ListSelectionHandler_string_selected_from_preview_invalid(handler):
    handler.mw.data_store.displayed_string_indices = [5]
    handler.mw.data_store.current_block_idx = 0
    handler.mw.data_store.data = [["S0"]]
    
    # 1. no block
    handler.mw.data_store.current_block_idx = -1
    handler.string_selected_from_preview(0)
    assert handler.mw.data_store.current_string_idx == -1
    
    # 2. invalid rel line
    handler.mw.data_store.current_block_idx = 0
    handler.string_selected_from_preview(99)
    assert handler.mw.data_store.current_string_idx == -1
    
    # 3. clear preview selection branch (when string_idx == -1)
    mock_preview = MagicMock()
    handler.mw.preview_text_edit = mock_preview
    handler.string_selected_from_preview(99)
    mock_preview.highlightManager.clearPreviewSelectedLineHighlight.assert_called()

def test_ListSelectionHandler_handle_block_item_text_changed_empty(handler):
    mock_item = MagicMock()
    mock_item.text.return_value = "   "
    handler.handle_block_item_text_changed(mock_item, 0)
    handler.mw.ui_updater.populate_blocks.assert_called_once()
    
def test_ListSelectionHandler_handle_block_item_text_changed_folder(handler):
    mock_item = MagicMock()
    mock_item.text.return_value = "NewFolder [1/2]"
    mock_item.data.side_effect = lambda col, role: "folder_1" if role == Qt.UserRole + 1 else None
    
    mock_folder = MagicMock()
    mock_folder.id = "folder_1"
    mock_folder.name = "OldFolder"
    mock_folder.parent_id = None
    
    handler.mw.project_manager.find_virtual_folder.return_value = mock_folder
    handler.mw.project_manager.project.virtual_folders = [mock_folder] # no collision
    
    handler.handle_block_item_text_changed(mock_item, 0)
    assert mock_folder.name == "NewFolder"
    handler.mw.project_manager.save.assert_called_once()

def test_ListSelectionHandler_navigate_to_problem_backward(handler):
    handler.mw.data_store.current_block_idx = 0
    handler.mw.data_store.data = [["S0", "S1", "S2"]]
    handler._data_string_has_any_problem = MagicMock(side_effect=lambda b, s: s == 0)
    handler.string_selected_from_preview = MagicMock()
    handler.mw.data_store.current_string_idx = 2
    
    handler.navigate_to_problem_string(False)
    handler.string_selected_from_preview.assert_called_with(0)

def test_ListSelectionHandler_navigate_to_problem_not_found(handler):
    handler.mw.data_store.current_block_idx = 0
    handler.mw.data_store.data = [["S0", "S1"]]
    handler._data_string_has_any_problem = MagicMock(return_value=False)
    handler.string_selected_from_preview = MagicMock()
    
    handler.navigate_to_problem_string(True)
    handler.string_selected_from_preview.assert_not_called()

def test_ListSelectionHandler_preview_selection_with_selection(handler):
    mock_preview = handler.mw.preview_text_edit
    mock_preview.hasFocus.return_value = True
    
    mock_cursor = mock_preview.textCursor.return_value
    mock_cursor.hasSelection.return_value = True
    mock_cursor.selectionStart.return_value = 0
    mock_cursor.selectionEnd.return_value = 10
    
    mock_start_block = MagicMock()
    mock_start_block.blockNumber.return_value = 1
    mock_end_block = MagicMock()
    mock_end_block.blockNumber.return_value = 3
    mock_end_block.position.return_value = 100
    
    mock_preview.document.return_value.findBlock.side_effect = [mock_start_block, mock_end_block]
    
    handler.mw.data_store.displayed_string_indices = [10, 11, 12, 13]
    
    handler.handle_preview_selection_changed(None)
    mock_preview.set_selected_lines.assert_called_with([1, 2, 3])
    assert handler.mw.data_store.selected_string_indices == [11, 12, 13]

def test_ListSelectionHandler_move_selection_to_category_branches(handler):
    # No selection
    handler.mw.data_store.selected_string_indices = []
    with patch('PyQt6.QtWidgets.QMessageBox.warning') as mock_warn:
        handler.move_selection_to_category()
        mock_warn.assert_called_once()
    
    handler.mw.data_store.selected_string_indices = [0]
    # No project
    handler.mw.project_manager.project = None
    handler.move_selection_to_category() # should just return
    
    # Empty input
    handler.mw.project_manager.project = MagicMock()
    with patch('PyQt6.QtWidgets.QInputDialog.getText', return_value=("", True)):
        handler.move_selection_to_category()
        handler.mw.project_manager.move_strings_to_category.assert_not_called()

def test_ListSelectionHandler_toggle_show_overrides_only_checked(handler):
    handler.mw.preview_text_edit.verticalScrollBar().value.return_value = 120
    handler.mw.preview_text_edit.cursorRect.return_value.height.return_value = 20
    handler.mw.data_store.current_string_idx = 2
    handler.mw.data_store.current_block_idx = 0
    handler.mw.data_store.current_category_name = None

    handler.toggle_show_overrides_only(True)

    assert handler._saved_scrollbar_value == 120
    assert handler._saved_string_idx == 2
    assert handler._saved_approx_visible_lines == (120 // 20) + 50
    assert handler.mw.data_store.show_overrides_only is True
    handler.ui_updater.populate_strings_for_block.assert_called_with(0, None)

def test_ListSelectionHandler_toggle_show_overrides_only_unchecked_same_string(handler):
    handler._saved_scrollbar_value = 120
    handler._saved_string_idx = 2
    handler._saved_approx_visible_lines = 56
    
    handler.mw.data_store.current_string_idx = 2
    handler.mw.data_store.current_block_idx = 0
    handler.mw.data_store.current_category_name = None
    
    handler._get_displayed_indices = MagicMock(return_value=[0, 1, 2])
    
    mock_scroll = MagicMock()
    handler.mw.preview_text_edit.verticalScrollBar = MagicMock(return_value=mock_scroll)
    
    handler.toggle_show_overrides_only(False)
    
    assert handler.mw.data_store.show_overrides_only is False
    handler.ui_updater.populate_strings_for_block.assert_called_with(0, None)
    handler.mw.preview_text_edit.set_selected_lines.assert_called_with([2])
    mock_scroll.setValue.assert_called_with(120)
    assert handler._saved_approx_visible_lines == 0


def test_ListSelectionHandler_toggle_show_overrides_only_unchecked_different_string(handler):
    handler._saved_scrollbar_value = 120
    handler._saved_string_idx = 2
    handler._saved_approx_visible_lines = 56
    
    handler.mw.data_store.current_string_idx = 0
    handler.mw.data_store.current_block_idx = 0
    handler.mw.data_store.current_category_name = None
    
    handler.scroll_to_current_string_in_preview = MagicMock()
    
    handler.toggle_show_overrides_only(False)
    
    assert handler.mw.data_store.show_overrides_only is False
    handler.ui_updater.populate_strings_for_block.assert_called_with(0, None)
    handler.scroll_to_current_string_in_preview.assert_called_once()
    assert handler._saved_approx_visible_lines == 0


def test_ListSelectionHandler_toggle_hide_tags_global(handler):
    # The single visible checkbox controls all text panels.
    mock_orig_checkbox = MagicMock()
    handler.mw.hide_original_tags_checkbox = mock_orig_checkbox

    # Scenario 1: unchecked -> checked
    mock_orig_checkbox.isChecked.return_value = False

    handler.toggle_hide_tags_global()

    mock_orig_checkbox.setChecked.assert_called_with(True)

    # Scenario 2: checked -> unchecked
    mock_orig_checkbox.setChecked.reset_mock()
    mock_orig_checkbox.isChecked.return_value = True

    handler.toggle_hide_tags_global()

    mock_orig_checkbox.setChecked.assert_called_with(False)

    # Scenario 3: no checkbox present -> update both settings directly
    del handler.mw.hide_original_tags_checkbox
    handler.mw.data_store.hide_original_tags = False
    handler.mw.data_store.hide_translation_tags = False

    handler.mw.helper = MagicMock()
    handler.mw.data_store.current_block_idx = 0
    handler.mw.data_store.current_category_name = "test_cat"

    handler.toggle_hide_tags_global()
    
    assert handler.mw.data_store.hide_original_tags is True
    assert handler.mw.data_store.hide_translation_tags is True
    handler.mw.helper.reconfigure_all_highlighters.assert_called_once()
    handler.ui_updater.populate_strings_for_block.assert_called_with(0, "test_cat")


def test_ListSelectionHandler_hide_tags_checkbox_updates_all_panels(handler):
    handler.mw.data_store.hide_original_tags = False
    handler.mw.data_store.hide_translation_tags = False
    handler.mw.data_store.current_block_idx = 0
    handler.mw.data_store.current_category_name = "test_cat"
    handler.mw.helper = MagicMock()

    handler.toggle_hide_original_tags(True)

    assert handler.mw.data_store.hide_original_tags is True
    assert handler.mw.data_store.hide_translation_tags is True
    handler.mw.helper.reconfigure_all_highlighters.assert_called_once()
    handler.ui_updater.populate_strings_for_block.assert_called_once_with(0, "test_cat")
    handler.data_processor.schedule_autosave.assert_called_once()


def test_ListSelectionHandler_handle_virtual_row_selection(handler):
    mock_item = MagicMock()
    mock_item.data.side_effect = lambda col, role: {
        Qt.UserRole: 0,
        Qt.UserRole + 1: 1,
        Qt.UserRole + 11: 42
    }.get(role, None)

    # Setup mock translation handler & prompt composer & client
    mock_composer = MagicMock()
    mock_client = MagicMock()
    mock_client.get_chapter_mappings.return_value = [{"bmg_id": "test_Str_1"}]
    mock_composer.prompt_composer._get_mempalace_client.return_value = mock_client
    mock_composer.prompt_composer._get_wing_name.return_value = "Zelda_TP"
    handler.mw.translation_handler = mock_composer
    handler.resolve_bmg_id_to_indices = MagicMock(return_value=(0, 1))
    handler._get_displayed_indices = MagicMock(return_value=[(0, 1)])

    with patch.object(handler, '_schedule_string_selection') as mock_schedule:
        handler._handle_virtual_row_selection(mock_item)
        assert handler.mw.data_store.current_block_idx == 0
        assert handler.mw.data_store.current_string_idx == 1
        assert handler.mw.data_store.current_chapter_id == 42
        assert handler.mw.data_store.chapter_mappings == [(0, 1)]
        mock_schedule.assert_called_once_with(0)


def test_ListSelectionHandler_handle_speaker_selection(handler):
    mock_item = MagicMock()
    mock_item.data.side_effect = lambda col, role: {
        Qt.UserRole + 15: "Zelda",
        Qt.UserRole + 13: [(0, 1), (0, 2)]
    }.get(role, None)

    with patch.object(handler, '_schedule_string_selection') as mock_schedule:
        handler._handle_speaker_selection(mock_item)
        assert handler.mw.data_store.current_block_idx == -3
        assert handler.mw.data_store.current_speaker_name == "Zelda"
        assert handler.mw.data_store.chapter_mappings == [(0, 1), (0, 2)]
        assert handler.mw.data_store.physical_block_idx == 0
        assert handler.mw.data_store.current_string_idx == 1
        mock_schedule.assert_called_once_with(0)


def test_ListSelectionHandler_handle_chapter_selection(handler):
    # Setup mock translation handler & prompt composer & client
    mock_composer = MagicMock()
    mock_client = MagicMock()
    mock_client.get_chapter_mappings.return_value = [{"bmg_id": "test_Str_2"}]
    mock_composer.prompt_composer._get_mempalace_client.return_value = mock_client
    mock_composer.prompt_composer._get_wing_name.return_value = "Zelda_TP"
    handler.mw.translation_handler = mock_composer
    handler.resolve_bmg_id_to_indices = MagicMock(return_value=(0, 2))

    with patch.object(handler, '_schedule_string_selection') as mock_schedule:
        handler._handle_chapter_selection(42)
        assert handler.mw.data_store.current_block_idx == -2
        assert handler.mw.data_store.current_chapter_id == 42
        assert handler.mw.data_store.chapter_mappings == [(0, 2)]
        assert handler.mw.data_store.physical_block_idx == 0
        assert handler.mw.data_store.current_string_idx == 2
        mock_schedule.assert_called_once_with(0)


def test_ListSelectionHandler_handle_folder_selection(handler):
    handler.mw.string_settings_updater = MagicMock()
    handler._handle_folder_selection()
    assert handler.mw.data_store.current_block_idx == -1
    assert handler.mw.data_store.physical_block_idx == -1
    assert handler.mw.data_store.current_string_idx == -1
    handler.mw.string_settings_updater.update_string_settings_panel.assert_called()


def test_ListSelectionHandler_handle_physical_block_selection(handler):
    handler.mw.project_manager.project = MagicMock()
    handler.mw.project_manager.project.blocks = [MagicMock()]
    handler.mw.project_manager.project.blocks[0].last_selected_string_idx = 5
    handler.mw.block_to_project_file_map = {0: 0}
    handler._get_displayed_indices = MagicMock(return_value=[5])
    handler.mw.string_settings_updater = MagicMock()

    with patch.object(handler, '_schedule_string_selection') as mock_schedule:
        handler._handle_physical_block_selection(0, "test_cat", -1, -1, None)
        assert handler.mw.data_store.current_block_idx == 0
        assert handler.mw.data_store.physical_block_idx == 0
        assert handler.mw.data_store.current_string_idx == 5
        assert handler.mw.data_store.current_category_name == "test_cat"
        mock_schedule.assert_called_once_with(0)



