import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt5.QtCore import Qt
from ui.updaters.block_list_updater import BlockListUpdater

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    pw = QTreeWidget()
    mw.block_list_widget = pw
    mw.block_names = {"0": "Block Zero", "1": "Block One"}
    mw.data = [["Str0"], ["Str1", "Str2"]]
    
    pm = MagicMock()
    pm.project.blocks = []
    block0 = MagicMock()
    block0.source_file = "src/block0.txt"
    pm.project.blocks.append(block0)
    pm.SOURCES_DIR = "src"
    mw.project_manager = pm
    
    mw.problems_per_subline = {
        (0, 0, 0): {"prob1"},
        (1, 0, 0): {"prob1", "prob2"},
    }
    
    gr = MagicMock()
    gr.get_problem_definitions.return_value = {
        "prob1": {"priority": 1, "name": "Width Error"},
        "prob2": {"priority": 2, "name": "Empty Odd Line Error"}
    }
    mw.current_game_rules = gr
    
    return mw

@pytest.fixture
def mock_dp():
    dp = MagicMock()
    dp.get_current_string_text.side_effect = lambda b, s: (f"Text {b} {s}", None)
    return dp

@pytest.fixture
def updater(mock_mw, mock_dp):
    return BlockListUpdater(mock_mw, mock_dp)

def test_BlockListUpdater_populate_blocks(updater):
    # Mock create_item because it's a custom method on main window's block list widget
    mock_item = QTreeWidgetItem()
    updater.mw.block_list_widget.create_item = MagicMock(return_value=mock_item)
    
    updater.populate_blocks()
    
    # Verify that it creates 2 items
    assert updater.mw.block_list_widget.create_item.call_count == 2
    
    # Check that dir_nodes logic works
    assert updater.mw.block_list_widget.topLevelItemCount() > 0

def test_BlockListUpdater_update_block_item_text_with_problem_count(updater):
    # Setup tree item
    item = QTreeWidgetItem(["Block 0Base"])
    item.setData(0, Qt.UserRole, 0)
    updater.mw.block_list_widget.addTopLevelItem(item)
    
    updater.update_block_item_text_with_problem_count(0)
    
    expected_text = "Block Zero [1] (1 width)"
    assert item.text(0) == expected_text

    item1 = QTreeWidgetItem(["Block 1Base"])
    item1.setData(0, Qt.UserRole, 1)
    updater.mw.block_list_widget.addTopLevelItem(item1)
    
    updater.update_block_item_text_with_problem_count(1)
    expected_text1 = "Block One [2] (1 width, 1 empty)"
    assert item1.text(0) == expected_text1

def test_BlockListUpdater_clear_all_problem_block_highlights_and_text(updater):
    # Setup tree item
    item = QTreeWidgetItem(["Block Zero [1] (1 width)"])
    item.setData(0, Qt.UserRole, 0)
    updater.mw.block_list_widget.addTopLevelItem(item)
    
    updater.clear_all_problem_block_highlights_and_text()
    
    assert item.text(0) == "Block Zero"
