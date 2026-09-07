import pytest
from PyQt6.QtWidgets import (QApplication, QAbstractItemView, QPushButton)
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtTest import QTest
from core.script_markup import (
    HierarchyMark,
    HierarchyType,
    HierarchyTypeDefinition,
)
from ui.script_markup_studio_dialog import (
    ScriptMarkupStudioDialog,
    _RAW_HIERARCHY_GUTTER_WIDTH,
    _HELP_HTML,
)
from components.editor.minimap import TextMinimap
from .conftest import _FakeMainWindow, _FakeSettingsManager
from .helpers import (
    _make_dialog,
    _use_custom_mode,
    _use_hierarchy_mode,
    _use_picoripi_mode,
    _set_hierarchy_type,
    _select_lines,
)

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
    raw_search_layout = dialog.raw_panel.layout().itemAt(0).layout()
    assert raw_search_layout.stretch(
        raw_search_layout.indexOf(dialog.search_edit)
    ) == 1

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
