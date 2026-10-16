"""Plugin folders under a physical block: the block tree shows them, a rebuild keeps them, selecting one fills the
strings list with exactly its rows."""
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

from core.data_store import ViewKind
from core.filter_query_api import FilterQueryAPI
from handlers.list_selection_handler import ListSelectionHandler
from ui.updaters.block_list_updater import BlockListUpdater

SMALL_ROWS = [(0, 1), (0, 2)]


class _Rules:
    """Explicit fake GameRules: block 0 has a folder with a subfolder and a flat folder."""

    def __init__(self):
        self.text_of = None

    def get_problem_definitions(self):
        return {}

    def get_virtual_folders(self, block_idx, text_of):
        self.text_of = text_of
        if block_idx != 0:
            return []
        return [
            {"title": "Small text", "children": [{"title": "Battery", "rows": SMALL_ROWS}]},
            {"title": "Contents", "rows": [(0, 0)]},
        ]


def _create_item(text, block_idx, role):
    item = QTreeWidgetItem([text])
    item.setData(0, role, block_idx)
    return item


@pytest.fixture
def tree_mw(mock_mw):
    tree = QTreeWidget()
    tree.create_item = _create_item
    mock_mw.block_list_widget = tree
    mock_mw.project_manager = None  # legacy physical tree: block items sit at the top level
    mock_mw.data_store.data = [["Battery pack", "Press the button."]]
    mock_mw.data_store.block_names = {"0": "Manual"}
    mock_mw.data_store.problems_per_subline = {}
    mock_mw.current_game_rules = _Rules()
    mock_mw.filter_query_api = FilterQueryAPI(mock_mw)
    mock_mw.data_processor = MagicMock()
    mock_mw.data_processor.get_current_string_text.side_effect = lambda b, s: (f"Current {s}", "edited")
    mock_mw.ui_updater = MagicMock()
    return mock_mw


@pytest.fixture
def updater(tree_mw):
    return BlockListUpdater(tree_mw, tree_mw.data_processor)


def _find(item, title):
    for index in range(item.childCount()):
        if item.child(index).data(0, Qt.ItemDataRole.UserRole + 4) == title:
            return item.child(index)
    raise AssertionError(f"no folder {title!r}")


def test_block_tree_shows_plugin_folders_under_the_block(updater, tree_mw):
    block = updater._create_block_tree_item(0, {})
    tree_mw.block_list_widget.addTopLevelItem(block)

    small = _find(block, "Small text")
    assert small.data(0, Qt.ItemDataRole.UserRole) == -2
    assert small.data(0, Qt.ItemDataRole.UserRole + 18) == "aggregate"
    assert small.data(0, Qt.ItemDataRole.UserRole + 13) == SMALL_ROWS
    assert small.child(0).data(0, Qt.ItemDataRole.UserRole + 13) == SMALL_ROWS
    assert _find(block, "Contents").data(0, Qt.ItemDataRole.UserRole + 13) == [(0, 0)]


def test_plugin_text_of_gives_current_text_or_the_original(updater, tree_mw):
    updater._create_block_tree_item(0, {})
    text_of = tree_mw.current_game_rules.text_of
    assert text_of(0) == "Current 0"
    tree_mw.data_processor.get_current_string_text.side_effect = lambda b, s: ("  ", "edited")
    assert text_of(0) == "Battery pack"


def test_selecting_a_plugin_folder_fills_the_strings_list_with_its_rows(updater, tree_mw):
    block = updater._create_block_tree_item(0, {})
    tree_mw.block_list_widget.addTopLevelItem(block)
    small = _find(block, "Small text")

    handler = ListSelectionHandler(tree_mw, MagicMock(), tree_mw.ui_updater)
    with patch.object(handler, "_schedule_string_selection"), \
            patch.object(handler, "_update_block_toolbar_button_states"):
        handler.block_selected(small.child(0), None)

    store = tree_mw.data_store
    assert store.current_view_kind == ViewKind.CHAPTER
    assert store.chapter_mappings == SMALL_ROWS
    assert (store.current_block_idx, store.current_string_idx) == (0, 1)
    tree_mw.ui_updater.populate_current_view.assert_called_with(force=True)


def test_a_rebuild_selects_the_same_plugin_folder_again(updater, tree_mw):
    updater.populate_blocks()
    tree = tree_mw.block_list_widget
    contents = _find(tree.topLevelItem(0), "Contents")
    tree.setCurrentItem(contents)

    updater.populate_blocks()

    current = tree.currentItem()
    assert current is not None
    assert current.data(0, Qt.ItemDataRole.UserRole + 13) == [(0, 0)]
