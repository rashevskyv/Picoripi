import pytest
from unittest.mock import MagicMock, patch
from handlers.project_action_handler import ProjectActionHandler
from core.project_manager import ProjectManager
from PyQt5.QtWidgets import QMessageBox

def test_ProjectActionHandler_init(mock_mw):
    # MW without project_manager
    if hasattr(mock_mw, 'project_manager'):
        delattr(mock_mw, 'project_manager')
    
    h = ProjectActionHandler(mock_mw, MagicMock(), MagicMock())
    assert hasattr(mock_mw, 'project_manager')
    assert isinstance(mock_mw.project_manager, ProjectManager)

def test_ProjectActionHandler_set_project_actions_enabled(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), MagicMock())
    h._set_project_actions_enabled(True)
    mock_mw.close_project_action.setEnabled.assert_called_with(True)
    mock_mw.import_block_action.setEnabled.assert_called_with(True)
    
    h._set_project_actions_enabled(False)
    mock_mw.close_project_action.setEnabled.assert_called_with(False)

@patch('handlers.project_action_handler.ProjectManager')
@patch('handlers.project_action_handler.Path.is_dir')
@patch('handlers.project_action_handler.QMessageBox')
@patch('components.project_dialogs.NewProjectDialog')
def test_ProjectActionHandler_create_new_project_action(mock_dialog_class, mock_msg_box, mock_is_dir, mock_pm_class, mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    mock_dialog = mock_dialog_class.return_value
    mock_dialog.exec_.return_value = mock_dialog.Accepted
    mock_dialog.get_project_info.return_value = {
        'directory': 'C:/proj', 'name': 'Test Project', 'plugin': 'plug',
        'description': '', 'source_path': '', 'translation_path': '',
        'is_directory_mode': False, 'auto_create_translations': False
    }
    
    # Mock PM
    mock_pm = mock_pm_class.return_value
    mock_pm.create_new_project.return_value = True
    mock_pm.project.name = "Test Project"
    
    mock_is_dir.return_value = False # skip plugin loading
    
    h.create_new_project_action()
    
    mock_pm.create_new_project.assert_called_once()
    mock_mw.ui_updater.update_title.assert_called_once()
    mock_msg_box.information.assert_called_once()

@patch('handlers.project_action_handler.ProjectManager')
@patch('handlers.project_action_handler.QMessageBox')
@patch('handlers.project_action_handler.QFileDialog.getOpenFileName')
def test_ProjectActionHandler_open_project_action(mock_getOpen, mock_msg_box, mock_pm_class, mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    mock_getOpen.return_value = ("C:/test.uiproj", "")
    
    # Mock PM instance
    mock_pm = mock_pm_class.return_value
    mock_pm.load.return_value = True
    mock_pm.project.name = "Test Project"
    
    h.open_project_action()
    
    mock_pm.load.assert_called_with("C:/test.uiproj")
    mock_mw.ui_updater.update_title.assert_called_once()

@patch('handlers.project_action_handler.QMessageBox')
def test_ProjectActionHandler_close_project_action(mock_msg_box, mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    mock_mw.unsaved_changes = True
    mock_msg_box.question.return_value = QMessageBox.Discard
    
    mock_mw.data = ["something"]
    h.close_project_action()
    
    assert mock_mw.data == []
    assert mock_mw.edited_data == {}
    assert mock_mw.project_manager is None
    assert mock_mw.unsaved_changes is False
    mock_mw.block_list_widget.clear.assert_called_once()
    mock_mw.ui_updater.update_text_views.assert_called_once()

from PyQt5.QtCore import Qt

@patch('handlers.project_action_handler.QMessageBox')
@patch('components.project_dialogs.ImportBlockDialog')
def test_ProjectActionHandler_import_block_action(mock_dialog_class, mock_msg_box, mock_mw):
    mock_mw.project_manager = MagicMock()
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    
    mock_dialog = mock_dialog_class.return_value
    mock_dialog.exec_.return_value = mock_dialog.Accepted
    mock_dialog.get_block_info.return_value = {
        'name': 'New Block', 'source_file': 'src.json',
        'translation_file': None, 'description': ''
    }
    
    # Mock PM
    mock_mw.project_manager.add_block.return_value = True
    h._populate_blocks_from_project = MagicMock()
    
    h.import_block_action()
    
    mock_mw.project_manager.add_block.assert_called_once()
    h._populate_blocks_from_project.assert_called_once()
    mock_msg_box.information.assert_called_once()

@patch('handlers.project_action_handler.QMessageBox')
@patch('handlers.project_action_handler.QFileDialog.getExistingDirectory')
def test_ProjectActionHandler_import_directory_action(mock_getDir, mock_msg_box, mock_mw):
    mock_mw.project_manager = MagicMock()
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    
    mock_getDir.return_value = "C:/import_dir"
    mock_mw.project_manager.import_directory.return_value = ["block1", "block2"]
    h._populate_blocks_from_project = MagicMock()
    
    h.import_directory_action()
    
    mock_mw.project_manager.import_directory.assert_called_with("C:/import_dir")
    h._populate_blocks_from_project.assert_called_once()
    mock_msg_box.information.assert_called_once()

@patch('handlers.project_action_handler.QMessageBox')
def test_ProjectActionHandler_delete_block_action(mock_msg_box, mock_mw):
    mock_mw.project_manager = MagicMock()
    mock_block = MagicMock()
    mock_block.id = "id_1"
    mock_block.name = "Block 1"
    mock_mw.project_manager.project.blocks = [mock_block]
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    
    # Setup mock current item
    mock_item = MagicMock()
    mock_item.data.side_effect = lambda col, role: 0 if role == Qt.UserRole else None # returns block_idx = 0
    mock_parent = mock_item.parent.return_value
    mock_parent.childCount.return_value = 0
    mock_mw.block_list_widget.currentItem.return_value = mock_item
    
    mock_msg_box.Yes = QMessageBox.Yes
    mock_msg_box.question.return_value = QMessageBox.Yes
    mock_mw.project_manager.project.remove_block.return_value = True
    h._populate_blocks_from_project = MagicMock()
    
    h.delete_block_action()
    
    mock_mw.project_manager.project.remove_block.assert_called_with("id_1")
    mock_mw.project_manager.save.assert_called_once()
    h._populate_blocks_from_project.assert_called_once()

def test_ProjectActionHandler_move_block_up_action(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    h.move_block_up_action()
    mock_mw.block_list_widget.move_current_item_up.assert_called_once()

def test_ProjectActionHandler_move_block_down_action(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    h.move_block_down_action()
    mock_mw.block_list_widget.move_current_item_down.assert_called_once()

def test_ProjectActionHandler_add_folder_action(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    h.add_folder_action()
    mock_mw.block_list_widget._create_folder_at_cursor.assert_called_once()

@patch('components.project_dialogs.MoveToFolderDialog')
def test_ProjectActionHandler_add_items_to_folder_action(mock_dialog_class, mock_mw):
    mock_mw.project_manager = MagicMock()
    mock_mw.block_to_project_file_map = {}
    mock_block = MagicMock()
    mock_block.id = "id_1"
    mock_mw.project_manager.project.blocks = [mock_block]
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    
    mock_item = MagicMock()
    mock_item.data.side_effect = lambda col, role: 0 if role == Qt.UserRole else None # block_idx = 0
    mock_mw.block_list_widget.selectedItems.return_value = [mock_item]
    
    mock_dialog = mock_dialog_class.return_value
    from PyQt5.QtWidgets import QDialog
    mock_dialog.exec_.return_value = QDialog.Accepted
    mock_dialog.get_selected_folder_id.return_value = "folder_1"
    
    h.add_items_to_folder_action()
    mock_mw.project_manager.save.assert_called_once()

@patch('handlers.project_action_handler.Path.exists')
def test_ProjectActionHandler_populate_blocks_from_project(mock_exists, mock_mw):
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project.blocks = [MagicMock(source_file='a.json', translation_file=None, internal_key=None, name="Block A")]
    mock_mw.project_manager.get_absolute_path.return_value = "C:/test/a.json"
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.original_keys = []
    mock_mw.current_game_rules.load_data_from_json_obj.return_value = (["data"], {"0": "Block A"})
    
    mock_exists.return_value = True
    
    with patch('handlers.project_action_handler.load_json_file') as mock_load:
        mock_load.return_value = ("{}", False)
        
        h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
        h._populate_blocks_from_project()
        
        assert len(mock_mw.data) == 1
        assert mock_mw.data[0] == "data"

def test_ProjectActionHandler_expand_all_action(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    h._update_all_folder_expansion_state = MagicMock()
    h.expand_all_action()
    h._update_all_folder_expansion_state.assert_called_with(True)
    mock_mw.ui_updater.populate_blocks.assert_called_once()

def test_ProjectActionHandler_collapse_all_action(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    h._update_all_folder_expansion_state = MagicMock()
    h.collapse_all_action()
    h._update_all_folder_expansion_state.assert_called_with(False)
    mock_mw.ui_updater.populate_blocks.assert_called_once()

def test_ProjectActionHandler_update_all_folder_expansion_state(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    mock_mw.project_manager = MagicMock()
    folder1 = MagicMock(children=[])
    folder2 = MagicMock(children=[folder1])
    mock_mw.project_manager.project.virtual_folders = [folder2]
    
    h._update_all_folder_expansion_state(True)
    assert folder1.is_expanded is True
    assert folder2.is_expanded is True
    mock_mw.project_manager.save.assert_called_once()
    
# --- New Tests for missing coverage ---

@patch('handlers.project_action_handler.QMessageBox')
@patch('handlers.project_action_handler.FolderDeleteDialog')
def test_ProjectActionHandler_delete_block_action_folder(mock_dialog_class, mock_msg_box, mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    mock_mw.project_manager = MagicMock()
    pm = mock_mw.project_manager
    pm.project.remove_block.return_value = True

    h._populate_blocks_from_project = MagicMock()

    # Create folder mock
    folder = MagicMock()
    folder.name = "TestFolder"
    folder.block_ids = []
    folder.children = []
    pm.find_virtual_folder.return_value = folder
    
    mock_item = MagicMock()
    # Return folder_id (not None), block_idx (None)
    def item_data(col, role):
        if role == Qt.UserRole + 1: return "folder_1"
        return None
    mock_item.data.side_effect = item_data
    mock_parent = mock_item.parent.return_value
    mock_parent.childCount.return_value = 0
    mock_mw.block_list_widget.currentItem.return_value = mock_item
    mock_mw.block_list_widget.invisibleRootItem.return_value = mock_parent

    # Action 0 (Cancel Empty folder)
    mock_msg_box.No = QMessageBox.No
    mock_msg_box.Yes = QMessageBox.Yes
    mock_msg_box.question.return_value = QMessageBox.No
    h.delete_block_action()
    assert pm._remove_folder_from_anywhere.call_count == 0
    
    # Action 2 (Delete empty folder)
    mock_parent.indexOfChild.return_value = 0
    mock_msg_box.question.return_value = QMessageBox.Yes
    h.delete_block_action()
    pm._remove_folder_from_anywhere.assert_called_with("folder_1")
    pm.save.assert_called()

    # Action 1 (Delete folder, keep contents)
    folder.block_ids = ["b1"] # No longer empty -> triggers FolderDeleteDialog
    mock_dialog = mock_dialog_class.return_value
    mock_dialog.exec_.return_value = 1
    mock_dialog.result_action = 1
    folder.parent_id = "parent_folder"
    parent_folder = MagicMock()
    parent_folder.children = []
    parent_folder.block_ids = []
    pm.find_virtual_folder.side_effect = lambda id: parent_folder if id == "parent_folder" else folder
    
    pm._remove_folder_from_anywhere.reset_mock()
    h.delete_block_action()
    pm._remove_folder_from_anywhere.assert_called_with("folder_1")
    assert "b1" in parent_folder.block_ids # Moved up
    
    # Action 2 via dialog (Delete folder + contents)
    folder.parent_id = None
    pm.find_virtual_folder.side_effect = lambda id: folder
    mock_dialog.result_action = 2
    h.delete_block_action()
    pm.project.remove_block.assert_called_with("b1")


@patch('handlers.project_action_handler.ProjectManager')
@patch('handlers.project_action_handler.QMessageBox')
@patch('handlers.project_action_handler.Path')
def test_ProjectActionHandler_open_recent_project(mock_Path, mock_msg_box, mock_pm_class, mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    mock_mw.settings_manager = MagicMock()
    
    mock_path_obj = mock_Path.return_value
    
    # Path doesn't exist
    mock_path_obj.exists.return_value = False
    h._open_recent_project("fake_path.uiproj")
    mock_msg_box.critical.assert_called_once()
    mock_mw.settings_manager.remove_recent_project.assert_called_with("fake_path.uiproj")
    
    # Path exists
    mock_path_obj.exists.return_value = True
    mock_msg_box.critical.reset_mock()
    
    mock_pm = mock_pm_class.return_value
    mock_pm.load.return_value = True
    mock_pm.project.plugin_name = "test_plug"
    mock_pm.project.name = "MyProj"
    
    h._populate_blocks_from_project = MagicMock()
    
    with patch('PyQt5.QtCore.QTimer.singleShot', side_effect=lambda delay, func: func()):
        h._open_recent_project("real_path.uiproj")
        
        mock_pm.load.assert_called_with("real_path.uiproj")
        assert mock_mw.last_opened_path == "real_path.uiproj"
        assert mock_mw.active_game_plugin == "test_plug"
        mock_mw.load_game_plugin.assert_called_once()
        mock_pm.load_settings_from_project.assert_called_with(mock_mw)
        h._populate_blocks_from_project.assert_called_once()
        
    # Failed load
    mock_pm.load.return_value = False
    h._open_recent_project("fail_path.uiproj")
    mock_msg_box.critical.assert_called_once()

# --- New tests for _populate_blocks_from_project with internal_key and translations ---
@patch('handlers.project_action_handler.Path.exists')
def test_ProjectActionHandler_populate_blocks_internal_key(mock_exists, mock_mw):
    mock_mw.project_manager = MagicMock()
    # A block with internal_key
    mock_block = MagicMock(source_file='a.json', translation_file=None, internal_key='target_key')
    mock_block.name = "Block A"
    mock_mw.project_manager.project.blocks = [mock_block]
    mock_mw.project_manager.get_absolute_path.return_value = "C:/test/a.json"
    
    mock_mw.current_game_rules = MagicMock()
    # parsed_data has two sub-blocks, we want the one mapped to 'target_key'
    mock_mw.current_game_rules.load_data_from_json_obj.return_value = (["data1", "data2"], {"0": "other_key", "1": "target_key"})
    
    mock_exists.return_value = True
    with patch('handlers.project_action_handler.load_json_file') as mock_load:
        mock_load.return_value = ("{}", False)
        
        h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
        h._populate_blocks_from_project()
        
        # It should append exactly data2
        assert len(mock_mw.data) == 1
        assert mock_mw.data[0] == "data2"
        assert mock_mw.block_names["0"] == "Block A"

@patch('handlers.project_action_handler.Path.exists')
def test_ProjectActionHandler_populate_blocks_internal_key_missing(mock_exists, mock_mw):
    mock_mw.project_manager = MagicMock()
    # A block with internal_key that isn't mapped
    mock_block = MagicMock(source_file='a.json', translation_file=None, internal_key='missing_key')
    mock_block.name = "Block A"
    mock_mw.project_manager.project.blocks = [mock_block]
    mock_mw.project_manager.get_absolute_path.return_value = "C:/test/a.json"
    
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.load_data_from_json_obj.return_value = (["data1"], {"0": "other_key"})
    
    mock_exists.return_value = True
    with patch('handlers.project_action_handler.load_json_file') as mock_load:
        mock_load.return_value = ("{}", False)
        
        h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
        h._populate_blocks_from_project()
        
        # Should append an empty block if missing
        assert len(mock_mw.data) == 1
        assert mock_mw.data[0] == []
        assert "Missing" in mock_mw.block_names["0"]

@patch('handlers.project_action_handler.Path.exists')
def test_ProjectActionHandler_populate_blocks_with_translations(mock_exists, mock_mw):
    mock_mw.project_manager = MagicMock()
    mock_block = MagicMock(source_file='a.json', translation_file='t_a.json', internal_key=None)
    mock_block.name = "Block A"
    mock_mw.project_manager.project.blocks = [mock_block]
    mock_mw.project_manager.get_absolute_path.return_value = "C:/test/a.json"
    
    mock_mw.current_game_rules = MagicMock()
    # Source returns data
    mock_mw.current_game_rules.load_data_from_json_obj.side_effect = [
        (["src_data"], {"0": "Key"}), # Load source
        (["trans_data"], {"0": "Key"}) # Load translation
    ]
    
    mock_exists.return_value = True
    with patch('handlers.project_action_handler.load_json_file') as mock_load:
        mock_load.return_value = ("{}", False)
        
        h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
        h._populate_blocks_from_project()
        
        assert len(mock_mw.data) == 1
        assert mock_mw.data[0] == "src_data"
        assert len(mock_mw.edited_file_data) == 1
        assert mock_mw.edited_file_data[0] == "trans_data"

@patch('handlers.project_action_handler.QMessageBox')
def test_ProjectActionHandler_clear_recent_projects(mock_msg_box, mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    mock_mw.settings_manager = MagicMock()
    
    # Test No
    mock_msg_box.question.return_value = QMessageBox.No
    h._clear_recent_projects()
    mock_mw.settings_manager.clear_recent_projects.assert_not_called()
    
    # Test Yes
    mock_msg_box.question.return_value = mock_msg_box.Yes
    h._update_recent_projects_menu = MagicMock()
    h._clear_recent_projects()
    mock_mw.settings_manager.clear_recent_projects.assert_called_once()
    mock_mw.settings_manager.save_settings.assert_called_once()
    h._update_recent_projects_menu.assert_called_once()

