import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QSplitter, QWidget
from PyQt5.QtCore import Qt
from main import MainWindow
from ui.main_window.main_window_helper import MainWindowHelper
import base64

class MockedMainWindow:
    def __init__(self) -> None:
        self.main_splitter = None
        self.right_splitter = None
        self.bottom_right_splitter = None
        self.editor_preview_splitter = None
        self.settings_manager = MagicMock()
        self.window_geometry_to_restore = None
        self.data_store = MagicMock()
        self.data_store.edited_data = {}
        self.last_opened_path = ""
        self.resize = MagicMock()
        self.setGeometry = MagicMock()
        self.ui_updater = MagicMock()
        self.app_action_handler = MagicMock()
        self.search_panel_widget = MagicMock()
        self.search_handler = MagicMock()

    @property
    def main_splitter_state(self):
        return MainWindow.main_splitter_state.fget(self)

    @main_splitter_state.setter
    def main_splitter_state(self, val):
        MainWindow.main_splitter_state.fset(self, val)

    @property
    def right_splitter_state(self):
        return MainWindow.right_splitter_state.fget(self)

    @right_splitter_state.setter
    def right_splitter_state(self, val):
        MainWindow.right_splitter_state.fset(self, val)

    @property
    def bottom_right_splitter_state(self):
        return MainWindow.bottom_right_splitter_state.fget(self)

    @bottom_right_splitter_state.setter
    def bottom_right_splitter_state(self, val):
        MainWindow.bottom_right_splitter_state.fset(self, val)

    @property
    def editor_preview_splitter_state(self):
        return MainWindow.editor_preview_splitter_state.fget(self)

    @editor_preview_splitter_state.setter
    def editor_preview_splitter_state(self, val):
        MainWindow.editor_preview_splitter_state.fset(self, val)

def test_splitter_properties(qapp):
    mw = MockedMainWindow()
    
    # Check that they return None when splitters are not created
    assert mw.main_splitter_state is None
    assert mw.right_splitter_state is None
    assert mw.bottom_right_splitter_state is None
    assert mw.editor_preview_splitter_state is None
    
    # Create real QSplitter widgets
    mw.main_splitter = QSplitter(Qt.Horizontal)
    mw.right_splitter = QSplitter(Qt.Vertical)
    mw.bottom_right_splitter = QSplitter(Qt.Horizontal)
    mw.editor_preview_splitter = QSplitter(Qt.Vertical)
    
    # Add dummy widgets to make splitters have children (so sizes() != [])
    for splitter in [mw.main_splitter, mw.right_splitter, mw.bottom_right_splitter, mw.editor_preview_splitter]:
        splitter.addWidget(QWidget())
        splitter.addWidget(QWidget())
        splitter.resize(1000, 1000)
    
    # Test getters return base64 string
    assert isinstance(mw.main_splitter_state, str)
    assert len(mw.main_splitter_state) > 0
    
    # Test setter logic
    mw.main_splitter.setSizes([100, 900])
    saved_state = mw.main_splitter_state
    
    # Change sizes
    mw.main_splitter.setSizes([400, 600])
    assert mw.main_splitter.sizes() != [100, 900]
    
    # Restore sizes
    mw.main_splitter_state = saved_state
    assert mw.main_splitter.sizes()[0] == 100

def test_restore_state_after_settings_load(qapp):
    mw = MockedMainWindow()
    mw.main_splitter = QSplitter(Qt.Horizontal)
    mw.right_splitter = QSplitter(Qt.Vertical)
    
    # Add dummy widgets to make splitters have children
    mw.main_splitter.addWidget(QWidget())
    mw.main_splitter.addWidget(QWidget())
    mw.right_splitter.addWidget(QWidget())
    mw.right_splitter.addWidget(QWidget())
    
    state_val = base64.b64encode(mw.main_splitter.saveState().data()).decode('ascii')
    
    # Configure mock settings manager to return state
    def mock_get(key, default=None):
        if key == "main_splitter_state":
            return state_val
        return None
    mw.settings_manager.get.side_effect = mock_get
    
    helper = MainWindowHelper(mw)
    
    # Mock other calls within restore_state_after_settings_load to avoid exceptions
    with patch.object(helper, 'rebuild_unsaved_block_indices'), \
         patch('PyQt5.QtWidgets.QApplication.desktop') as mock_desktop:
        
        helper.restore_state_after_settings_load()
        
        # Verify settings_manager was queried for splitter states
        mw.settings_manager.get.assert_any_call("main_splitter_state")
        mw.settings_manager.get.assert_any_call("right_splitter_state")
