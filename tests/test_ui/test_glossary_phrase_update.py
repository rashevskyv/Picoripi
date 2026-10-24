"""Tests for phrase-scoped glossary translation updates."""
from unittest.mock import patch

from PyQt6.QtWidgets import QMessageBox

from components.glossary_translation_update_dialog import GlossaryTranslationUpdateDialog
from core.glossary_manager import GlossaryEntry, GlossaryOccurrence
from utils.search_text import find_phrase_spans, replace_phrase


def _occ(row: int, text: str) -> GlossaryOccurrence:
    return GlossaryOccurrence(GlossaryEntry("term", "new"), 2, row, 0, 0, 0, text)


def _dialog(qapp, candidates, translations, applied=None, **kwargs):
    def record(occ, text):
        if applied is not None:
            applied.append((occ, text))

    return GlossaryTranslationUpdateDialog(
        parent=None,
        term="term",
        old_translation="old phrase",
        new_translation="new phrase",
        occurrences=candidates,
        get_original_text=lambda occ: f"Original {occ.string_idx}",
        get_current_translation=lambda occ: translations[occ.string_idx],
        apply_translation=record,
        **kwargs,
    )


def test_phrase_matching_requires_full_case_insensitive_word_bounded_phrase():
    text = "(OLD phrase), old phraseology, phrase old, [old phrase]"
    assert find_phrase_spans(text, "old phrase") == [(1, 11)]
    assert replace_phrase(text, "old phrase", "new phrase") == "(new phrase), old phraseology, phrase old, [old phrase]"


def test_ukrainian_phrase_excludes_isolated_words_and_inflections():
    text = "Мер Бо прийшов. МЕР БО! Бо сказав: мер пішов. Мер Боянин."
    assert find_phrase_spans(text, "мер бо") == [(0, 6), (16, 22)]
    assert replace_phrase(text, "мер бо", "голова бо") == (
        "голова бо прийшов. голова бо! Бо сказав: мер пішов. Мер Боянин."
    )


def test_dialog_filters_candidates_and_input_can_narrow_broaden_or_clear(qapp):
    first, second = _occ(0, "A OLD phrase!"), _occ(1, "phrase only")
    dlg = _dialog(qapp, [first, first, second], {0: "A OLD phrase!", 1: "phrase only"})
    assert dlg._occurrence_list.count() == 1
    assert dlg._translation_edit.toPlainText() == "A new phrase!"

    dlg._old_translation_edit.setText("phrase only")
    assert dlg._occurrence_list.count() == 1
    assert dlg._occurrences == [second]
    dlg._old_translation_edit.setText("phrase")
    assert dlg._occurrences == [first, second]
    dlg._old_translation_edit.clear()
    assert dlg._occurrence_list.count() == 0
    assert dlg._translation_edit.toPlainText() == ""
    assert not dlg._apply_button.isEnabled()
    dlg.deleteLater()


def test_replace_all_only_changes_eligible_unique_targets_and_preserves_tags(qapp):
    one = _occ(0, "{COLOR:old phrase} old phrase!")
    duplicate = _occ(0, "duplicate candidate")
    no_phrase = _occ(1, "old phraseology")
    translations = {0: "{COLOR:old phrase} old phrase!", 1: "old phraseology"}
    applied = []
    dlg = _dialog(qapp, [one, duplicate, no_phrase], translations, applied)
    with patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), \
         patch("PyQt6.QtWidgets.QMessageBox.information"):
        dlg._run_quick_replace_all()
    assert applied == [(one, "{COLOR:old phrase} new phrase!")]
    dlg.deleteLater()


def test_phrase_highlights_cover_full_phrase_and_not_fuzzy_words(qapp):
    dlg = _dialog(qapp, [_occ(0, "old phrase")], {0: "old phrase"})
    dlg._translation_edit.setPlainText("Old phrase; old phraseology")
    dlg._update_text_highlights()
    selections = dlg._translation_edit.extraSelections()
    assert [(s.cursor.selectionStart(), s.cursor.selectionEnd()) for s in selections] == [(0, 10)]
    dlg.deleteLater()


def test_phrase_highlight_uses_qt_utf16_positions_after_emoji(qapp):
    dlg = _dialog(qapp, [_occ(0, "old phrase")], {0: "old phrase"})
    dlg._translation_edit.setPlainText("😀 Old phrase")
    dlg._update_text_highlights()
    selection = dlg._translation_edit.extraSelections()[0].cursor
    assert selection.selectionStart() == 3
    assert selection.selectionEnd() == 13
    dlg.deleteLater()


def test_busy_ai_freezes_input_and_blocks_manual_batch(qapp):
    occ = _occ(0, "old phrase")
    translations = {0: "old phrase"}
    dlg = _dialog(qapp, [occ], translations)
    dlg.set_ai_busy(True)
    assert not dlg._old_translation_edit.isEnabled()
    assert not dlg._apply_all_button.isEnabled()
    with patch("PyQt6.QtWidgets.QMessageBox.question") as confirm:
        dlg._run_apply_all()
        confirm.assert_not_called()
    dlg.deleteLater()


def test_apply_all_and_ai_all_use_only_matching_unique_strings(qapp):
    first = _occ(0, "old phrase")
    unrelated = _occ(1, "phrase only")
    translations = {0: "old phrase", 1: "phrase only"}
    applied, requested = [], []
    dlg = _dialog(qapp, [first, first, unrelated], translations, applied,
                  ai_request_all=lambda occurrences: requested.extend(occurrences))
    with patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), \
         patch("PyQt6.QtWidgets.QMessageBox.information"):
        dlg._run_ai_for_all()
        assert requested == [first]
        dlg.set_batch_active(False)
        dlg.set_ai_busy(False)
        dlg._run_apply_all()
    assert applied == [(first, "new phrase")]
    dlg.deleteLater()


def test_no_match_and_empty_query_cannot_apply_or_request_ai(qapp):
    first = _occ(0, "old phrase")
    applied, requested = [], []
    dlg = _dialog(qapp, [first], {0: "old phrase"}, applied,
                  ai_request_single=lambda occurrence: requested.append(occurrence),
                  ai_request_all=lambda occurrences: requested.extend(occurrences))
    for query in ("missing phrase", "", "   "):
        dlg._status_label.setText("stale status")
        dlg._old_translation_edit.setText(query)
        assert dlg._original_view.toPlainText() == ""
        assert dlg._translation_edit.toPlainText() == ""
        assert dlg._status_label.text() == ""
        assert dlg._translation_edit.extraSelections() == []
        with patch("PyQt6.QtWidgets.QMessageBox.information"):
            dlg._apply_current()
            dlg._run_apply_all()
            dlg._run_quick_replace_all()
            dlg._run_ai_for_current()
            dlg._run_ai_for_all()
    assert applied == []
    assert requested == []
    dlg.deleteLater()


def test_new_query_can_revisit_a_previously_applied_string(qapp):
    first = _occ(0, "old phrase; next phrase")
    applied = []
    dlg = _dialog(qapp, [first], {0: "old phrase; next phrase"}, applied)
    dlg._apply_current()
    dlg._old_translation_edit.setText("next phrase")
    with patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), \
         patch("PyQt6.QtWidgets.QMessageBox.information"):
        dlg._run_quick_replace_all()
    assert applied == [(first, "new phrase; next phrase"), (first, "old phrase; new phrase")]
    dlg.deleteLater()
