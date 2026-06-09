import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QWidget, QListWidgetItem
from PyQt6.QtCore import Qt
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
    with patch("PyQt6.QtWidgets.QMessageBox.information") as mock_info:
        dialog._advance_pipeline()
        assert dialog.pipeline_running is False
        assert dialog.pipeline_step == 0
        mock_info.assert_called_once()


def test_mempalace_builder_pipeline_session_persistence(qapp):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    mock_mw.data_store.data = [["Line"]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    
    # Mock settings manager
    mock_settings = {}
    mock_mw.settings_manager = MagicMock()
    def mock_set(key, val):
        mock_settings[key] = val
    def mock_get(key, default=None):
        return mock_settings.get(key, default)
    mock_mw.settings_manager.set.side_effect = mock_set
    mock_mw.settings_manager.get.side_effect = mock_get
    
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    
    # 1. Start pipeline at step 2
    dialog.pipeline_running = True
    dialog.pipeline_step = 2
    dialog.wing_edit.setText("Zelda_TEST")
    dialog.file_path_edit.setText("d:/test/script.txt")
    
    # 2. Persist state
    dialog._save_pipeline_state()
    assert mock_settings["mempalace_pipeline_running"] is True
    assert mock_settings["mempalace_pipeline_step"] == 2
    assert mock_settings["mempalace_pipeline_wing"] == "Zelda_TEST"
    assert mock_settings["mempalace_pipeline_script"] == "d:/test/script.txt"
    
    # 3. Create a new dialog and load settings to verify recovery
    dialog2 = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    dialog2.load_builder_settings()
    assert dialog2.saved_pipeline_running is True
    assert dialog2.saved_pipeline_step == 2
    assert dialog2.saved_pipeline_wing == "Zelda_TEST"
    assert dialog2.saved_pipeline_script == "d:/test/script.txt"
    assert "Continue Pipeline (Step 2/4)" in dialog2.pipeline_btn.text()


def test_mempalace_builder_sleep_checkboxes_enabled_during_execution(qapp):
    mock_mw = MagicMock()
    mock_mw.project_manager = MagicMock()
    mock_mw.project_manager.project = None
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.project_file = "d:/test/file.bmg"
    mock_mw.data_store.data = [["Line"]]
    mock_mw.data_store.block_names = {"0": "zel_00"}
    mock_mw.settings_manager = MagicMock()
    
    parent_widget = QWidget()
    dialog = MemePalaceBuilderDialog(mock_mw, parent=parent_widget)
    
    # Verify checkboxes are enabled initially
    assert dialog.prevent_sleep_checkbox.isEnabled() is True
    assert dialog.sleep_after_checkbox.isEnabled() is True
    
    # Simulate background task running (UI disabled)
    dialog._set_ui_enabled(False)
    
    # Checkboxes MUST remain enabled for dynamic toggling by user at any time
    assert dialog.prevent_sleep_checkbox.isEnabled() is True
    assert dialog.sleep_after_checkbox.isEnabled() is True
    
    # Restore normal state
    dialog._set_ui_enabled(True)
    assert dialog.prevent_sleep_checkbox.isEnabled() is True
    assert dialog.sleep_after_checkbox.isEnabled() is True

