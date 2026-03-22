import pytest
import gc
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication, QWidget

@pytest.fixture(autouse=True)
def silent_logging(mocker):
    """Mocks logging so tests don't pollute output unnecessarily."""
    try:
        mocker.patch('utils.logging_utils.log_info')
        mocker.patch('utils.logging_utils.log_error')
        mocker.patch('utils.logging_utils.log_warning')
    except Exception:
        pass

@pytest.fixture
def mock_project_manager():
    """Provides a mocked ProjectManager instance that doesn't touch the disk."""
    pm_mock = MagicMock()
    pm_mock.current_project = MagicMock()
    pm_mock.current_project.name = "TestProject"
    return pm_mock

@pytest.fixture
def mock_ui_provider():
    """Mocks the UI Provider for handlers."""
    ui_mock = MagicMock()
    ui_mock.data_store = ui_mock
    ui_mock.edited_text_edit = MagicMock()
    ui_mock.original_text_edit = MagicMock()
    ui_mock.block_list_widget = MagicMock()
    return ui_mock

@pytest.fixture(scope="session")
def qapp():
    """Provides a single QApplication instance for the entire test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

@pytest.fixture(autouse=True)
def cleanup_qt(qapp):
    """Ensures all top-level widgets are destroyed and memory is collected after each test."""
    yield
    # Close all top-level widgets that might have been created
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    
    # Process events to let deleteLater work
    QApplication.processEvents()
    
    # Force garbage collection
    gc.collect()

@pytest.fixture
def mock_mw(qapp):
    """Provides a mocked MainWindow instance."""
    mw = MagicMock()
    mw.data_store = mw
    mw.data_store.unsaved_changes = False
    # Common UI elements
    mw.block_list_widget = MagicMock()
    mw.edited_text_edit = MagicMock()
    mw.original_text_edit = MagicMock()
    mw.preview_text_edit = MagicMock()
    
    mw.settings_manager = MagicMock()
    mw.settings_manager.session_state = MagicMock()
    mw.settings_manager.session_state.get_state_for_file.return_value = {}
    
    # Helper and font map
    mw.helper = MagicMock()
    mw.font_map = {}
    mw.data_store.data = []
    mw.data_store.problems_per_subline = {}
    mw.string_metadata = {}
    mw.line_width_warning_threshold_pixels = 100
    mw.game_dialog_max_width_pixels = 240
    mw.current_game_rules = MagicMock()
    
    return mw

@pytest.fixture
def temp_dir(tmp_path):
    """Alias for tmp_path for compatibility with some tests."""
    return str(tmp_path)

@pytest.fixture
def sample_json_data():
    return {"key": "value", "nested": [1, 2, 3]}

@pytest.fixture
def sample_json_path(tmp_path, sample_json_data):
    path = tmp_path / "sample.json"
    with open(path, 'w', encoding='utf-8') as f:
        import json
        json.dump(sample_json_data, f)
    return str(path)

@pytest.fixture
def invalid_json_path(tmp_path):
    path = tmp_path / "invalid.json"
    with open(path, 'w') as f:
        f.write("{ invalid json")
    return str(path)

@pytest.fixture
def sample_text_content():
    return "Line 1\nLine 2\nCyrillic: Привіт"

@pytest.fixture
def sample_text_path(tmp_path, sample_text_content):
    path = tmp_path / "sample.txt"
    with open(path, 'w', encoding='utf-8') as f:
        f.write(sample_text_content)
    return str(path)

@pytest.fixture
def sample_utf16_path(tmp_path):
    path = tmp_path / "utf16.txt"
    content = "Тестовий текст UTF-16"
    with open(path, 'w', encoding='utf-16') as f:
        f.write(content)
    return str(path)

@pytest.fixture
def sample_glossary_md():
    """Sample glossary markdown for GlossaryManager tests."""
    return """# Glossary

| Original | Translation | Notes |
|----------|-------------|-------|
| Link | Лінк | Ім'я героя гри |
| Zelda | Зельда | Принцеса |
| Hyrule | Хайрул | Королівство |
| Rupee | Рупія | Валюта гри |
"""

