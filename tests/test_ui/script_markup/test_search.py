from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from .helpers import (
    _flush_search,
    _make_dialog,
    _select_lines,
)

def test_studio_search_preserves_raw_cursor_and_selection(qapp):
    dialog = _make_dialog(qapp)
    dialog.raw_edit.setPlainText("Act One\nScene setup\nAct Two\n")
    _select_lines(dialog, 0, 1)
    before = dialog.raw_edit.textCursor()

    dialog.search_edit.setText("Act Two")
    _flush_search(dialog)

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
    _flush_search(dialog)
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
    _flush_search(dialog)
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
    _flush_search(dialog)
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
    _flush_search(dialog)

    dialog._refresh()

    assert dialog.raw_edit.extraSelections()[0].cursor.selectedText() == "Act Two"
    assert dialog.search_status_label.text() == "1/1"

def test_studio_search_options_case_word_and_regex(qapp):
    dialog = _make_dialog(qapp)
    dialog.raw_edit.setPlainText("act\nAct\nAction\nAct 2\nAct A\n")

    dialog.search_edit.setText("Act")
    _flush_search(dialog)
    assert dialog.search_status_label.text() == "1/5"

    dialog.search_case_cb.setChecked(True)
    assert dialog.search_status_label.text() == "1/4"

    dialog.search_word_cb.setChecked(True)
    assert dialog.search_status_label.text() == "1/3"

    dialog.search_edit.setText(r"Act \d")
    dialog.search_regex_cb.setChecked(True)
    _flush_search(dialog)
    assert dialog.search_status_label.text() == "1/1"
    assert dialog.raw_edit.extraSelections()[0].cursor.selectedText() == "Act 2"

    dialog.search_edit.setText("(")
    _flush_search(dialog)
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
