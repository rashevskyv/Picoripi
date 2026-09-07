from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from core.script_markup import (
    HierarchyMark,
    HierarchyType,
)
from .helpers import (
    _make_dialog,
    _use_hierarchy_mode,
    _find_tree_item,
)

def test_studio_tree_collapsed_parent_selection_includes_hidden_children(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.SPEAKER, text="MIDNA", order=3),
    ]
    dialog._refresh()
    act = dialog.flags_list.topLevelItem(0)

    act.setExpanded(False)
    collapsed_keys = dialog._flatten_key_groups(
        dialog._outline_key_groups(dialog._outline_action_items(act), include_children=False)
    )
    assert len(collapsed_keys) == 3

    act.setExpanded(True)
    expanded_keys = dialog._flatten_key_groups(
        dialog._outline_key_groups(dialog._outline_action_items(act), include_children=False)
    )
    assert len(expanded_keys) == 1

def test_studio_tree_shift_selection_uses_last_clicked_anchor(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nScene 1\nScene 2\nScene 3\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.STRUCTURE, text="Scene 1", order=2),
        HierarchyMark(2, 2, 1, HierarchyType.STRUCTURE, text="Scene 2", order=3),
        HierarchyMark(3, 3, 1, HierarchyType.STRUCTURE, text="Scene 3", order=4),
    ]
    dialog._refresh()
    dialog.flags_list.expandAll()
    act = dialog.flags_list.topLevelItem(0)
    scene_two = act.child(1)
    scene_three = act.child(2)

    dialog.flags_list._selection_anchor_item = scene_two
    assert dialog.flags_list._select_range_to_item(scene_three)

    selected = [item.text(0) for item in dialog.flags_list.selectedItems()]
    assert len(selected) == 2
    assert any("Scene 2" in text for text in selected)
    assert any("Scene 3" in text for text in selected)
    assert all("Act One" not in text for text in selected)

def test_studio_tree_mouse_shift_selection_persists_after_click(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nScene 1\nScene 2\nScene 3\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.STRUCTURE, text="Scene 1", order=2),
        HierarchyMark(2, 2, 1, HierarchyType.STRUCTURE, text="Scene 2", order=3),
        HierarchyMark(3, 3, 1, HierarchyType.STRUCTURE, text="Scene 3", order=4),
    ]
    dialog._refresh()
    dialog.flags_list.expandAll()
    dialog.show()
    qapp.processEvents()
    act = dialog.flags_list.topLevelItem(0)
    scene_two = act.child(1)
    scene_three = act.child(2)

    QTest.mouseClick(
        dialog.flags_list.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        dialog.flags_list.visualItemRect(scene_two).center(),
    )
    qapp.processEvents()
    QTest.mouseClick(
        dialog.flags_list.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        dialog.flags_list.visualItemRect(scene_three).center(),
    )
    qapp.processEvents()

    selected = [item.text(0) for item in dialog.flags_list.selectedItems()]
    assert len(selected) == 2
    assert any("Scene 2" in text for text in selected)
    assert any("Scene 3" in text for text in selected)

def test_studio_tree_selection_survives_outline_refresh(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nScene 1\nScene 2\nScene 3\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.STRUCTURE, text="Scene 1", order=2),
        HierarchyMark(2, 2, 1, HierarchyType.STRUCTURE, text="Scene 2", order=3),
        HierarchyMark(3, 3, 1, HierarchyType.STRUCTURE, text="Scene 3", order=4),
    ]
    dialog._refresh()
    dialog.flags_list.expandAll()
    act = dialog.flags_list.topLevelItem(0)
    scene_two = act.child(1)
    scene_three = act.child(2)
    scene_two.setSelected(True)
    scene_three.setSelected(True)
    dialog.flags_list._selection_anchor_item = scene_two

    dialog._refresh()

    act = dialog.flags_list.topLevelItem(0)
    selected = [item.text(0) for item in dialog.flags_list.selectedItems()]
    assert len(selected) == 2
    assert any("Scene 2" in text for text in selected)
    assert any("Scene 3" in text for text in selected)
    assert dialog.flags_list._selection_anchor_item is act.child(1)

def test_studio_unmarked_tree_selection_survives_outline_refresh(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Opening line\nAnother line\n")
    dialog.hierarchy_marks = []
    dialog._refresh()
    item = dialog.flags_list.topLevelItem(0)
    dialog.flags_list.setCurrentItem(item)
    item.setSelected(True)
    dialog.flags_list._selection_anchor_item = item

    dialog._refresh()

    restored = dialog.flags_list.topLevelItem(0)
    assert restored.isSelected()
    assert dialog.flags_list.currentItem() is restored
    assert dialog.flags_list._selection_anchor_item is restored

def test_studio_tree_click_on_row_whitespace_selects_item(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.resize(900, 560)
    dialog.show()
    dialog.raw_edit.setPlainText("Act One\nScene One\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 1, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
    ]
    dialog._refresh()
    qapp.processEvents()
    item = dialog.flags_list.topLevelItem(0)
    rect = dialog.flags_list.visualItemRect(item)
    click_pos = QPoint(dialog.flags_list.viewport().width() - 4, rect.center().y())

    QTest.mouseClick(
        dialog.flags_list.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        click_pos,
    )
    qapp.processEvents()

    assert item.isSelected()
    assert dialog.flags_list.currentItem() is item

def test_studio_raw_scroll_survives_hierarchy_refresh(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.resize(900, 560)
    dialog.show()
    dialog.raw_edit.setPlainText("\n".join(f"Line {idx}" for idx in range(220)))
    dialog.hierarchy_marks = [
        HierarchyMark(0, 219, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
    ]
    dialog._refresh()
    qapp.processEvents()
    bar = dialog.raw_edit.verticalScrollBar()
    assert bar.maximum() > 0
    target = min(80, bar.maximum())
    bar.setValue(target)
    qapp.processEvents()

    dialog._refresh()
    qapp.processEvents()

    assert bar.value() == target

def test_studio_tree_scroll_survives_outline_refresh(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.resize(900, 560)
    dialog.show()
    lines = [f"Scene {idx}" for idx in range(120)]
    dialog.raw_edit.setPlainText("\n".join(lines))
    dialog.hierarchy_marks = [
        HierarchyMark(idx, idx, 0, HierarchyType.STRUCTURE, text=f"Scene {idx}", order=idx + 1)
        for idx in range(120)
    ]
    dialog._refresh()
    qapp.processEvents()
    bar = dialog.flags_list.verticalScrollBar()
    assert bar.maximum() > 0
    target = min(60, bar.maximum())
    bar.setValue(target)
    qapp.processEvents()

    dialog._refresh()
    qapp.processEvents()

    assert bar.value() == target

def test_studio_tree_double_click_jump_scrolls_to_source_line(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.resize(900, 560)
    dialog.show()
    dialog.raw_edit.setPlainText("\n".join(f"Line {idx}" for idx in range(180)))
    dialog.hierarchy_marks = [
        HierarchyMark(0, 179, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(120, 120, 1, HierarchyType.STRUCTURE, text="Scene 120", order=2),
    ]
    dialog._refresh()
    dialog.flags_list.expandAll()
    qapp.processEvents()
    scene = _find_tree_item(dialog.flags_list, "Scene 120")
    rect = dialog.flags_list.visualItemRect(scene)
    click_pos = QPoint(dialog.flags_list.viewport().width() - 4, rect.center().y())

    assert dialog.flags_list._item_at_row(click_pos) is scene
    QTest.mouseDClick(
        dialog.flags_list.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        click_pos,
    )
    qapp.processEvents()

    assert dialog.raw_edit.textCursor().blockNumber() == 120
    assert dialog.raw_edit.verticalScrollBar().value() > 0
    assert dialog._raw_navigation_line == 120

def test_studio_raw_text_can_jump_to_exact_text_node_in_tree(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act\nMIDNA\nFirst line\nSecond line\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.SPEAKER, text="MIDNA", order=2),
        HierarchyMark(2, 3, 2, HierarchyType.TEXT, order=3),
    ]
    dialog._refresh()

    assert dialog._jump_raw_line_to_outline(3)

    current = dialog.flags_list.currentItem()
    assert current is not None
    assert "Text:" in current.text(0)
    assert current.isSelected()

def test_studio_tree_disclosure_click_never_schedules_rename(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act\nScene\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 1, 0, HierarchyType.STRUCTURE, text="Act", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.STRUCTURE, text="Scene", order=2),
    ]
    dialog._refresh()
    dialog.show()
    qapp.processEvents()
    item = dialog.flags_list.topLevelItem(0)
    dialog.flags_list.setCurrentItem(item)
    item.setSelected(True)
    calls = []
    monkeypatch.setattr(dialog, "_rename_outline_item", lambda selected: calls.append(selected))
    rect = dialog.flags_list.visualItemRect(item)
    disclosure_pos = QPoint(max(1, rect.left() - 8), rect.center().y())

    assert dialog.flags_list._position_is_disclosure(item, disclosure_pos)
    QTest.mouseClick(
        dialog.flags_list.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        disclosure_pos,
    )
    QTest.qWait(500)
    qapp.processEvents()

    assert calls == []

def test_studio_tree_f2_renames_selected_node(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nScene One\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 1, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
    ]
    dialog._refresh()
    item = dialog.flags_list.topLevelItem(0)
    dialog.flags_list.setCurrentItem(item)
    item.setSelected(True)
    dialog.flags_list.setFocus()
    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QInputDialog.getText",
        lambda *args, **kwargs: ("Opening Structure", True),
    )

    QTest.keyClick(dialog.flags_list, Qt.Key.Key_F2)
    qapp.processEvents()

    assert dialog.hierarchy_marks[0].text == "Opening Structure"
    assert "Opening Structure" in dialog.flags_list.topLevelItem(0).text(0)

def test_studio_tree_selected_click_renames_node(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nScene One\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 1, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
    ]
    dialog._refresh()
    dialog.show()
    qapp.processEvents()
    dialog.flags_list._pending_rename_timer.setInterval(1)
    item = dialog.flags_list.topLevelItem(0)
    dialog.flags_list.setCurrentItem(item)
    item.setSelected(True)
    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QInputDialog.getText",
        lambda *args, **kwargs: ("Clicked Structure", True),
    )

    QTest.mouseClick(
        dialog.flags_list.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        dialog.flags_list.visualItemRect(item).center(),
    )
    QTest.qWait(5)
    qapp.processEvents()

    assert dialog.hierarchy_marks[0].text == "Clicked Structure"
    assert "Clicked Structure" in dialog.flags_list.topLevelItem(0).text(0)
