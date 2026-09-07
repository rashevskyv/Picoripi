from unittest.mock import patch
from PyQt6.QtWidgets import (QAbstractItemView)
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from core.script_markup import (
    HierarchyMark,
    HierarchyType,
)
from .helpers import (
    _make_dialog,
    _use_hierarchy_mode,
    _set_hierarchy_type,
    _select_lines,
    _tree_item_count,
    _find_tree_item,
)

def test_studio_hierarchy_tree_preserves_expansion_state(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.SPEAKER, text="MIDNA", order=3),
    ]
    dialog._refresh()
    act_item = dialog.flags_list.topLevelItem(0)
    chapter_item = act_item.child(0)
    act_item.setExpanded(False)
    chapter_item.setExpanded(True)

    dialog._refresh()

    act_item = dialog.flags_list.topLevelItem(0)
    chapter_item = act_item.child(0)
    assert not act_item.isExpanded()
    assert chapter_item.isExpanded()

def test_studio_collapsed_parent_stays_collapsed_when_child_is_selected(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nScene One\nMIDNA\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
        HierarchyMark(2, 3, 2, HierarchyType.STRUCTURE, text="Scene One", order=3),
    ]
    dialog._refresh()
    act_item = dialog.flags_list.topLevelItem(0)
    scene_item = act_item.child(0).child(0)
    scene_item.setSelected(True)
    dialog.flags_list.setCurrentItem(scene_item)
    act_item.setExpanded(False)

    dialog._refresh()

    act_item = dialog.flags_list.topLevelItem(0)
    assert not act_item.isExpanded()

def test_studio_manual_tree_collapse_overrides_pending_reveal(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nScene One\nMIDNA\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
        HierarchyMark(2, 3, 2, HierarchyType.STRUCTURE, text="Scene One", order=3),
    ]
    dialog._refresh()
    act_item = dialog.flags_list.topLevelItem(0)
    scene_key = dialog._hierarchy_mark_key(dialog.hierarchy_marks[2])
    dialog._queue_outline_reveal(scene_key)

    act_item.setExpanded(False)
    qapp.processEvents()
    dialog._refresh()

    act_item = dialog.flags_list.topLevelItem(0)
    assert not act_item.isExpanded()
    assert not dialog._outline_reveal_keys

def test_studio_can_expand_collapse_tree_and_use_mark_shortcuts(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nIgnore me\n")
    _set_hierarchy_type(dialog, HierarchyType.STRUCTURE)
    dialog.hierarchy_depth_spin.setValue(0)
    _select_lines(dialog, 0, 0)

    dialog._activate_mark_shortcut()

    dialog.hierarchy_depth_spin.setValue(1)
    _select_lines(dialog, 1, 1)
    dialog._activate_mark_shortcut()

    assert len(dialog.hierarchy_marks) == 2
    act_item = dialog.flags_list.topLevelItem(0)
    act_item.setExpanded(False)
    dialog._expand_outline_all()
    assert act_item.isExpanded()
    dialog._collapse_outline_all()
    assert not act_item.isExpanded()

    _select_lines(dialog, 2, 2)
    dialog._activate_ignore_shortcut()

    ignored = [mark for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.IGNORE]
    assert len(ignored) == 1
    assert ignored[0].start_line == 2

def test_studio_tree_search_filters_branches_and_survives_tree_refresh(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nMIDNA\nHello.\nAct Two\nZANT\nBegone.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 2, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 2, 1, HierarchyType.SPEAKER, text="MIDNA", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.TEXT, order=3),
        HierarchyMark(3, 5, 0, HierarchyType.STRUCTURE, text="Act Two", order=4),
        HierarchyMark(4, 5, 1, HierarchyType.SPEAKER, text="ZANT", order=5),
        HierarchyMark(5, 5, 2, HierarchyType.TEXT, order=6),
    ]
    dialog._refresh()
    act_one = dialog.flags_list.topLevelItem(0)
    act_two = dialog.flags_list.topLevelItem(1)
    act_one.setExpanded(False)

    dialog.outline_search_edit.setText("midna")

    assert not act_one.isHidden()
    assert not act_one.child(0).isHidden()
    assert act_one.isExpanded()
    assert act_two.isHidden()

    dialog._refresh()
    assert dialog.flags_list.topLevelItem(1).isHidden()

    dialog.outline_search_edit.clear()
    assert not dialog.flags_list.topLevelItem(0).isHidden()
    assert not dialog.flags_list.topLevelItem(1).isHidden()
    assert not dialog.flags_list.topLevelItem(0).isExpanded()

    dialog.outline_search_edit.setText("second")
    dialog._fill_flags([(1, "First issue"), (2, "Second issue")])
    assert dialog.flags_list.topLevelItem(0).isHidden()
    assert not dialog.flags_list.topLevelItem(1).isHidden()

def test_studio_can_delete_hierarchy_node_from_tree(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.SPEAKER, text="MIDNA", order=3),
    ]
    dialog._refresh()
    chapter_item = dialog.flags_list.topLevelItem(0).child(0)

    removed = dialog._delete_outline_item_marks(chapter_item)

    assert removed == 1
    assert len(dialog.hierarchy_marks) == 2
    assert all(mark.text != "Chapter One" for mark in dialog.hierarchy_marks)
    assert "## Chapter One" not in dialog._psm_text
    assert "> [RAW] Chapter One" in dialog._psm_text

def test_studio_can_delete_hierarchy_branch_from_tree(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.SPEAKER, text="MIDNA", order=3),
    ]
    dialog._refresh()
    act_item = dialog.flags_list.topLevelItem(0)

    removed = dialog._delete_outline_item_marks(act_item, include_children=True)

    assert removed == 3
    assert dialog.hierarchy_marks == []

def test_studio_can_change_hierarchy_depth_from_tree_branch(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.SPEAKER, text="MIDNA", order=3),
    ]
    dialog._refresh()
    chapter_item = dialog.flags_list.topLevelItem(0).child(0)
    branch_keys = dialog._outline_mark_keys(chapter_item, include_children=True)

    changed = dialog._change_outline_depth_keys(branch_keys, 1)

    depths = {mark.text: mark.depth for mark in dialog.hierarchy_marks}
    assert changed == 2
    assert depths["Chapter One"] == 2
    assert depths["MIDNA"] == 3

    chapter_item = dialog.flags_list.topLevelItem(0).child(0)
    branch_keys = dialog._outline_mark_keys(chapter_item, include_children=True)
    changed = dialog._set_outline_branch_depth(branch_keys, 1)

    depths = {mark.text: mark.depth for mark in dialog.hierarchy_marks}
    assert changed == 2
    assert depths["Chapter One"] == 1
    assert depths["MIDNA"] == 2

def test_studio_tree_depth_shortcuts_move_selected_branch_and_support_undo(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.SPEAKER, text="MIDNA", order=3),
    ]
    dialog._refresh()
    dialog._record_history(force=True)
    chapter_item = dialog.flags_list.topLevelItem(0).child(0)
    chapter_item.setExpanded(True)
    dialog.flags_list.setCurrentItem(chapter_item)
    chapter_item.setSelected(True)
    dialog.flags_list.setFocus()
    modifiers = (
        Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.ShiftModifier
    )

    QTest.keyClick(dialog.flags_list, Qt.Key.Key_Down, modifiers)
    qapp.processEvents()

    depths = {mark.text: mark.depth for mark in dialog.hierarchy_marks}
    assert depths["Chapter One"] == 2
    assert depths["MIDNA"] == 3
    assert len(dialog.flags_list.selectedItems()) == 1

    QTest.keyClick(dialog.flags_list, Qt.Key.Key_Up, modifiers)
    qapp.processEvents()

    depths = {mark.text: mark.depth for mark in dialog.hierarchy_marks}
    assert depths["Chapter One"] == 1
    assert depths["MIDNA"] == 2
    assert dialog._undo_history()
    depths = {mark.text: mark.depth for mark in dialog.hierarchy_marks}
    assert depths["Chapter One"] == 2
    assert depths["MIDNA"] == 3

def test_studio_dragging_tree_node_onto_target_changes_depth(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 0, HierarchyType.STRUCTURE, text="Chapter One", order=2),
    ]
    dialog._refresh()
    target_item = dialog.flags_list.topLevelItem(0)
    source_item = dialog.flags_list.topLevelItem(1)

    moved = dialog._handle_outline_drop(
        [source_item],
        target_item,
        QAbstractItemView.DropIndicatorPosition.OnItem,
    )

    assert moved
    depths = {mark.text: mark.depth for mark in dialog.hierarchy_marks}
    assert depths["Act One"] == 0
    assert depths["Chapter One"] == 1
    assert "Chapter One" in dialog.flags_list.topLevelItem(0).child(0).text(0)

def test_studio_tree_key_lookup_builds_one_linear_cache(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.hierarchy_marks = [
        HierarchyMark(
            line,
            line,
            0,
            HierarchyType.STRUCTURE,
            text=f"Node {line}",
            order=line,
        )
        for line in range(100)
    ]
    keys = [dialog._hierarchy_mark_key(mark) for mark in dialog.hierarchy_marks]
    original_key = dialog._hierarchy_mark_key
    dialog._invalidate_hierarchy_mark_caches()

    with patch.object(dialog, "_hierarchy_mark_key", wraps=original_key) as key_builder:
        assert all(dialog._hierarchy_mark_for_key(key) is not None for key in keys)

    assert key_builder.call_count == len(dialog.hierarchy_marks)

def test_studio_tree_drag_preview_is_compact_and_translucent(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 0, HierarchyType.STRUCTURE, text="Chapter One", order=2),
    ]
    dialog._refresh()
    dialog.show()
    qapp.processEvents()
    first = dialog.flags_list.topLevelItem(0)
    second = dialog.flags_list.topLevelItem(1)
    first.setSelected(True)
    second.setSelected(True)

    preview = dialog.flags_list._drag_preview_pixmap()

    assert not preview.isNull()
    assert preview.width() <= 420
    image = preview.toImage()
    alphas = [
        image.pixelColor(x, y).alpha()
        for y in range(image.height())
        for x in range(image.width())
    ]
    assert any(alpha > 0 for alpha in alphas)
    assert max(alphas) <= 128

def test_studio_dragging_same_depth_action_onto_speaker_nests_action(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("ILIA\nHello.\nLink waves.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 2, 4, HierarchyType.SPEAKER, text="ILIA", order=1),
        HierarchyMark(2, 2, 4, HierarchyType.ACTION, text="Link waves", order=2),
    ]
    dialog._refresh()
    speaker_item = _find_tree_item(dialog.flags_list, "ILIA")
    action_item = _find_tree_item(dialog.flags_list, "Link waves")

    moved = dialog._handle_outline_drop(
        [action_item],
        speaker_item,
        QAbstractItemView.DropIndicatorPosition.AboveItem,
    )

    assert moved
    depths = {mark.text: mark.depth for mark in dialog.hierarchy_marks}
    assert depths["ILIA"] == 4
    assert depths["Link waves"] == 5
    assert "Link waves" in _find_tree_item(dialog.flags_list, "ILIA").child(0).text(0)

def test_studio_tree_multi_selection_delete_collects_selected_nodes(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nChapter Two\nChapter Three\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
        HierarchyMark(2, 2, 1, HierarchyType.STRUCTURE, text="Chapter Two", order=3),
        HierarchyMark(3, 3, 1, HierarchyType.STRUCTURE, text="Chapter Three", order=4),
    ]
    dialog._refresh()
    chapter_one = dialog.flags_list.topLevelItem(0).child(0)
    chapter_two = dialog.flags_list.topLevelItem(0).child(1)
    chapter_one.setSelected(True)
    chapter_two.setSelected(True)

    action_items = dialog._outline_action_items(chapter_one)
    mark_keys = dialog._flatten_key_groups(
        dialog._outline_key_groups(action_items, include_children=False)
    )

    assert len(mark_keys) == 2
    assert dialog._delete_outline_mark_keys(mark_keys) == 2
    remaining = {mark.text for mark in dialog.hierarchy_marks}
    assert remaining == {"Act One", "Chapter Three"}

def test_studio_join_selected_structures_merges_duplicate_containers(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Act 1\n"
        "Chapter 1\n"
        "Act 1\n"
        "Chapter 2\n"
        "Act 2\n"
        "Chapter 3\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 1, 0, HierarchyType.STRUCTURE, text="Act 1", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.STRUCTURE, text="Chapter 1", order=2),
        HierarchyMark(2, 3, 0, HierarchyType.STRUCTURE, text="Act 1", order=3),
        HierarchyMark(3, 3, 1, HierarchyType.STRUCTURE, text="Chapter 2", order=4),
        HierarchyMark(4, 5, 0, HierarchyType.STRUCTURE, text="Act 2", order=5),
        HierarchyMark(5, 5, 1, HierarchyType.STRUCTURE, text="Chapter 3", order=6),
    ]
    dialog._hierarchy_mark_order = 7
    dialog._refresh()

    first_act = dialog.flags_list.topLevelItem(0)
    second_act = dialog.flags_list.topLevelItem(1)
    keys = dialog._outline_direct_mark_keys([first_act, second_act])

    joined = dialog._join_structure_mark_keys(keys)

    assert joined == 2
    act_ones = [
        mark for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.STRUCTURE and mark.text == "Act 1"
    ]
    assert len(act_ones) == 1
    assert (act_ones[0].start_line, act_ones[0].end_line, act_ones[0].depth) == (0, 3, 0)
    ignored = [mark for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.IGNORE]
    assert [(mark.start_line, mark.end_line) for mark in ignored] == [(2, 2)]
    assert dialog.flags_list.topLevelItemCount() == 3
    merged_act = dialog.flags_list.topLevelItem(0)
    assert "Act 1" in merged_act.text(0)
    assert merged_act.childCount() == 2
    assert "Chapter 1" in merged_act.child(0).text(0)
    assert "Chapter 2" in merged_act.child(1).text(0)
    assert "Act 2" in dialog.flags_list.topLevelItem(2).text(0)
    assert dialog._psm_text.count("# Act 1") == 1
    assert "> [RAW] Act 1" not in dialog._psm_text

def test_studio_join_selected_structures_refuses_to_cross_peer_structure(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act 1\nAct 2\nAct 1\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE, text="Act 1", order=1),
        HierarchyMark(1, 1, 0, HierarchyType.STRUCTURE, text="Act 2", order=2),
        HierarchyMark(2, 2, 0, HierarchyType.STRUCTURE, text="Act 1", order=3),
    ]
    dialog._refresh()

    first_act = dialog.flags_list.topLevelItem(0)
    third_act = dialog.flags_list.topLevelItem(2)
    keys = dialog._outline_direct_mark_keys([first_act, third_act])

    assert dialog._join_structure_mark_keys(keys) == 0
    assert len(dialog.hierarchy_marks) == 3

def test_studio_tree_multi_selection_drag_moves_all_selected_branches(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("ILIA\nLink waves.\nEpona snorts.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 2, 4, HierarchyType.SPEAKER, text="ILIA", order=1),
        HierarchyMark(1, 1, 4, HierarchyType.ACTION, text="Link waves", order=2),
        HierarchyMark(2, 2, 4, HierarchyType.ACTION, text="Epona snorts", order=3),
    ]
    dialog._refresh()
    speaker_item = _find_tree_item(dialog.flags_list, "ILIA")
    action_one = _find_tree_item(dialog.flags_list, "Link waves")
    action_two = _find_tree_item(dialog.flags_list, "Epona snorts")
    action_one.setSelected(True)
    action_two.setSelected(True)

    moved = dialog._handle_outline_drop(
        dialog.flags_list.selectedItems(),
        speaker_item,
        QAbstractItemView.DropIndicatorPosition.OnItem,
    )

    assert moved
    depths = {mark.text: mark.depth for mark in dialog.hierarchy_marks}
    assert depths["ILIA"] == 4
    assert depths["Link waves"] == 5
    assert depths["Epona snorts"] == 5
    speaker = _find_tree_item(dialog.flags_list, "ILIA")
    assert speaker.childCount() == 2
    assert "Link waves" in speaker.child(0).text(0)
    assert "Epona snorts" in speaker.child(1).text(0)

def test_studio_tree_multi_selection_applies_current_type_and_depth(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("A\nB\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 2, HierarchyType.ACTION, text="A", order=1),
        HierarchyMark(1, 1, 2, HierarchyType.ACTION, text="B", order=2),
    ]
    dialog._refresh()
    first = dialog.flags_list.topLevelItem(0)
    second = dialog.flags_list.topLevelItem(1)
    first.setSelected(True)
    second.setSelected(True)
    _set_hierarchy_type(dialog, HierarchyType.SPEAKER)
    dialog.hierarchy_depth_spin.setValue(3)
    keys = dialog._flatten_key_groups(
        dialog._outline_key_groups(dialog._outline_action_items(first), include_children=False)
    )

    assert dialog._apply_outline_type_depth_keys(keys) == 2
    assert {
        (mark.text, mark.type_id, mark.depth)
        for mark in dialog.hierarchy_marks
    } == {
        ("A", HierarchyType.SPEAKER, 3),
        ("B", HierarchyType.SPEAKER, 3),
    }

def test_studio_hierarchy_tooltip_shows_type_depth_and_path(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nScene One\nILIA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Scene One", order=2),
        HierarchyMark(2, 3, 4, HierarchyType.SPEAKER, text="ILIA", order=3),
        HierarchyMark(3, 3, 5, HierarchyType.TEXT, order=4),
    ]
    dialog._refresh()

    tooltip = dialog._hierarchy_tooltip_for_line(3)

    assert "Type: Text" in tooltip
    assert "Depth: 5" in tooltip
    assert "Range: lines 4-4" in tooltip
    assert "[0] Structure: Act One" in tooltip
    assert "[1] Structure: Scene One" in tooltip
    assert "[4] Speaker: ILIA" in tooltip

def test_studio_hierarchy_tooltip_uses_real_tree_parents_not_overlapping_siblings(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Appendix C\nOld block\nold text\nspacer\nspacer\n"
        "16. Hyrule Castle\nMIDNA\nHurry up and get that Sol back!\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 7, 0, HierarchyType.STRUCTURE, text="Appendix C", order=1),
        # This stale sibling still covers the later source lines, but it is not
        # the parent of Hyrule Castle in the actual depth-indexed tree.
        HierarchyMark(1, 7, 2, HierarchyType.STRUCTURE, text="8. Malo Mart", order=2),
        HierarchyMark(5, 7, 2, HierarchyType.STRUCTURE, text="16. Hyrule Castle", order=3),
        HierarchyMark(6, 7, 3, HierarchyType.SPEAKER, text="MIDNA", order=4),
        HierarchyMark(7, 7, 4, HierarchyType.TEXT, order=5),
    ]
    dialog._refresh()

    tooltip = dialog._hierarchy_tooltip_for_line(7)

    assert "[0] Structure: Appendix C" in tooltip
    assert "[2] Structure: 16. Hyrule Castle" in tooltip
    assert "[3] Speaker: MIDNA" in tooltip
    assert "[4] Text: Hurry up and get that Sol back!" in tooltip
    assert "8. Malo Mart" not in tooltip

def test_studio_tree_delete_survives_stale_qt_item(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 1, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
    ]
    dialog._refresh()
    stale_item = dialog.flags_list.topLevelItem(0).child(0)
    mark_key = stale_item.data(0, Qt.ItemDataRole.UserRole + 2)

    dialog.flags_list.clear()

    assert dialog._delete_outline_item_marks(stale_item) == 0
    assert dialog._delete_outline_mark_keys([mark_key]) == 1
    assert len(dialog.hierarchy_marks) == 1

def test_studio_hierarchy_tree_shows_ignored_and_unmarked_lines(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Legal notice\n"
        "Act I\n"
        "Needs work\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.IGNORE),
        HierarchyMark(1, 1, 0, HierarchyType.STRUCTURE),
    ]

    dialog._refresh()

    assert dialog.highlighter.line_kinds[0] == HierarchyType.IGNORE
    assert dialog.highlighter.line_kinds[2] == HierarchyType.UNMARKED
    assert "Legal notice" not in dialog._psm_text
    assert _tree_item_count(dialog.flags_list) == 4
    assert "Ignored" in dialog.flags_list.topLevelItem(0).text(0)
    assert any(
        "Unmarked" in dialog.flags_list.topLevelItem(i).text(0)
        for i in range(dialog.flags_list.topLevelItemCount())
    )

def test_studio_tree_multi_selection_can_be_marked_unmarked(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("MIDNA\nFirst line.\nSecond line.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 2, 0, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.TEXT, order=2),
        HierarchyMark(2, 2, 1, HierarchyType.TEXT, order=3),
    ]
    dialog._refresh()
    first = _find_tree_item(dialog.flags_list, "First line")
    second = _find_tree_item(dialog.flags_list, "Second line")
    first.setSelected(True)
    second.setSelected(True)

    assert dialog._mark_outline_items_unmarked([first, second]) == 2
    assert [(mark.type_id, mark.start_line) for mark in dialog.hierarchy_marks] == [
        (HierarchyType.SPEAKER, 0)
    ]
    assert dialog._unmarked_ranges(dialog.raw_edit.toPlainText().splitlines()) == [(1, 2)]

def test_studio_tree_multi_selection_can_be_marked_ignored(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Keep\nRemove A\nRemove B\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.TEXT, order=1),
        HierarchyMark(1, 1, 0, HierarchyType.TEXT, order=2),
        HierarchyMark(2, 2, 0, HierarchyType.TEXT, order=3),
    ]
    dialog._hierarchy_mark_order = 4
    dialog._refresh()
    first = _find_tree_item(dialog.flags_list, "Remove A")
    second = _find_tree_item(dialog.flags_list, "Remove B")
    first.setSelected(True)
    second.setSelected(True)

    assert dialog._mark_outline_items_ignored([first, second]) == 2
    assert [
        (mark.type_id, mark.start_line, mark.end_line)
        for mark in sorted(dialog.hierarchy_marks, key=lambda value: value.start_line)
    ] == [
        (HierarchyType.TEXT, 0, 0),
        (HierarchyType.IGNORE, 1, 2),
    ]

def test_studio_tree_unmarked_range_can_be_marked_ignored(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Marked\nNeeds review\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.TEXT, order=1),
    ]
    dialog._hierarchy_mark_order = 2
    dialog._refresh()
    unmarked = _find_tree_item(dialog.flags_list, "Needs review")

    assert dialog._mark_outline_items_ignored([unmarked]) == 1
    ignored = [
        mark for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.IGNORE
    ]
    assert [(mark.start_line, mark.end_line) for mark in ignored] == [(1, 1)]
