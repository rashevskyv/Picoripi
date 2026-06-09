import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QFileDialog
from handlers.project_action_handler import ProjectActionHandler
from ui.components.bfn_preview_widget import BfnPreviewWidget
from core.bfn_core import BfnCore

@patch('handlers.project_action_handler.ProjectManager')
@patch('handlers.project_action_handler.QMessageBox')
def test_project_font_loading_on_open(mock_msg_box, mock_pm_class, qapp, mock_mw):
    """
    Test that when a project is opened via open_project_action,
    load_all_font_maps is called to load the BFN fonts,
    and update_font_combobox is called to sync UI components.
    """
    # Initialize ProjectActionHandler
    mock_mw.ui_updater = MagicMock()
    handler = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)

    # Setup string settings updater mock
    mock_mw.string_settings_updater = MagicMock()

    # Mock the QFileDialog to return a dummy project path
    dummy_project_path = "C:/path/to/test_project.uiproj"
    
    # Mock ProjectManager instance
    mock_pm = mock_pm_class.return_value
    mock_pm.load.return_value = True
    
    mock_project = MagicMock()
    mock_project.name = "Test Font Project"
    mock_project.plugin_name = "zelda_mc"
    mock_project.blocks = []
    mock_pm.project = mock_project

    # Setup patch for QFileDialog
    with patch.object(QFileDialog, 'getOpenFileName', return_value=(dummy_project_path, "")):
        handler.open_project_action()

    # Verify project load sequence calls
    mock_pm.load.assert_called_once_with(dummy_project_path)
    mock_pm.load_settings_from_project.assert_called_once_with(mock_mw)
    mock_mw.settings_manager.load_all_font_maps.assert_called_once()
    mock_mw.string_settings_updater.update_font_combobox.assert_called_once()


@patch('handlers.project_action_handler.ProjectManager')
@patch('handlers.project_action_handler.QMessageBox')
def test_project_font_loading_on_open_recent(mock_msg_box, mock_pm_class, qapp, mock_mw):
    """
    Test that when a project is opened via _open_recent_project (e.g. on startup or history),
    load_all_font_maps and update_font_combobox are successfully executed.
    """
    mock_mw.ui_updater = MagicMock()
    handler = ProjectActionHandler(mock_mw, MagicMock(), mock_mw.ui_updater)
    mock_mw.string_settings_updater = MagicMock()

    dummy_project_path = "C:/path/to/recent_project.uiproj"
    
    # Mock ProjectManager
    mock_pm = mock_pm_class.return_value
    mock_pm.load.return_value = True
    
    mock_project = MagicMock()
    mock_project.name = "Recent Font Project"
    mock_project.plugin_name = "zelda_ww"
    mock_project.blocks = []
    mock_pm.project = mock_project

    # Mock file existence check and run
    with patch('handlers.project_action_handler.Path.exists', return_value=True):
        handler._open_recent_project(dummy_project_path)

    # Verify calls
    mock_pm.load.assert_called_once_with(dummy_project_path)
    mock_pm.load_settings_from_project.assert_called_once_with(mock_mw)
    mock_mw.settings_manager.load_all_font_maps.assert_called_once()
    mock_mw.string_settings_updater.update_font_combobox.assert_called_once()


def test_bfn_preview_widget_active_font_resolves_correctly(qapp, mock_mw):
    """
    Test that BfnPreviewWidget successfully resolves and returns the active BFN font
    loaded after project opening.
    """
    # 1. Setup mock main window states after font map loading
    mock_mw.data_store.current_block_idx = 1
    mock_mw.data_store.current_string_idx = 5
    
    # Custom string metadata overrides
    mock_mw.string_metadata = {
        (1, 5): {"font_file": "zelda_font.bfn"}
    }
    
    # Loaded BFN fonts dictionary on main window
    mock_bfn = MagicMock(spec=BfnCore)
    mock_mw.all_bfn_fonts = {
        "zelda_font.bfn": mock_bfn
    }
    
    # 2. Instantiate BfnPreviewWidget
    preview_widget = BfnPreviewWidget(mock_mw)
    
    # 3. Assert active font resolves to our loaded mock BFN font
    active_font = preview_widget.get_active_bfn_font()
    assert active_font == mock_bfn
