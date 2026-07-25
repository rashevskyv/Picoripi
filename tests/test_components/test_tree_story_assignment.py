import pytest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtWidgets import QWidget, QTreeWidgetItem, QHeaderView, QMenu

from components.custom_tree_widget import CustomTreeWidget


class _RecordingSelectionHandler:
    """Stub that models loading a leaf's view and selecting a preview line."""

    def __init__(self):
        self._target_block_idx = None
        self._target_string_idx = None
        self.displayed = []
        self.selected = None

    def block_selected(self, item, _previous):
        # Emulate populating the folder's filtered preview from the leaf mappings.
        self.displayed = [
            tuple(row)
            for row in (item.data(0, Qt.UserRole + 13) or [])
            if isinstance(row, (tuple, list)) and len(row) == 2
        ]

    def _get_relative_index(self, row):
        try:
            return self.displayed.index(tuple(row))
        except ValueError:
            return -1

    def string_selected_from_preview(self, rel, is_manual_click=False):
        if 0 <= rel < len(self.displayed):
            self.selected = self.displayed[rel]


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
    window.list_selection_handler = _RecordingSelectionHandler()
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


def _glossary_entry(original, translation):
    entry = MagicMock()
    entry.original = original
    entry.translation = translation
    return entry


def test_open_speaker_in_glossary_maps_translation_to_original(qtbot):
    """A translated speaker folder must open its glossary entry (keyed by original)."""
    window, tree, _block = _assignment_tree(qtbot)
    translator = MagicMock()
    translator._glossary_manager.get_entries.return_value = [
        _glossary_entry("WOMAN 1", "Жінка 1"),
        _glossary_entry("ZELDA", "Зельда"),
    ]
    window.translation_handler = translator

    tree._open_speaker_in_glossary("Жінка 1")
    translator.show_glossary_dialog.assert_called_once_with("WOMAN 1")


def test_open_speaker_in_glossary_uses_name_as_is_when_untranslated(qtbot):
    """An untranslated speaker (no glossary entry) opens the glossary at its own name."""
    window, tree, _block = _assignment_tree(qtbot)
    translator = MagicMock()
    translator._glossary_manager.get_entries.return_value = [
        _glossary_entry("ZELDA", "Зельда"),
    ]
    window.translation_handler = translator

    tree._open_speaker_in_glossary("WOMAN 5")
    translator.show_glossary_dialog.assert_called_once_with("WOMAN 5")


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
        "Notes",
        "",
        "Clear All Context",
    ]
    assert palace_menu.actions()[1].menu() is None
    assert [action.text() for action in palace_menu.actions()[4].menu().actions()] == [
        "Add / Edit Notes...",
        "Remove Notes",
    ]
    assert not palace_menu.actions()[4].menu().actions()[1].isEnabled()


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


def test_context_notes_apply_to_every_selected_row(qtbot):
    _window, tree, block = _assignment_tree(qtbot)

    assert tree._set_notes_for_rows([(0, 1), (0, 2)], "Keep this deliberately terse")
    assert block.metadata["story_context_assignments"] == {
        "1": {"translator_note": "Keep this deliberately terse", "notated": True},
        "2": {"translator_note": "Keep this deliberately terse", "notated": True},
    }

    assert tree._set_notes_for_rows([(0, 1), (0, 2)], "")
    assert "story_context_assignments" not in block.metadata


def test_chapter_assignment_waits_for_virtual_tree_before_restoring_source(qtbot):
    window, tree, block = _assignment_tree(qtbot)
    windows = QTreeWidgetItem(["Windows"])
    dialog = QTreeWidgetItem(windows, ["Dialog"])
    none = QTreeWidgetItem(dialog, ["None"])
    none.setData(0, Qt.UserRole, -3)
    none.setData(0, Qt.UserRole + 15, "None")
    none.setData(0, Qt.UserRole + 17, "unbound")
    none.setData(0, Qt.UserRole + 13, [(0, 1), (0, 2), (0, 3)])
    tree.addTopLevelItem(windows)
    tree.setCurrentItem(none)
    window.data_store.current_string_idx = 1

    updater = MagicMock()
    updater._is_loading_chapters = True
    window.ui_updater.block_list_updater = updater

    def show_loading_tree():
        tree.clear()
        tree.addTopLevelItem(QTreeWidgetItem(["Story (Loading)"]))

    def finish_virtual_load(callback):
        tree.clear()
        rebuilt_windows = QTreeWidgetItem(["Windows"])
        rebuilt_dialog = QTreeWidgetItem(rebuilt_windows, ["Dialog"])
        rebuilt_none = QTreeWidgetItem(rebuilt_dialog, ["None"])
        rebuilt_none.setData(0, Qt.UserRole, -3)
        rebuilt_none.setData(0, Qt.UserRole + 15, "None")
        rebuilt_none.setData(0, Qt.UserRole + 17, "unbound")
        rebuilt_none.setData(0, Qt.UserRole + 13, [(0, 2), (0, 3)])
        tree.addTopLevelItem(rebuilt_windows)
        updater._is_loading_chapters = False
        callback()

    updater.populate_blocks.side_effect = show_loading_tree
    updater.when_virtual_blocks_ready.side_effect = finish_virtual_load
    locator = tree._virtual_item_locator(none)

    with patch(
        "components.tree_drag_drop_mixin.QTimer.singleShot",
        side_effect=lambda _delay, callback: callback(),
    ):
        assert tree._assign_rows_to_story_context(
            [(0, 1)], "story", 20, ("Act One", "Fishing"),
            "Act One > Fishing", locator,
        )

    assert block.metadata["story_context_assignments"]["1"]["structure_id"] == 20
    assert tree.currentItem().text(0) == "None"
    assert tree.currentItem().parent().text(0) == "Dialog"
    assert tree.currentItem().parent().parent().text(0) == "Windows"
    # The continuation row (the string after the moved block) is primed and
    # dispatched so the cursor lands on it inside the restored source leaf.
    assert window.list_selection_handler.selected == (0, 2)


def test_assignment_selects_row_after_moved_block_even_if_cursor_survives(qtbot):
    window, tree, block = _assignment_tree(qtbot)
    source = QTreeWidgetItem(["MIDNA"])
    source.setData(0, Qt.UserRole, -3)
    source.setData(0, Qt.UserRole + 15, "MIDNA")
    source.setData(0, Qt.UserRole + 13, [(0, 1), (0, 2), (0, 3)])
    tree.addTopLevelItem(source)
    tree.setCurrentItem(source)
    window.data_store.current_string_idx = 3

    updater = MagicMock()
    updater._is_loading_chapters = False
    window.ui_updater.block_list_updater = updater

    def rebuild_tree():
        tree.clear()
        rebuilt = QTreeWidgetItem(["MIDNA"])
        rebuilt.setData(0, Qt.UserRole, -3)
        rebuilt.setData(0, Qt.UserRole + 15, "MIDNA")
        rebuilt.setData(0, Qt.UserRole + 13, [(0, 2), (0, 3)])
        tree.addTopLevelItem(rebuilt)

    updater.populate_blocks.side_effect = rebuild_tree

    with patch(
        "components.tree_drag_drop_mixin.QTimer.singleShot",
        side_effect=lambda _delay, callback: callback(),
    ):
        assert tree._assign_rows_to_story_context(
            [(0, 1)], "speaker", "SYSTEM", (), "SYSTEM", None,
        )

    assert block.metadata["story_context_assignments"]["1"] == {"speaker": "SYSTEM"}
    assert tree.currentItem().text(0) == "MIDNA"
    assert window.list_selection_handler.selected == (0, 2)

def test_assignment_selects_non_empty_row_after_moved_block(qtbot):
    window, tree, block = _assignment_tree(qtbot)
    source = QTreeWidgetItem(["MIDNA"])
    source.setData(0, Qt.UserRole, -3)
    source.setData(0, Qt.UserRole + 15, "MIDNA")
    source.setData(0, Qt.UserRole + 13, [(0, 1), (0, 2), (0, 3), (0, 4)])
    tree.addTopLevelItem(source)
    tree.setCurrentItem(source)
    window.data_store.current_string_idx = 1

    # Mock data_processor
    data_processor = MagicMock()
    def get_text(b, s):
        if s == 2:
            return "{tab}", "test" # empty/tags-only
        elif s == 3:
            return "Non-empty text", "test" # non-empty
        elif s == 4:
            return "Another non-empty", "test"
        return "", "test"
    data_processor.get_current_string_text.side_effect = get_text
    window.data_processor = data_processor

    updater = MagicMock()
    updater._is_loading_chapters = False
    window.ui_updater.block_list_updater = updater

    def rebuild_tree():
        tree.clear()
        rebuilt = QTreeWidgetItem(["MIDNA"])
        rebuilt.setData(0, Qt.UserRole, -3)
        rebuilt.setData(0, Qt.UserRole + 15, "MIDNA")
        rebuilt.setData(0, Qt.UserRole + 13, [(0, 2), (0, 3), (0, 4)])
        tree.addTopLevelItem(rebuilt)

    updater.populate_blocks.side_effect = rebuild_tree

    with patch(
        "components.tree_drag_drop_mixin.QTimer.singleShot",
        side_effect=lambda _delay, callback: callback(),
    ):
        assert tree._assign_rows_to_story_context(
            [(0, 1)], "speaker", "SYSTEM", (), "SYSTEM", None,
        )

    # (0, 2) is empty, so it should have skipped it and selected (0, 3)
    assert window.list_selection_handler.selected == (0, 3)


def _run_move_and_capture_selection(qtbot, mappings, moved, empty_rows):
    """Move `moved` out of a source leaf and return the row the cursor lands on.

    `empty_rows` are rendered as tag-only text so the real `remove_all_tags`
    predicate decides emptiness, exactly like the running app.
    """
    window, tree, _block = _assignment_tree(qtbot)
    source = QTreeWidgetItem(["MIDNA"])
    source.setData(0, Qt.UserRole, -3)
    source.setData(0, Qt.UserRole + 15, "MIDNA")
    source.setData(0, Qt.UserRole + 13, list(mappings))
    tree.addTopLevelItem(source)
    tree.setCurrentItem(source)
    window.data_store.current_string_idx = mappings[0][1]

    empty = set(empty_rows)
    data_processor = MagicMock()
    data_processor.get_current_string_text.side_effect = (
        lambda b, s: ("{autobox:9}" if (b, s) in empty else f"line {s}", "test")
    )
    window.data_processor = data_processor

    updater = MagicMock()
    updater._is_loading_chapters = False
    window.ui_updater.block_list_updater = updater

    remaining = [row for row in mappings if row not in set(moved)]

    def rebuild_tree():
        tree.clear()
        rebuilt = QTreeWidgetItem(["MIDNA"])
        rebuilt.setData(0, Qt.UserRole, -3)
        rebuilt.setData(0, Qt.UserRole + 15, "MIDNA")
        rebuilt.setData(0, Qt.UserRole + 13, list(remaining))
        tree.addTopLevelItem(rebuilt)

    updater.populate_blocks.side_effect = rebuild_tree

    with patch(
        "components.tree_drag_drop_mixin.QTimer.singleShot",
        side_effect=lambda _delay, callback: callback(),
    ):
        assert tree._assign_rows_to_story_context(
            list(moved), "speaker", "SYSTEM", (), "SYSTEM", None,
        )
    return window.list_selection_handler.selected


@pytest.mark.parametrize(
    "mappings, moved, empty_rows, expected, note",
    [
        # Immediate next row has text -> land on it.
        ([(0, 1), (0, 2), (0, 3)], [(0, 1)], [], (0, 2), "next row has text"),
        # Next row empty -> skip to the following text row.
        ([(0, 1), (0, 2), (0, 3)], [(0, 1)], [(0, 2)], (0, 3), "skip one empty"),
        # Several empty rows in a row -> skip all of them.
        (
            [(0, 1), (0, 2), (0, 3), (0, 4)], [(0, 1)],
            [(0, 2), (0, 3)], (0, 4), "skip two empties",
        ),
        # Move a multi-row block -> continue past the whole block to next text.
        (
            [(0, 1), (0, 2), (0, 3), (0, 4), (0, 5)], [(0, 2), (0, 3)],
            [(0, 4)], (0, 5), "skip empty after moved block",
        ),
        # Moved the last row -> search upward for the nearest text row.
        ([(0, 1), (0, 2), (0, 3)], [(0, 3)], [], (0, 2), "upward when moved last"),
        # Upward search must also skip empty rows.
        (
            [(0, 1), (0, 2), (0, 3), (0, 4)], [(0, 4)],
            [(0, 3)], (0, 2), "upward skips empty",
        ),
        # No text anywhere among survivors -> fall back to first survivor.
        (
            [(0, 1), (0, 2), (0, 3)], [(0, 1)],
            [(0, 2), (0, 3)], (0, 2), "fallback to first survivor when all empty",
        ),
        # Cross-block continuation is resolved by absolute (block, string).
        (
            [(0, 5), (1, 0), (1, 1)], [(0, 5)],
            [(1, 0)], (1, 1), "continuation crosses physical blocks",
        ),
    ],
)
def test_continuation_lands_on_next_text_row(
    qtbot, mappings, moved, empty_rows, expected, note
):
    selected = _run_move_and_capture_selection(qtbot, mappings, moved, empty_rows)
    assert selected == expected, note

