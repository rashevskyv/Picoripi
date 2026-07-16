import pytest
from unittest.mock import MagicMock, patch
from handlers.project_action_handler import ProjectActionHandler
from core.project_manager import ProjectManager
from PyQt6.QtWidgets import QMessageBox, QDialog

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
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
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

def test_ProjectActionHandler_close_project_action(mock_mw):
    mock_mw.settings_manager = MagicMock()
    mock_data_processor = MagicMock()
    h = ProjectActionHandler(mock_mw, mock_data_processor, mock_mw.ui_updater)
    mock_mw.unsaved_changes = True

    mock_mw.data = ["something"]
    mock_mw.active_game_plugin = "pokemon_fr"

    h.close_project_action()

    # Verify autosave session was triggered
    mock_data_processor._autosave_session.assert_called_once_with(force=True)

    assert mock_mw.data == []
    assert mock_mw.edited_data == {}
    assert mock_mw.project_manager is None
    assert mock_mw.unsaved_changes is False
    assert mock_mw.active_game_plugin == ""
    mock_mw.load_game_plugin.assert_called_once()
    mock_mw.settings_manager.set.assert_any_call("last_opened_path", "")
    mock_mw.settings_manager.set.assert_any_call("active_game_plugin", "")
    mock_mw.settings_manager.save_settings.assert_called()
    mock_mw.block_list_widget.clear.assert_called_once()
    mock_mw.ui_updater.update_text_views.assert_called_once()
    mock_mw.ui_updater.update_plugin_status_label.assert_called_once()

from PyQt6.QtCore import Qt

@patch('handlers.project_action_handler.QMessageBox')
@patch('components.project_dialogs.ImportBlockDialog')
def test_ProjectActionHandler_import_block_action(mock_dialog_class, mock_msg_box, mock_mw):
    mock_mw.project_manager = MagicMock()
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)

    mock_dialog = mock_dialog_class.return_value
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_block_info.return_value = {
        'name': 'New Block', 'source_file': 'src.json',
        'translation_file': None, 'description': ''
    }

    # Mock PM
    mock_mw.project_manager.add_block.return_value = True
    h._populate_blocks_from_project = MagicMock(side_effect=lambda on_completed=None: on_completed(True) if on_completed else None)

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
    h._populate_blocks_from_project = MagicMock(side_effect=lambda on_completed=None: on_completed(True) if on_completed else None)

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

    mock_msg_box.StandardButton = QMessageBox.StandardButton
    mock_msg_box.question.return_value = QMessageBox.StandardButton.Yes
    mock_mw.project_manager.project.remove_block.return_value = True
    h._populate_blocks_from_project = MagicMock()

    h.delete_block_action()

    mock_mw.project_manager.project.remove_block.assert_called_with("id_1")
    mock_mw.project_manager.save.assert_called_once()
    h._populate_blocks_from_project.assert_called_once()

def test_ProjectActionHandler_move_block_action(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    h.move_block_action(-1)
    mock_mw.block_list_widget.move_current_item.assert_called_with(-1)

    h.move_block_action(1)
    mock_mw.block_list_widget.move_current_item.assert_called_with(1)

def test_ProjectActionHandler_add_folder_action(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    h.add_folder_action()
    mock_mw.virtual_folder_handler.add_folder_action.assert_called_once()

def test_ProjectActionHandler_add_items_to_folder_action(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    h.add_items_to_folder_action()
    mock_mw.virtual_folder_handler.add_items_to_folder_action.assert_called_once()

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
    mock_mw.block_list_widget.expandAll.assert_called_once()

def test_ProjectActionHandler_collapse_all_action(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    h._update_all_folder_expansion_state = MagicMock()
    h.collapse_all_action()
    h._update_all_folder_expansion_state.assert_called_with(False)
    mock_mw.ui_updater.populate_blocks.assert_called_once()
    mock_mw.block_list_widget.collapseAll.assert_called_once()

def test_ProjectActionHandler_update_all_folder_expansion_state(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    h._update_all_folder_expansion_state(True)
    mock_mw.virtual_folder_handler.update_all_folder_expansion_state.assert_called_once_with(True)

# --- New Tests for missing coverage ---

def test_ProjectActionHandler_delete_block_action_folder(mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)

    mock_item = MagicMock()
    def item_data(col, role):
        if role == Qt.UserRole + 1: return "folder_1"
        return None
    mock_item.data.side_effect = item_data
    mock_mw.block_list_widget.currentItem.return_value = mock_item

    h.delete_block_action()
    mock_mw.virtual_folder_handler.delete_folder_action.assert_called_once_with("folder_1", mock_item)


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

    h._populate_blocks_from_project = MagicMock(side_effect=lambda on_completed=None: on_completed(True) if on_completed else None)

    with patch('PyQt6.QtCore.QTimer.singleShot', side_effect=lambda delay, func: func()):
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
    mock_msg_box.StandardButton = QMessageBox.StandardButton
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    mock_mw.settings_manager = MagicMock()

    # Test No
    mock_msg_box.question.return_value = QMessageBox.StandardButton.No
    h._clear_recent_projects()
    mock_mw.settings_manager.clear_recent_projects.assert_not_called()

    # Test Yes
    mock_msg_box.question.return_value = QMessageBox.StandardButton.Yes
    h._update_recent_projects_menu = MagicMock()
    h._clear_recent_projects()
    mock_mw.settings_manager.clear_recent_projects.assert_called_once()
    mock_mw.settings_manager.save_settings.assert_called_once()
    h._update_recent_projects_menu.assert_called_once()


@patch('handlers.project_action_handler.ProjectManager')
@patch('handlers.project_action_handler.QMessageBox')
@patch('handlers.project_action_handler.Path')
def test_ProjectActionHandler_open_recent_project_session_restore_avoid_timer(mock_Path, mock_msg_box, mock_pm_class, mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    mock_mw.settings_manager = MagicMock()

    mock_path_obj = mock_Path.return_value
    mock_path_obj.exists.return_value = True

    mock_pm = mock_pm_class.return_value
    mock_pm.load.return_value = True
    mock_pm.project.plugin_name = "test_plug"
    mock_pm.project.name = "MyProj"

    # Session state IS restored
    h._populate_blocks_from_project = MagicMock(side_effect=lambda on_completed=None: on_completed(True) if on_completed else None)

    h._restore_view_timer = MagicMock()
    h._open_recent_project("real_path.uiproj")
    h._restore_view_timer.start.assert_not_called()

@patch('handlers.project_action_handler.ProjectManager')
@patch('handlers.project_action_handler.QMessageBox')
@patch('handlers.project_action_handler.Path')
def test_ProjectActionHandler_open_recent_project_no_session_restore_runs_timer(mock_Path, mock_msg_box, mock_pm_class, mock_mw):
    h = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    mock_mw.settings_manager = MagicMock()

    mock_path_obj = mock_Path.return_value
    mock_path_obj.exists.return_value = True

    mock_pm = mock_pm_class.return_value
    mock_pm.load.return_value = True
    mock_pm.project.plugin_name = "test_plug"
    mock_pm.project.name = "MyProj"

    # Session state is NOT restored
    h._populate_blocks_from_project = MagicMock(side_effect=lambda on_completed=None: on_completed(False) if on_completed else None)

    h._restore_view_timer = MagicMock()
    h._open_recent_project("real_path.uiproj")
    h._restore_view_timer.start.assert_called_once_with(150)


def test_ProjectLoadWorker_run_and_emits(mock_mw):
    from handlers.project_action_handler import ProjectLoadWorker

    mock_pm = MagicMock()
    mock_block = MagicMock(source_file='a.json', translation_file=None, internal_key=None)
    mock_block.name = "Block A"
    mock_block.metadata = {}
    mock_pm.project.blocks = [mock_block]
    mock_pm.get_absolute_path.return_value = "C:/test/a.json"

    mock_rules = MagicMock()
    mock_rules.original_keys = ['key1']
    mock_rules.load_data_from_json_obj.return_value = (["data"], {"0": "Block A"})

    worker = ProjectLoadWorker(mock_pm, mock_rules)

    # Track signal emits
    emitted_results = []
    emitted_progress = []
    worker.finished.connect(emitted_results.append)
    worker.progress.connect(lambda current, total: emitted_progress.append((current, total)))

    with patch('handlers.project_action_handler.Path.exists', return_value=True), \
         patch('handlers.project_action_handler.load_json_file', return_value=("{}", False)):
        worker.run()

    assert len(emitted_results) == 1
    result = emitted_results[0]
    assert result['data'] == ["data"]
    assert result['block_names'] == {"0": "Block A"}
    assert result['plugin_keys_backup'] == ['key1']

    assert len(emitted_progress) > 0
    # The progress should show block loading and translation loading stages
    assert emitted_progress[0] == (0, 2)


def test_ProjectActionHandler_populate_blocks_from_project_session_restore(mock_mw):
    mock_mw.project_manager = MagicMock()
    mock_block = MagicMock(source_file='a.json', translation_file='t_a.json', name="Block A")
    mock_mw.project_manager.project.blocks = [mock_block]
    mock_mw.project_manager.get_absolute_path.side_effect = lambda path, **kwargs: "abs_" + path

    mock_mw.current_game_rules = MagicMock()

    mock_data_processor = MagicMock()
    mock_data_processor.load_session_file.return_value = True

    mock_mw.data_store = MagicMock()
    mock_mw.data_store.data = [['restored']]
    mock_mw.data_store.block_to_project_file_map = {0: 10}

    h = ProjectActionHandler(mock_mw, mock_data_processor, mock_mw.ui_updater)

    on_completed_mock = MagicMock()

    with patch('handlers.project_action_handler.ProjectLoadWorker') as mock_worker_class:
        h._populate_blocks_from_project(on_completed=on_completed_mock)

        # Verify load_session_file was called
        mock_data_processor.load_session_file.assert_called_once()
        mock_data_processor._autosave_session.assert_not_called()

        # Verify block_to_project_file_map was copied
        assert mock_mw.block_to_project_file_map == {0: 10}

        # Verify paths were updated
        assert mock_mw.data_store.json_path == "abs_a.json"
        assert mock_mw.data_store.edited_json_path == "abs_t_a.json"

        # Fast session restore should skip ProjectLoadWorker and avoid the load progress dialog.
        mock_worker_class.assert_not_called()

        # Verify callback was called with True
        on_completed_mock.assert_called_once_with(True)


def test_startup_splash_waits_for_restored_virtual_blocks(mock_mw):
    from ui.updaters.block_list_updater import BlockListUpdater

    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project.blocks = [
        MagicMock(source_file='a.json', translation_file='t_a.json')
    ]
    mock_mw.project_manager.get_absolute_path.side_effect = lambda path, **kwargs: "abs_" + path
    mock_mw.current_game_rules = MagicMock()
    mock_mw._startup_splash = MagicMock()
    mock_mw.finish_startup_loading = MagicMock()
    mock_mw.data_store.data = [["restored"]]
    mock_mw.data_store.block_to_project_file_map = {0: 0}

    data_processor = MagicMock()
    data_processor.load_session_file.return_value = True
    block_updater = BlockListUpdater(mock_mw, data_processor)
    block_updater._is_loading_chapters = True
    mock_mw.ui_updater.block_list_updater = block_updater
    handler = ProjectActionHandler(mock_mw, data_processor, mock_mw.ui_updater)
    completed = MagicMock()

    handler._populate_blocks_from_project(on_completed=completed)

    completed.assert_not_called()
    mock_mw.finish_startup_loading.assert_not_called()

    block_updater._is_loading_chapters = False
    block_updater._notify_virtual_blocks_ready()

    completed.assert_called_once_with(True)
    mock_mw.finish_startup_loading.assert_called_once_with()


def test_ProjectActionHandler_populate_blocks_from_project_empty_session_falls_back(mock_mw):
    mock_mw.project_manager = MagicMock()
    mock_block = MagicMock(source_file='a.json', translation_file='t_a.json', name="Block A")
    mock_mw.project_manager.project.blocks = [mock_block]
    mock_mw.project_manager.get_absolute_path.side_effect = lambda path, **kwargs: "abs_" + path

    mock_mw.current_game_rules = MagicMock()

    mock_data_processor = MagicMock()
    mock_data_processor.load_session_file.return_value = True

    mock_mw.data_store = MagicMock()
    mock_mw.data_store.data = []
    mock_mw.data_store.block_to_project_file_map = {}

    h = ProjectActionHandler(mock_mw, mock_data_processor, mock_mw.ui_updater)
    on_completed_mock = MagicMock()

    with patch('handlers.project_action_handler.ProjectLoadWorker') as mock_worker_class:
        mock_worker = mock_worker_class.return_value
        callbacks = []
        mock_worker.finished.connect.side_effect = callbacks.append

        def run_mock():
            for cb in callbacks:
                cb({
                    'data': [['data']],
                    'edited_file_data': [['t_data']],
                    'block_names': {'0': 'Block A'},
                    'block_to_project_file_map': {0: 10},
                    'plugin_keys_backup': None
                })
        mock_worker.run.side_effect = run_mock

        h._populate_blocks_from_project(on_completed=on_completed_mock)

        mock_data_processor.load_session_file.assert_called_once()
        mock_data_processor._autosave_session.assert_called_once_with(force=True)
        mock_worker_class.assert_called_once()
        assert mock_mw.data_store.data == [['data']]
        assert mock_mw.block_to_project_file_map == {0: 10}
        assert mock_mw.data_store.json_path == "abs_a.json"
        assert mock_mw.data_store.edited_json_path == "abs_t_a.json"
