from PyQt6.QtWidgets import (QApplication, QWidget, QAbstractItemView, QMessageBox, QPushButton, QPlainTextEdit)
from core.script_markup import (
    HierarchyAIPromptTooLarge,
    HierarchyMark,
    HierarchyType,
    HierarchyTypeDefinition,
    LineKind,
    default_type_definitions,
    mark_text,
)
from ui.script_markup_studio_dialog import (
    ScriptMarkupStudioDialog,
    _ClassificationHighlighter,
    _RAW_HIERARCHY_GUTTER_WIDTH,
    _HELP_HTML,
)
from .helpers import (
    _make_dialog,
    _use_hierarchy_mode,
    _large_hierarchy_script,
)

def test_studio_hierarchy_mark_lookup_is_cached_between_repaints(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nMIDNA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 2, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.SPEAKER, text="MIDNA", order=2),
    ]
    dialog._refresh()

    first = dialog._hierarchy_mark_by_key_map()
    second = dialog._hierarchy_mark_by_key_map()

    assert first is second

    dialog.hierarchy_marks.append(
        HierarchyMark(2, 2, 1, HierarchyType.TEXT, text="Hello.", order=3)
    )
    dialog._refresh()

    assert dialog._hierarchy_mark_by_key_map() is not first

def test_studio_reset_raw_hierarchy_view_is_noop_when_already_reset(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    calls = []
    monkeypatch.setattr(
        dialog,
        "_set_raw_hierarchy_block_format",
        lambda line_depths, hidden_lines: calls.append((line_depths, hidden_lines)),
    )

    dialog._reset_raw_hierarchy_view()

    assert calls == []

    dialog._raw_line_depths = {0: 1}
    dialog._reset_raw_hierarchy_view()

    assert calls == [({}, set())]

def test_classification_highlighter_skips_unchanged_rehighlight(qapp, monkeypatch):
    edit = QPlainTextEdit()
    highlighter = _ClassificationHighlighter(edit.document())
    calls = []
    monkeypatch.setattr(highlighter, "rehighlight", lambda: calls.append(True))

    highlighter.set_line_kinds({0: LineKind.ACTION})
    highlighter.set_line_kinds({0: LineKind.ACTION})
    highlighter.set_line_kinds({0: LineKind.IGNORE})

    assert calls == [True, True]

def test_studio_hierarchy_outline_skips_unchanged_rebuild(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nMIDNA\nHello there\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
    ]

    dialog._refresh_hierarchy()
    calls = []
    original_make_tree_item = dialog._make_tree_item

    def counting_make_tree_item(*args, **kwargs):
        calls.append(args)
        return original_make_tree_item(*args, **kwargs)

    monkeypatch.setattr(dialog, "_make_tree_item", counting_make_tree_item)

    dialog._refresh_hierarchy()

    assert calls == []

    dialog.hierarchy_marks.append(
        HierarchyMark(1, 2, 1, HierarchyType.SPEAKER, text="MIDNA", order=2)
    )
    dialog._refresh_hierarchy()

    assert calls

def test_studio_grouped_unmarked_outline_rebuilds_when_preview_text_changes(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    lines = []
    for idx in range(81):
        lines.extend([f"Unmarked line {idx}", ""])
    dialog.raw_edit.setPlainText("\n".join(lines))

    dialog._refresh_hierarchy()
    calls = []
    original_make_tree_item = dialog._make_tree_item

    def counting_make_tree_item(*args, **kwargs):
        calls.append(args)
        return original_make_tree_item(*args, **kwargs)

    monkeypatch.setattr(dialog, "_make_tree_item", counting_make_tree_item)

    edited_lines = list(lines)
    edited_lines[0] = "Changed unmarked line"
    dialog.raw_edit.setPlainText("\n".join(edited_lines))
    dialog._refresh_hierarchy()

    assert calls

def test_studio_hierarchy_line_styles_are_cached_until_marks_change(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nMIDNA\nHello there\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
    ]
    calls = []

    def fake_line_styles_for_marks(marks, type_definitions):
        calls.append(tuple((mark.start_line, mark.end_line, mark.type_id) for mark in marks))
        return {mark.start_line: (mark.type_id, "#ffffff") for mark in marks}

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.line_styles_for_marks",
        fake_line_styles_for_marks,
    )

    dialog._refresh_hierarchy()
    dialog._refresh_hierarchy()

    assert len(calls) == 1

    dialog.hierarchy_marks.append(
        HierarchyMark(1, 2, 1, HierarchyType.SPEAKER, text="MIDNA", order=2)
    )
    dialog._refresh_hierarchy()

    assert len(calls) == 2

    dialog.hierarchy_type_definitions[HierarchyType.STRUCTURE] = HierarchyTypeDefinition(
        HierarchyType.STRUCTURE,
        "Structure",
        "Changed color for cache invalidation",
        "#123456",
    )
    dialog._refresh_hierarchy()

    assert len(calls) == 3

def test_studio_large_hierarchy_second_refresh_reuses_caches(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    script, marks = _large_hierarchy_script()
    dialog.raw_edit.setPlainText(script)
    dialog.hierarchy_marks = marks
    line_style_calls = []
    tree_item_calls = []

    def fake_line_styles_for_marks(marks, type_definitions):
        line_style_calls.append(len(marks))
        return {mark.start_line: (mark.type_id, "#ffffff") for mark in marks}

    original_make_tree_item = dialog._make_tree_item

    def counting_make_tree_item(*args, **kwargs):
        tree_item_calls.append(args)
        return original_make_tree_item(*args, **kwargs)

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.line_styles_for_marks",
        fake_line_styles_for_marks,
    )
    monkeypatch.setattr(dialog, "_make_tree_item", counting_make_tree_item)

    dialog._refresh_hierarchy()

    assert line_style_calls
    assert tree_item_calls

    line_style_calls.clear()
    tree_item_calls.clear()
    dialog._refresh_hierarchy()

    assert line_style_calls == []
    assert tree_item_calls == []
    assert dialog._psm_text
    assert dialog.flags_list.topLevelItemCount() > 0

def test_studio_large_hierarchy_text_change_keeps_mark_dependent_caches(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    script, marks = _large_hierarchy_script()
    dialog.raw_edit.setPlainText(script)
    dialog.hierarchy_marks = marks

    dialog._refresh_hierarchy()

    calls = []

    def fake_line_styles_for_marks(marks, type_definitions):
        calls.append(len(marks))
        return {mark.start_line: (mark.type_id, "#ffffff") for mark in marks}

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.line_styles_for_marks",
        fake_line_styles_for_marks,
    )

    edited_lines = script.splitlines()
    edited_lines[2] = "Changed dialogue line for cache smoke"
    dialog.raw_edit.setPlainText("\n".join(edited_lines))
    dialog._refresh_hierarchy()

    assert calls == []
    assert "Changed dialogue line for cache smoke" in dialog._psm_text

def test_studio_raw_hierarchy_view_cache_updates_when_fold_state_changes(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    raw_lines = ["Act One", "MIDNA", "Hello there"]
    mark = HierarchyMark(0, 2, 0, HierarchyType.STRUCTURE, text="Act One", order=1)
    dialog.hierarchy_marks = [mark]

    _depths, _headers, hidden_lines = dialog._raw_hierarchy_view_data(raw_lines)
    assert hidden_lines == set()

    dialog._collapsed_hierarchy_keys.add(dialog._hierarchy_mark_key(mark))
    _depths, _headers, hidden_lines = dialog._raw_hierarchy_view_data(raw_lines)

    assert hidden_lines == {1, 2}

def test_studio_large_hierarchy_fold_cache_hit_returns_copies(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    script, marks = _large_hierarchy_script(line_count=48)
    raw_lines = script.splitlines()
    dialog.hierarchy_marks = marks

    line_depths, fold_headers, hidden_lines = dialog._raw_hierarchy_view_data(raw_lines)
    line_depths[999] = 999
    fold_headers[999] = "mutated"
    hidden_lines.add(999)

    line_depths, fold_headers, hidden_lines = dialog._raw_hierarchy_view_data(raw_lines)

    assert 999 not in line_depths
    assert 999 not in fold_headers
    assert 999 not in hidden_lines
