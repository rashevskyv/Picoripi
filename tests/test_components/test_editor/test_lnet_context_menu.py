from types import SimpleNamespace
from unittest.mock import MagicMock

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QMainWindow, QMenu

from components.editor.lnet_context_menu_logic import LNETContextMenuLogic


def test_preview_mempalace_menu_receives_all_selected_physical_rows(qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    window.data_store = SimpleNamespace(
        displayed_string_indices=[(4, 7), (4, 8), (9, 3)],
        physical_block_idx=4,
        current_block_idx=4,
        edited_data={},
    )
    window.translation_handler = None
    window.spellchecker_manager = None
    window.list_selection_handler = MagicMock()
    window.editor_operation_handler = MagicMock()

    block_tree = MagicMock()
    block_tree._add_mempalace_context_menu.return_value = True
    window.block_list_widget = block_tree

    editor = MagicMock()
    editor.window.return_value = window
    editor.objectName.return_value = "preview_text_edit"
    editor.get_selected_lines.return_value = [0, 2]
    logic = LNETContextMenuLogic(editor)
    menu = QMenu(window)

    logic.populate(menu, QPoint(0, 0))

    block_tree._add_mempalace_context_menu.assert_called_once_with(
        menu,
        [(4, 7), (9, 3)],
        preserve_tree_selection=True,
    )


def test_preview_mempalace_menu_maps_normal_block_rows(qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    window.data_store = SimpleNamespace(
        displayed_string_indices=[11, 15],
        physical_block_idx=6,
        current_block_idx=6,
    )
    editor = MagicMock()
    editor.get_selected_lines.return_value = [0, 1]

    rows = LNETContextMenuLogic(editor)._preview_mempalace_rows(
        window, QPoint(0, 0)
    )

    assert rows == [(6, 11), (6, 15)]
