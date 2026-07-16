import json
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QWidget, QAbstractItemView, QMessageBox, QPushButton, QPlainTextEdit
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
from ui.script_markup_studio_dialog import (
    ScriptMarkupStudioDialog,
    _ClassificationHighlighter,
    _RAW_HIERARCHY_GUTTER_WIDTH,
    _HELP_HTML,
)
from components.editor.minimap import TextMinimap


def _fresh_autosave_path():
    return Path(tempfile.gettempdir()) / f"picoripi_sms_test_{uuid.uuid4().hex}.json"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def _make_dialog(qapp):
    mock_mw = MagicMock()
    # current_game_rules=None → "Picoripi rules" mode uses the real BaseGameRules.
    mock_mw.current_game_rules = None
    mock_mw.script_markup_studio_autosave_path = _fresh_autosave_path()
    parent = QWidget()
    dialog = ScriptMarkupStudioDialog(mock_mw, parent=parent)
    dialog._test_parent = parent  # keep parent alive (WA_DeleteOnClose)
    return dialog


def _use_custom_mode(dialog):
    dialog.mode = "custom"
    dialog._update_mode_controls()


def _use_hierarchy_mode(dialog):
    dialog.mode = "hierarchy"
    dialog._update_mode_controls()


def _use_picoripi_mode(dialog):
    dialog.mode = "picoripi"
    dialog._update_mode_controls()


def _set_hierarchy_type(dialog, type_id):
    for idx in range(dialog.hierarchy_type_combo.count()):
        if dialog.hierarchy_type_combo.itemData(idx) == type_id:
            dialog.hierarchy_type_combo.setCurrentIndex(idx)
            return
    raise AssertionError(f"Missing hierarchy type {type_id}")


def _select_lines(dialog, first_line, last_line):
    doc = dialog.raw_edit.document()
    start_block = doc.findBlockByNumber(first_line)
    end_block = doc.findBlockByNumber(last_line)
    cursor = dialog.raw_edit.textCursor()
    cursor.setPosition(start_block.position())
    cursor.setPosition(
        end_block.position() + len(end_block.text()),
        QTextCursor.MoveMode.KeepAnchor,
    )
    dialog.raw_edit.setTextCursor(cursor)


def _tree_item_count(tree):
    def count_item(item):
        return 1 + sum(count_item(item.child(i)) for i in range(item.childCount()))

    return sum(count_item(tree.topLevelItem(i)) for i in range(tree.topLevelItemCount()))


def _find_tree_item(tree, text):
    def walk(item):
        if text in item.text(0):
            return item
        for idx in range(item.childCount()):
            found = walk(item.child(idx))
            if found is not None:
                return found
        return None

    for idx in range(tree.topLevelItemCount()):
        found = walk(tree.topLevelItem(idx))
        if found is not None:
            return found
    raise AssertionError(f"Missing tree item containing {text!r}")


def _large_hierarchy_script(line_count=1200):
    lines = []
    marks = []
    order = 1

    for section in range((line_count + 11) // 12):
        base = len(lines)
        if base >= line_count:
            break

        lines.append(f"Scene {section}")
        scene_end = min(base + 11, line_count - 1)
        marks.append(
            HierarchyMark(
                base,
                scene_end,
                0,
                HierarchyType.STRUCTURE,
                text=f"Scene {section}",
                order=order,
            )
        )
        order += 1

        if len(lines) >= line_count:
            break

        speaker_line = len(lines)
        lines.append(f"Speaker {section}")
        marks.append(
            HierarchyMark(
                speaker_line,
                speaker_line,
                1,
                HierarchyType.SPEAKER,
                text=f"Speaker {section}",
                order=order,
            )
        )
        order += 1

        for offset in range(2, 12):
            if len(lines) >= line_count:
                break
            line_no = len(lines)
            lines.append(f"Dialogue line {section}-{offset}")
            marks.append(
                HierarchyMark(
                    line_no,
                    line_no,
                    2,
                    HierarchyType.TEXT,
                    order=order,
                )
            )
            order += 1

    return "\n".join(lines), marks


def test_studio_raw_editor_has_minimap(qapp):
    dialog = _make_dialog(qapp)
    dialog.resize(1200, 800)
    dialog.raw_edit.setPlainText("\n".join(f"Raw script line {i}" for i in range(160)))
    dialog.show()
    QApplication.processEvents()
    dialog.raw_edit._sync_viewport_margins()

    assert dialog.raw_edit.minimapAreaWidth() == TextMinimap.WIDTH
    assert dialog.raw_edit.viewportMargins().left() == _RAW_HIERARCHY_GUTTER_WIDTH
    assert dialog.raw_edit.viewportMargins().right() == TextMinimap.WIDTH
    assert dialog.raw_edit.minimap.isVisible()


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


class _FakeSettingsManager:
    def __init__(self, initial=None):
        self.values = dict(initial or {})
        self.saved = 0

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def save_settings(self, save_project_settings=True):
        self.saved += 1


class _FakeMainWindow(QWidget):
    def __init__(self, settings_manager=None):
        super().__init__()
        self.current_game_rules = None
        self.settings_manager = settings_manager
        self.script_markup_studio_autosave_path = _fresh_autosave_path()


# --------------------------------------------------------------- construction
def test_studio_constructs(qapp):
    dialog = _make_dialog(qapp)
    assert dialog.windowTitle() == "Script Markup Studio"
    assert dialog.mode == "hierarchy"  # new default engine
    assert not dialog.hierarchy_box.isHidden()
    assert dialog.range_panel.isHidden()
    assert dialog.recipe_box.isHidden()
    assert dialog.teach_box.isHidden()
    assert dialog.script_menu_btn.text() == "Script"
    assert dialog.save_project_primary_btn.text() == "Save Project…"
    assert not dialog.save_project_primary_btn.isHidden()
    assert dialog.finish_mempalace_btn.text() == "Finish for MemPalace…"
    assert not dialog.finish_mempalace_btn.isHidden()
    assert dialog.project_state_label.text() == "Markup project: Not saved"
    assert [action.text() for action in dialog.project_menu.actions() if not action.isSeparator()] == [
        "Open project...",
        "Save project...",
        "Reset marks...",
    ]
    assert [action.text() for action in dialog.template_menu.actions()] == [
        "Open template...",
        "Save template...",
    ]
    assert [action.text() for action in dialog.auto_markup_menu.actions()] == [
        "Join selected structures",
        "Continue from marked examples...",
        "AI mark missing...",
    ]
    assert dialog.recipe_menu_btn.isHidden()
    assert not dialog.load_recipe_btn.isVisible()
    assert not dialog.save_recipe_btn.isVisible()
    assert not dialog.project_menu_btn.isHidden()
    assert not dialog.template_menu_btn.isHidden()
    assert not dialog.auto_markup_menu_btn.isHidden()
    assert dialog.load_markup_btn.isVisible()
    assert dialog.save_markup_btn.isVisible()
    assert dialog.reset_markup_btn.isVisible()
    assert dialog.load_template_btn.isVisible()
    assert dialog.save_template_btn.isVisible()
    assert dialog.join_structures_btn.isVisible()
    assert dialog.continue_examples_btn.isVisible()
    assert dialog.ai_markup_btn.isVisible()
    assert dialog.legend_label.isHidden()
    assert dialog.main_splitter.orientation() == Qt.Orientation.Horizontal
    assert dialog.flags_list.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    assert dialog.main_splitter.widget(0) is dialog.raw_panel
    assert dialog.main_splitter.widget(1) is dialog.outline_panel


def test_studio_buttons_explain_their_actions(qapp):
    dialog = _make_dialog(qapp)

    missing_buttons = [
        button.text()
        for button in dialog.findChildren(QPushButton)
        if not button.toolTip().strip()
    ]
    assert missing_buttons == []

    menus = [
        dialog.script_menu,
        dialog.project_menu,
        dialog.template_menu,
        dialog.auto_markup_menu,
        dialog.recipe_menu,
    ]
    missing_actions = [
        action.text()
        for menu in menus
        for action in menu.actions()
        if not action.isSeparator() and not action.toolTip().strip()
    ]
    assert missing_actions == []

    ignore_button = next(
        button for button in dialog.teach_box.findChildren(QPushButton)
        if button.text() == "Ignore"
    )
    assert "Ctrl+I" in ignore_button.toolTip()
    assert "Ctrl+F" in dialog.search_edit.toolTip()
    assert "Enter" in dialog.search_next_btn.toolTip()
    assert "Shift+Enter" in dialog.search_prev_btn.toolTip()
    assert "Ctrl+M" in dialog.hierarchy_mark_btn.toolTip()
    assert "F2" in dialog.flags_list.toolTip()
    for shortcut in ("Ctrl+S", "Ctrl+P", "Ctrl+T", "Ctrl+B", "Ctrl+I"):
        assert shortcut in dialog.hierarchy_mark_btn.toolTip()
        assert shortcut in dialog.hierarchy_type_combo.toolTip()

    teacher = dialog._build_speaker_teacher()
    preview = dialog._build_preview_dialog()
    help_dialog = dialog._build_help_dialog()
    missing_dialog_buttons = [
        button.text()
        for window in (teacher, preview, help_dialog)
        for button in window.findChildren(QPushButton)
        if not button.toolTip().strip()
    ]
    assert missing_dialog_buttons == []


def test_studio_restores_saved_window_geometry(qapp):
    screen_geom = QApplication.primaryScreen().availableGeometry()
    if screen_geom.width() < 740 or screen_geom.height() < 540:
        pytest.skip("Screen is too small for exact Script Markup Studio geometry restore.")
    saved = {
        "x": screen_geom.left() + 10,
        "y": screen_geom.top() + 10,
        "width": min(780, screen_geom.width() - 20),
        "height": min(560, screen_geom.height() - 20),
    }
    settings = _FakeSettingsManager({"script_markup_studio_geometry": saved})
    parent = _FakeMainWindow(settings)

    dialog = ScriptMarkupStudioDialog(parent, parent=parent)
    dialog._test_parent = parent

    geom = dialog.geometry()
    assert geom.x() == saved["x"]
    assert geom.y() == saved["y"]
    assert geom.width() == saved["width"]
    assert geom.height() == saved["height"]


def test_studio_saves_window_geometry(qapp):
    settings = _FakeSettingsManager()
    parent = _FakeMainWindow(settings)
    dialog = ScriptMarkupStudioDialog(parent, parent=parent)
    dialog._test_parent = parent
    dialog.setGeometry(60, 70, 820, 620)

    dialog._save_window_geometry()

    saved = settings.values["script_markup_studio_geometry"]
    assert saved == {"x": 60, "y": 70, "width": 820, "height": 620}
    assert parent.script_markup_studio_geometry == saved
    assert settings.saved == 1


def test_studio_autosaves_and_restores_session_on_close(qapp, tmp_path):
    autosave_path = tmp_path / "script_markup_studio_autosave.json"
    parent = _FakeMainWindow()
    parent.script_markup_studio_autosave_path = autosave_path
    dialog = ScriptMarkupStudioDialog(parent, parent=parent)
    dialog._test_parent = parent
    _use_hierarchy_mode(dialog)
    dialog.current_raw_path = "C:/scripts/raw.txt"
    dialog.path_label.setText(dialog.current_raw_path)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\n")
    dialog.hierarchy_type_definitions["custom:camera"] = HierarchyTypeDefinition(
        "custom:camera",
        "Camera",
        "Camera direction.",
        "#abc123",
    )
    dialog._rebuild_hierarchy_type_combo()
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 2, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
    ]
    dialog._hierarchy_mark_order = 2
    dialog._refresh()
    dialog.search_edit.setText("MIDNA")
    cursor = dialog.raw_edit.textCursor()
    cursor.setPosition(8)
    dialog.raw_edit.setTextCursor(cursor)
    mark_key = dialog._hierarchy_mark_key(dialog.hierarchy_marks[1])
    assert dialog._start_range_edit(mark_key)
    assert dialog._update_range_edit_preview("end", 3)
    dialog.hierarchy_label_edit.setText("Edited Chapter")
    dialog.main_splitter.setSizes([777, 333])

    dialog.closeEvent(QCloseEvent())

    assert autosave_path.exists()
    restored = ScriptMarkupStudioDialog(parent, parent=parent)
    restored._test_parent = parent

    assert restored.raw_edit.toPlainText() == "Act One\nChapter One\nMIDNA\nHello.\n"
    assert restored.current_raw_path == "C:/scripts/raw.txt"
    assert restored.hierarchy_type_definitions["custom:camera"].color == "#abc123"
    assert len(restored.hierarchy_marks) == 2
    assert restored._range_edit_mark_key is not None
    assert restored._range_edit_end_line == 3
    assert restored.hierarchy_label_edit.text() == "Edited Chapter"
    assert restored.hierarchy_mark_btn.text() == "Save edit"
    assert restored.search_edit.text() == "MIDNA"
    assert restored.raw_edit.textCursor().position() == 8
    assert restored.main_splitter.sizes()[0] > restored.main_splitter.sizes()[1]


def test_studio_mode_toggle_shows_only_relevant_controls(qapp):
    dialog = _make_dialog(qapp)
    assert not dialog.hierarchy_box.isHidden()
    assert dialog.recipe_box.isHidden()
    assert dialog.teach_box.isHidden()

    _use_custom_mode(dialog)
    assert dialog.hierarchy_box.isHidden()
    assert not dialog.range_panel.isHidden()
    assert not dialog.recipe_box.isHidden()
    assert dialog.recipe_box.isEnabled()
    assert not dialog.teach_box.isHidden()
    assert dialog.teach_box.isEnabled()
    assert not dialog.recipe_menu_btn.isHidden()
    assert dialog.load_recipe_btn.isVisible()
    assert dialog.save_recipe_btn.isVisible()
    assert dialog.project_menu_btn.isHidden()
    assert dialog.template_menu_btn.isHidden()
    assert dialog.auto_markup_menu_btn.isHidden()
    assert not dialog.load_markup_btn.isVisible()
    assert not dialog.save_markup_btn.isVisible()
    assert not dialog.reset_markup_btn.isVisible()
    assert not dialog.load_template_btn.isVisible()
    assert not dialog.save_template_btn.isVisible()
    assert not dialog.join_structures_btn.isVisible()
    assert not dialog.continue_examples_btn.isVisible()
    assert not dialog.ai_markup_btn.isVisible()

    _use_picoripi_mode(dialog)
    assert dialog.hierarchy_box.isHidden()
    assert not dialog.range_panel.isHidden()
    assert dialog.recipe_box.isHidden()
    assert dialog.teach_box.isHidden()
    assert dialog.recipe_menu_btn.isHidden()
    assert dialog.project_menu_btn.isHidden()
    assert dialog.template_menu_btn.isHidden()
    assert dialog.auto_markup_menu_btn.isHidden()
    assert not dialog.load_markup_btn.isVisible()
    assert not dialog.save_markup_btn.isVisible()
    assert not dialog.reset_markup_btn.isVisible()
    assert not dialog.join_structures_btn.isVisible()
    assert not dialog.continue_examples_btn.isVisible()
    assert not dialog.ai_markup_btn.isVisible()


def test_studio_search_preserves_raw_cursor_and_selection(qapp):
    dialog = _make_dialog(qapp)
    dialog.raw_edit.setPlainText("Act One\nScene setup\nAct Two\n")
    _select_lines(dialog, 0, 1)
    before = dialog.raw_edit.textCursor()

    dialog.search_edit.setText("Act Two")

    after = dialog.raw_edit.textCursor()
    assert after.selectionStart() == before.selectionStart()
    assert after.selectionEnd() == before.selectionEnd()
    assert len(dialog.raw_edit.extraSelections()) == 1
    assert dialog.raw_edit.extraSelections()[0].cursor.selectedText() == "Act Two"
    assert dialog.search_status_label.text() == "1/1"


def test_studio_search_next_advances_without_moving_raw_cursor(qapp):
    dialog = _make_dialog(qapp)
    dialog.raw_edit.setPlainText("Act One\nAct Two\nAct Two\n")
    cursor = dialog.raw_edit.textCursor()
    cursor.setPosition(0)
    dialog.raw_edit.setTextCursor(cursor)

    dialog.search_edit.setText("Act Two")
    first = dialog.raw_edit.extraSelections()[0].cursor.selectionStart()
    dialog._find_next_search_match()
    second = dialog.raw_edit.extraSelections()[0].cursor.selectionStart()

    assert second > first
    assert dialog.raw_edit.textCursor().position() == 0
    assert dialog.search_status_label.text() == "2/2"


def test_studio_search_next_cycles_from_active_match_not_raw_cursor(qapp):
    dialog = _make_dialog(qapp)
    dialog.raw_edit.setPlainText("Act Two\nAct Two\nAct Two\n")
    cursor = dialog.raw_edit.textCursor()
    cursor.setPosition(0)
    dialog.raw_edit.setTextCursor(cursor)

    dialog.search_edit.setText("Act Two")
    starts = [dialog.raw_edit.extraSelections()[0].cursor.selectionStart()]
    dialog._find_next_search_match()
    starts.append(dialog.raw_edit.extraSelections()[0].cursor.selectionStart())
    dialog._find_next_search_match()
    starts.append(dialog.raw_edit.extraSelections()[0].cursor.selectionStart())
    dialog._find_next_search_match()
    starts.append(dialog.raw_edit.extraSelections()[0].cursor.selectionStart())

    assert starts[0] < starts[1] < starts[2]
    assert starts[3] == starts[0]
    assert dialog.raw_edit.textCursor().position() == 0
    assert dialog.search_status_label.text() == "1/3"


def test_studio_search_enter_advances_without_triggering_default_button(qapp):
    dialog = _make_dialog(qapp)
    dialog.raw_edit.setPlainText("Act Two\nAct Two\n")
    dialog.help_btn.clicked.disconnect()
    help_clicks = []
    dialog.help_btn.clicked.connect(lambda: help_clicks.append(True))
    dialog.help_btn.setAutoDefault(True)
    dialog.help_btn.setDefault(True)

    dialog.search_edit.setText("Act Two")
    first = dialog.raw_edit.extraSelections()[0].cursor.selectionStart()
    QTest.keyClick(dialog.search_edit, Qt.Key.Key_Return)
    second = dialog.raw_edit.extraSelections()[0].cursor.selectionStart()

    assert second > first
    assert dialog.search_status_label.text() == "2/2"
    assert help_clicks == []

    QTest.keyClick(
        dialog.search_edit,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier,
    )
    assert dialog.raw_edit.extraSelections()[0].cursor.selectionStart() == first
    assert dialog.search_status_label.text() == "1/2"
    assert help_clicks == []


def test_studio_search_highlight_survives_refresh(qapp):
    dialog = _make_dialog(qapp)
    dialog.raw_edit.setPlainText("Act One\nAct Two\n")
    dialog.search_edit.setText("Act Two")

    dialog._refresh()

    assert dialog.raw_edit.extraSelections()[0].cursor.selectedText() == "Act Two"
    assert dialog.search_status_label.text() == "1/1"


def test_studio_search_options_case_word_and_regex(qapp):
    dialog = _make_dialog(qapp)
    dialog.raw_edit.setPlainText("act\nAct\nAction\nAct 2\nAct A\n")

    dialog.search_edit.setText("Act")
    assert dialog.search_status_label.text() == "1/5"

    dialog.search_case_cb.setChecked(True)
    assert dialog.search_status_label.text() == "1/4"

    dialog.search_word_cb.setChecked(True)
    assert dialog.search_status_label.text() == "1/3"

    dialog.search_edit.setText(r"Act \d")
    dialog.search_regex_cb.setChecked(True)
    assert dialog.search_status_label.text() == "1/1"
    assert dialog.raw_edit.extraSelections()[0].cursor.selectedText() == "Act 2"

    dialog.search_edit.setText("(")
    assert dialog.search_status_label.text() == "Bad regex"
    assert dialog.raw_edit.extraSelections() == []


def test_studio_text_change_invalidates_search_without_reading_full_document(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    dialog.raw_edit.setPlainText("Act One\nAct Two\n")
    dialog._search_document_revision = -1

    def fail_to_plain_text():
        raise AssertionError("textChanged should not read the full raw document")

    monkeypatch.setattr(dialog.raw_edit, "toPlainText", fail_to_plain_text)

    dialog._invalidate_search_matches()

    assert dialog._search_document_revision == dialog._raw_text_revision
    assert dialog._search_text_fingerprint is None


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


# ------------------------------------------------------------- Picoripi engine
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


# --------------------------------------------------------------- custom engine
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


# ------------------------------------------------------------ teach by example
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


# --------------------------------------------------------------- preview/help
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


def test_studio_help_dialog_renders_html(qapp):
    dialog = _make_dialog(qapp)
    help_dlg = dialog._build_help_dialog()
    help_dlg._test_parent = dialog
    text = dialog._help_browser.toPlainText()
    assert "Script Markup Studio" in text
    assert "Three modes" in text
    assert "Speaker" in text
    assert "Enter" in text
    assert "Minimap" in text
    assert "Keyboard shortcuts" in text
    assert "<h2" not in text  # rendered, not literal markup
    for shortcut in (
        "Ctrl+F",
        "Enter",
        "Shift+Enter",
        "Ctrl+M",
        "Ctrl+I",
        "Ctrl+S",
        "Ctrl+P",
        "Ctrl+T",
        "Ctrl+B",
        "F2",
        "Ctrl+Z",
        "Ctrl+Y",
    ):
        assert shortcut in _HELP_HTML


# ----------------------------------------------------------- hierarchy markup
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


def test_studio_hierarchy_project_payload_roundtrips_markup(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.current_raw_path = "C:/scripts/raw.txt"
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\nNeeds work\n")
    dialog.hierarchy_type_definitions["custom:camera"] = HierarchyTypeDefinition(
        "custom:camera",
        "Camera",
        "Camera direction.",
        "#abc123",
    )
    dialog._rebuild_hierarchy_type_combo()
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.SPEAKER, text="MIDNA", order=3),
        HierarchyMark(3, 3, 3, HierarchyType.TEXT, order=4),
    ]
    dialog._refresh()

    payload = dialog._hierarchy_project_payload()
    restored = _make_dialog(qapp)

    assert restored._apply_hierarchy_project_payload(payload)

    assert restored.raw_edit.toPlainText() == dialog.raw_edit.toPlainText()
    assert restored.current_raw_path == "C:/scripts/raw.txt"
    assert len(restored.hierarchy_marks) == 4
    assert restored._hierarchy_mark_order == 4
    assert restored.hierarchy_type_definitions["custom:camera"].color == "#abc123"
    assert "rendered_markdown" in payload
    assert payload["unmarked_ranges"]
    assert "Chapter One" in restored.flags_list.topLevelItem(0).child(0).text(0)


def test_studio_publishes_saved_hierarchy_project_for_mempalace(qapp, tmp_path):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\n")
    raw_path = tmp_path / "raw_script.txt"
    dialog.current_raw_path = str(raw_path)
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE, text="Act One", order=1)
    ]
    project_path = tmp_path / "script_markup_project.json"
    dialog.mw.mempalace_builder_dialog = MagicMock()

    with patch(
        "ui.script_markup_studio_dialog.QFileDialog.getSaveFileName",
        return_value=(str(project_path), "JSON"),
    ) as save_dialog, patch("ui.script_markup_studio_dialog.QMessageBox.information"):
        assert dialog._save_hierarchy_project()

    expected = str(project_path.resolve())
    assert dialog.current_hierarchy_project_path == expected
    assert save_dialog.call_args.args[3] == "JSON (*.json)"
    assert save_dialog.call_args.args[2] == str(tmp_path / "script_markup_project.json")
    assert dialog.project_state_label.text() == f"Markup project: {expected}"
    assert dialog.mw.script_markup_studio_project_path == expected
    dialog.mw.mempalace_builder_dialog._load_active_markup_studio_project.assert_called_once()


def test_studio_publishes_opened_hierarchy_project_for_mempalace(qapp, tmp_path):
    source = _make_dialog(qapp)
    _use_hierarchy_mode(source)
    source.raw_edit.setPlainText("Act One\n")
    source.hierarchy_marks = [
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE, text="Act One", order=1)
    ]
    source._refresh()
    project_path = tmp_path / "script_markup_project.json"
    project_path.write_text(
        json.dumps(source._hierarchy_project_payload()),
        encoding="utf-8",
    )
    restored = _make_dialog(qapp)

    with patch(
        "ui.script_markup_studio_dialog.QFileDialog.getOpenFileName",
        return_value=(str(project_path), "JSON"),
    ):
        assert restored._load_hierarchy_project()

    expected = str(project_path.resolve())
    assert restored.current_hierarchy_project_path == expected
    assert restored.mw.script_markup_studio_project_path == expected


def test_studio_finishes_complete_markup_for_mempalace(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("MIDNA\nHello.\n")
    speaker = HierarchyMark(
        0, 0, 0, HierarchyType.SPEAKER, text="MIDNA", order=1,
        origin="local_autofill", approved=False,
    )
    text = HierarchyMark(
        1, 1, 1, HierarchyType.TEXT, order=2,
        origin="local_autofill", approved=False,
    )
    dialog.hierarchy_marks = [speaker, text]
    dialog._refresh()
    questions = []
    saves = []
    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.question",
        lambda *_args: questions.append(_args) or QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        dialog,
        "_save_hierarchy_project",
        lambda: saves.append(True) or True,
    )

    assert dialog._finish_markup_for_mempalace() is True

    assert all(mark.approved for mark in dialog.hierarchy_marks)
    assert len(questions) == 1
    assert "accept 2 visible Auto-fill nodes" in questions[0][2]
    assert saves == [True]


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


def test_studio_applies_ai_marks_without_touching_manual_marks(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nRUSL\nHello.\nFADO\nHey!\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 4, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.SPEAKER, text="RUSL", order=2),
    ]
    dialog._hierarchy_mark_order = 3
    dialog._refresh()

    added, skipped = dialog._apply_hierarchy_ai_marks([
        HierarchyMark(2, 2, 2, HierarchyType.TEXT),
        HierarchyMark(3, 3, 1, HierarchyType.SPEAKER, text="FADO"),
        HierarchyMark(4, 4, 2, HierarchyType.TEXT),
        HierarchyMark(0, 0, 0, HierarchyType.STRUCTURE, text="Duplicate"),
    ])

    assert added == 3
    assert skipped == 1
    assert {mark.text for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.SPEAKER} == {
        "RUSL",
        "FADO",
    }
    assert "# Act One" in dialog._psm_text
    assert "**RUSL**: Hello." in dialog._psm_text
    assert "**FADO**: Hey!" in dialog._psm_text


def test_studio_continue_from_examples_requires_existing_marks(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("RUSL\nHello.\n")
    messages = []

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.information",
        lambda _parent, title, text: messages.append((title, text)),
    )

    def fail_provider_lookup():
        raise AssertionError("Provider should not be created without marked examples.")

    monkeypatch.setattr(dialog, "_create_hierarchy_ai_provider", fail_provider_lookup)

    dialog._continue_hierarchy_from_examples()

    assert messages == [
        (
            "Continue from marked examples",
            "Mark at least one hierarchy example manually, then run this auto-fill again.",
        )
    ]


def test_studio_continue_from_examples_is_local_and_applies_repeated_speaker_blocks(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nRUSL\nHello.\nFADO\nHey!\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 4, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.SPEAKER, text="RUSL", order=2),
        HierarchyMark(2, 2, 2, HierarchyType.TEXT, order=3),
    ]
    dialog._hierarchy_mark_order = 3
    messages = []

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.information",
        lambda _parent, title, text: messages.append((title, text)),
    )

    def fail_provider_lookup():
        raise AssertionError("Continue from marked examples must not use an AI provider.")

    monkeypatch.setattr(dialog, "_create_hierarchy_ai_provider", fail_provider_lookup)

    dialog._continue_hierarchy_from_examples()

    assert messages
    assert messages[-1][0] == "Continue from marked examples"
    assert "Added 2 local hierarchy marks." in messages[-1][1]
    assert {mark.text for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.SPEAKER} == {
        "RUSL",
        "FADO",
    }
    assert "**RUSL**: Hello." in dialog._psm_text
    assert "**FADO**: Hey!" in dialog._psm_text


def test_studio_continue_finds_learned_context_inside_existing_text(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "MIDNA\n"
        "Known line.\n"
        "(Example condition}\n"
        "Example reply.\n"
        "(Another condition}\n"
        "Another reply.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 3, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 1, 4, HierarchyType.TEXT, order=2),
        HierarchyMark(
            2,
            2,
            4,
            HierarchyType.CONTEXT,
            text="Example condition",
            start_col=1,
            end_col=18,
            order=3,
        ),
        HierarchyMark(3, 5, 5, HierarchyType.TEXT, order=4),
    ]
    dialog._hierarchy_mark_order = 5
    assert dialog._unmarked_ranges(dialog.raw_edit.toPlainText().splitlines()) == []
    messages = []
    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.information",
        lambda _parent, title, text: messages.append((title, text)),
    )

    dialog._continue_hierarchy_from_examples()

    assert "Added 1 local hierarchy marks." in messages[-1][1]
    contexts = sorted(
        (mark.start_line, mark.text, mark.start_col, mark.end_col)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.CONTEXT
    )
    assert contexts == [
        (2, "Example condition", 1, 18),
        (4, "Another condition", 1, 18),
    ]
    assert sorted(
        (mark.start_line, mark.end_line, mark.depth)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT
    ) == [(1, 1, 4), (3, 3, 5), (5, 5, 5)]


def test_studio_continue_fills_speaker_on_synthetic_scene_start(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "TALO\nTime to practice!\n~~~~~~~~~~~~~~~~\nMALO\nKnown line.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(
            0, 2, 2, HierarchyType.STRUCTURE, text="Scene 4", order=1
        ),
        HierarchyMark(3, 3, 3, HierarchyType.SPEAKER, text="MALO", order=2),
        HierarchyMark(4, 4, 4, HierarchyType.TEXT, order=3),
    ]
    dialog._hierarchy_mark_order = 4
    messages = []
    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.information",
        lambda _parent, title, text: messages.append((title, text)),
    )

    dialog._continue_hierarchy_from_examples()

    assert "Added 2 local hierarchy marks." in messages[-1][1]
    assert any(
        mark.type_id == HierarchyType.SPEAKER
        and mark.start_line == 0
        and mark.text == "TALO"
        for mark in dialog.hierarchy_marks
    )
    assert any(
        mark.type_id == HierarchyType.TEXT
        and (mark.start_line, mark.end_line) == (1, 1)
        for mark in dialog.hierarchy_marks
    )


def test_studio_continue_learns_custom_type_and_splits_existing_text(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    custom_type = "custom:camera"
    dialog.hierarchy_type_definitions[custom_type] = HierarchyTypeDefinition(
        custom_type,
        "Camera",
        "Camera direction",
        "#dceeff",
    )
    dialog.raw_edit.setPlainText(
        "MIDNA\n"
        "Known line.\n"
        "<Camera: close-up>\n"
        "Reply.\n"
        "<Camera: wide shot>\n"
        "Next reply.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 3, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 5, 4, HierarchyType.TEXT, order=2),
        HierarchyMark(
            2,
            2,
            4,
            custom_type,
            text="Camera: close-up",
            start_col=1,
            end_col=17,
            order=3,
        ),
    ]
    dialog._hierarchy_mark_order = 4
    messages = []
    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.information",
        lambda _parent, title, text: messages.append((title, text)),
    )

    dialog._continue_hierarchy_from_examples()

    assert "Added 1 local hierarchy marks." in messages[-1][1]
    assert "Other/custom types: 1" in messages[-1][1]
    assert sorted(
        (mark.start_line, mark.text, mark.start_col, mark.end_col)
        for mark in dialog.hierarchy_marks
        if mark.type_id == custom_type
    ) == [
        (2, "Camera: close-up", 1, 17),
        (4, "Camera: wide shot", 1, 18),
    ]
    assert sorted(
        (mark.start_line, mark.end_line)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT
    ) == [(1, 1), (3, 3), (5, 5)]


def test_studio_continue_fills_unicode_speaker_with_number_suffix(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "MIDNA\nKnown line.\nCAFÉ MAN #1\nWelcome to my shop.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 1, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(1, 1, 2, HierarchyType.TEXT, order=2),
    ]
    dialog._hierarchy_mark_order = 3
    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMessageBox.information",
        lambda *_args: None,
    )

    dialog._continue_hierarchy_from_examples()

    assert any(
        mark.type_id == HierarchyType.SPEAKER
        and mark.start_line == 2
        and mark.text == "CAFÉ MAN #1"
        for mark in dialog.hierarchy_marks
    )
    assert any(
        mark.type_id == HierarchyType.TEXT
        and (mark.start_line, mark.end_line) == (3, 3)
        for mark in dialog.hierarchy_marks
    )


def test_studio_hierarchy_ai_progress_shows_scope_and_elapsed_time(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    progress_values = []
    step_updates = []

    class FakeStatus:
        is_running = True
        detail = ""

        def update_progress(self, value):
            progress_values.append(value)

        def set_detail_text(self, text):
            self.detail = text

        def update_step(self, index, text, status):
            step_updates.append((index, text, status))

    status = FakeStatus()
    dialog._hierarchy_ai_status = status
    dialog._hierarchy_ai_started_at = 10.0
    monkeypatch.setattr("ui.script_markup_studio_dialog.time.monotonic", lambda: 75.0)

    dialog._on_hierarchy_ai_progress(1, 3, "Act One")

    assert progress_values == [0]
    assert "Scope 1/3: Act One" in status.detail
    assert "Waiting for AI response... elapsed 01:05" in status.detail
    assert step_updates == [(1, "Processing structure 1/3", 1)]


def test_studio_auto_join_duplicate_structures_does_not_require_single_line_headings(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Part A\nFirst block.\nPart A\nSecond block.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 1, 0, HierarchyType.STRUCTURE, text="Part A", order=1),
        HierarchyMark(2, 3, 0, HierarchyType.STRUCTURE, text="Part A", order=2),
    ]
    dialog._refresh()

    changed = dialog._auto_join_adjacent_duplicate_structures()
    dialog._apply_ignore_precedence()
    dialog._refresh()

    assert changed == 1
    structures = [
        mark for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.STRUCTURE
    ]
    assert [(mark.start_line, mark.end_line, mark.text) for mark in structures] == [
        (0, 3, "Part A"),
    ]
    ignored = [
        mark for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.IGNORE
    ]
    assert [(mark.start_line, mark.end_line) for mark in ignored] == [(2, 2)]
    assert dialog._psm_text.count("# Part A") == 1


def test_studio_auto_join_duplicate_structures_respects_breaker_boundaries(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Scene\nBeat one.\n~~~~~\nScene\nBeat two.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 1, 1, HierarchyType.STRUCTURE, text="Scene", order=1),
        HierarchyMark(2, 2, 1, HierarchyType.BREAKER, order=2),
        HierarchyMark(3, 4, 1, HierarchyType.STRUCTURE, text="Scene", order=3),
    ]
    dialog._refresh()

    assert dialog._auto_join_adjacent_duplicate_structures() == 0
    structures = [
        mark for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.STRUCTURE
    ]
    assert [(mark.start_line, mark.end_line, mark.text) for mark in structures] == [
        (0, 1, "Scene"),
        (3, 4, "Scene"),
    ]


def test_studio_prepares_ai_markup_jobs_by_structure_when_full_prompt_is_too_large(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nA\n" + ("x" * 120) + "\nAct Two\nB\n" + ("y" * 120) + "\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 2, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(3, 5, 0, HierarchyType.STRUCTURE, text="Act Two", order=2),
    ]
    dialog._refresh()

    def fake_builder(payload, max_prompt_chars=None):
        scope = payload.get("scope") or {}
        label = scope.get("label") or "full script"
        if label == "full script":
            raise HierarchyAIPromptTooLarge("full prompt too large")
        return SimpleNamespace(
            scope_label=label,
            prompt_chars=100,
            unmarked_range_count=len(payload.get("unmarked_ranges", [])),
            messages=[],
        )

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.build_hierarchy_auto_markup_messages",
        fake_builder,
    )

    jobs = dialog._prepare_hierarchy_ai_jobs(
        dialog.raw_edit.toPlainText().splitlines(),
        dialog._unmarked_ranges(dialog.raw_edit.toPlainText().splitlines()),
    )

    assert [job.scope_label.split(" (raw script")[0] for job in jobs] == ["Act One", "Act Two"]


def test_studio_ai_markup_reports_raw_line_when_even_single_scope_is_too_large(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(("Very long line\n") * 20)
    dialog._refresh()

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.build_hierarchy_auto_markup_messages",
        lambda _payload, max_prompt_chars=None: (_ for _ in ()).throw(
            HierarchyAIPromptTooLarge("full prompt too large")
        ),
    )

    try:
        dialog._prepare_hierarchy_ai_jobs(
            dialog.raw_edit.toPlainText().splitlines(),
            dialog._unmarked_ranges(dialog.raw_edit.toPlainText().splitlines()),
        )
    except HierarchyAIPromptTooLarge as exc:
        assert "A raw script section is too large" in str(exc)
        assert "raw script line 1" in str(exc)
    else:
        raise AssertionError("Expected raw-scope guidance for too-large script.")


def test_studio_ai_markup_prepares_unstructured_scope_outside_structures(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Outside structure\nAct One\nInside structure\n")
    dialog.hierarchy_marks = [
        HierarchyMark(1, 2, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
    ]
    dialog._refresh()

    def fake_builder(payload, max_prompt_chars=None):
        scope = payload.get("scope") or {}
        label = scope.get("label") or "full script"
        if label == "full script":
            raise HierarchyAIPromptTooLarge("full prompt too large")
        return SimpleNamespace(
            scope_label=label,
            prompt_chars=100,
            unmarked_range_count=len(payload.get("unmarked_ranges", [])),
            messages=[],
        )

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.build_hierarchy_auto_markup_messages",
        fake_builder,
    )

    jobs = dialog._prepare_hierarchy_ai_jobs(
        dialog.raw_edit.toPlainText().splitlines(),
        dialog._unmarked_ranges(dialog.raw_edit.toPlainText().splitlines()),
    )

    assert jobs[0].scope_label == "Unstructured source (raw script line 1)"
    assert jobs[1].scope_label.startswith("Act One")
    assert "lines 1-1" not in jobs[0].scope_label


def test_studio_hierarchy_template_payload_loads_type_definitions_only(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Camera pans.\n")
    dialog.hierarchy_type_definitions["custom:camera"] = HierarchyTypeDefinition(
        "custom:camera",
        "Camera",
        "Camera direction.",
        "#abc123",
    )
    dialog._rebuild_hierarchy_type_combo()
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 1, "custom:camera", text="Camera pans", order=1),
    ]
    dialog._refresh()

    payload = dialog._hierarchy_template_payload()
    restored = _make_dialog(qapp)

    assert restored._apply_hierarchy_template_payload(payload)

    assert restored.hierarchy_marks == []
    assert restored.hierarchy_type_definitions["custom:camera"].label == "Camera"
    assert restored.hierarchy_type_definitions["custom:camera"].color == "#abc123"
    assert payload["examples"][0]["source_excerpt"] == "Camera pans."
    assert payload["ai_instructions"]


def test_studio_undo_redo_restores_raw_text(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)

    dialog.raw_edit.setPlainText("Act One\n")
    dialog._flush_pending_history()

    assert dialog.raw_edit.toPlainText() == "Act One\n"
    assert dialog._undo_history()
    assert dialog.raw_edit.toPlainText() == ""
    assert dialog._redo_history()
    assert dialog.raw_edit.toPlainText() == "Act One\n"


def test_studio_ctrl_z_keeps_raw_editor_at_edited_location(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    lines = [f"Script line {idx}" for idx in range(260)]
    original = "\n".join(lines)
    dialog.raw_edit.setPlainText(original)
    dialog._flush_pending_history()
    dialog.resize(1000, 700)
    dialog.show()
    qapp.processEvents()

    block = dialog.raw_edit.document().findBlockByNumber(190)
    cursor = dialog.raw_edit.textCursor()
    cursor.setPosition(block.position() + len(block.text()))
    dialog.raw_edit.setTextCursor(cursor)
    dialog.raw_edit.centerCursor()
    qapp.processEvents()
    cursor.insertText(" changed")
    dialog.raw_edit.setTextCursor(cursor)
    qapp.processEvents()
    visible_before = dialog.raw_edit.firstVisibleBlock().blockNumber()

    QTest.keyClick(
        dialog.raw_edit,
        Qt.Key.Key_Z,
        Qt.KeyboardModifier.ControlModifier,
    )
    qapp.processEvents()

    assert dialog.raw_edit.toPlainText() == original
    assert visible_before > 100
    assert dialog.raw_edit.firstVisibleBlock().blockNumber() >= visible_before - 2
    assert dialog.raw_edit.textCursor().blockNumber() == 190


def test_studio_undo_redo_restores_hierarchy_marks_and_depth(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\n")
    dialog._flush_pending_history()
    _set_hierarchy_type(dialog, HierarchyType.STRUCTURE)
    _select_lines(dialog, 0, 0)

    dialog._mark_selection_as_hierarchy()

    assert len(dialog.hierarchy_marks) == 1
    assert dialog._undo_history()
    assert dialog.hierarchy_marks == []
    assert dialog._redo_history()
    assert len(dialog.hierarchy_marks) == 1

    key = dialog._hierarchy_mark_key(dialog.hierarchy_marks[0])
    dialog._change_outline_depth_keys([key], 1)

    assert dialog.hierarchy_marks[0].depth == 1
    assert dialog._undo_history()
    assert dialog.hierarchy_marks[0].depth == 0
    assert dialog._redo_history()
    assert dialog.hierarchy_marks[0].depth == 1


def test_studio_undo_redo_restores_saved_editor_changes(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nChapter One\nMIDNA\nHello.\n")
    dialog._flush_pending_history()
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 2, 1, HierarchyType.STRUCTURE, text="Chapter One", order=2),
    ]
    dialog._hierarchy_mark_order = 2
    dialog._refresh()
    dialog._record_history()
    mark_key = dialog._hierarchy_mark_key(dialog.hierarchy_marks[1])

    assert dialog._start_range_edit(mark_key)
    dialog.hierarchy_depth_spin.setValue(2)
    _set_hierarchy_type(dialog, HierarchyType.ACTION)
    dialog.hierarchy_label_edit.setText("Door opens")
    dialog._mark_selection_as_hierarchy()

    edited = next(mark for mark in dialog.hierarchy_marks if mark.order == 2)
    assert edited.depth == 2
    assert edited.type_id == HierarchyType.ACTION
    assert edited.text == "Door opens"

    assert dialog._undo_history()
    restored = next(mark for mark in dialog.hierarchy_marks if mark.order == 2)
    assert restored.depth == 1
    assert restored.type_id == HierarchyType.STRUCTURE
    assert restored.text == "Chapter One"

    assert dialog._redo_history()
    redone = next(mark for mark in dialog.hierarchy_marks if mark.order == 2)
    assert redone.depth == 2
    assert redone.type_id == HierarchyType.ACTION
    assert redone.text == "Door opens"


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


def test_studio_opens_builder_project_at_exact_line_without_reloading_it_twice(qapp, tmp_path):
    source = _make_dialog(qapp)
    _use_hierarchy_mode(source)
    source.raw_edit.setPlainText("Act\nMIDNA\nFirst line\nSecond line\n")
    source.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act", order=1),
        HierarchyMark(1, 1, 1, HierarchyType.SPEAKER, text="MIDNA", order=2),
        HierarchyMark(2, 3, 2, HierarchyType.TEXT, order=3),
    ]
    source._refresh()
    project_path = tmp_path / "script_markup_project.json"
    project_path.write_text(
        json.dumps(source._hierarchy_project_payload()),
        encoding="utf-8",
    )
    studio = _make_dialog(qapp)

    assert studio.open_hierarchy_project_at_line(str(project_path), 2)
    assert studio.current_hierarchy_project_path == str(project_path.resolve())
    assert studio.raw_edit.textCursor().blockNumber() == 2
    assert studio.flags_list.currentItem() is not None

    studio.raw_edit.appendPlainText("Unsaved new markup")
    assert studio.open_hierarchy_project_at_line(str(project_path), 3)
    assert studio.raw_edit.textCursor().blockNumber() == 3
    assert "Unsaved new markup" in studio.raw_edit.toPlainText()


def test_studio_assigns_linked_dialogue_to_speaker_and_saves(qapp, tmp_path):
    studio = _make_dialog(qapp)
    _use_hierarchy_mode(studio)
    studio.raw_edit.setPlainText("LETTER\nAbout Mail Delivery\n")
    studio.hierarchy_marks = [
        HierarchyMark(
            0, 0, 3, HierarchyType.SPEAKER, text="LETTER", order=1,
            origin="speaker_assignment",
        ),
        HierarchyMark(1, 1, 4, HierarchyType.TEXT, order=2),
    ]
    studio._refresh()
    project_path = tmp_path / "script_markup_project.json"
    project_path.write_text(
        json.dumps(studio._hierarchy_project_payload()), encoding="utf-8"
    )
    studio.current_hierarchy_project_path = str(project_path.resolve())

    assert studio.assign_speaker_at_line(str(project_path), 1, "POSTMAN")

    assert studio.hierarchy_marks[0].text == "POSTMAN"
    saved = json.loads(project_path.read_text(encoding="utf-8"))
    assert saved["hierarchy_marks"][0]["text"] == "POSTMAN"


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


def test_studio_ctrl_wheel_zooms_raw_text(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    calls = []
    monkeypatch.setattr(dialog.raw_edit, "zoomIn", lambda steps=1: calls.append(("in", steps)))
    monkeypatch.setattr(dialog.raw_edit, "_sync_viewport_margins", lambda: None)

    class WheelEvent:
        def modifiers(self):
            return Qt.KeyboardModifier.ControlModifier

        def angleDelta(self):
            return QPoint(0, 120)

        def accept(self):
            calls.append(("accepted", 0))

    dialog.raw_edit.wheelEvent(WheelEvent())

    assert calls == [("in", 1), ("accepted", 0)]


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


def test_studio_raw_script_uses_dedicated_hierarchy_gutter_without_text_margin(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nScene One\nILIA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Scene One", order=2),
        HierarchyMark(2, 3, 3, HierarchyType.SPEAKER, text="ILIA", order=3),
        HierarchyMark(3, 3, 4, HierarchyType.TEXT, order=4),
    ]

    dialog._refresh()

    doc = dialog.raw_edit.document()
    assert dialog.raw_edit.viewportMargins().left() == _RAW_HIERARCHY_GUTTER_WIDTH
    assert dialog.raw_edit.hierarchy_gutter.width() == _RAW_HIERARCHY_GUTTER_WIDTH
    assert doc.findBlockByNumber(0).blockFormat().leftMargin() == 0
    assert doc.findBlockByNumber(1).blockFormat().leftMargin() == 0
    assert doc.findBlockByNumber(2).blockFormat().leftMargin() == 0
    assert doc.findBlockByNumber(3).blockFormat().leftMargin() == 0


def test_studio_raw_script_deep_nodes_do_not_push_text_right(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Deep line\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 0, 12, HierarchyType.TEXT, order=1),
    ]

    dialog._refresh()

    assert dialog.raw_edit.document().findBlockByNumber(0).blockFormat().leftMargin() == 0


def test_studio_raw_script_can_collapse_and_expand_hierarchy_node(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Act One\nScene One\nILIA\nHello.\n")
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 0, HierarchyType.STRUCTURE, text="Act One", order=1),
        HierarchyMark(1, 3, 1, HierarchyType.STRUCTURE, text="Scene One", order=2),
        HierarchyMark(2, 3, 3, HierarchyType.SPEAKER, text="ILIA", order=3),
        HierarchyMark(3, 3, 4, HierarchyType.TEXT, order=4),
    ]
    dialog._refresh()
    scene_key = dialog._hierarchy_mark_key(dialog.hierarchy_marks[1])

    assert scene_key in dialog._raw_fold_headers.values()
    assert dialog.raw_edit.document().findBlockByNumber(2).isVisible()

    assert dialog._toggle_raw_hierarchy_fold(scene_key)

    assert not dialog.raw_edit.document().findBlockByNumber(2).isVisible()
    assert not dialog.raw_edit.document().findBlockByNumber(3).isVisible()
    assert dialog._raw_fold_extra_selections()

    assert dialog._toggle_raw_hierarchy_fold(scene_key)

    assert dialog.raw_edit.document().findBlockByNumber(2).isVisible()
    assert dialog.raw_edit.document().findBlockByNumber(3).isVisible()


def test_studio_action_inside_text_splits_text_node(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "ILIA\n"
        "Oh, hi, Link.\n"
        "I washed Epona for you!\n"
        "[*Link plucks a reed from the ground*]\n"
        "It's such a nice melody...\n"
        "Epona looks happy.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 5, 4, HierarchyType.SPEAKER, text="ILIA", order=1),
        HierarchyMark(1, 5, 5, HierarchyType.TEXT, order=2),
    ]
    dialog._hierarchy_mark_order = 3
    dialog._refresh()
    _set_hierarchy_type(dialog, HierarchyType.ACTION)
    dialog.hierarchy_depth_spin.setValue(5)
    _select_lines(dialog, 3, 3)

    dialog._mark_selection_as_hierarchy()

    text_ranges = sorted(
        (mark.start_line, mark.end_line)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT
    )
    action = next(mark for mark in dialog.hierarchy_marks if mark.type_id == HierarchyType.ACTION)
    assert text_ranges == [(1, 2), (4, 5)]
    assert action.depth == 5
    speaker_item = dialog.flags_list.topLevelItem(0)
    assert speaker_item.isExpanded()
    assert speaker_item.childCount() == 3
    assert "Text" in speaker_item.child(0).text(0)
    assert "Action" in speaker_item.child(1).text(0)
    assert "Text" in speaker_item.child(2).text(0)
    assert dialog._psm_text == (
        "**ILIA**: Oh, hi, Link. I washed Epona for you!\n"
        "\n"
        "[*Link plucks a reed from the ground*]\n"
        "\n"
        "**ILIA**: It's such a nice melody... Epona looks happy.\n"
    )


def test_studio_text_added_after_actions_splits_around_existing_actions(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "CORO\n"
        "First dialogue.\n"
        "[After clearing the twilight]\n"
        "Second dialogue.\n"
        "[Coro gives Link the small key]\n"
        "Third dialogue.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 5, 3, HierarchyType.SPEAKER, text="CORO", order=1),
        HierarchyMark(2, 2, 4, HierarchyType.ACTION, order=2),
        HierarchyMark(4, 4, 4, HierarchyType.ACTION, order=3),
    ]
    dialog._hierarchy_mark_order = 4
    dialog._refresh()
    _set_hierarchy_type(dialog, HierarchyType.TEXT)
    dialog.hierarchy_depth_spin.setValue(4)
    _select_lines(dialog, 1, 5)

    dialog._mark_selection_as_hierarchy()

    assert sorted(
        (mark.start_line, mark.end_line, mark.depth)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT
    ) == [(1, 1, 4), (3, 3, 4), (5, 5, 4)]
    speaker_item = dialog.flags_list.topLevelItem(0)
    assert [
        "Text" if "Text" in speaker_item.child(index).text(0) else "Action"
        for index in range(5)
    ] == ["Text", "Action", "Text", "Action", "Text"]
    assert dialog._psm_text == (
        "**CORO**: First dialogue.\n"
        "\n"
        "[*After clearing the twilight*]\n"
        "\n"
        "**CORO**: Second dialogue.\n"
        "\n"
        "[*Coro gives Link the small key*]\n"
        "\n"
        "**CORO**: Third dialogue.\n"
    )


def test_studio_text_added_after_custom_node_splits_around_it(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "MIDNA\n"
        "First dialogue.\n"
        "<Camera: close-up>\n"
        "Second dialogue.\n"
    )
    custom_type = "custom:camera"
    dialog.hierarchy_marks = [
        HierarchyMark(0, 3, 3, HierarchyType.SPEAKER, text="MIDNA", order=1),
        HierarchyMark(
            2,
            2,
            4,
            custom_type,
            text="Camera: close-up",
            start_col=1,
            end_col=17,
            order=2,
        ),
        HierarchyMark(1, 3, 4, HierarchyType.TEXT, order=3),
    ]

    dialog._refresh()

    assert sorted(
        (mark.start_line, mark.end_line, mark.depth)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT
    ) == [(1, 1, 4), (3, 3, 4)]
    custom = next(mark for mark in dialog.hierarchy_marks if mark.type_id == custom_type)
    assert custom.depth == 4


def test_studio_splits_selected_text_into_blank_line_paragraphs(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Scene One\n"
        "\n"
        "First paragraph, first wrapped line.\n"
        "First paragraph, second wrapped line.\n"
        "\n"
        "Second paragraph.\n"
        "\n"
        "Third paragraph.\n"
        "\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 8, 0, HierarchyType.STRUCTURE, text="Scene One", order=1),
        HierarchyMark(2, 7, 2, HierarchyType.TEXT, order=2),
    ]
    dialog._hierarchy_mark_order = 3
    _set_hierarchy_type(dialog, HierarchyType.TEXT)
    dialog.hierarchy_depth_spin.setValue(2)
    dialog.hierarchy_split_text_cb.setChecked(True)
    _select_lines(dialog, 2, 7)

    dialog._mark_selection_as_hierarchy()

    assert sorted(
        (mark.start_line, mark.end_line, mark.depth)
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT
    ) == [(2, 3, 2), (5, 5, 2), (7, 7, 2)]
    assert not any(
        mark.type_id == HierarchyType.SPEAKER
        for mark in dialog.hierarchy_marks
    )
    assert all(
        not dialog.raw_edit.document().findBlockByNumber(line_no).text()
        for line_no in (1, 4, 6, 8)
    )


def test_studio_assigns_paragraph_text_to_editable_speaker_choice(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("\nParagraph one.\n\nParagraph two.\nZELDA\n")
    dialog.hierarchy_marks = [
        HierarchyMark(1, 1, 1, HierarchyType.TEXT, order=1),
        HierarchyMark(3, 3, 1, HierarchyType.TEXT, order=2),
        HierarchyMark(4, 4, 0, HierarchyType.SPEAKER, text="ZELDA", order=3),
    ]
    dialog._hierarchy_mark_order = 4
    captured = {}

    def choose_speaker(_parent, _title, _label, items, current, editable):
        captured["items"] = items
        captured["current"] = current
        captured["editable"] = editable
        return "MIDNA", True

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QInputDialog.getItem",
        choose_speaker,
    )
    dialog._refresh()
    dialog.resize(1000, 700)
    dialog.show()
    qapp.processEvents()
    text_item = _find_tree_item(dialog.flags_list, "Paragraph one")
    dialog.flags_list.setCurrentItem(text_item)
    text_item.setSelected(True)

    def choose_assign_action(menu, _global_pos):
        captured["actions"] = [action.text() for action in menu.actions()]
        return next(
            action
            for action in menu.actions()
            if action.text() == "Assign to speaker..."
        )

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMenu.exec",
        choose_assign_action,
    )

    dialog._show_outline_context_menu(
        dialog.flags_list.visualItemRect(text_item).center()
    )

    assigned = next(
        mark
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.SPEAKER and mark.origin == "speaker_assignment"
    )
    assert captured["items"] == ["ZELDA"]
    assert captured["current"] == 0
    assert captured["editable"] is True
    assert "Assign to speaker..." in captured["actions"]
    assert (assigned.text, assigned.origin, assigned.approved) == (
        "MIDNA",
        "speaker_assignment",
        True,
    )
    assert (assigned.start_line, assigned.depth) == (1, 1)
    second_text = next(
        mark
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT and mark.start_line == 3
    )
    assert second_text.depth == 1
    assert _find_tree_item(dialog.flags_list, "Paragraph two").parent() is None
    assert "**MIDNA**: Paragraph one." in dialog._psm_text


def test_studio_assigned_speaker_stays_inside_structure_starting_on_text_line(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "5. Hidden Skills\n"
        "Part 1\n"
        "Old teaching.\n"
        "\n"
        "We meet again. You have a little more skill.\n"
    )
    dialog.hierarchy_marks = [
        HierarchyMark(0, 4, 1, HierarchyType.STRUCTURE, text="5. Hidden Skills", order=1),
        HierarchyMark(1, 3, 2, HierarchyType.STRUCTURE, text="Part 1", order=2),
        HierarchyMark(2, 2, 3, HierarchyType.SPEAKER, text="HERO'S SHADE", order=3),
        HierarchyMark(2, 2, 4, HierarchyType.TEXT, order=4),
        # A manually named Structure may begin on the same source line as its
        # first Text. The preceding blank line still belongs to Part 1.
        HierarchyMark(4, 4, 2, HierarchyType.STRUCTURE, text="Part 2", order=5),
        HierarchyMark(4, 4, 4, HierarchyType.TEXT, order=6),
    ]
    dialog._hierarchy_mark_order = 7
    dialog._refresh()
    text = next(
        mark
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.TEXT and mark.start_line == 4
    )

    assert dialog._assign_text_marks_to_speaker(
        [dialog._hierarchy_mark_key(text)],
        "HERO'S SHADE",
    ) == 1

    speaker = next(
        mark
        for mark in dialog.hierarchy_marks
        if mark.type_id == HierarchyType.SPEAKER
        and mark.origin == "speaker_assignment"
    )
    assert (speaker.start_line, speaker.depth) == (4, 4)
    assert text.depth == 5

    part_2_item = _find_tree_item(dialog.flags_list, "Structure: Part 2")
    speaker_item = _find_tree_item(dialog.flags_list, "Speaker: HERO'S SHADE")
    text_item = _find_tree_item(dialog.flags_list, "Text: We meet again")
    assert speaker_item.parent() is part_2_item
    assert text_item.parent() is speaker_item


def test_studio_reassign_repairs_speaker_anchored_before_current_structure(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "5. Hidden Skills\nPart 1\nOld teaching.\n\nWe meet again.\n"
    )
    stale_speaker = HierarchyMark(
        3,
        3,
        4,
        HierarchyType.SPEAKER,
        text="HERO'S SHADE",
        order=4,
        origin="speaker_assignment",
    )
    text = HierarchyMark(4, 4, 5, HierarchyType.TEXT, order=6)
    dialog.hierarchy_marks = [
        HierarchyMark(0, 4, 1, HierarchyType.STRUCTURE, text="5. Hidden Skills", order=1),
        HierarchyMark(1, 3, 2, HierarchyType.STRUCTURE, text="Part 1", order=2),
        stale_speaker,
        HierarchyMark(4, 4, 2, HierarchyType.STRUCTURE, text="Part 2", order=5),
        text,
    ]
    dialog._hierarchy_mark_order = 7
    dialog._refresh()

    assert dialog._assign_text_marks_to_speaker(
        [dialog._hierarchy_mark_key(text)],
        "HERO'S SHADE",
    ) == 1

    assigned_speakers = [
        mark
        for mark in dialog.hierarchy_marks
        if mark.origin == "speaker_assignment"
    ]
    assert assigned_speakers == [stale_speaker]
    assert (stale_speaker.start_line, stale_speaker.end_line, stale_speaker.depth) == (4, 4, 4)
    assert text.depth == 5
    part_2_item = _find_tree_item(dialog.flags_list, "Structure: Part 2")
    speaker_item = _find_tree_item(dialog.flags_list, "Speaker: HERO'S SHADE")
    assert speaker_item.parent() is part_2_item


def test_studio_bulk_converts_speaker_text_blocks_to_item_entries(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText(
        "Collection Screen\nWallet\nA wallet from your childhood.\n"
        "Big Wallet\nA wallet with greater capacity.\n"
    )
    wallet = HierarchyMark(1, 1, 4, HierarchyType.SPEAKER, text="Wallet", order=2)
    wallet_description = HierarchyMark(2, 2, 5, HierarchyType.TEXT, order=3)
    big_wallet = HierarchyMark(3, 3, 4, HierarchyType.SPEAKER, text="Big Wallet", order=4)
    big_wallet_description = HierarchyMark(4, 4, 5, HierarchyType.TEXT, order=5)
    dialog.hierarchy_marks = [
        HierarchyMark(0, 4, 1, HierarchyType.STRUCTURE, text="Collection Screen", order=1),
        wallet,
        wallet_description,
        big_wallet,
        big_wallet_description,
    ]
    dialog._refresh()

    assert dialog._convert_speaker_blocks_to_items([
        dialog._hierarchy_mark_key(wallet),
        dialog._hierarchy_mark_key(big_wallet),
    ]) == 4

    assert (wallet.type_id, wallet.depth) == (HierarchyType.ITEM, 4)
    assert (wallet_description.type_id, wallet_description.depth) == (
        HierarchyType.ITEM_DESCRIPTION,
        5,
    )
    assert (big_wallet.type_id, big_wallet_description.type_id) == (
        HierarchyType.ITEM,
        HierarchyType.ITEM_DESCRIPTION,
    )
    assert not any(mark.type_id == HierarchyType.SPEAKER for mark in dialog.hierarchy_marks)
    assert not any(mark.type_id == HierarchyType.TEXT for mark in dialog.hierarchy_marks)
    assert "- **Wallet**: A wallet from your childhood." in dialog._psm_text

    assert dialog._convert_item_blocks_to_speakers([
        dialog._hierarchy_mark_key(wallet),
        dialog._hierarchy_mark_key(big_wallet),
    ]) == 4

    assert (wallet.type_id, wallet.depth) == (HierarchyType.SPEAKER, 4)
    assert (wallet_description.type_id, wallet_description.depth) == (
        HierarchyType.TEXT,
        5,
    )
    assert (big_wallet.type_id, big_wallet_description.type_id) == (
        HierarchyType.SPEAKER,
        HierarchyType.TEXT,
    )


def test_studio_context_menu_converts_speaker_and_item_blocks_both_ways(
    qapp,
    monkeypatch,
):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Wallet\nA wallet from your childhood.\n")
    wallet = HierarchyMark(0, 0, 3, HierarchyType.SPEAKER, text="Wallet", order=1)
    description = HierarchyMark(1, 1, 4, HierarchyType.TEXT, order=2)
    dialog.hierarchy_marks = [wallet, description]
    dialog._refresh()
    dialog.resize(1000, 700)
    dialog.show()
    qapp.processEvents()

    captured_actions = []

    def choose_conversion(menu, _global_pos):
        actions = [action for action in menu.actions() if action.text()]
        captured_actions.append([action.text() for action in actions])
        expected = (
            "Convert Speaker Block to Item"
            if wallet.type_id == HierarchyType.SPEAKER
            else "Convert Item Block to Speaker"
        )
        return next(action for action in actions if action.text() == expected)

    monkeypatch.setattr(
        "ui.script_markup_studio_dialog.QMenu.exec",
        choose_conversion,
    )

    speaker_item = _find_tree_item(dialog.flags_list, "Speaker: Wallet")
    dialog.flags_list.setCurrentItem(speaker_item)
    speaker_item.setSelected(True)
    dialog._show_outline_context_menu(
        dialog.flags_list.visualItemRect(speaker_item).center()
    )
    assert (wallet.type_id, description.type_id) == (
        HierarchyType.ITEM,
        HierarchyType.ITEM_DESCRIPTION,
    )

    item = _find_tree_item(dialog.flags_list, "Item: Wallet")
    dialog.flags_list.setCurrentItem(item)
    item.setSelected(True)
    dialog._show_outline_context_menu(
        dialog.flags_list.visualItemRect(item).center()
    )
    assert (wallet.type_id, description.type_id) == (
        HierarchyType.SPEAKER,
        HierarchyType.TEXT,
    )
    assert "Convert Speaker Block to Item" in captured_actions[0]
    assert "Convert Item Block to Speaker" in captured_actions[1]
    assert dialog._undo_history() is True
    assert [mark.type_id for mark in dialog.hierarchy_marks] == [
        HierarchyType.ITEM,
        HierarchyType.ITEM_DESCRIPTION,
    ]


def test_studio_old_project_type_payload_gains_builtin_item_types(qapp):
    dialog = _make_dialog(qapp)
    old_structure = default_type_definitions()[HierarchyType.STRUCTURE]

    dialog._apply_hierarchy_type_payload([
        dialog._hierarchy_type_to_dict(old_structure),
    ])

    assert HierarchyType.ITEM in dialog.hierarchy_type_definitions
    assert HierarchyType.ITEM_DESCRIPTION in dialog.hierarchy_type_definitions
    assert dialog.hierarchy_type_combo.findData(HierarchyType.ITEM) == -1
    assert dialog.hierarchy_type_combo.findData(HierarchyType.ITEM_DESCRIPTION) == -1
    assert dialog.hierarchy_type_combo.findData(HierarchyType.SPEAKER) >= 0
    assert dialog.hierarchy_role_combo.findData("item") >= 0


def test_studio_role_switch_retags_speaker_children_and_back(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog.raw_edit.setPlainText("Wallet\nA wallet from your childhood.\n")
    parent = HierarchyMark(0, 0, 4, HierarchyType.SPEAKER, order=1)
    child = HierarchyMark(1, 1, 5, HierarchyType.TEXT, order=2)
    dialog.hierarchy_marks = [parent, child]
    dialog._refresh()

    assert dialog._start_range_edit(dialog._hierarchy_mark_key(parent))
    assert dialog.hierarchy_type_combo.currentData() == HierarchyType.SPEAKER
    assert dialog.hierarchy_role_combo.currentData() == "speaker"
    dialog.hierarchy_role_combo.setCurrentIndex(
        dialog.hierarchy_role_combo.findData("item")
    )
    assert dialog._save_hierarchy_edit()

    assert parent.type_id == HierarchyType.ITEM
    assert child.type_id == HierarchyType.ITEM_DESCRIPTION
    assert _find_tree_item(dialog.flags_list, "Item: Wallet") is not None
    assert _find_tree_item(dialog.flags_list, "Item Description: A wallet") is not None

    assert dialog._start_range_edit(dialog._hierarchy_mark_key(parent))
    dialog.hierarchy_role_combo.setCurrentIndex(
        dialog.hierarchy_role_combo.findData("speaker")
    )
    assert dialog._save_hierarchy_edit()

    assert parent.type_id == HierarchyType.SPEAKER
    assert child.type_id == HierarchyType.TEXT


def test_studio_item_role_maps_speaker_and_text_tools_without_extra_picker_types(qapp):
    dialog = _make_dialog(qapp)
    _use_hierarchy_mode(dialog)
    dialog._select_hierarchy_type_id(HierarchyType.SPEAKER)
    dialog.hierarchy_role_combo.setCurrentIndex(
        dialog.hierarchy_role_combo.findData("item")
    )

    assert dialog._current_hierarchy_type_id() == HierarchyType.ITEM
    assert dialog.hierarchy_type_combo.currentData() == HierarchyType.SPEAKER

    dialog._select_hierarchy_type_id(HierarchyType.ITEM_DESCRIPTION)
    assert dialog._current_hierarchy_type_id() == HierarchyType.ITEM_DESCRIPTION
    assert dialog.hierarchy_type_combo.currentData() == HierarchyType.TEXT


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
    assert dialog._start_range_edit(mark_key)

    selections = dialog.raw_edit.extraSelections()
    assert selections[0].cursor.selectedText() == "MIDNA"
    assert len(selections) >= 3


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
