from PyQt6.QtWidgets import (QApplication, QWidget, QAbstractItemView, QMessageBox, QPushButton, QPlainTextEdit)
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QCloseEvent, QTextCursor
from PyQt6.QtTest import QTest
from core.script_markup import (
    HierarchyAIPromptTooLarge,
    HierarchyMark,
    HierarchyType,
    HierarchyTypeDefinition,
    LineKind,
    default_type_definitions,
    mark_text,
)
from .helpers import (
    _make_dialog,
    _use_custom_mode,
    _use_hierarchy_mode,
    _use_picoripi_mode,
    _set_hierarchy_type,
    _select_lines,
    _tree_item_count,
)

def test_studio_picoripi_mode_uses_existing_rules(qapp):
    dialog = _make_dialog(qapp)
    _use_picoripi_mode(dialog)
    dialog.raw_edit.setPlainText(
        "[Chapter: Prologue]\n"
        "{Action: Midna appears}\n"
        "MIDNA: Well, look what we have here!\n"
    )
    dialog._refresh()
    assert "## Prologue" in dialog._psm_text
    assert "{Action: Midna appears}" in dialog._psm_text
    assert "MIDNA: Well, look what we have here!" in dialog._psm_text
    assert "via Picoripi rules" in dialog.stats_label.text()

def test_studio_custom_mode_renders_and_counts(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dialog.raw_edit.setPlainText(
        "[Chapter: Prologue]\n"
        "MIDNA: Well, look what we have here!\n"
        "ZELDA: Be careful.\n"
    )
    dialog._refresh()
    assert "## Prologue" in dialog._psm_text
    assert "MIDNA: Well, look what we have here!" in dialog._psm_text
    assert "ZELDA: Be careful." in dialog._psm_text
    assert dialog.highlighter.line_kinds
    assert "Speakers: 2" in dialog.stats_label.text()

def test_studio_gutter_on_by_default(qapp):
    dialog = _make_dialog(qapp)
    assert dialog.cb_gutter.isChecked()

def test_studio_timeline_range_excludes_front_matter(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Legal blah blah\n"
        "Table of contents\n"
        "ZELDA: This is real dialogue.\n"
    )
    cursor = dialog.raw_edit.textCursor()
    block = dialog.raw_edit.document().findBlockByNumber(2)
    cursor.setPosition(block.position())
    dialog.raw_edit.setTextCursor(cursor)
    dialog._set_timeline_start()

    assert dialog.start_line == 3
    assert "ZELDA: This is real dialogue." in dialog._psm_text
    assert "Legal blah" not in dialog._psm_text
    assert "Table of contents" not in dialog._psm_text

def test_studio_clear_range_restores_full_file(qapp):
    dialog = _make_dialog(qapp)
    dialog.start_line = 5
    dialog.end_line = 10
    dialog._clear_timeline_range()
    assert dialog.start_line == 0 and dialog.end_line == 0
    assert "full file" in dialog.range_label.text()

def test_studio_groups_consecutive_lines_by_speaker(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dialog.raw_edit.setPlainText(
        "RUSL: First line of Rusl.\n"
        "second wrapped line of rusl.\n"   # continuation → same speaker
        "FADO: Hey there.\n"               # new speaker → tint flips
    )
    dialog._refresh()
    blocks = dialog.highlighter.line_blocks
    assert blocks[0] == blocks[1]          # both belong to RUSL → same tint
    assert blocks[0] != blocks[2]          # FADO is a different block → flipped

def test_studio_flags_possible_missed_dialogue(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dialog.raw_edit.setPlainText('He turned and said "Hello there, friend" warmly.\n')
    dialog._refresh()
    assert dialog.flags_list.topLevelItemCount() >= 1

def test_studio_manual_action_mark_renders_and_tooltips(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Link rushes through the twilight.\n"
        "ILIA: Oh, hi, Link.\n"
    )
    cursor = dialog.raw_edit.textCursor()
    cursor.setPosition(0)
    cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
    dialog.raw_edit.setTextCursor(cursor)

    dialog._mark_selection_as(LineKind.ACTION)

    assert "{Action: Link rushes through the twilight.}" in dialog._psm_text
    assert dialog.highlighter.line_kinds[0] == LineKind.ACTION
    assert "Marked as Action" in dialog._tooltip_for_raw_position(QPoint(1, 1))

def test_studio_manual_action_mark_feeds_picoripi_rules(qapp):
    dialog = _make_dialog(qapp)
    _use_picoripi_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Link rushes through the twilight.\n"
        "ILIA\n"
        "Oh, hi, Link.\n"
    )
    cursor = dialog.raw_edit.textCursor()
    cursor.setPosition(0)
    cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
    dialog.raw_edit.setTextCursor(cursor)

    dialog._mark_selection_as(LineKind.ACTION)

    assert "{Action: Link rushes through the twilight.}" in dialog._psm_text
    assert "ILIA: Oh, hi, Link." in dialog._psm_text

def test_studio_speaker_teacher_learns_custom_separator(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dlg = dialog._build_speaker_teacher()
    dlg._test_parent = dialog
    dlg._sample_edit.setPlainText("Rusl - Take this shield.")
    dlg._name_edit.setText("Rusl")
    dlg._text_edit.setText("Take this shield.")
    dlg._on_ok()
    assert dlg.result_pattern is not None
    if dlg.result_pattern not in dialog.recipe.speaker_patterns:
        dialog.recipe.speaker_patterns.insert(0, dlg.result_pattern)

    dialog.raw_edit.setPlainText("Midna - Hello there.\n")
    dialog._refresh()
    assert "MIDNA: Hello there." in dialog._psm_text

def test_studio_preview_dialog_shows_rendered_script(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dialog.raw_edit.setPlainText("MIDNA: Hello there.\n")
    dialog._refresh()
    pv = dialog._build_preview_dialog()
    pv._test_parent = dialog
    assert "MIDNA: Hello there." in pv._view.toPlainText()

def test_studio_preview_window_is_modeless_and_live(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dialog.raw_edit.setPlainText("MIDNA: Hello there.\n")
    dialog._refresh()

    dialog._open_preview()
    qapp.processEvents()

    assert dialog._preview_dialog is not None
    assert dialog._preview_dialog.isVisible()
    assert "MIDNA: Hello there." in dialog._preview_view.toPlainText()

    dialog.raw_edit.setPlainText("ZELDA: Be careful.\n")
    dialog._refresh()

    assert "ZELDA: Be careful." in dialog._preview_view.toPlainText()
    assert "MIDNA: Hello there." not in dialog._preview_view.toPlainText()
    dialog._preview_dialog.close()

def test_studio_hierarchy_mode_renders_new_markdown_and_colours(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Act I\n"
        "Chapter One\n"
        "MIDNA\n"
        "Well, look what we have here.\n"
        "Midna drops from a branch\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE),
        HierarchyMark(1, 1, 1, HierarchyType.STRUCTURE),
        HierarchyMark(2, 2, 2, HierarchyType.SPEAKER),
        HierarchyMark(3, 3, 3, HierarchyType.TEXT),
        HierarchyMark(4, 4, 2, HierarchyType.ACTION),
    ]

    dialog._refresh()

    assert "# Act I" in dialog._psm_text
    assert "## Chapter One" in dialog._psm_text
    assert "**MIDNA**: Well, look what we have here." in dialog._psm_text
    assert "[*Midna drops from a branch*]" in dialog._psm_text
    assert dialog.highlighter.line_kinds[2] == HierarchyType.SPEAKER
    assert dialog.highlighter.line_colors[4] == dialog.hierarchy_type_definitions[HierarchyType.ACTION].color
    assert _tree_item_count(dialog.flags_list) == 5
    assert not dialog.legend_label.isHidden()
    assert "Action" in dialog.legend_label.text()

def test_studio_reset_markup_requires_confirmation_and_clears_all_marks(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    raw_text = "Act One\nChapter One\nMIDNA\nHello.\n"
    dialog.raw_edit.setPlainText(raw_text)
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.SPEAKER, text="MIDNA", order=3),
    ]
    dialog._hierarchy_mark_order = 3
    dialog._collapsed_hierarchy_keys.add(dialog._hierarchy_mark_key(dialog.hierarchy_marks[0]))
    assert dialog._start_range_edit(dialog._hierarchy_mark_key(dialog.hierarchy_marks[1]))
    dialog._refresh()
    dialog._record_history(force=True)

    answers = [
        QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    ]
    questions = []

    def fake_question(parent, title, text, buttons, default_button):
        questions.append((parent, title, text, buttons, default_button))
        return answers.pop(0)

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.question",
        fake_question,
    )

    dialog._reset_current_markup()

    assert len(dialog.hierarchy_marks) == 3
    assert dialog.raw_edit.toPlainText() == raw_text
    assert questions[0][1] == "Reset marks?"
    assert "Clear all hierarchy marks" in questions[0][2]

    dialog._reset_current_markup()

    assert dialog.hierarchy_marks == []
    assert dialog._hierarchy_mark_order == 0
    assert dialog._collapsed_hierarchy_keys == set()
    assert dialog._range_edit_mark_key is None
    assert dialog.raw_edit.toPlainText() == raw_text
    assert dialog.stats_label.text().startswith("Nodes: 0")
    assert "Act One" not in dialog._psm_text

def test_studio_unmarked_ranges_remain_inside_structure_container(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nRUSL\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 2, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
    ]

    dialog._refresh()

    assert dialog._unmarked_ranges(dialog.raw_edit.toPlainText().splitlines()) == [(1, 2)]
    assert "Unmarked" in dialog.flags_list.topLevelItem(1).text(0)

def test_studio_hierarchy_type_combo_is_editable_and_coloured(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)

    assert dialog.hierarchy_type_combo.isEditable()
    structure_idx = dialog.hierarchy_type_combo.findData(HierarchyType.STRUCTURE)
    color = dialog.hierarchy_type_combo.itemData(
        structure_idx,
        Qt.ItemDataRole.BackgroundRole,
    )

    assert dialog.hierarchy_type_combo.minimumWidth() >= 170
    assert color.name() == dialog.hierarchy_type_definitions[HierarchyType.STRUCTURE].color

def test_studio_can_add_custom_hierarchy_type_from_type_box(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Camera pans across Ordon Village.\n")
    _select_lines(dialog, 0, 0)
    dialog.hierarchy_depth_spin.setValue(1)
    dialog.hierarchy_type_combo.setEditText("Camera cue")
    dialog.hierarchy_label_edit.setText("Camera pans")

    dialog._mark_selection_as_hierarchy()

    custom_type = dialog._hierarchy_type_def_for_text("Camera cue")
    assert custom_type is not None
    assert custom_type.type_id.startswith("custom:")
    assert dialog.hierarchy_marks[0].type_id == custom_type.type_id
    assert "Camera cue" in dialog.flags_list.topLevelItem(0).text(0)
    assert "Camera pans" in dialog._psm_text
    idx = dialog.hierarchy_type_combo.findData(custom_type.type_id)
    assert idx >= 0
    assert dialog.hierarchy_type_combo.itemData(
        idx,
        Qt.ItemDataRole.BackgroundRole,
    ).name() == custom_type.color

def test_studio_marks_selection_as_hierarchy_node(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act I\n")
    _set_hierarchy_type(dialog, HierarchyType.STRUCTURE)
    dialog.hierarchy_depth_spin.setValue(0)
    dialog.hierarchy_label_edit.setText("Act One")
    cursor = dialog.raw_edit.textCursor()
    cursor.setPosition(0)
    cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
    dialog.raw_edit.setTextCursor(cursor)

    dialog._mark_selection_as_hierarchy()

    assert len(dialog.hierarchy_marks) == 1
    mark = dialog.hierarchy_marks[0]
    assert mark.depth == 0
    assert mark.type_id == HierarchyType.STRUCTURE
    assert "# Act One" in dialog._psm_text

def test_studio_manual_structure_iterator_advances_and_resets_by_parent(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Chapter 1\nA\nB\nChapter 2\nC\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 2, 0, HierarchyType.STRUCTURE, text="Chapter 1", order=1),
        HierarchyMark(3, 4, 0, HierarchyType.STRUCTURE, text="Chapter 2", order=2),
    ]
    dialog._hierarchy_mark_order = 2
    _set_hierarchy_type(dialog, HierarchyType.STRUCTURE)
    dialog.hierarchy_depth_spin.setValue(1)

    for line in (1, 2, 4):
        dialog.hierarchy_label_edit.setText("Scene $4")
        _select_lines(dialog, line, line)
        dialog._mark_selection_as_hierarchy()

    scenes = [
        mark.text for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.STRUCTURE and mark.depth == 1
    ]
    assert scenes == ["Scene 4", "Scene 5", "Scene 4"]

def test_studio_manual_inline_context_preserves_character_ranges_and_roundtrips(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    raw = "MIDNA (If other people are around)\nDo not transform here.\n"
    dialog.raw_edit.setPlainText(raw)

    def select_chars(start: int, end: int):
        cursor = dialog.raw_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        dialog.raw_edit.setTextCursor(cursor)

    _set_hierarchy_type(dialog, HierarchyType.SPEAKER)
    dialog.hierarchy_depth_spin.setValue(3)
    select_chars(0, 5)
    dialog._mark_selection_as_hierarchy()

    _set_hierarchy_type(dialog, HierarchyType.CONTEXT)
    dialog.hierarchy_depth_spin.setValue(4)
    select_chars(7, 33)
    dialog._mark_selection_as_hierarchy()

    _set_hierarchy_type(dialog, HierarchyType.TEXT)
    dialog.hierarchy_depth_spin.setValue(5)
    _select_lines(dialog, 1, 1)
    dialog._mark_selection_as_hierarchy()

    speaker = next(mark for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.SPEAKER)
    context = next(mark for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.CONTEXT)
    assert (speaker.start_col, speaker.end_col, mark_text(speaker, raw.splitlines())) == (0, 5, "MIDNA")
    assert (context.start_col, context.end_col, mark_text(context, raw.splitlines())) == (
        7, 33, "If other people are around",
    )
    assert dialog._hierarchy_mark_at_line(0, 2).type_id == HierarchyType.SPEAKER
    assert dialog._hierarchy_mark_at_line(0, 10).type_id == HierarchyType.CONTEXT
    assert "{Context: If other people are around}" in dialog._psm_text
    assert "**MIDNA**: Do not transform here." in dialog._psm_text

    payload = dialog._hierarchy_project_payload()
    restored = _make_dialog(qapp)
    assert restored._apply_hierarchy_project_payload(payload)
    restored_context = next(
        mark for mark in restored.hierarchy_marks if mark.type_id == HierarchyType.CONTEXT
    )
    assert (restored_context.start_col, restored_context.end_col) == (7, 33)

def test_studio_auto_marks_are_visible_and_can_be_approved_as_examples(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("MIDNA\nHello.\n")
    automatic = HierarchyMark(
        0, 0, 3, HierarchyType.SPEAKER,
        text="MIDNA", order=1, origin="local_autofill", approved=False,
    )
    dialog.hierarchy_marks = [automatic]
    dialog._refresh()

    item = dialog.flags_list.topLevelItem(0)
    assert "[Auto]" in item.text(0)
    assert dialog._approve_hierarchy_mark_keys([dialog._hierarchy_mark_key(automatic)]) == 1
    assert automatic.approved
    assert "[Auto]" in dialog.flags_list.topLevelItem(0).text(0)
    assert "✓" not in dialog.flags_list.topLevelItem(0).text(0)

    payload = dialog._hierarchy_project_payload()
    restored = _make_dialog(qapp)
    assert restored._apply_hierarchy_project_payload(payload)
    assert restored.hierarchy_marks[0].origin == "local_autofill"
    assert restored.hierarchy_marks[0].approved

def test_studio_legacy_mark_payload_defaults_to_manual_and_approved(qapp):
    dialog = _make_dialog(qapp)

    mark = dialog._hierarchy_mark_from_dict({
        "start_line": 0,
        "end_line": 0,
        "depth": 0,
        "type_id": HierarchyType.STRUCTURE,
        "text": "Act One",
    })

    assert mark.origin == "manual"
    assert mark.approved

def test_studio_nested_hierarchy_mark_does_not_replace_parent(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Act One\n"
        "Chapter One\n"
        "RUSL\n"
        "Take this shield.\n"
        "Chapter Two\n"
    )
    _set_hierarchy_type(dialog, HierarchyType.STRUCTURE)

    dialog.hierarchy_depth_spin.setValue(0)
    dialog.hierarchy_label_edit.setText("Act 1")
    _select_lines(dialog, 0, 4)
    dialog._mark_selection_as_hierarchy()

    dialog.hierarchy_depth_spin.setValue(1)
    dialog.hierarchy_label_edit.setText("Chapter 1")
    _select_lines(dialog, 1, 3)
    dialog._mark_selection_as_hierarchy()

    assert len(dialog.hierarchy_marks) == 2
    assert "# Act 1" in dialog._psm_text
    assert "## Chapter 1" in dialog._psm_text
    act_item = dialog.flags_list.topLevelItem(0)
    assert "Act 1" in act_item.text(0)
    assert act_item.childCount() == 1
    assert "Chapter 1" in act_item.child(0).text(0)

def test_studio_hierarchy_type_shortcuts_select_type_without_selection(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nMIDNA\nHello.\n")
    cursor = dialog.raw_edit.textCursor()
    cursor.setPosition(0)
    dialog.raw_edit.setTextCursor(cursor)

    for type_id in (
        HierarchyType.STRUCTURE,
        HierarchyType.SPEAKER,
        HierarchyType.TEXT,
        HierarchyType.BREAKER,
        HierarchyType.IGNORE,
    ):
        if type_id == HierarchyType.IGNORE:
            dialog._activate_ignore_shortcut()
        else:
            dialog._activate_hierarchy_type_shortcut(type_id)
        assert dialog.hierarchy_type_combo.currentData() == type_id
        assert dialog.hierarchy_marks == []

def test_studio_hierarchy_type_shortcuts_mark_selected_text(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nMIDNA\nHello.\n~~~~\nIgnore me\n")

    shortcuts = [
        (0, HierarchyType.STRUCTURE, dialog.structure_shortcut, Qt.Key.Key_S),
        (1, HierarchyType.SPEAKER, dialog.speaker_shortcut, Qt.Key.Key_P),
        (2, HierarchyType.TEXT, dialog.text_shortcut, Qt.Key.Key_T),
        (3, HierarchyType.BREAKER, dialog.breaker_shortcut, Qt.Key.Key_B),
        (4, HierarchyType.IGNORE, dialog.ignore_shortcut, Qt.Key.Key_I),
    ]

    dialog.show()
    qapp.processEvents()
    for line, type_id, _shortcut, key in shortcuts:
        _select_lines(dialog, line, line)
        dialog.raw_edit.setFocus()
        QTest.keyClick(dialog.raw_edit, key, Qt.KeyboardModifier.ControlModifier)
        assert dialog.hierarchy_marks[-1].start_line == line
        assert dialog.hierarchy_marks[-1].type_id == type_id

def test_studio_merges_adjacent_ignored_hierarchy_blocks(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Noise A\n\nNoise B\nKeep\nNoise C\n")
    _set_hierarchy_type(dialog, HierarchyType.IGNORE)

    _select_lines(dialog, 0, 0)
    dialog._mark_selection_as_hierarchy()
    _select_lines(dialog, 2, 2)
    dialog._mark_selection_as_hierarchy()
    _select_lines(dialog, 4, 4)
    dialog._mark_selection_as_hierarchy()

    ignored = sorted(
        [mark for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.IGNORE],
        key=lambda mark: mark.start_line,
    )
    assert [(mark.start_line, mark.end_line, mark.depth) for mark in ignored] == [
        (0, 2, 0),
        (4, 4, 0),
    ]

def test_studio_ignored_mark_overrides_existing_hierarchy_marks(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nRUSL\nHello.\nKeep me.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.SPEAKER, text="RUSL", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.TEXT, order=3),
    ]
    dialog._hierarchy_mark_order = 4
    dialog._refresh()
    _set_hierarchy_type(dialog, HierarchyType.IGNORE)
    _select_lines(dialog, 1, 2)

    dialog._mark_selection_as_hierarchy()

    assert [
        (mark.start_line, mark.end_line, mark.type_id)
        for mark in sorted(dialog.hierarchy_marks, key=lambda mark: mark.start_line)
    ] == [
        (0, 3, HierarchyType.STRUCTURE),
        (1, 2, HierarchyType.IGNORE),
    ]
    assert "RUSL" not in dialog._psm_text
    assert "Hello." not in dialog._psm_text
    assert "Keep me." in dialog._psm_text

def test_studio_can_remark_part_of_ignored_range_as_structure(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Ignored before\nScene heading\nScene body\nIgnored after\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.IGNORE, order=1),
    ]
    dialog._hierarchy_mark_order = 2
    dialog._refresh()
    _set_hierarchy_type(dialog, HierarchyType.STRUCTURE)
    dialog.hierarchy_depth_spin.setValue(2)
    _select_lines(dialog, 1, 2)

    dialog._mark_selection_as_hierarchy()

    assert [
        (mark.start_line, mark.end_line, mark.depth, mark.type_id)
        for mark in sorted(dialog.hierarchy_marks, key=lambda mark: mark.start_line)
    ] == [
        (0, 0, 0, HierarchyType.IGNORE),
        (1, 2, 2, HierarchyType.STRUCTURE),
        (3, 3, 0, HierarchyType.IGNORE),
    ]

def test_studio_groups_ignored_text_under_one_collapsed_tree_node(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Noise A\nKeep\nNoise B\nNoise C\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.IGNORE, order=1),
        HierarchyMark(1, 1, 0, HierarchyType.STRUCTURE, text="Keep", order=2),
        HierarchyMark(2, 3, 0, HierarchyType.IGNORE, order=3),
    ]

    dialog._refresh()

    ignored_root = dialog.flags_list.topLevelItem(0)
    assert ignored_root.text(0) == "Ignored: 3 lines in 2 ranges"
    assert not ignored_root.isExpanded()
    assert ignored_root.childCount() == 3
    assert [ignored_root.child(i).text(0) for i in range(3)] == [
        "Line 1: Noise A",
        "Line 3: Noise B",
        "Line 4: Noise C",
    ]

def test_studio_refresh_normalizes_existing_ignored_blocks(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Noise A\n\nNoise B\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.IGNORE, order=1),
        HierarchyMark(2, 2, 0, HierarchyType.IGNORE, order=2),
    ]

    dialog._refresh()

    ignored = [mark for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.IGNORE]
    assert len(ignored) == 1
    assert ignored[0].start_line == 0
    assert ignored[0].end_line == 2
    ignored_root = dialog.flags_list.topLevelItem(0)
    assert ignored_root.text(0) == "Ignored: 3 lines in 1 range"
    assert ignored_root.child(0).text(0) == "Line 1: Noise A"
