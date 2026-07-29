# tests/test_handlers/test_virtual_folder_handler.py

from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QMessageBox, QDialog
from PyQt6.QtCore import Qt
from handlers.virtual_folder_handler import VirtualFolderHandler


def test_VirtualFolderHandler_add_folder_action(mock_mw):
    mock_mw.block_list_widget = MagicMock()
    h = VirtualFolderHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    h.add_folder_action()
    mock_mw.block_list_widget._create_folder_at_cursor.assert_called_once()


@patch('components.project_dialogs.MoveToFolderDialog')
def test_VirtualFolderHandler_add_items_to_folder_action(mock_dialog_class, mock_mw):
    mock_mw.project_manager = MagicMock()
    mock_mw.block_to_project_file_map = {}
    mock_block = MagicMock()
    mock_block.id = "id_1"
    mock_mw.project_manager.project.blocks = [mock_block]
    mock_mw.block_list_widget = MagicMock()
    h = VirtualFolderHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    
    mock_item = MagicMock()
    mock_item.data.side_effect = lambda col, role: 0 if role == Qt.UserRole else None # block_idx = 0
    mock_mw.block_list_widget.selectedItems.return_value = [mock_item]
    
    mock_dialog = mock_dialog_class.return_value
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_selected_folder_id.return_value = "folder_1"
    
    h.add_items_to_folder_action()
    mock_mw.project_manager.save.assert_called_once()
    mock_mw.project_manager.move_block_to_folder.assert_called_once_with("id_1", "folder_1")


@patch('handlers.virtual_folder_handler.QMessageBox')
@patch('handlers.virtual_folder_handler.FolderDeleteDialog')
def test_VirtualFolderHandler_delete_folder_action(mock_dialog_class, mock_msg_box, mock_mw):
    mock_mw.project_manager = MagicMock()
    pm = mock_mw.project_manager
    pm.project.remove_block.return_value = True

    h = VirtualFolderHandler(mock_mw, MagicMock(), mock_mw.ui_updater)

    # Create folder mock
    folder = MagicMock()
    folder.name = "TestFolder"
    folder.block_ids = []
    folder.children = []
    pm.find_virtual_folder.return_value = folder
    
    mock_item = MagicMock()
    mock_parent = mock_item.parent.return_value
    mock_parent.childCount.return_value = 0
    mock_mw.block_list_widget.currentItem.return_value = mock_item
    mock_mw.block_list_widget.invisibleRootItem.return_value = mock_parent

    mock_msg_box.StandardButton = QMessageBox.StandardButton
    
    # Action 2 (Delete empty folder)
    mock_parent.indexOfChild.return_value = 0
    mock_msg_box.question.return_value = QMessageBox.StandardButton.Yes
    h.delete_folder_action("folder_1", mock_item)
    pm._remove_folder_from_anywhere.assert_called_with("folder_1")
    pm.save.assert_called()


def test_VirtualFolderHandler_update_all_folder_expansion_state(mock_mw):
    h = VirtualFolderHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    mock_mw.project_manager = MagicMock()
    folder1 = MagicMock(children=[])
    folder2 = MagicMock(children=[folder1])
    mock_mw.project_manager.project.virtual_folders = [folder2]
    
    h.update_all_folder_expansion_state(True)
    assert folder1.is_expanded is True
    assert folder2.is_expanded is True
    mock_mw.project_manager.save.assert_called_once()


def test_bulk_expansion_can_skip_large_project_write(mock_mw):
    h = VirtualFolderHandler(mock_mw, MagicMock(), MagicMock())

    h.update_all_folder_expansion_state(False, persist=False)

    mock_mw.project_manager.save.assert_not_called()
