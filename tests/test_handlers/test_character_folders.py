# tests/test_handlers/test_character_folders.py
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

def test_save_character_for_current_string(qapp, mock_mw, mock_project):
    """Test saving character assignment and verifying metadata updates."""
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
    
    # Save a new character
    handler.save_character_for_current_string("Villain")
    assert mock_project.blocks[0].metadata["character_assignments"]["0"] == "Villain"
    mock_mw.project_manager.save.assert_called_once()
    mock_mw.ui_updater.block_list_updater.populate_blocks.assert_called_once()
    mock_mw.data_processor.schedule_autosave.assert_called_once()

    # Clear character (empty string)
    mock_mw.project_manager.save.reset_mock()
    handler.save_character_for_current_string("")
    assert "0" not in mock_project.blocks[0].metadata["character_assignments"]
    mock_mw.project_manager.save.assert_called_once()

def test_populate_characters_folder(qapp, mock_mw, mock_project):
    """Test populating the virtual Characters folder in tree widget."""
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
    
    # We should have a root item "Characters" and a child item "Hero"
    root = tree.invisibleRootItem()
    characters_node = None
    for i in range(root.childCount()):
        child = root.child(i)
        if child.text(0) == "Characters":
            characters_node = child
            break
            
    assert characters_node is not None
    assert characters_node.childCount() == 1
    assert characters_node.child(0).text(0) == "Hero"
    assert characters_node.child(0).data(0, Qt.ItemDataRole.UserRole) == -3
    assert characters_node.child(0).data(0, Qt.ItemDataRole.UserRole + 15) == "Hero"

def test_select_character_folder(qapp, mock_mw, mock_project):
    """Test selecting a Character folder item updates the displayed preview mapping."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    mock_mw.data_store.current_block_idx = -1
    mock_mw.data_store.chapter_mappings = []
    
    # Crucial state mock so block_selected doesn't exit early
    mock_mw.is_loading_data = False
    mock_mw._restoring_selection = False
    mock_mw.is_programmatically_changing_text = False
    
    handler = ListSelectionHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)
    
    # Create fake item for character
    item = QTreeWidgetItem(["Hero"])
    user_role_int = int(Qt.ItemDataRole.UserRole)
    item.setData(0, user_role_int, -3)
    item.setData(0, user_role_int + 15, "Hero")
    item.setData(0, user_role_int + 13, [(0, 0)]) # Set pre-calculated mappings
    
    mock_mw.block_list_widget = MagicMock()
    mock_mw.block_list_widget.currentItem.return_value = item
    
    handler.block_selected(item, 0)
    
    assert mock_mw.current_block_idx == 0
    assert mock_mw.current_character_name == "Hero"
    assert mock_mw.chapter_mappings == [(0, 0)]
    mock_mw.ui_updater.populate_strings_for_block.assert_called_with(-3)

def test_string_settings_updater_characters(qapp, mock_mw, mock_project):
    """Test character_combobox populating and text setting in settings updater."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_string_idx = 0
    
    print(f"DEBUG UPDATER TEST: mock_mw.project_manager.project = {mock_mw.project_manager.project}")
    print(f"DEBUG UPDATER TEST: mock_project = {mock_project}")
    
    from PyQt6.QtWidgets import QComboBox, QLabel
    cb = QComboBox()
    cb.setEditable(True)
    mock_mw.character_combobox = cb
    
    lbl = QLabel()
    mock_mw.character_label = lbl
    
    spk_lbl = QLabel()
    mock_mw.speaker_label = spk_lbl
    
    mock_mw.font_combobox = MagicMock()
    mock_mw.width_spinbox = MagicMock()
    mock_mw.apply_width_button = MagicMock()
    mock_mw.block_to_project_file_map = {0: 0}
    
    updater = StringSettingsUpdater(mock_mw, mock_mw.data_processor)
    
    # Populate string 0 which has character "Hero"
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

def test_transition_from_character_to_physical_block_clears_state(qapp, mock_mw, mock_project):
    """Test that transitioning from a virtual character folder to a physical block clears current_character_name."""
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = mock_project
    mock_mw.block_to_project_file_map = {0: 0}
    
    # 1. Start in character state
    mock_mw.data_store.current_block_idx = -3
    mock_mw.data_store.current_character_name = "Hero"
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
    
    # Check that block state is resolved to physical block 0 and character name is cleared
    assert mock_mw.data_store.current_block_idx == 0
    assert mock_mw.data_store.current_character_name is None
    assert mock_mw.data_store.chapter_mappings == []
