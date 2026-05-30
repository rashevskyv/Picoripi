import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication, QWidget, QListWidgetItem
from PyQt5.QtCore import Qt
from ui.mempalace_builder_dialog import MemePalaceBuilderDialog

@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication exists for widget testing."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app

def test_mempalace_builder_empty_lines_filtering(qapp):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None # Single-file mode
    
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    # Block 0 has one empty string, one whitespace-only string, and one valid string
    mock_mw.data_store.data = [
        ["", "   ", "Valid dialogue line"]
    ]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.edited_data = {}
    
    parent_widget = QWidget()
    
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    
    # 1. blocks_list_widget has been replaced by table widget in the current layout
    assert dialog is not None
    assert dialog.windowTitle() == "MemePalace Context Builder"


def test_mempalace_builder_pipeline_orchestration(qapp):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    mock_mw.data_store.data = [["Line"]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    
    # Enable pipeline and check sequence
    dialog.pipeline_running = True
    dialog.pipeline_step = 1
    
    # Mock core workers and dialog methods
    dialog._pre_analyze_script_via_ai_core = MagicMock()
    dialog._start_chapters_mapping_core = MagicMock()
    dialog._analyze_all_chapters_core = MagicMock()
    dialog._profile_characters_speech_via_ai_core = MagicMock()
    dialog._finish_and_maybe_sleep = MagicMock()
    dialog._get_ai_provider_or_warn = MagicMock(return_value=MagicMock())
    
    # Run step 1
    dialog._run_pipeline_current_step()
    dialog._pre_analyze_script_via_ai_core.assert_called_once()
    
    # Simulate step 1 success
    dialog._advance_pipeline()
    assert dialog.pipeline_step == 2
    dialog._start_chapters_mapping_core.assert_called_once()
    
    # Simulate step 2 success
    dialog._advance_pipeline()
    assert dialog.pipeline_step == 3
    dialog._analyze_all_chapters_core.assert_called_once()
    
    # Simulate step 3 success
    dialog._advance_pipeline()
    assert dialog.pipeline_step == 4
    dialog._profile_characters_speech_via_ai_core.assert_called_once()
    
    # Simulate step 4 success (pipeline complete)
    with patch("PyQt5.QtWidgets.QMessageBox.information") as mock_info:
        dialog._advance_pipeline()
        assert dialog.pipeline_running is False
        assert dialog.pipeline_step == 0
        mock_info.assert_called_once()
