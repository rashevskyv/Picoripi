import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication, QWidget

from ui.script_markup_studio_dialog import ScriptMarkupStudioDialog


@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication exists for widget testing."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def _make_dialog(qapp):
    mock_mw = MagicMock()
    # current_game_rules=None → the dialog falls back to the real BaseGameRules,
    # so "Picoripi rules" mode is exercised with the genuine parser in tests.
    mock_mw.current_game_rules = None
    # _auto_discover_script will get a MagicMock path (not a str) → safely skipped.
    parent = QWidget()
    dialog = ScriptMarkupStudioDialog(mock_mw, parent=parent)
    # Keep the parent alive for the lifetime of the dialog (WA_DeleteOnClose +
    # GC of a local parent would otherwise destroy the C++ object).
    dialog._test_parent = parent
    return dialog


def _use_custom_mode(dialog):
    dialog.mode = "custom"
    dialog._update_mode_controls()


def test_studio_constructs(qapp):
    dialog = _make_dialog(qapp)
    assert dialog is not None
    assert dialog.windowTitle() == "Script Markup Studio"


def test_studio_refresh_renders_preview_and_stats(qapp):
    dialog = _make_dialog(qapp)
    dialog.raw_edit.setPlainText(
        "[Chapter: Prologue]\n"
        "MIDNA: Well, look what we have here!\n"
        "ZELDA: Be careful.\n"
    )
    dialog._refresh()

    preview = dialog.preview_edit.toPlainText()
    assert "## Prologue" in preview
    assert "MIDNA: Well, look what we have here!" in preview
    assert "ZELDA: Be careful." in preview
    # Highlighter received a per-line classification map.
    assert dialog.highlighter.line_kinds
    assert "Speakers: 2" in dialog.stats_label.text()


def test_studio_teach_speaker_adds_rule(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    # Mixed-case speaker style not covered by the default uppercase rule.
    dialog.raw_edit.setPlainText("Rusl: Take this shield.\n")
    dialog._refresh()
    assert "Rusl: Take this shield." not in dialog.preview_edit.toPlainText()

    # Put the cursor on the line and teach it as a speaker.
    cursor = dialog.raw_edit.textCursor()
    cursor.setPosition(0)
    dialog.raw_edit.setTextCursor(cursor)
    dialog._teach_current_line("speaker")

    assert "RUSL: Take this shield." in dialog.preview_edit.toPlainText()


def test_studio_flags_possible_missed_dialogue(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dialog.raw_edit.setPlainText('He turned and said "Hello there, friend" warmly.\n')
    dialog._refresh()
    assert dialog.flags_list.count() >= 1


def test_studio_picoripi_mode_uses_existing_rules(qapp):
    dialog = _make_dialog(qapp)
    assert dialog.mode == "picoripi"  # default
    dialog.raw_edit.setPlainText(
        "[Chapter: Prologue]\n"
        "{Action: Midna appears}\n"
        "MIDNA: Well, look what we have here!\n"
    )
    dialog._refresh()
    preview = dialog.preview_edit.toPlainText()
    assert "## Prologue" in preview
    assert "{Action: Midna appears}" in preview
    assert "MIDNA: Well, look what we have here!" in preview
    assert "via Picoripi rules" in dialog.stats_label.text()


def test_studio_mode_toggle_disables_recipe_controls(qapp):
    dialog = _make_dialog(qapp)
    # Picoripi mode: recipe + teach controls are disabled.
    assert not dialog.recipe_box.isEnabled()
    assert not dialog.teach_box.isEnabled()
    _use_custom_mode(dialog)
    assert dialog.recipe_box.isEnabled()
    assert dialog.teach_box.isEnabled()


def test_studio_gutter_on_by_default(qapp):
    dialog = _make_dialog(qapp)
    assert dialog.cb_gutter.isChecked()


def test_studio_timeline_range_excludes_front_matter(qapp):
    dialog = _make_dialog(qapp)
    dialog.raw_edit.setPlainText(
        "Legal blah blah\n"
        "Table of contents\n"
        "ZELDA: This is real dialogue.\n"
    )
    # Move cursor to line 3 and mark it as the timeline start.
    cursor = dialog.raw_edit.textCursor()
    block = dialog.raw_edit.document().findBlockByNumber(2)
    cursor.setPosition(block.position())
    dialog.raw_edit.setTextCursor(cursor)
    dialog._set_timeline_start()

    assert dialog.start_line == 3
    preview = dialog.preview_edit.toPlainText()
    assert "ZELDA: This is real dialogue." in preview
    assert "Legal blah" not in preview
    assert "Table of contents" not in preview


def test_studio_help_dialog_renders_html(qapp):
    dialog = _make_dialog(qapp)
    help_dlg = dialog._build_help_dialog()
    help_dlg._test_parent = dialog  # keep alive
    text = dialog._help_browser.toPlainText()
    # Rendered as rich text, not a wall of raw markup.
    assert "Script Markup Studio" in text
    assert "Speaker" in text and "Gutter" in text
    assert "<h2" not in text  # tags were rendered, not shown literally


def test_studio_speaker_teacher_learns_custom_separator(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dlg = dialog._build_speaker_teacher()
    dlg._test_parent = dialog  # keep alive

    # Simulate the user marking the two parts on a 'Name - text' line.
    dlg._sample_edit.setPlainText("Rusl - Take this shield.")
    dlg._name_edit.setText("Rusl")
    dlg._text_edit.setText("Take this shield.")
    dlg._on_ok()

    assert dlg.result_pattern is not None
    if dlg.result_pattern not in dialog.recipe.speaker_patterns:
        dialog.recipe.speaker_patterns.insert(0, dlg.result_pattern)

    # The learned rule now classifies that format in the engine.
    dialog.raw_edit.setPlainText("Midna - Hello there.\n")
    dialog._refresh()
    assert "MIDNA: Hello there." in dialog.preview_edit.toPlainText()


def test_studio_builds_line_map_on_refresh(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dialog.raw_edit.setPlainText(
        "[Chapter: Prologue]\n"
        "MIDNA: Hello there.\n"
        "ZELDA: Hi.\n"
    )
    dialog._refresh()
    # Both dialogue source lines (index 1 and 2) map to an output line.
    assert 1 in dialog._src_to_out
    assert 2 in dialog._src_to_out


def test_studio_content_sync_moves_and_highlights_preview(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dialog.raw_edit.setPlainText(
        "[Chapter: Prologue]\n"
        "MIDNA: Hello there.\n"
        "ZELDA: Hi.\n"
    )
    dialog._refresh()

    out_idx = dialog._output_for_source(2)   # ZELDA line
    assert out_idx is not None

    dialog._scroll_preview_to_source(2, highlight=True)
    assert dialog.preview_edit.textCursor().blockNumber() == out_idx
    assert len(dialog.preview_edit.extraSelections()) == 1   # highlighted

    # Passive scroll sync moves the caret but clears the highlight.
    dialog._scroll_preview_to_source(1, highlight=False)
    assert dialog.preview_edit.textCursor().blockNumber() == dialog._output_for_source(1)
    assert dialog.preview_edit.extraSelections() == []


def test_studio_content_sync_respects_suspend(qapp):
    dialog = _make_dialog(qapp)
    _use_custom_mode(dialog)
    dialog.raw_edit.setPlainText("MIDNA: Hello there.\n")
    dialog._refresh()
    dialog._suspend_sync = True
    # Should be a no-op while suspended.
    before = dialog.preview_edit.textCursor().blockNumber()
    dialog._on_left_clicked()
    assert dialog.preview_edit.textCursor().blockNumber() == before


def test_studio_clear_range_restores_full_file(qapp):
    dialog = _make_dialog(qapp)
    dialog.start_line = 5
    dialog.end_line = 10
    dialog._clear_timeline_range()
    assert dialog.start_line == 0 and dialog.end_line == 0
    assert "full file" in dialog.range_label.text()
