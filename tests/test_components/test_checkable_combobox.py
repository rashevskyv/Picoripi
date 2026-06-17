# tests/test_components/test_checkable_combobox.py
import pytest
from PyQt6.QtCore import Qt, QPointF, QEvent
from PyQt6.QtGui import QMouseEvent
from components.checkable_combobox import CheckableComboBox

def test_checkable_combobox_items(qapp):
    """Test adding items, checking them, and getting checked data."""
    cb = CheckableComboBox()
    cb.add_item("Item 1", "data_1")
    cb.add_item("Item 2", "data_2", is_checked=True)
    cb.add_item("Item 3", "data_3")

    # Item 2 is checked initially
    assert cb.checked_data() == ["data_2"]
    assert cb.lineEdit().text() == "Item 2"

    # Set checked data
    cb.set_checked_data(["data_1", "data_3"])
    assert cb.checked_data() == ["data_1", "data_3"]
    assert cb.lineEdit().text() == "Item 1, Item 3"

    # All selected
    cb.set_checked_data(["data_1", "data_2", "data_3"])
    assert cb.lineEdit().text() == "All selected"

    # None selected
    cb.set_checked_data([])
    assert cb.lineEdit().text() == "None selected"

def test_checkable_combobox_signals(qapp):
    """Test that checkedItemsChanged is emitted on change."""
    cb = CheckableComboBox()
    cb.add_item("Item 1", "data_1")
    cb.add_item("Item 2", "data_2")

    emitted_data = []
    cb.checkedItemsChanged.connect(emitted_data.append)

    # Toggle check state using model
    item = cb.model().item(0)
    item.setCheckState(Qt.CheckState.Checked)

    assert len(emitted_data) == 1
    assert emitted_data[0] == ["data_1"]

def test_checkable_combobox_clear(qapp):
    """Test clear method resets items and text."""
    cb = CheckableComboBox()
    cb.add_item("Item A", "A", is_checked=True)
    cb.add_item("Item B", "B", is_checked=False)
    assert cb.lineEdit().text() == "Item A"

    cb.clear()
    assert cb.model().rowCount() == 0
    assert cb.lineEdit().text() == "None selected"

def test_checkable_combobox_event_filter(qapp):
    """Test eventFilter intercepts click events on the viewport to toggle check state without closing popup."""
    cb = CheckableComboBox()
    cb.add_item("Item A", "A", is_checked=False)
    
    viewport = cb.view().viewport()
    
    cb.show()
    cb.showPopup()
    
    # Create a mouse click event with QPointF
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(5.0, 5.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    # We mock the indexAt on the view to return the first index
    first_index = cb.view().model().index(0, 0)
    original_index_at = cb.view().indexAt
    cb.view().indexAt = lambda pos: first_index
    
    try:
        res = cb.eventFilter(viewport, event)
        assert res is True  # Event should be consumed
        assert cb.model().item(0).checkState() == Qt.CheckState.Checked
    finally:
        cb.view().indexAt = original_index_at
        cb.hide()
