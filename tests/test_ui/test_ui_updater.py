import pytest
# Auto-generated test file for ui/ui_updater.py

from unittest.mock import MagicMock, patch
from ui.ui_updater import UIUpdater
from utils.constants import APP_VERSION

@pytest.fixture
def updater(mock_mw):
    return UIUpdater(mock_mw, MagicMock())

def test_UIUpdater_init(updater, mock_mw):
    assert updater.mw == mock_mw
    assert updater.data_processor is not None

def test_UIUpdater_get_tree_state(updater):
    from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
    from PyQt5.QtCore import Qt
    updater.mw.block_list_widget = QTreeWidget()
    
    item = QTreeWidgetItem(["Block 0"])
    item.setData(0, Qt.UserRole, 0)
    item.addChild(QTreeWidgetItem(["Child"]))
    updater.mw.block_list_widget.addTopLevelItem(item)
    updater.mw.block_list_widget.setCurrentItem(item)
    item.setExpanded(True)

    state = updater.get_tree_state()
    assert "block_0" in state["expanded_ids"]
    assert "block_0" == state["selected_id"]

def test_UIUpdater_apply_tree_state(updater):
    from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
    from PyQt5.QtCore import Qt
    updater.mw.block_list_widget = QTreeWidget()
    item = QTreeWidgetItem(["Block 0"])
    item.setData(0, Qt.UserRole, 0)
    updater.mw.block_list_widget.addTopLevelItem(item)
    
    state = {
        "expanded_ids": ["block_0"],
        "selected_id": "block_0",
        "selected_type": "block",
        "selected_string_idx": 0,
        "v_scroll": 0,
        "h_scroll": 0
    }
    with patch('PyQt5.QtCore.QTimer.singleShot', side_effect=lambda ms, func: func()):
        updater.apply_tree_state(state)
    assert item.isExpanded()
    # verify that block selection is restored
    updater.mw.list_selection_handler.block_selected.assert_called_with(item, None)

def test_UIUpdater_get_item_id(updater):
    from PyQt5.QtWidgets import QTreeWidgetItem
    from PyQt5.QtCore import Qt
    item = QTreeWidgetItem(["Test"])
    item.setData(0, Qt.UserRole, 1)
    result = updater._get_item_id(item)
    assert result == "block_1"

def test_UIUpdater_highlight_glossary_occurrence(updater):
    from core.glossary_manager import GlossaryOccurrence, GlossaryEntry
    entry = GlossaryEntry(original="test", translation="test")
    occurrence = GlossaryOccurrence(entry=entry, block_idx=0, string_idx=0, line_idx=5, start=2, end=6, line_text="test")
    updater.mw.original_text_edit.highlightManager = MagicMock()
    updater.highlight_glossary_occurrence(occurrence)
    updater.mw.original_text_edit.highlightManager.add_search_match_highlight.assert_called_with(5, 2, 4)

def test_UIUpdater_get_aggregated_problems_for_block(updater):
    updater.mw.data_store.data = [[]]
    updater.mw.current_game_rules = MagicMock()
    updater.mw.current_game_rules.get_problem_definitions.return_value = {"prob1": {}, "prob2": {}}
    updater.mw.data_store.problems_per_subline = {
        (0, 0, 0): {"prob1", "prob2"}
    }
    updater.mw.detection_enabled = {"prob1": True, "prob2": False}
    result = updater._get_aggregated_problems_for_block(0)
    assert result.get("prob1") == 1
    assert result.get("prob2") == 0

def test_UIUpdater_create_block_tree_item(updater):
    from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
    updater.mw.block_list_widget = QTreeWidget()
    mock_item = QTreeWidgetItem([])
    updater.mw.block_list_widget.create_item = MagicMock(return_value=mock_item)
    updater.mw.data_store.block_names = {"0": "Block Zero"}
    updater.mw.data_store.problems_per_subline = {}
    updater.mw.current_game_rules = MagicMock()
    updater.mw.project_manager = None
    item = updater._create_block_tree_item(0, {})
    assert item == mock_item

def test_UIUpdater_add_virtual_folder_to_tree(updater):
    from PyQt5.QtWidgets import QTreeWidget
    from PyQt5.QtGui import QIcon
    updater.mw.block_list_widget = QTreeWidget()
    updater.mw.project_manager.project = MagicMock()
    updater.mw.project_manager.project.blocks = []
    updater.mw.style.return_value.standardIcon.return_value = QIcon()
    folder = MagicMock()
    folder.name = "TestFolder"
    folder.is_expanded = False
    folder.children = []
    folder.block_ids = []
    updater._add_virtual_folder_to_tree(updater.mw.block_list_widget.invisibleRootItem(), folder, {}, None)

def test_UIUpdater_populate_blocks(updater):
    from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
    updater.mw.block_list_widget = QTreeWidget()
    mock_item = QTreeWidgetItem([])
    updater.mw.block_list_widget.create_item = MagicMock(return_value=mock_item)
    updater.mw.data_store.data = [[]]
    updater.mw.data_store.block_names = {"0": "Block 0"}
    updater.mw.current_game_rules = MagicMock()
    updater.mw.project_manager = None
    updater.mw.block_list_widget.clear = MagicMock()
    updater.populate_blocks()
    updater.mw.block_list_widget.clear.assert_called()

def test_UIUpdater_update_block_item_text_with_problem_count(updater):
    from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
    from PyQt5.QtCore import Qt
    updater.mw.block_list_widget = QTreeWidget()
    item = QTreeWidgetItem(["Block 0"])
    item.setData(0, Qt.UserRole, 0) # block_idx
    item.setData(0, Qt.UserRole + 4, "Block 0 Base") # base_name
    updater.mw.block_list_widget.addTopLevelItem(item)
    
    updater.mw.current_game_rules = MagicMock()
    updater.mw.current_game_rules.get_problem_definitions.return_value = {"prob1": {"priority": 1}}
    updater.mw.current_game_rules.get_short_problem_name.return_value = "P1"
    updater._get_aggregated_problems_for_block = MagicMock(return_value={"prob1": 2})
    
    updater.update_block_item_text_with_problem_count(0)
    assert item.text(0) == "Block 0 Base (2 P1)"

def test_UIUpdater_synchronize_original_cursor(updater, mock_mw):
    mock_edited_cursor = MagicMock()
    mock_edited_cursor.blockNumber.return_value = 2
    mock_edited_cursor.positionInBlock.return_value = 5
    
    mock_mw.edited_text_edit = MagicMock()
    mock_mw.edited_text_edit.textCursor.return_value = mock_edited_cursor
    mock_mw.edited_text_edit.document.return_value.toPlainText.return_value = "nonempty"
    
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    
    mock_mw.original_text_edit = MagicMock()
    mock_mw.original_text_edit.highlightManager = MagicMock()
    
    updater.synchronize_original_cursor()
    
    mock_mw.original_text_edit.highlightManager.setLinkedCursorPosition.assert_called_with(2, 5)

def test_UIUpdater_apply_highlights_for_block(updater, mock_mw):
    mock_mw.preview_text_edit = MagicMock()
    mock_mw.preview_text_edit.highlightManager = MagicMock()
    mock_mw.current_game_rules = MagicMock()
    mock_mw.data = [["s1", "s2"]]
    mock_mw.displayed_string_indices = [0, 1]
    
    mock_mw.list_selection_handler._data_string_has_any_problem.side_effect = lambda b, r: r == 1
    updater._apply_highlights_for_block(0)
    
    mock_mw.preview_text_edit.highlightManager.clearAllProblemHighlights.assert_called_once()
    mock_mw.preview_text_edit.addProblemLineHighlight.assert_called_once_with(1)

def test_UIUpdater_apply_highlights_to_editor(updater, mock_mw):
    editor = MagicMock()
    editor.highlightManager = MagicMock()
    doc = MagicMock()
    doc.blockCount.return_value = 2
    editor.document.return_value = doc
    
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.get_problem_definitions.return_value = {
        "P1": {"severity": "error"},
        "P2": {"color": "warning_color"}
    }
    mock_mw.problems_per_subline = {
        (0, 0, 0): {"P1"},
        (0, 0, 1): {"P2"}
    }
    
    updater._apply_highlights_to_editor(editor, 0, 0)
    
    editor.highlightManager.clearAllProblemHighlights.assert_called_once()
    editor.highlightManager.addCriticalProblemHighlight.assert_called_once_with(0)
    editor.highlightManager.addWarningLineHighlight.assert_called_once_with(1, "warning_color")

def test_UIUpdater_apply_highlights_for_block_no_edit(updater, mock_mw):
    """Early return when preview_edit is None."""
    mock_mw.preview_text_edit = None
    updater._apply_highlights_for_block(0)  # should not raise

def test_UIUpdater_apply_highlights_for_block_no_rules(updater, mock_mw):
    """Early return when current_game_rules is None."""
    mock_mw.preview_text_edit = MagicMock()
    del mock_mw.preview_text_edit.highlightManager  # no highlightManager
    mock_mw.current_game_rules = MagicMock()
    updater._apply_highlights_for_block(0)

def test_UIUpdater_apply_highlights_for_block_out_of_range(updater, mock_mw):
    """Early return when block_idx is out of range."""
    mock_mw.preview_text_edit = MagicMock()
    mock_mw.preview_text_edit.highlightManager = MagicMock()
    mock_mw.current_game_rules = MagicMock()
    mock_mw.data = [["s1"]]
    updater._apply_highlights_for_block(5)  # out of range
    mock_mw.preview_text_edit.highlightManager.clearAllProblemHighlights.assert_called_once()
    mock_mw.preview_text_edit.addProblemLineHighlight.assert_not_called()

def test_UIUpdater_apply_highlights_for_block_with_no_displayed_indices(updater, mock_mw):
    """When displayed_string_indices is empty, uses all indices."""
    mock_mw.preview_text_edit = MagicMock()
    mock_mw.preview_text_edit.highlightManager = MagicMock()
    mock_mw.current_game_rules = MagicMock()
    mock_mw.data = [["s1", "s2"]]
    mock_mw.displayed_string_indices = []  # empty, should auto use all
    mock_mw.list_selection_handler._data_string_has_any_problem.return_value = False
    updater._apply_highlights_for_block(0)
    mock_mw.preview_text_edit.highlightManager.clearAllProblemHighlights.assert_called_once()

def test_UIUpdater_apply_highlights_for_block_with_categorized(updater, mock_mw):
    """Test highlight_categorized branch."""
    mock_mw.preview_text_edit = MagicMock()
    mock_mw.preview_text_edit.highlightManager = MagicMock()
    mock_mw.current_game_rules = MagicMock()
    mock_mw.data = [["s1", "s2"]]
    mock_mw.displayed_string_indices = [0, 1]
    mock_mw.highlight_categorized = True
    mock_mw.current_category_name = None
    mock_mw.list_selection_handler._data_string_has_any_problem.return_value = False
    
    pm = MagicMock()
    proj = MagicMock()
    block = MagicMock()
    cat = MagicMock(); cat.line_indices = [0]
    block.categories = [cat]
    proj.blocks = [block]
    pm.project = proj
    mock_mw.project_manager = pm
    mock_mw.block_to_project_file_map = {0: 0}
    
    updater._apply_highlights_for_block(0)
    mock_mw.preview_text_edit.highlightManager.setCategorizedLineHighlights.assert_called_once()

def test_UIUpdater_apply_highlights_to_editor_no_editor(updater, mock_mw):
    """Early return when editor is None."""
    updater._apply_highlights_to_editor(None, 0, 0)  # should not raise

def test_UIUpdater_apply_highlights_to_editor_negative_idx(updater, mock_mw):
    """Early return when block_idx or string_idx is negative."""
    editor = MagicMock()
    editor.highlightManager = MagicMock()
    updater._apply_highlights_to_editor(editor, -1, 0)
    editor.highlightManager.clearAllProblemHighlights.assert_called_once()
    editor.document.assert_not_called()  # should not proceed

def test_UIUpdater_apply_highlights_to_editor_with_empty_subline_problem(updater, mock_mw):
    """Test the PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY branch (line 762-764)."""
    editor = MagicMock()
    editor.highlightManager = MagicMock()
    doc = MagicMock()
    doc.blockCount.return_value = 1
    editor.document.return_value = doc
    
    problem_ids = MagicMock()
    problem_ids.PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = "PEOS"
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.get_problem_definitions.return_value = {}
    mock_mw.current_game_rules.problem_ids = problem_ids
    mock_mw.problems_per_subline = {(0, 0, 0): {"PEOS"}}
    
    updater._apply_highlights_to_editor(editor, 0, 0)
    editor.highlightManager.addEmptyOddSublineHighlight.assert_called_once_with(0)

def test_UIUpdater_get_all_categorized_indices_for_block(updater, mock_mw):
    assert updater._get_all_categorized_indices_for_block(-1) == set()
    
    pm = MagicMock()
    proj = MagicMock()
    block = MagicMock()
    cat1 = MagicMock(); cat1.line_indices = [0, 1]
    cat2 = MagicMock(); cat2.line_indices = [1, 2]
    block.categories = [cat1, cat2]
    proj.blocks = [block]
    pm.project = proj
    mock_mw.project_manager = pm
    mock_mw.block_to_project_file_map = {0: 0}
    
    assert updater._get_all_categorized_indices_for_block(0) == {0, 1, 2}

@patch.object(UIUpdater, 'update_text_views')
@patch.object(UIUpdater, '_apply_highlights_for_block')
def test_UIUpdater_populate_strings_for_block(mock_hl, mock_ut, updater, mock_mw):
    mock_mw.data = [["s1", "s2", "s3"]]
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: f"p_{x}"
    mock_mw.preview_text_edit = MagicMock()
    mock_mw.preview_text_edit.highlightManager = MagicMock()
    mock_mw.preview_text_edit.document.return_value.blockCount.return_value = 3
    mock_mw.preview_text_edit.toPlainText.return_value = ""
    mock_mw.project_manager = None  # Disable category logic
    updater.data_processor.get_current_string_text.side_effect = lambda b, r: (f"t_{r}", False)
    mock_mw.current_string_idx = -1
    mock_mw.displayed_string_indices = []
    
    updater.populate_strings_for_block(0, force=True)
    
    mock_mw.preview_text_edit.setPlainText.assert_called_with("p_t_0\np_t_1\np_t_2")
    mock_hl.assert_called_once_with(0)
    mock_ut.assert_called_once()
    assert mock_mw.displayed_string_indices == [0, 1, 2]

@patch.object(UIUpdater, 'synchronize_original_cursor')
@patch.object(UIUpdater, 'update_text_views')
def test_UIUpdater_populate_strings_for_block_invalid(mock_ut, mock_sync, updater, mock_mw):
    """Test populate_strings_for_block w/ invalid block_idx -> clears state."""
    mock_mw.data = []
    mock_mw.project_manager = None
    mock_mw.displayed_string_indices = [5, 6]
    mock_mw.preview_text_edit = MagicMock()
    mock_mw.original_text_edit = MagicMock()
    mock_mw.edited_text_edit = MagicMock()
    
    updater.populate_strings_for_block(-1)
    
    assert mock_mw.displayed_string_indices == []
    mock_mw.preview_text_edit.setPlainText.assert_called_with("")
    mock_ut.assert_called_once()


def test_UIUpdater_update_text_views(updater, mock_mw):
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    mock_mw.data = [["orig"]]
    updater.data_processor._get_string_from_source.return_value = "orig"
    updater.data_processor.get_current_string_text.return_value = ("edit", False)
    
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.get_text_representation_for_editor.side_effect = lambda x: f"E_{x}"
    mock_mw.show_multiple_spaces_as_dots = False
    
    # Create proper mock cursors (position/anchor/hasSelection need int return values)
    def make_cursor():
        c = MagicMock()
        c.position.return_value = 0
        c.anchor.return_value = 0
        c.hasSelection.return_value = False
        return c
    
    mock_mw.original_text_edit = MagicMock()
    mock_mw.edited_text_edit = MagicMock()
    mock_mw.original_text_edit.toPlainText.return_value = ""
    mock_mw.edited_text_edit.toPlainText.return_value = ""
    mock_mw.original_text_edit.textCursor.return_value = make_cursor()
    mock_mw.edited_text_edit.textCursor.return_value = make_cursor()
    mock_mw.problems_per_subline = {}
    
    updater.update_text_views()
    
    mock_mw.original_text_edit.setPlainText.assert_called_with("E_orig")
    mock_mw.edited_text_edit.setPlainText.assert_called_with("E_edit")

def test_UIUpdater_update_text_views_no_selection(updater, mock_mw):
    """Test where current_block_idx = -1 (inactive case)"""
    mock_mw.current_block_idx = -1
    mock_mw.current_string_idx = -1
    mock_mw.current_game_rules = None
    mock_mw.show_multiple_spaces_as_dots = False
    mock_mw.original_text_edit = MagicMock()
    mock_mw.edited_text_edit = MagicMock()
    mock_mw.original_text_edit.toPlainText.return_value = ""
    mock_mw.edited_text_edit.toPlainText.return_value = ""
    mock_mw.original_text_edit.textCursor = MagicMock()
    mock_mw.edited_text_edit.textCursor = MagicMock()
    
    updater.update_text_views()
    # With empty string, setPlainText is not called (no diff)
    mock_mw.original_text_edit.setPlainText.assert_not_called()

@patch.object(UIUpdater, 'update_text_views')
@patch.object(UIUpdater, '_apply_highlights_for_block')
def test_UIUpdater_populate_strings_with_project_manager(mock_hl, mock_ut, updater, mock_mw):
    """Populate with real project_manager so category logic is exercised."""
    pm = MagicMock()
    proj = MagicMock()
    block = MagicMock()
    block.categories = []  # no categories
    proj.blocks = [block]
    pm.project = proj  
    mock_mw.project_manager = pm
    mock_mw.block_to_project_file_map = {0: 0}
    
    mock_mw.data = [["s1", "s2"]]
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: f"p_{x}"
    mock_mw.preview_text_edit = MagicMock()
    mock_mw.preview_text_edit.toPlainText.return_value = ""
    mock_mw.preview_text_edit.highlightManager = MagicMock()
    mock_mw.preview_text_edit.document.return_value.blockCount.return_value = 2
    mock_mw.current_string_idx = -1
    mock_mw.displayed_string_indices = []
    updater.data_processor.get_current_string_text.side_effect = lambda b, r: (f"t_{r}", False)
    
    updater.populate_strings_for_block(0, force=True)
    
    # Verify that the full string set is displayed
    assert mock_mw.displayed_string_indices == [0, 1]

def test_UIUpdater_update_text_views_with_width_label(updater, mock_mw):
    """Test update_text_views with original_width_label."""
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    mock_mw.data = [["orig"]]
    updater.data_processor._get_string_from_source.return_value = "orig"
    updater.data_processor.get_current_string_text.return_value = ("orig", False)
    mock_mw.current_game_rules = None
    mock_mw.show_multiple_spaces_as_dots = False
    mock_mw.original_text_edit = MagicMock()
    mock_mw.edited_text_edit = MagicMock()
    mock_mw.original_text_edit.toPlainText.return_value = ""
    mock_mw.edited_text_edit.toPlainText.return_value = ""
    
    c = MagicMock(); c.position.return_value = 0; c.anchor.return_value = 0; c.hasSelection.return_value = False
    mock_mw.original_text_edit.textCursor.return_value = c
    mock_mw.edited_text_edit.textCursor.return_value = c
    mock_mw.problems_per_subline = {}
    
    # Add original_width_label to cover those lines
    mock_mw.original_width_label = MagicMock()
    mock_mw.helper = MagicMock()
    mock_mw.helper.get_font_map_for_string.return_value = {}
    mock_mw.icon_sequences = []
    
    with patch('ui.ui_updater.calculate_strict_string_width', return_value=42):
        updater.update_text_views()
    
    mock_mw.original_width_label.setText.assert_called_with("Width: 42px")
    mock_mw.original_width_label.show.assert_called()


@patch.object(UIUpdater, 'update_text_views')
@patch.object(UIUpdater, '_apply_highlights_for_block')
def test_UIUpdater_populate_strings_with_category(mock_hl, mock_ut, updater, mock_mw):
    """Populate with category_name so lines 833-840 are covered."""
    pm = MagicMock()
    proj = MagicMock()
    block = MagicMock()
    cat = MagicMock(); cat.name = "MyCat"; cat.line_indices = [2, 3]
    block.categories = [cat]
    proj.blocks = [block]
    pm.project = proj
    mock_mw.project_manager = pm
    mock_mw.block_to_project_file_map = {0: 0}
    
    mock_mw.data = [["s0", "s1", "s2", "s3"]]
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: f"p_{x}"
    mock_mw.preview_text_edit = MagicMock()
    mock_mw.preview_text_edit.toPlainText.return_value = ""
    mock_mw.preview_text_edit.highlightManager = MagicMock()
    mock_mw.preview_text_edit.document.return_value.blockCount.return_value = 2
    mock_mw.current_string_idx = 2  # within category
    mock_mw.displayed_string_indices = []
    updater.data_processor.get_current_string_text.side_effect = lambda b, r: (f"t_{r}", False)
    
    updater.populate_strings_for_block(0, category_name="MyCat", force=True)
    
    assert mock_mw.displayed_string_indices == [2, 3]
    mock_mw.preview_text_edit.set_selected_lines.assert_called_with([0])  # current_string_idx=2 maps to idx 0


def test_UIUpdater_update_status_bar(updater):
    mock_cursor = MagicMock()
    mock_cursor.hasSelection.return_value = False
    mock_cursor.positionInBlock.return_value = 5
    mock_block = MagicMock()
    mock_block.text.return_value = "Line text"
    mock_cursor.block.return_value = mock_block
    updater.mw.edited_text_edit.textCursor.return_value = mock_cursor
    updater.mw.data_store.current_block_idx = 0
    updater.mw.data_store.current_string_idx = 0
    updater.update_status_bar()
    updater.mw.status_label_part1.setText.assert_called_with("Pos: 5")

def test_UIUpdater_update_status_bar_selection(updater):
    mock_cursor = MagicMock()
    mock_cursor.hasSelection.return_value = True
    mock_cursor.selectedText.return_value = "Selected text"
    
    mock_doc = MagicMock()
    mock_block = MagicMock()
    mock_block.position.return_value = 0
    mock_doc.findBlock.return_value = mock_block
    updater.mw.edited_text_edit.document.return_value = mock_doc
    
    mock_cursor.selectionStart.return_value = 0
    updater.mw.edited_text_edit.textCursor.return_value = mock_cursor
    updater.mw.data_store.current_block_idx = 0
    updater.mw.data_store.current_string_idx = 0

    updater.update_status_bar_selection()
    updater.mw.status_label_part1.setText.assert_called()

def test_UIUpdater_clear_status_bar(updater):
    updater.clear_status_bar()
    updater.mw.status_label_part1.setText.assert_called_with("Pos: 0")
    updater.mw.status_label_part2.setText.assert_called_with("Line: 0/0")
    updater.mw.status_label_part3.setText.assert_called_with("Width: 0px")

def test_UIUpdater_synchronize_original_cursor(updater):
    updater.mw.data_store.current_block_idx = 0
    updater.mw.data_store.current_string_idx = 0
    updater.mw.edited_text_edit.document().toPlainText.return_value = "Non empty"
    updater.mw.original_text_edit.highlightManager = MagicMock()

    mock_cursor = MagicMock()
    mock_cursor.blockNumber.return_value = 5
    mock_cursor.positionInBlock.return_value = 10
    updater.mw.edited_text_edit.textCursor.return_value = mock_cursor
    
    updater.synchronize_original_cursor()
    updater.mw.original_text_edit.highlightManager.setLinkedCursorPosition.assert_called_with(5, 10)

def test_UIUpdater_highlight_problem_block(updater):
    # Method is currently an empty pass, just ensure it runs
    updater.highlight_problem_block(0, True, is_critical=True)

def test_UIUpdater_clear_all_problem_block_highlights_and_text(updater):
    from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
    from PyQt5.QtCore import Qt
    updater.mw.block_list_widget = QTreeWidget()
    item = QTreeWidgetItem(["Block 0"])
    item.setData(0, Qt.UserRole, 0)
    item.setData(0, Qt.UserRole + 4, "Block 0 Base")
    updater.mw.block_list_widget.addTopLevelItem(item)
    
    updater.mw.data_store.block_names = {"0": "Block 0"}
    updater.clear_all_problem_block_highlights_and_text()
    assert item.text(0) == "Block 0 Base"

def test_UIUpdater_update_title(updater):
    updater.mw.data_store.unsaved_changes = True
    updater.mw.project_manager.project.name = "TestProj"
    updater.update_title()
    updater.mw.setWindowTitle.assert_called()
    title_arg = updater.mw.setWindowTitle.call_args[0][0]
    assert "TestProj" in title_arg

def test_UIUpdater_update_plugin_status_label(updater):
    updater.mw.current_game_rules.get_display_name.return_value = "pokemon_fr"
    updater.update_plugin_status_label()
    updater.mw.plugin_status_label.setText.assert_called_with("Plugin: pokemon_fr")

def test_UIUpdater_update_statusbar_paths(updater):
    updater.mw.data_store.json_path = "some_orig.json"
    updater.mw.data_store.edited_json_path = "some_edited.json"
    updater.mw.original_path_label = MagicMock()
    updater.mw.edited_path_label = MagicMock()
    updater.update_statusbar_paths()
    updater.mw.original_path_label.setText.assert_called()
    updater.mw.edited_path_label.setText.assert_called()

def test_UIUpdater_clear_highlights_no_base_name(updater):
    """Cover line 656: base_display_name is None (no UserRole+4 set)."""
    from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
    from PyQt5.QtCore import Qt
    updater.mw.block_list_widget = QTreeWidget()
    item = QTreeWidgetItem(["Block 0"])
    item.setData(0, Qt.UserRole, 0)
    # NOT setting UserRole+4, so base_display_name will be None -> falls back to block_names
    updater.mw.block_list_widget.addTopLevelItem(item)
    updater.mw.data_store.block_names = {"0": "Block 0"}
    updater.clear_all_problem_block_highlights_and_text()
    # No error and item text restored
    assert item.text(0) == "Block 0"

def test_UIUpdater_update_title_json_path(updater):
    """Cover line 670: json_path branch."""
    updater.mw.project_manager = None  # no project
    updater.mw.data_store.json_path = "some_file.json"
    updater.mw.data_store.unsaved_changes = False
    updater.update_title()
    title_arg = updater.mw.setWindowTitle.call_args[0][0]
    assert "some_file.json" in title_arg

def test_UIUpdater_update_title_no_file(updater):
    """Cover line 672-673: no file open branch."""
    updater.mw.project_manager = None
    updater.mw.data_store.json_path = None
    updater.mw.data_store.unsaved_changes = False
    updater.update_title()
    title_arg = updater.mw.setWindowTitle.call_args[0][0]
    assert "No File Open" in title_arg

def test_UIUpdater_update_plugin_status_label_no_rules(updater):
    """Cover line 684: plugin_status_label with no game rules."""
    updater.mw.current_game_rules = None
    updater.update_plugin_status_label()
    updater.mw.plugin_status_label.setText.assert_called_with("Plugin: [None]")

def test_UIUpdater_synchronize_original_cursor_no_text(updater, mock_mw):
    """Cover line 626: early return when current_block_idx == -1."""
    mock_mw.current_block_idx = -1
    mock_mw.current_string_idx = -1
    mock_mw.edited_text_edit = MagicMock()
    mock_mw.edited_text_edit.document.return_value.toPlainText.return_value = ""
    mock_mw.original_text_edit = MagicMock()
    mock_mw.original_text_edit.highlightManager = MagicMock()
    
    updater.synchronize_original_cursor()
    # When current_block_idx==-1, original cursor sync still tells highlightManager to clear position
    mock_mw.original_text_edit.highlightManager.setLinkedCursorPosition.assert_called_with(-1, -1)

