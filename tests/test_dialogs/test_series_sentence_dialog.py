"""SeriesSentenceDialog (D45): one checked row per line, the three selection buttons, and the rows the user applies."""
from PyQt6.QtCore import Qt

from dialogs.series_sentence_dialog import SeriesSentenceDialog


def _row(string_idx, tick, safe, reason=""):
    return {
        "block_idx": 2, "block_name": "Block 3", "string_idx": string_idx,
        "source": f"Sentence {string_idx} here", "translation": f"Речення {string_idx}", "project": "TP HD",
        "own_speaker_en": "Ann", "speaker_en": "Ann" if safe else "Bob",
        "safe": safe, "reason": reason, "tick": tick,
    }


def _checks(dialog):
    return [dialog.table.item(index, 0).checkState() == Qt.CheckState.Checked for index in range(dialog.table.rowCount())]


def test_each_row_starts_with_the_tick_it_was_given(qapp):
    dialog = SeriesSentenceDialog(None, [_row(0, True, True), _row(1, False, False, "The speaker names differ.")])
    assert _checks(dialog) == [True, False]
    dialog.close()


def test_select_safe_select_all_and_clear_change_only_the_checks(qapp):
    dialog = SeriesSentenceDialog(None, [_row(0, True, True), _row(1, False, False, "The speaker names differ."),
                                         _row(2, False, True)])
    dialog.select_all_btn.click()
    assert _checks(dialog) == [True, True, True]
    dialog.clear_btn.click()
    assert _checks(dialog) == [False, False, False]
    dialog.select_safe_btn.click()
    assert _checks(dialog) == [True, False, True]
    dialog.close()


def test_apply_returns_only_the_ticked_rows_as_positions_and_texts(qapp):
    dialog = SeriesSentenceDialog(None, [_row(0, True, True), _row(1, False, False, "The speaker names differ.")])
    dialog.table.item(1, 0).setCheckState(Qt.CheckState.Checked)
    assert dialog.accepted_rows() == [
        (2, 0, "Речення 0", "Sentence 0 here"),
        (2, 1, "Речення 1", "Sentence 1 here"),
    ]
    dialog.close()


def test_the_reason_column_says_why_a_row_is_doubtful(qapp):
    dialog = SeriesSentenceDialog(None, [_row(0, True, True), _row(1, False, False, "The addressee differs.")])
    assert dialog.table.item(0, 7).text() == "Safe"
    assert dialog.table.item(1, 7).text() == "The addressee differs."
    dialog.close()
