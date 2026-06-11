import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt, QModelIndex, QRect
from PyQt6.QtGui import QPainter, QColor, QFont, QImage
from PyQt6.QtWidgets import QStyleOptionViewItem, QStyle

from components.translation_variations_dialog import TranslationVariationsDialog, VariationsListDelegate

@pytest.fixture
def mock_parent():
    parent = MagicMock()
    parent.variations_window_geometry = None
    parent.variations_splitter_state = None
    parent.settings_manager = None
    parent.translation_handler = None
    parent.current_game_rules = None
    return parent

def test_variations_dialog_init(mock_parent):
    variations = ["var1", "var2 long translation", "var3 extremely long translation options"]
    dialog = TranslationVariationsDialog(None, variations=variations, show_refresh=True)
    dialog.mw = mock_parent
    
    assert dialog._list.count() == 3
    assert dialog._list.item(0).data(Qt.ItemDataRole.UserRole) == "var1"
    assert dialog._list.item(1).data(Qt.ItemDataRole.UserRole) == "var2 long translation"
    assert dialog._list.item(2).data(Qt.ItemDataRole.UserRole) == "var3 extremely long translation options"
    
    # Check that delegate is set
    delegate = dialog._list.itemDelegate()
    assert isinstance(delegate, VariationsListDelegate)

def test_variations_list_delegate_paint(mock_parent):
    variations = ["var1", "var2 long translation", "var3 extremely long translation options"]
    dialog = TranslationVariationsDialog(None, variations=variations, show_refresh=True)
    dialog.mw = mock_parent
    delegate = dialog._list.itemDelegate()
    
    image = QImage(100, 100, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 100, 20)
    option.state = QStyle.StateFlag.State_Selected
    option.font = QFont()
    
    # Get a real index from the QListWidget model
    index = dialog._list.model().index(0, 0)
    
    # Paint call
    delegate.paint(painter, option, index)
    
    # Test for unselected state
    option.state = QStyle.StateFlag.State_None
    delegate.paint(painter, option, index)
