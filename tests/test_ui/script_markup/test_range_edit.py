from PyQt6.QtCore import QPoint, Qt
from core.script_markup import (
    HierarchyMark,
    HierarchyType,
    mark_text,
)
from .helpers import (
    _flush_search,
    _make_dialog,
    _use_hierarchy_mode,
    _set_hierarchy_type,
)

def test_studio_can_edit_hierarchy_node_range_from_tree(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\nNext line.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 4, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 2, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
    ]
    dialog._refresh()
    chapter_item = dialog.flags_list.topLevelItem(0).child(0)
    mark_key = chapter_item.data(0, Qt.ItemDataRole.UserRole + 2)

    assert dialog._start_range_edit(mark_key)
    assert dialog._range_edit_start_line == 1
    assert dialog._range_edit_end_line == 2
    assert dialog.hierarchy_mark_btn.text() == "Save edit"
    assert dialog.hierarchy_clear_btn.text() == "Stop edit"
    assert "#107c41" in dialog.hierarchy_mark_btn.styleSheet()
    assert "#fde7e9" in dialog.hierarchy_clear_btn.styleSheet()

    assert dialog._update_range_edit_preview("end", 4)
    chapter = next(mark for mark in dialog.hierarchy_marks if mark.text == "Chapter One")
    assert chapter.end_line == 2

    dialog._mark_selection_as_hierarchy()

    chapter = next(mark for mark in dialog.hierarchy_marks if mark.text == "Chapter One")
    assert chapter.start_line == 1
    assert chapter.end_line == 4
    assert dialog._range_edit_mark_key is None
    assert dialog.hierarchy_mark_btn.text() == "Mark selection"
    assert dialog.hierarchy_clear_btn.text() == "Clear"
    assert dialog.hierarchy_mark_btn.styleSheet() == ""
    assert dialog.hierarchy_clear_btn.styleSheet() == ""

def test_studio_node_editor_can_drag_inline_character_boundaries(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(": MIDNA\n")
    speaker = HierarchyMark(
        0,
        0,
        1,
        HierarchyType.SPEAKER,
        text="IDNA",
        order=1,
        start_col=3,
        end_col=7,
    )
    dialog.hierarchy_marks = [speaker]
    dialog._refresh()
    dialog.show()
    qapp.processEvents()

    assert dialog._start_range_edit(dialog._hierarchy_mark_key(speaker))
    assert dialog._range_edit_columns() == (3, 7)
    left_geometry = dialog._range_column_handle_geometry(0, 3)
    right_geometry = dialog._range_column_handle_geometry(0, 7)
    assert left_geometry is not None
    assert right_geometry is not None
    left_pos = QPoint(left_geometry[0], (left_geometry[1] + left_geometry[2]) // 2)
    right_pos = QPoint(right_geometry[0], (right_geometry[1] + right_geometry[2]) // 2)
    assert dialog._range_edit_handle_at_pos(left_pos) == "left"
    assert dialog._range_edit_handle_at_pos(right_pos) == "right"

    class MouseEvent:
        def __init__(self, pos):
            self._pos = pos

        def pos(self):
            return self._pos

        def button(self):
            return Qt.MouseButton.LeftButton

        def accept(self):
            pass

    assert dialog._range_edit_mouse_press(MouseEvent(left_pos))
    assert dialog.raw_edit.viewport().cursor().shape() == Qt.CursorShape.SizeHorCursor
    assert dialog._range_edit_mouse_release(MouseEvent(left_pos))

    assert dialog._update_range_edit_preview("left", 0, 2)
    assert dialog._update_range_edit_preview("right", 0, 7)
    dialog._mark_selection_as_hierarchy()

    assert (speaker.start_col, speaker.end_col) == (2, 7)
    assert mark_text(speaker, dialog.raw_edit.toPlainText().splitlines()) == "MIDNA"

def test_studio_shrinking_structure_clamps_and_removes_descendants(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Act\nChapter\nScene 1\nILIA\nHello\nBreaker\nScene 2\nMALO\nBye\nEnd\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 9, 0, HierarchyType.STRUCTURE, text="Act", order=1),
        HierarchyMark(1, 8, 1, HierarchyType.STRUCTURE, text="Chapter", order=2),
        HierarchyMark(2, 5, 2, HierarchyType.STRUCTURE, text="Scene 1", order=3),
        HierarchyMark(3, 5, 3, HierarchyType.SPEAKER, text="ILIA", order=4),
        HierarchyMark(4, 4, 4, HierarchyType.TEXT, order=5),
        HierarchyMark(5, 5, 3, HierarchyType.BREAKER, order=6),
        HierarchyMark(6, 8, 2, HierarchyType.STRUCTURE, text="Scene 2", order=7),
        HierarchyMark(7, 8, 3, HierarchyType.SPEAKER, text="MALO", order=8),
        HierarchyMark(8, 8, 4, HierarchyType.TEXT, order=9),
    ]
    dialog._hierarchy_mark_order = 9
    dialog._refresh()
    act = next(mark for mark in dialog.hierarchy_marks if mark.text == "Act")

    assert dialog._start_range_edit(dialog._hierarchy_mark_key(act))
    assert dialog._update_range_edit_preview("start", 2)
    assert dialog._update_range_edit_preview("end", 5)
    dialog._mark_selection_as_hierarchy()

    act = next(mark for mark in dialog.hierarchy_marks if mark.text == "Act")
    chapter = next(mark for mark in dialog.hierarchy_marks if mark.text == "Chapter")
    assert (act.start_line, act.end_line) == (2, 5)
    assert (chapter.start_line, chapter.end_line) == (2, 5)
    assert all(
        act.start_line <= mark.start_line <= mark.end_line <= act.end_line
        for mark in dialog.hierarchy_marks
        if mark.depth > act.depth
    )
    assert not any(mark.text in {"Scene 2", "MALO"} for mark in dialog.hierarchy_marks)

def test_studio_editor_saves_type_label_and_depth(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 2, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
    ]
    dialog._refresh()
    mark_key = dialog.flags_list.topLevelItem(0).child(0).data(0, Qt.ItemDataRole.UserRole + 2)

    assert dialog._start_range_edit(mark_key)
    dialog.hierarchy_depth_spin.setValue(2)
    _set_hierarchy_type(dialog, HierarchyType.ACTION)
    dialog.hierarchy_label_edit.setText("Door opens")
    dialog._update_range_edit_preview("start", 2)
    dialog._mark_selection_as_hierarchy()

    edited = next(mark for mark in dialog.hierarchy_marks if mark.text == "Door opens")
    assert edited.depth == 2
    assert edited.type_id == HierarchyType.ACTION
    assert edited.start_line == 2
    assert edited.end_line == 2
    assert "[*MIDNA*]" in dialog._psm_text
    assert "[*Door opens*]" not in dialog._psm_text

def test_studio_bulk_editor_fills_common_label_and_saves_changed_label_only(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("[Door opens]\n[Door closes]\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 3, HierarchyType.ACTION, text="Scene 4", order=1),
        HierarchyMark(1, 1, 3, HierarchyType.ACTION, text="Scene 4", order=2),
    ]
    dialog._refresh()
    keys = [dialog._hierarchy_mark_key(mark) for mark in dialog.hierarchy_marks]

    assert dialog._start_bulk_hierarchy_edit(keys)
    assert dialog.hierarchy_depth_spin.value() == 3
    assert dialog.hierarchy_type_combo.currentData() == HierarchyType.ACTION
    assert dialog.hierarchy_label_edit.text() == "Scene 4"

    dialog.hierarchy_label_edit.setText("Scene 5")
    dialog._mark_selection_as_hierarchy()

    assert [mark.text for mark in dialog.hierarchy_marks] == ["Scene 5", "Scene 5"]
    assert {mark.depth for mark in dialog.hierarchy_marks} == {3}
    assert {mark.type_id for mark in dialog.hierarchy_marks} == {HierarchyType.ACTION}
    assert "[*Door opens*]" in dialog._psm_text
    assert "Scene 5" not in dialog._psm_text

def test_studio_bulk_editor_leaves_mixed_label_unchanged_when_saved_blank(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("[Door opens]\n[Door closes]\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 2, HierarchyType.ACTION, text="First label", order=1),
        HierarchyMark(1, 1, 4, HierarchyType.SPEAKER, text="Second label", order=2),
    ]
    dialog._refresh()
    keys = [dialog._hierarchy_mark_key(mark) for mark in dialog.hierarchy_marks]

    assert dialog._start_bulk_hierarchy_edit(keys)
    assert dialog.hierarchy_label_edit.text() == ""
    assert dialog.hierarchy_type_combo.currentData() is None

    dialog._mark_selection_as_hierarchy()

    assert [mark.text for mark in dialog.hierarchy_marks] == ["First label", "Second label"]
    assert [mark.depth for mark in dialog.hierarchy_marks] == [2, 4]
    assert [mark.type_id for mark in dialog.hierarchy_marks] == [
        HierarchyType.ACTION,
        HierarchyType.SPEAKER,
    ]

def test_studio_bulk_editor_applies_only_changed_type_and_depth(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("[Door opens]\n[Door closes]\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 2, HierarchyType.ACTION, text="First label", order=1),
        HierarchyMark(1, 1, 4, HierarchyType.SPEAKER, text="Second label", order=2),
    ]
    dialog._refresh()
    keys = [dialog._hierarchy_mark_key(mark) for mark in dialog.hierarchy_marks]

    assert dialog._start_bulk_hierarchy_edit(keys)
    _set_hierarchy_type(dialog, HierarchyType.ACTION)
    dialog.hierarchy_depth_spin.setValue(5)
    dialog._mark_selection_as_hierarchy()

    assert [mark.text for mark in dialog.hierarchy_marks] == ["First label", "Second label"]
    assert {mark.depth for mark in dialog.hierarchy_marks} == {5}
    assert {mark.type_id for mark in dialog.hierarchy_marks} == {HierarchyType.ACTION}

def test_studio_editor_stop_discards_pending_changes(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 2, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
    ]
    dialog._refresh()
    mark_key = dialog.flags_list.topLevelItem(0).child(0).data(0, Qt.ItemDataRole.UserRole + 2)

    assert dialog._start_range_edit(mark_key)
    dialog.hierarchy_label_edit.setText("Changed")
    dialog._update_range_edit_preview("end", 3)
    dialog._clear_selected_hierarchy_marks()

    original = next(mark for mark in dialog.hierarchy_marks if mark.text == "Chapter One")
    assert original.end_line == 2
    assert dialog._range_edit_mark_key is None

def test_studio_range_edit_handles_share_raw_highlight_layer_with_search(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 2, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
    ]
    dialog._refresh()
    mark_key = dialog.flags_list.topLevelItem(0).child(0).data(0, Qt.ItemDataRole.UserRole + 2)

    dialog.search_edit.setText("MIDNA")
    _flush_search(dialog)
    assert dialog._start_range_edit(mark_key)

    selections = dialog.raw_edit.extraSelections()
    assert selections[0].cursor.selectedText() == "MIDNA"
    assert len(selections) >= 3
