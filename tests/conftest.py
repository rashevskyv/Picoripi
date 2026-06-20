import pytest
import gc
from PyQt6.QtCore import QThread, Qt
# Monkeypatch Qt item roles for backwards compatibility
Qt.EditRole = Qt.ItemDataRole.EditRole
Qt.DisplayRole = Qt.ItemDataRole.DisplayRole
Qt.UserRole = Qt.ItemDataRole.UserRole
Qt.ToolTipRole = Qt.ItemDataRole.ToolTipRole
Qt.BackgroundRole = Qt.ItemDataRole.BackgroundRole
Qt.ForegroundRole = Qt.ItemDataRole.ForegroundRole
Qt.CheckStateRole = Qt.ItemDataRole.CheckStateRole
Qt.FontRole = Qt.ItemDataRole.FontRole
Qt.SizeHintRole = Qt.ItemDataRole.SizeHintRole

from unittest.mock import MagicMock, Mock
from PyQt6.QtWidgets import QApplication, QWidget

class MockMainWindow(MagicMock):
    """A specialized MagicMock subclass for MainWindow in tests, exposing physical_block_idx."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._physical_block_idx = -1

    @property
    def physical_block_idx(self) -> int:
        if hasattr(self, '_physical_block_idx'):
            val = self._physical_block_idx
            if not isinstance(val, Mock):
                try:
                    val_int = int(val)
                    if val_int >= 0:
                        return val_int
                except (TypeError, ValueError):
                    pass
        if hasattr(self, 'current_block_idx'):
            c_idx = self.current_block_idx
            if not isinstance(c_idx, Mock):
                try:
                    c_idx_int = int(c_idx)
                    if c_idx_int >= 0:
                        return c_idx_int
                except (TypeError, ValueError):
                    pass
        return -1

    def __getattribute__(self, name):
        if name in ('physical_block_idx', '_physical_block_idx'):
            return object.__getattribute__(self, name)
        return super().__getattribute__(name)

    @physical_block_idx.setter
    def physical_block_idx(self, val: int) -> None:
        self._physical_block_idx = val


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

def _stop_lingering_qthreads():
    """Best-effort: stop any still-running QThreads before gc tears them down.

    Letting a running QThread be garbage-collected aborts the process with
    "QThread: Destroyed while thread is still running". The SpellcheckerManager
    in particular leaves a background worker thread alive across many tests,
    which previously caused intermittent worker crashes under pytest-xdist.
    We walk all live QObjects we can see and ask each running QThread to quit.
    """
    # Walk all live QObjects on the heap and find QThreads.
    threads = [obj for obj in gc.get_objects() if isinstance(obj, QThread)]
    for thread in threads:
        try:
            if not thread.isRunning():
                continue
            # Try the manager-provided cooperative shutdown hooks if any object
            # holds the thread; we don't have a reference to its worker, so we
            # rely on QThread.quit() + a short wait. Workers that watch
            # threading.Event or check thread.isInterruptionRequested() will
            # exit; otherwise we time out and move on.
            thread.requestInterruption()
            thread.quit()
            thread.wait(500)
        except RuntimeError:
            # The C++ object may already be gone; that's fine.
            pass


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

    # Stop any background QThreads before gc.collect() — destroying a running
    # QThread aborts the process.
    _stop_lingering_qthreads()

    # Force garbage collection
    gc.collect()

@pytest.fixture
def mock_mw(qapp):
    """Provides a mocked MainWindow instance."""
    mw = MockMainWindow()
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
    mw.data_store.current_chapter_id = None
    mw.data_store.current_category_name = None
    mw.data_store.current_speaker_name = None
    mw.data_store.show_warnings_only = False
    mw.data_store.active_warning_filters = []
    mw.data_store.hide_empty_strings = False
    mw.data_store.hide_translated = False
    mw.data_store.hide_categorized = False
    mw.data_store.highlight_categorized = False
    mw.data_store.show_overrides_only = False
    mw.data_store.show_unsaved_only = False
    mw.line_width_warning_threshold_pixels = 100
    mw.game_dialog_max_width_pixels = 240
    mw.current_game_rules = MagicMock()
    mw.active_game_plugin = ""
    mw.state = None
    mw._is_test_mode = True
    from core.filter_query_api import FilterQueryAPI
    mw.filter_query_api = FilterQueryAPI(mw)
    mw.data_store.displayed_string_indices = []

    # Default to "no BFN editor open" so production code doesn't try to call
    # methods on a magic-mock and either blow up or produce nonsensical state.
    # Tests that need an active BFN editor should explicitly assign a real
    # DummyBfnEditor (see tests/test_ui/test_bfn_preview_widget.py).
    mw._bfn_editor_window = None

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


@pytest.fixture(autouse=True)
def clear_caches_before_test():
    """Clears width caches before each test to prevent dict ID collision bugs in tests."""
    from utils.utils import clear_width_caches
    clear_width_caches()


