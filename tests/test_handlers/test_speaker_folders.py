# tests/test_handlers/test_speaker_folders.py
import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt
from handlers.list_selection_handler import ListSelectionHandler
from ui.updaters.block_list_updater import BlockListUpdater
from ui.updaters.string_settings_updater import StringSettingsUpdater

@pytest.fixture
def mock_project():
    project = MagicMock()
    block = MagicMock()
    block.metadata = {"character_assignments": {"0": "Hero"}}
    project.blocks = [block]
    return project

def test_save_speaker_for_current_string(qapp, mock_mw, mock_project):
    """Test saving speaker assignment and verifying metadata updates."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_string_idx = 0
    mock_mw.block_to_project_file_map = {0: 0}
    
    mock_mw.block_list_widget = MagicMock()
    mock_item = MagicMock()
    mock_item.data.return_value = 0
    mock_mw.block_list_widget.currentItem.return_value = mock_item

    mock_mw.ui_updater = MagicMock()
    mock_mw.ui_updater.block_list_updater = MagicMock()
    mock_mw.string_settings_updater = MagicMock()
    mock_mw.data_processor = MagicMock()

    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)
    
    # Save a new speaker
    handler.save_speaker_for_current_string("Villain")
    assert mock_project.blocks[0].metadata["character_assignments"]["0"] == "Villain"
    mock_mw.project_manager.save.assert_called_once()
    mock_mw.ui_updater.block_list_updater.populate_blocks.assert_called_once()
    mock_mw.data_processor.schedule_autosave.assert_called_once()

    # Clear speaker (empty string)
    mock_mw.project_manager.save.reset_mock()
    handler.save_speaker_for_current_string("")
    assert "0" not in mock_project.blocks[0].metadata["character_assignments"]
    mock_mw.project_manager.save.assert_called_once()

def test_save_speaker_restores_editor_focus_after_combobox_change(qapp, mock_mw, mock_project):
    """Regression: Ctrl+Z after speaker combobox selection should reach app undo, not the combobox line edit."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_string_idx = 0
    mock_mw.block_to_project_file_map = {0: 0}

    mock_mw.block_list_widget = MagicMock()
    mock_item = MagicMock()
    mock_item.data.return_value = 0
    mock_mw.block_list_widget.currentItem.return_value = mock_item

    mock_mw.ui_updater = MagicMock()
    mock_mw.ui_updater.block_list_updater = MagicMock()
    mock_mw.string_settings_updater = MagicMock()
    mock_mw.data_processor = MagicMock()

    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)

    with patch('handlers.list_selection_handler.QTimer.singleShot', side_effect=lambda _ms, callback: callback()):
        handler.save_speaker_for_current_string("Villain")

    mock_mw.edited_text_edit.setFocus.assert_called_once_with(Qt.FocusReason.OtherFocusReason)

def test_populate_speakers_folder(qapp, mock_mw, mock_project):
    """Test populating the virtual Speakers folder in tree widget."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    
    # Create real widget to test QTreeWidgetItem additions
    from PyQt6.QtWidgets import QTreeWidget
    tree = QTreeWidget()
    mock_mw.block_list_widget = tree
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.get_problem_definitions.return_value = {}
    
    # Enable show_unsaved_blocks_only = False
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.show_unsaved_blocks_only = False
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.problems_per_subline = {}

    updater = BlockListUpdater(mock_mw, mock_mw.data_processor)
    updater.populate_blocks()
    
    # We should have a root item "Speakers" and a child item "Hero"
    root = tree.invisibleRootItem()
    speakers_node = None
    for i in range(root.childCount()):
        child = root.child(i)
        if child.text(0) == "Speakers":
            speakers_node = child
            break
            
    assert speakers_node is not None
    assert speakers_node.childCount() == 1
    assert speakers_node.child(0).text(0) == "Hero"
    assert speakers_node.child(0).data(0, Qt.ItemDataRole.UserRole) == -3
    assert speakers_node.child(0).data(0, Qt.ItemDataRole.UserRole + 15) == "Hero"

def test_select_speaker_folder(qapp, mock_mw, mock_project):
    """Test selecting a Speaker folder item updates the displayed preview mapping."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    mock_mw.data_store.current_block_idx = -1
    mock_mw.data_store.chapter_mappings = []
    
    # Crucial state mock so block_selected doesn't exit early
    mock_mw.is_loading_data = False
    mock_mw._restoring_selection = False
    mock_mw.is_programmatically_changing_text = False
    
    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)
    
    # Create fake item for speaker
    item = QTreeWidgetItem(["Hero"])
    user_role_int = int(Qt.ItemDataRole.UserRole)
    item.setData(0, user_role_int, -3)
    item.setData(0, user_role_int + 15, "Hero")
    item.setData(0, user_role_int + 13, [(0, 0)]) # Set pre-calculated mappings
    
    mock_mw.block_list_widget = MagicMock()
    mock_mw.block_list_widget.currentItem.return_value = item
    
    handler.block_selected(item, 0)
    assert mock_mw.data_store.current_block_idx == -3
    assert mock_mw.data_store.physical_block_idx == 0
    assert mock_mw.current_speaker_name == "Hero"
    assert mock_mw.chapter_mappings == [(0, 0)]
    mock_mw.ui_updater.populate_strings_for_block.assert_called_with(-3)

def test_string_settings_updater_speakers(qapp, mock_mw, mock_project):
    """Test speaker_combobox populating and text setting in settings updater."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_string_idx = 0
    
    print(f"DEBUG UPDATER TEST: mock_mw.project_manager.project = {mock_mw.project_manager.project}")
    print(f"DEBUG UPDATER TEST: mock_project = {mock_project}")
    
    from PyQt6.QtWidgets import QComboBox, QLabel
    cb = QComboBox()
    cb.setEditable(True)
    mock_mw.speaker_combobox = cb
    
    lbl = QLabel()
    mock_mw.speaker_select_label = lbl
    
    spk_lbl = QLabel()
    mock_mw.speaker_label = spk_lbl
    
    mock_mw.font_combobox = MagicMock()
    mock_mw.width_spinbox = MagicMock()
    mock_mw.apply_width_button = MagicMock()
    mock_mw.block_to_project_file_map = {0: 0}
    
    updater = StringSettingsUpdater(mock_mw, mock_mw.data_processor)
    
    # Populate string 0 which has speaker "Hero"
    updater.update_string_settings_panel()
    
    # hero, empty option, and None option
    assert cb.count() == 3
    assert cb.itemText(1) == "None"
    assert cb.itemText(2) == "Hero"
    assert cb.currentText() == "Hero"
    
    # Check that tooltips are assigned successfully to both cb and lbl
    assert cb.toolTip() != ""
    assert lbl.toolTip() != ""
    assert cb.toolTip() == lbl.toolTip()

def test_transition_from_speaker_to_physical_block_clears_state(qapp, mock_mw, mock_project):
    """Test that transitioning from a virtual speaker folder to a physical block clears current_speaker_name."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    mock_mw.block_to_project_file_map = {0: 0}
    
    # 1. Start in speaker state
    mock_mw.data_store.current_block_idx = -3
    mock_mw.data_store.current_speaker_name = "Hero"
    mock_mw.data_store.chapter_mappings = [(0, 0)]
    mock_mw.is_loading_data = False
    mock_mw._restoring_selection = False
    mock_mw.is_programmatically_changing_text = False
    
    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)
    
    # 2. Select physical block 0
    physical_item = QTreeWidgetItem(["Block 0"])
    user_role_int = int(Qt.ItemDataRole.UserRole)
    physical_item.setData(0, user_role_int, 0)
    
    mock_mw.block_list_widget = MagicMock()
    mock_mw.block_list_widget.currentItem.return_value = physical_item
    
    handler.block_selected(physical_item, 0)
    
    # Check that block state is resolved to physical block 0 and speaker name is cleared
    assert mock_mw.data_store.current_block_idx == 0
    assert mock_mw.data_store.current_speaker_name is None
    assert mock_mw.data_store.chapter_mappings == []

def test_save_speaker_preserves_virtual_selection(qapp, mock_mw, mock_project):
    """Test that saving a speaker preserves virtual folder selection state even if data_store.current_block_idx is a physical block."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    mock_mw.block_to_project_file_map = {0: 0}
    
    # Simulate being in virtual speakers mode
    mock_mw.data_store.current_block_idx = 0  # physical block (from active row selection)
    mock_mw.data_store.current_string_idx = 0
    mock_mw.data_store.current_speaker_name = "Hero"
    
    # Create actual QTreeWidget and item
    from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
    tree = QTreeWidget()
    virtual_item = QTreeWidgetItem(["Hero"])
    virtual_item.setData(0, int(Qt.ItemDataRole.UserRole), -3)
    virtual_item.setData(0, int(Qt.ItemDataRole.UserRole + 15), "Hero")
    virtual_item.setData(0, int(Qt.ItemDataRole.UserRole + 13), [(0, 0)])
    tree.addTopLevelItem(virtual_item)
    tree.setCurrentItem(virtual_item)
    
    mock_mw.block_list_widget = tree
    
    # We mock populate_blocks to ensure it gets called with -3 (virtual block)
    mock_mw.ui_updater.block_list_updater = MagicMock()
    
    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)
    
    # Save a new speaker (e.g. changing from implicit/None/MemePalace to a project metadata assignment)
    handler.save_speaker_for_current_string("Villain")
    
    # Check that populate_blocks was called with override_block_idx = -3 (NOT physical block 0)
    mock_mw.ui_updater.block_list_updater.populate_blocks.assert_called_with(override_folder_id="Hero", override_block_idx=-3)

def test_save_speaker_does_not_save_if_unchanged_from_displayed(qapp, mock_mw, mock_project):
    """Test that save_speaker_for_current_string returns early without saving or updating UI when the speaker text matches the last displayed value."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    mock_mw.block_to_project_file_map = {0: 0}
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_string_idx = 0
    
    from PyQt6.QtWidgets import QComboBox
    cb = QComboBox()
    cb.setEditable(True)
    cb._last_displayed_char = "Hero"
    mock_mw.speaker_combobox = cb
    
    mock_mw.ui_updater = MagicMock()
    mock_mw.ui_updater.block_list_updater = MagicMock()
    
    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)
    
    # Try saving "Hero" which is the same as the displayed speaker
    handler.save_speaker_for_current_string("Hero")
    
    # Assert save was NOT called
    mock_mw.project_manager.save.assert_not_called()
    mock_mw.ui_updater.block_list_updater.populate_blocks.assert_not_called()

def test_save_speaker_in_virtual_folder_does_not_navigate(qapp, mock_mw, mock_project):
    """Test that changing speaker in virtual mode changes metadata without moving folder or row selection."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    mock_mw.block_to_project_file_map = {0: 0}
    
    # Crucial state mock so block_selected doesn't exit early
    mock_mw.is_loading_data = False
    mock_mw._restoring_selection = False
    mock_mw.is_programmatically_changing_text = False
    mock_mw._restoring_session_state = False
    
    # Simulate being in virtual speakers mode for "Hero"
    mock_mw.data_store.current_block_idx = -3
    mock_mw.data_store.physical_block_idx = 0
    mock_mw.data_store.current_string_idx = 0
    mock_mw.data_store.current_speaker_name = "Hero"
    
    # Mock QTreeWidget and current item
    from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
    tree = QTreeWidget()
    
    # Hero item has two strings initially: (0,0) and (0,1)
    virtual_item = QTreeWidgetItem(["Hero"])
    virtual_item.setData(0, int(Qt.ItemDataRole.UserRole), -3)
    virtual_item.setData(0, int(Qt.ItemDataRole.UserRole + 15), "Hero")
    virtual_item.setData(0, int(Qt.ItemDataRole.UserRole + 13), [(0, 0), (0, 1)])
    tree.addTopLevelItem(virtual_item)
    
    # Rebuilt Hero item no longer contains the edited string after the assignment changes.
    rebuilt_hero_item = QTreeWidgetItem(["Hero"])
    rebuilt_hero_item.setData(0, int(Qt.ItemDataRole.UserRole), -3)
    rebuilt_hero_item.setData(0, int(Qt.ItemDataRole.UserRole + 15), "Hero")
    rebuilt_hero_item.setData(0, int(Qt.ItemDataRole.UserRole + 13), [(0, 1)])
    
    # Setup list widget mocks
    tree.setCurrentItem(virtual_item)
    mock_mw.block_list_widget = tree
    
    mock_mw.ui_updater = MagicMock()
    mock_mw.ui_updater.block_list_updater = MagicMock()
    
    # Make block_list_updater populate_blocks swap the items to simulate rebuild
    def mock_populate(override_folder_id, override_block_idx):
        if override_folder_id == "Hero":
            tree.clear()
            tree.addTopLevelItem(rebuilt_hero_item)
            
    mock_mw.ui_updater.block_list_updater.populate_blocks.side_effect = mock_populate
    
    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)
    mock_mw.list_selection_handler = handler
    
    # Set current mappings in store
    mock_mw.data_store.chapter_mappings = [(0, 0), (0, 1)]
    
    handler.string_selected_from_preview = MagicMock()

    # Change speaker of current string (0,0) to "Villain"
    handler.save_speaker_for_current_string("Villain")
    
    # 1. Verify speaker metadata changed, but virtual folder and physical row did not navigate.
    assert mock_project.blocks[0].metadata["character_assignments"]["0"] == "Villain"
    assert mock_mw.data_store.current_speaker_name == "Hero"
    assert mock_mw.data_store.current_block_idx == -3
    assert mock_mw.data_store.physical_block_idx == 0
    assert mock_mw.data_store.current_string_idx == 0
    
    # 2. Verify targets were cleared without selecting a different row.
    assert handler._target_block_idx is None
    assert handler._target_string_idx is None
    assert mock_mw.data_store.chapter_mappings == [(0, 0), (0, 1)]
    handler.string_selected_from_preview.assert_not_called()
    
    # 3. Verify populate_blocks kept the existing folder selected.
    mock_mw.ui_updater.block_list_updater.populate_blocks.assert_called_with(override_folder_id="Hero", override_block_idx=-3)

def test_save_speaker_in_virtual_folder_keeps_same_physical_string_when_old_folder_has_later_sibling(qapp, mock_mw):
    """Regression: changing speaker must not jump to the next old-speaker string in another block."""
    project = MagicMock()
    project.blocks = []
    for idx in range(8):
        block = MagicMock()
        block.metadata = {"character_assignments": {}}
        project.blocks.append(block)
    project.blocks[5].metadata["character_assignments"] = {"10": "Black Cat"}
    project.blocks[7].metadata["character_assignments"] = {"2": "Black Cat"}

    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = project
    mock_mw.block_to_project_file_map = {i: i for i in range(8)}
    mock_mw.data_store.data = [[] for _ in range(8)]
    mock_mw.data_store.data[5] = [""] * 11
    mock_mw.data_store.data[7] = [""] * 3
    mock_mw.data_store.block_names = {str(i): f"Block {i}" for i in range(8)}
    mock_mw.data_store.current_block_idx = -3
    mock_mw.data_store.physical_block_idx = 5
    mock_mw.data_store.current_string_idx = 10
    mock_mw.data_store.current_speaker_name = "Black Cat"
    mock_mw.data_store.chapter_mappings = [(5, 10), (7, 2)]
    mock_mw.data_store.displayed_string_indices = [(5, 10)]
    mock_mw.is_loading_data = False
    mock_mw._restoring_selection = False
    mock_mw.is_programmatically_changing_text = False
    mock_mw._restoring_session_state = False

    from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
    tree = QTreeWidget()
    black_cat_item = QTreeWidgetItem(["Black Cat"])
    black_cat_item.setData(0, int(Qt.ItemDataRole.UserRole), -3)
    black_cat_item.setData(0, int(Qt.ItemDataRole.UserRole + 15), "Black Cat")
    black_cat_item.setData(0, int(Qt.ItemDataRole.UserRole + 13), [(5, 10), (7, 2)])
    tree.addTopLevelItem(black_cat_item)
    tree.setCurrentItem(black_cat_item)
    mock_mw.block_list_widget = tree

    rebuilt_black_cat_item = QTreeWidgetItem(["Black Cat"])
    rebuilt_black_cat_item.setData(0, int(Qt.ItemDataRole.UserRole), -3)
    rebuilt_black_cat_item.setData(0, int(Qt.ItemDataRole.UserRole + 15), "Black Cat")
    rebuilt_black_cat_item.setData(0, int(Qt.ItemDataRole.UserRole + 13), [(7, 2)])

    mock_mw.ui_updater = MagicMock()
    mock_mw.ui_updater.block_list_updater = MagicMock()
    mock_mw.preview_text_edit = None

    def mock_populate(override_folder_id, override_block_idx):
        if override_folder_id == "Black Cat":
            tree.clear()
            tree.addTopLevelItem(rebuilt_black_cat_item)

    mock_mw.ui_updater.block_list_updater.populate_blocks.side_effect = mock_populate
    mock_mw.preview_text_edit = MagicMock()

    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)
    mock_mw.list_selection_handler = handler

    def mock_populate_strings(block_idx):
        mock_mw.data_store.displayed_string_indices = list(mock_mw.data_store.chapter_mappings)
        handler.handle_preview_selection_changed([1])

    mock_mw.ui_updater.populate_strings_for_block.side_effect = mock_populate_strings

    handler.save_speaker_for_current_string("Black & White Cat")

    assert project.blocks[5].metadata["character_assignments"]["10"] == "Black & White Cat"
    assert mock_mw.data_store.current_block_idx == -3
    assert mock_mw.data_store.physical_block_idx == 5
    assert mock_mw.data_store.current_string_idx == 10
    assert mock_mw.data_store.current_speaker_name == "Black Cat"
    assert tree.currentItem() == rebuilt_black_cat_item
    assert mock_mw.data_store.chapter_mappings == [(5, 10), (7, 2)]
    assert handler._target_block_idx is None
    assert handler._target_string_idx is None

    mock_mw.preview_text_edit = None
    mock_mw.data_store.displayed_string_indices = list(mock_mw.data_store.chapter_mappings)
    handler.string_selected_from_preview(1)

    assert mock_mw.data_store.current_block_idx == -3
    assert mock_mw.data_store.physical_block_idx == 7
    assert mock_mw.data_store.current_string_idx == 2
    assert mock_mw.data_store.current_speaker_name == "Black Cat"
    assert mock_mw.data_store.chapter_mappings == [(7, 2)]

def test_save_speaker_with_real_rebuild_retains_old_folder_until_next_row(qapp, mock_mw):
    """Regression: real tree rebuild must not turn a retained row into permanent old-folder membership."""
    project = MagicMock()
    project.virtual_folders = []
    project.metadata = {}
    project.blocks = []
    for idx in range(8):
        block = MagicMock()
        block.id = f"block_{idx}"
        block.source_file = f"sources/block_{idx}.bmg"
        block.categories = []
        block.metadata = {"character_assignments": {}}
        project.blocks.append(block)
    project.blocks[5].metadata["character_assignments"] = {"10": "Black Cat"}
    project.blocks[7].metadata["character_assignments"] = {"2": "Black Cat"}

    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = project
    mock_mw.project_manager.SOURCES_DIR = "sources"
    mock_mw.translation_handler = None
    mock_mw.block_to_project_file_map = {i: i for i in range(8)}
    mock_mw.data_store.data = [[] for _ in range(8)]
    mock_mw.data_store.data[5] = [""] * 11
    mock_mw.data_store.data[7] = [""] * 3
    mock_mw.data_store.block_names = {str(i): f"Block {i}" for i in range(8)}
    mock_mw.data_store.problems_per_subline = {}
    mock_mw.data_store.edited_data = {}
    mock_mw.data_store.edited_sublines = set()
    mock_mw.data_store.current_block_idx = -3
    mock_mw.data_store.physical_block_idx = 5
    mock_mw.data_store.current_string_idx = 10
    mock_mw.data_store.current_speaker_name = "Black Cat"
    mock_mw.data_store.chapter_mappings = [(5, 10), (7, 2)]
    mock_mw.is_loading_data = False
    mock_mw._restoring_selection = False
    mock_mw.is_programmatically_changing_text = False
    mock_mw._restoring_session_state = False
    mock_mw.preview_text_edit = None

    from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
    tree = QTreeWidget()
    def create_item(text, block_idx=None, role=Qt.UserRole):
        item = QTreeWidgetItem([str(text)])
        if block_idx is not None:
            item.setData(0, role, block_idx)
        return item
    tree.create_item = create_item
    mock_mw.block_list_widget = tree

    mock_mw.ui_updater = MagicMock()
    updater = BlockListUpdater(mock_mw, mock_mw.data_processor)
    mock_mw.ui_updater.block_list_updater = updater
    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)
    mock_mw.list_selection_handler = handler

    updater.populate_blocks(override_folder_id="Black Cat", override_block_idx=-3)
    handler.save_speaker_for_current_string("Black & White Cat")

    assert project.blocks[5].metadata["character_assignments"]["10"] == "Black & White Cat"
    assert mock_mw.data_store.current_block_idx == -3
    assert mock_mw.data_store.physical_block_idx == 5
    assert mock_mw.data_store.current_string_idx == 10
    assert mock_mw.data_store.current_speaker_name == "Black Cat"
    assert mock_mw.data_store.chapter_mappings == [(5, 10), (7, 2)]
    assert handler._pending_speaker_retention == ("Black Cat", (5, 10), 0)
    assert tree.currentItem() is not None
    assert tree.currentItem().text(0) == "Black Cat"
    assert tree.currentItem().parent() is not None
    assert tree.currentItem().parent().text(0) == "Speakers"
    assert tree.currentItem().parent().isExpanded()

    mock_mw.data_store.displayed_string_indices = list(mock_mw.data_store.chapter_mappings)
    handler.string_selected_from_preview(1)

    assert mock_mw.data_store.current_block_idx == -3
    assert mock_mw.data_store.physical_block_idx == 7
    assert mock_mw.data_store.current_string_idx == 2
    assert mock_mw.data_store.current_speaker_name == "Black Cat"
    assert mock_mw.data_store.chapter_mappings == [(7, 2)]
    assert handler._pending_speaker_retention is None

def test_block_list_rebuild_keeps_pending_speaker_retention_before_selection(qapp, mock_mw):
    """Regression: rebuilt speaker item must include retained current row before currentItemChanged can fire."""
    project = MagicMock()
    project.virtual_folders = []
    project.metadata = {}
    project.blocks = []
    for idx in range(8):
        block = MagicMock()
        block.id = f"block_{idx}"
        block.source_file = f"sources/block_{idx}.bmg"
        block.categories = []
        block.metadata = {"character_assignments": {}}
        project.blocks.append(block)
    project.blocks[5].metadata["character_assignments"] = {"10": "Black & White Cat"}
    project.blocks[7].metadata["character_assignments"] = {"2": "Black Cat"}

    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = project
    mock_mw.project_manager.SOURCES_DIR = "sources"
    mock_mw.translation_handler = None
    mock_mw.block_to_project_file_map = {i: i for i in range(8)}
    mock_mw.data_store.data = [[] for _ in range(8)]
    mock_mw.data_store.data[5] = [""] * 11
    mock_mw.data_store.data[7] = [""] * 3
    mock_mw.data_store.block_names = {str(i): f"Block {i}" for i in range(8)}
    mock_mw.data_store.problems_per_subline = {}
    mock_mw.data_store.current_block_idx = -3
    mock_mw.data_store.physical_block_idx = 5
    mock_mw.data_store.current_string_idx = 10
    mock_mw.data_store.current_speaker_name = "Black Cat"
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.get_problem_definitions.return_value = {}

    from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator
    tree = QTreeWidget()
    def create_item(text, block_idx=None, role=Qt.UserRole):
        item = QTreeWidgetItem([str(text)])
        if block_idx is not None:
            item.setData(0, role, block_idx)
        return item
    tree.create_item = create_item
    mock_mw.block_list_widget = tree

    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)
    handler._pending_speaker_retention = ("Black Cat", (5, 10), 0)
    mock_mw.list_selection_handler = handler

    updater = BlockListUpdater(mock_mw, mock_mw.data_processor)
    updater.populate_blocks(override_folder_id="Black Cat", override_block_idx=-3)

    black_cat_item = None
    iterator = QTreeWidgetItemIterator(tree)
    while iterator.value():
        item = iterator.value()
        if item.data(0, Qt.UserRole) == -3 and item.data(0, Qt.UserRole + 15) == "Black Cat":
            black_cat_item = item
            break
        iterator += 1

    assert black_cat_item is not None
    assert black_cat_item.data(0, Qt.UserRole + 13) == [(5, 10), (7, 2)]
    assert tree.currentItem() == black_cat_item
    assert black_cat_item.parent() is not None
    assert black_cat_item.parent().isExpanded()
    assert handler._pending_speaker_retention == ("Black Cat", (5, 10), 0)
