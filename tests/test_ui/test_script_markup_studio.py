import tempfile
import uuid
from pathlib import Path

import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication, QWidget, QAbstractItemView
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QCloseEvent, QTextCursor
from PyQt6.QtTest import QTest

from core.script_markup import HierarchyMark, HierarchyType, HierarchyTypeDefinition, LineKind
from ui.script_markup_studio_dialog import (
    ScriptMarkupStudioDialog,
    _RAW_HIERARCHY_GUTTER_WIDTH,
)


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
    assert dialog.load_recipe_btn.isHidden()
    assert dialog.save_recipe_btn.isHidden()
    assert not dialog.load_markup_btn.isHidden()
    assert not dialog.save_markup_btn.isHidden()
    assert not dialog.load_template_btn.isHidden()
    assert not dialog.save_template_btn.isHidden()
    assert not dialog.ai_markup_btn.isHidden()
    assert dialog.legend_label.isHidden()
    assert dialog.main_splitter.orientation() == Qt.Orientation.Horizontal
    assert dialog.flags_list.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    assert dialog.main_splitter.widget(0) is dialog.raw_panel
    assert dialog.main_splitter.widget(1) is dialog.outline_panel


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
    assert not dialog.load_recipe_btn.isHidden()
    assert not dialog.save_recipe_btn.isHidden()
    assert dialog.load_markup_btn.isHidden()
    assert dialog.save_markup_btn.isHidden()
    assert dialog.load_template_btn.isHidden()
    assert dialog.save_template_btn.isHidden()
    assert dialog.ai_markup_btn.isHidden()

    _use_picoripi_mode(dialog)
    assert dialog.hierarchy_box.isHidden()
    assert not dialog.range_panel.isHidden()
    assert dialog.recipe_box.isHidden()
    assert dialog.teach_box.isHidden()
    assert dialog.load_markup_btn.isHidden()
    assert dialog.save_markup_btn.isHidden()
    assert dialog.ai_markup_btn.isHidden()


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
    assert "Speaker" in text
    assert "<h2" not in text  # rendered, not literal markup


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
    assert _tree_item_count(dialog.flags_list) == 3
    assert "Ignored" in dialog.flags_list.topLevelItem(0).text(0)
    assert any(
        "Unmarked" in dialog.flags_list.topLevelItem(i).text(0)
        for i in range(dialog.flags_list.topLevelItemCount())
    )
