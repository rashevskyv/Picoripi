from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtWidgets import QWidget, QTreeWidgetItem, QHeaderView, QMenu

from components.custom_tree_widget import CustomTreeWidget


def _assignment_tree(qtbot):
    window = QWidget()
    qtbot.addWidget(window)
    block = MagicMock()
    block.metadata = {}
    manager = MagicMock()
    manager.project.blocks = [block]
    window.project_manager = manager
    window.block_to_project_file_map = {0: 0}
    window.undo_manager = None
    window.data_store = MagicMock()
    window.data_store.selected_string_indices = [1, 2]
    window.data_store.physical_block_idx = 0
    window.ui_updater = MagicMock()
    tree = CustomTreeWidget(window)
    return window, tree, block


def test_tree_uses_constant_time_layout_settings(qtbot):
    _window, tree, _block = _assignment_tree(qtbot)

    assert tree.uniformRowHeights()
    assert tree.header().sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch


def test_assigns_multiple_selected_strings_to_speaker(qtbot):
    window, tree, block = _assignment_tree(qtbot)
    target = QTreeWidgetItem(["SYSTEM"])
    target.setData(0, Qt.UserRole, -3)
    target.setData(0, Qt.UserRole + 15, "SYSTEM")

    rows = tree._selected_editor_assignment_rows()
    assert rows == [(0, 1), (0, 2)]
    assert tree._assign_rows_to_story_target(rows, target)

    assert block.metadata["story_context_assignments"] == {
        "1": {"speaker": "SYSTEM"},
        "2": {"speaker": "SYSTEM"},
    }
    window.project_manager.save.assert_called_once()


def test_story_drop_records_path_and_none_is_explicit(qtbot):
    _window, tree, block = _assignment_tree(qtbot)
    act = QTreeWidgetItem(["Act One"])
    act.setData(0, Qt.UserRole, -2)
    act.setData(0, Qt.UserRole + 11, 10)
    scene = QTreeWidgetItem(act, ["Scene One"])
    scene.setData(0, Qt.UserRole, -2)
    scene.setData(0, Qt.UserRole + 11, 20)

    assert tree._assign_rows_to_story_target([(0, 1)], scene)
    assert block.metadata["story_context_assignments"]["1"] == {
        "structure_id": 20,
        "structure_path": ["Act One", "Scene One"],
    }

    none = QTreeWidgetItem(["None"])
    none.setData(0, Qt.UserRole, -2)
    none.setData(0, Qt.UserRole + 11, "story:none")
    assert tree._assign_rows_to_story_target([(0, 1)], none)
    assert block.metadata["story_context_assignments"]["1"] == {
        "structure_id": "story:none",
    }


def test_item_none_suppresses_only_item_facet(qtbot):
    _window, tree, block = _assignment_tree(qtbot)
    block.metadata = {
        "story_context_assignments": {"1": {"speaker": "MIDNA", "item": "Wallet"}}
    }
    target = QTreeWidgetItem(["None"])
    target.setData(0, Qt.UserRole, -4)
    target.setData(0, Qt.UserRole + 16, "None")

    assert tree._assign_rows_to_story_target([(0, 1)], target)
    assert block.metadata["story_context_assignments"]["1"] == {
        "speaker": "MIDNA",
        "item": "None",
    }


def test_qt6_drag_position_and_nested_folder_rows(qtbot):
    _window, tree, _block = _assignment_tree(qtbot)

    class Qt6Event:
        def position(self):
            return QPointF(12.7, 34.2)

    assert tree._event_point(Qt6Event()) == QPoint(13, 34)

    story_root = QTreeWidgetItem(["Story"])
    scene = QTreeWidgetItem(story_root, ["Scene"])
    scene.setData(0, Qt.UserRole + 13, [(0, 1), (0, 2)])
    speakers_root = QTreeWidgetItem(["Speakers"])
    speaker = QTreeWidgetItem(speakers_root, ["MIDNA"])
    speaker.setData(0, Qt.UserRole + 13, [(0, 2), (0, 3)])

    assert tree._dragged_assignment_rows([story_root, speakers_root]) == [
        (0, 1), (0, 2), (0, 3)
    ]


def test_window_level_none_clears_all_story_facets(qtbot):
    _window, tree, block = _assignment_tree(qtbot)
    block.metadata = {"story_context_assignments": {"1": {
        "structure_id": 20,
        "structure_path": ["Act One", "Scene One"],
        "speaker": "MIDNA",
        "item": "Wallet",
    }}}
    target = QTreeWidgetItem(["None"])
    target.setData(0, Qt.UserRole, -3)
    target.setData(0, Qt.UserRole + 15, "None")
    target.setData(0, Qt.UserRole + 17, "unbound")

    assert tree._assign_rows_to_story_target([(0, 1)], target)
    assert block.metadata["story_context_assignments"]["1"] == {
        "structure_id": "story:none",
        "speaker": "None",
        "item": "None",
    }


def test_drop_rechecks_none_target_at_release(qtbot):
    _window, tree, block = _assignment_tree(qtbot)
    source = QTreeWidgetItem(["Story"])
    source.setData(0, Qt.UserRole + 13, [(0, 1), (0, 2)])
    target = QTreeWidgetItem(["None"])
    target.setData(0, Qt.UserRole, -3)
    target.setData(0, Qt.UserRole + 15, "None")
    target.setData(0, Qt.UserRole + 17, "unbound")
    tree._pending_drag_items = [source]
    tree._custom_drop_target = None
    tree.itemAt = MagicMock(return_value=target)
    event = MagicMock()
    event.position.return_value = QPointF(10, 10)
    event.mimeData.return_value.hasFormat.return_value = False

    tree.dropEvent(event)

    assert block.metadata["story_context_assignments"] == {
        "1": {"structure_id": "story:none", "speaker": "None", "item": "None"},
        "2": {"structure_id": "story:none", "speaker": "None", "item": "None"},
    }
    event.acceptProposedAction.assert_called_once()


def test_virtual_target_locator_restores_none_and_expands_path(qtbot):
    _window, tree, _block = _assignment_tree(qtbot)
    windows = QTreeWidgetItem(["Windows"])
    boss = QTreeWidgetItem(windows, ["Boss name"])
    target = QTreeWidgetItem(boss, ["None"])
    target.setData(0, Qt.UserRole, -3)
    target.setData(0, Qt.UserRole + 15, "None")
    target.setData(0, Qt.UserRole + 17, "unbound")
    locator = tree._virtual_item_locator(target)

    rebuilt_windows = QTreeWidgetItem(["Windows"])
    rebuilt_boss = QTreeWidgetItem(rebuilt_windows, ["Boss name"])
    rebuilt_target = QTreeWidgetItem(rebuilt_boss, ["None"])
    rebuilt_target.setData(0, Qt.UserRole, -3)
    rebuilt_target.setData(0, Qt.UserRole + 15, "None")
    rebuilt_target.setData(0, Qt.UserRole + 17, "unbound")
    tree.addTopLevelItem(rebuilt_windows)

    assert tree._restore_virtual_item_locator(locator)
    assert tree.currentItem() is rebuilt_target
    assert rebuilt_windows.isExpanded()
    assert rebuilt_boss.isExpanded()


def test_context_menu_exposes_explicit_mempalace_operations(qtbot):
    _window, tree, _block = _assignment_tree(qtbot)
    story_root = QTreeWidgetItem(["Story"])
    scene = QTreeWidgetItem(story_root, ["Scene One"])
    scene.setData(0, Qt.UserRole, -2)
    scene.setData(0, Qt.UserRole + 11, 20)
    speakers_root = QTreeWidgetItem(["Speakers"])
    speaker = QTreeWidgetItem(speakers_root, ["MIDNA"])
    speaker.setData(0, Qt.UserRole, -3)
    speaker.setData(0, Qt.UserRole + 15, "MIDNA")
    items_root = QTreeWidgetItem(["Items"])
    item = QTreeWidgetItem(items_root, ["Wallet"])
    item.setData(0, Qt.UserRole, -4)
    item.setData(0, Qt.UserRole + 16, "Wallet")
    tree.addTopLevelItems([story_root, speakers_root, items_root])

    menu = QMenu(tree)
    assert tree._add_mempalace_context_menu(menu, [(0, 1), (0, 2)])

    palace_action = menu.actions()[0]
    assert palace_action.text() == "MemPalace Context (2 selected)"
    palace_menu = palace_action.menu()
    assert [action.text() for action in palace_menu.actions()] == [
        "Change Chapter / Scene…",
        "Change Speaker…",
        "Change Item",
        "",
        "Clear All Context",
    ]
    assert palace_menu.actions()[1].menu() is None


def test_context_menu_chapter_action_opens_hierarchical_picker(qtbot):
    _window, tree, block = _assignment_tree(qtbot)
    story_root = QTreeWidgetItem(["Story"])
    act = QTreeWidgetItem(story_root, ["Act One"])
    act.setData(0, Qt.UserRole, -2)
    act.setData(0, Qt.UserRole + 11, 10)
    scene = QTreeWidgetItem(act, ["Scene One"])
    scene.setData(0, Qt.UserRole, -2)
    scene.setData(0, Qt.UserRole + 11, 20)
    tree.addTopLevelItem(story_root)

    menu = QMenu(tree)
    tree._add_mempalace_context_menu(menu, [(0, 1), (0, 2)])
    chapter_action = menu.actions()[0].menu().actions()[0]

    with patch("components.chapter_picker.ChapterSelectionDialog.exec", return_value=1), patch(
        "components.chapter_picker.ChapterSelectionDialog.selection",
        return_value=(20, ("Act One", "Scene One")),
    ):
        chapter_action.trigger()

    assert block.metadata["story_context_assignments"] == {
        "1": {"structure_id": 20, "structure_path": ["Act One", "Scene One"]},
        "2": {"structure_id": 20, "structure_path": ["Act One", "Scene One"]},
    }


def test_context_menu_change_speaker_assigns_selected_rows(qtbot):
    _window, tree, block = _assignment_tree(qtbot)
    speakers_root = QTreeWidgetItem(["Speakers"])
    speaker = QTreeWidgetItem(speakers_root, ["MIDNA"])
    speaker.setData(0, Qt.UserRole, -3)
    speaker.setData(0, Qt.UserRole + 15, "MIDNA")
    tree.addTopLevelItem(speakers_root)
    menu = QMenu(tree)
    tree._add_mempalace_context_menu(menu, [(0, 1), (0, 2)])

    palace_menu = menu.actions()[0].menu()
    change_speaker_action = palace_menu.actions()[1]
    with patch("components.name_picker.SpeakerSelectionDialog.exec", return_value=1), patch(
        "components.name_picker.SpeakerSelectionDialog.selection", return_value="MIDNA"
    ):
        change_speaker_action.trigger()

    assert block.metadata["story_context_assignments"] == {
        "1": {"speaker": "MIDNA"},
        "2": {"speaker": "MIDNA"},
    }


def test_unbound_node_still_offers_mempalace_choices(qtbot):
    _window, tree, _block = _assignment_tree(qtbot)
    unbound = QTreeWidgetItem(["None"])
    unbound.setData(0, Qt.UserRole, -3)
    unbound.setData(0, Qt.UserRole + 15, "None")
    unbound.setData(0, Qt.UserRole + 17, "unbound")
    tree.addTopLevelItem(unbound)
    menu = QMenu(tree)

    assert tree._add_mempalace_context_menu(menu, [(0, 1)])
    palace_menu = menu.actions()[0].menu()
    assert palace_menu.actions()[0].text() == "Change Chapter / Scene…"
    assert palace_menu.actions()[0].menu() is None
    assert palace_menu.actions()[1].text() == "Change Speaker…"
    assert palace_menu.actions()[1].menu() is None
    assert palace_menu.actions()[2].menu().actions()[0].text() == "None"
