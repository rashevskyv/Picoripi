"""Regression tests for matching multiline reference translation lines in the glossary UI."""
from unittest.mock import MagicMock
from PyQt6.QtCore import Qt

from components.glossary_dialog import GlossaryDialog
from core.glossary_manager import GlossaryEntry, GlossaryOccurrence, TranslationVariant


def _entry(term: str, translation: str = "", variants: tuple = ()) -> GlossaryEntry:
    return GlossaryEntry(
        original=term,
        translation=translation,
        notes="n",
        section="Terms",
        translation_variants=variants,
    )


def test_multiline_occurrence_shows_full_messages_in_both_languages(qtbot):
    entry = _entry(
        "Master Sword",
        "Вищий Меч",
        variants=(TranslationVariant("Высший Меч", "RU variant"),),
    )
    # Occurrence is on EN line index 1 (line 2 in 1-based display)
    occ = GlossaryOccurrence(
        entry=entry,
        block_idx=1,
        string_idx=4,
        line_idx=1,
        start=16,
        end=28,
        line_text="The <legendary> Master Sword.",
    )
    source_data = {
        (1, 4): "First EN line & opening scene.\nThe <legendary> Master Sword."
    }
    ref_data = {
        (1, 4): (
            "Первая строка RU & пролог.\n"
            "Вторая строка RU <детали>.\n"
            "Легендарный Высший Меч."
        )
    }

    dialog = GlossaryDialog(
        entries=[entry],
        occurrence_map={entry.original: [occ]},
        parent=None,
        jump_callback=MagicMock(),
        reference_data=ref_data,
        reference_language="Russian (RU)",
        source_data=source_data,
    )
    qtbot.addWidget(dialog)
    dialog.focus_term("Master Sword")

    assert dialog._occurrence_list.count() == 1
    item = dialog._occurrence_list.item(0)
    display_html = item.data(Qt.ItemDataRole.DisplayRole)

    # Line 2 header
    assert "line <b>2</b>" in display_html
    assert "EN:" in display_html

    # Both EN lines visible, surrounding line preserved, escaping and highlighting verified
    assert "First EN line &amp; opening scene." in display_html
    assert "The &lt;legendary&gt;" in display_html
    assert "<b style='color: #60a5fa;'>Master Sword</b>" in display_html
    assert "<legendary>" not in display_html

    # All three RU lines visible, surrounding lines preserved, escaping and highlighting verified
    assert "RU:" in display_html
    assert "Первая строка RU &amp; пролог." in display_html
    assert "Вторая строка RU &lt;детали&gt;." in display_html
    assert "Легендарный" in display_html
    assert "<b style='color: #f59e0b; text-decoration: underline;'>Высший Меч</b>" in display_html
    assert "<детали>" not in display_html


def test_multiline_occurrence_omits_reference_only_when_record_absent_or_empty(qtbot):
    entry = _entry("Master Sword", "Вищий Меч")
    occ = GlossaryOccurrence(
        entry=entry,
        block_idx=1,
        string_idx=4,
        line_idx=2,  # line 3
        start=14,
        end=26,
        line_text="The legendary Master Sword.",
    )

    # Case A: reference record is absent
    dialog_absent = GlossaryDialog(
        entries=[entry],
        occurrence_map={entry.original: [occ]},
        parent=None,
        jump_callback=MagicMock(),
        reference_data={},
        reference_language="Russian (RU)",
    )
    qtbot.addWidget(dialog_absent)
    dialog_absent.focus_term("Master Sword")
    html_absent = dialog_absent._occurrence_list.item(0).data(Qt.ItemDataRole.DisplayRole)
    assert "RU:" not in html_absent

    # Case B: reference record is whitespace only
    dialog_empty = GlossaryDialog(
        entries=[entry],
        occurrence_map={entry.original: [occ]},
        parent=None,
        jump_callback=MagicMock(),
        reference_data={(1, 4): "   \n  "},
        reference_language="Russian (RU)",
    )
    qtbot.addWidget(dialog_empty)
    dialog_empty.focus_term("Master Sword")
    html_empty = dialog_empty._occurrence_list.item(0).data(Qt.ItemDataRole.DisplayRole)
    assert "RU:" not in html_empty

    # Case C: reference record has fewer lines than EN match (RU has 2 lines, EN match is line 3)
    # Must NOT be suppressed: both lines are shown
    ref_data_short = {
        (1, 4): "Первая строка RU.\nВторая строка RU."
    }
    dialog_short = GlossaryDialog(
        entries=[entry],
        occurrence_map={entry.original: [occ]},
        parent=None,
        jump_callback=MagicMock(),
        reference_data=ref_data_short,
        reference_language="Russian (RU)",
    )
    qtbot.addWidget(dialog_short)
    dialog_short.focus_term("Master Sword")
    html_short = dialog_short._occurrence_list.item(0).data(Qt.ItemDataRole.DisplayRole)
    assert "RU:" in html_short
    assert "Первая строка RU." in html_short
    assert "Вторая строка RU." in html_short

    # Case D: reference record has blank line at line_idx, but other lines nonempty
    # Must NOT be suppressed: all lines shown
    ref_data_blank_line = {
        (1, 4): "Первая строка RU.\nВторая строка RU.\n   \nЧетвертая строка RU."
    }
    dialog_blank = GlossaryDialog(
        entries=[entry],
        occurrence_map={entry.original: [occ]},
        parent=None,
        jump_callback=MagicMock(),
        reference_data=ref_data_blank_line,
        reference_language="Russian (RU)",
    )
    qtbot.addWidget(dialog_blank)
    dialog_blank.focus_term("Master Sword")
    html_blank = dialog_blank._occurrence_list.item(0).data(Qt.ItemDataRole.DisplayRole)
    assert "RU:" in html_blank
    assert "Первая строка RU." in html_blank
    assert "Четвертая строка RU." in html_blank


def test_multiline_occurrence_does_not_label_german_reference_as_ru(qtbot):
    entry = _entry("Master Sword", "Вищий Меч")
    occ = GlossaryOccurrence(
        entry=entry,
        block_idx=1,
        string_idx=4,
        line_idx=2,
        start=14,
        end=26,
        line_text="The legendary Master Sword.",
    )
    german_ref_data = {
        (1, 4): (
            "Erste Zeile DE.\n"
            "Zweite Zeile DE.\n"
            "Das legendäre Masterschwert.\n"
            "Vierte Zeile DE."
        )
    }

    # Case A: Explicit reference_language is German
    dialog_explicit = GlossaryDialog(
        entries=[entry],
        occurrence_map={entry.original: [occ]},
        parent=None,
        jump_callback=MagicMock(),
        reference_data=german_ref_data,
        reference_language="German (DE)",
    )
    qtbot.addWidget(dialog_explicit)
    dialog_explicit.focus_term("Master Sword")

    item_explicit = dialog_explicit._occurrence_list.item(0)
    html_explicit = item_explicit.data(Qt.ItemDataRole.DisplayRole)
    assert "RU:" not in html_explicit
    assert "Masterschwert" not in html_explicit

    # Case B: Without explicit reference_language, text is German (no Cyrillic)
    dialog_implicit = GlossaryDialog(
        entries=[entry],
        occurrence_map={entry.original: [occ]},
        parent=None,
        jump_callback=MagicMock(),
        reference_data=german_ref_data,
        reference_language=None,
    )
    qtbot.addWidget(dialog_implicit)
    dialog_implicit.focus_term("Master Sword")

    item_implicit = dialog_implicit._occurrence_list.item(0)
    html_implicit = item_implicit.data(Qt.ItemDataRole.DisplayRole)
    assert "RU:" not in html_implicit
    assert "Masterschwert" not in html_implicit


def test_multiline_occurrence_does_not_label_ukrainian_or_unlabeled_cyrillic_reference_as_ru(qtbot):
    entry = _entry("Master Sword", "Вищий Меч")
    occ = GlossaryOccurrence(
        entry=entry,
        block_idx=1,
        string_idx=4,
        line_idx=2,
        start=14,
        end=26,
        line_text="The legendary Master Sword.",
    )
    uk_ref_data = {
        (1, 4): (
            "Перший рядок UK.\n"
            "Другий рядок UK.\n"
            "Легендарний Вищий Меч.\n"
            "Четвертий рядок UK."
        )
    }

    # Case A: Cyrillic reference without language metadata (reference_language=None)
    dialog_unlabeled = GlossaryDialog(
        entries=[entry],
        occurrence_map={entry.original: [occ]},
        parent=None,
        jump_callback=MagicMock(),
        reference_data=uk_ref_data,
        reference_language=None,
    )
    qtbot.addWidget(dialog_unlabeled)
    dialog_unlabeled.focus_term("Master Sword")

    item_unlabeled = dialog_unlabeled._occurrence_list.item(0)
    html_unlabeled = item_unlabeled.data(Qt.ItemDataRole.DisplayRole)
    assert "RU:" not in html_unlabeled
    assert "Легендарний" not in html_unlabeled

    # Case B: Explicit Ukrainian label reference_language="Ukrainian (UK)"
    dialog_uk = GlossaryDialog(
        entries=[entry],
        occurrence_map={entry.original: [occ]},
        parent=None,
        jump_callback=MagicMock(),
        reference_data=uk_ref_data,
        reference_language="Ukrainian (UK)",
    )
    qtbot.addWidget(dialog_uk)
    dialog_uk.focus_term("Master Sword")

    item_uk = dialog_uk._occurrence_list.item(0)
    html_uk = item_uk.data(Qt.ItemDataRole.DisplayRole)
    assert "RU:" not in html_uk
    assert "Легендарний" not in html_uk


def test_multiline_occurrence_falls_back_to_line_text_when_source_unavailable(qtbot):
    entry = _entry("Master Sword", "Вищий Меч")
    occ = GlossaryOccurrence(
        entry=entry,
        block_idx=1,
        string_idx=4,
        line_idx=1,
        start=14,
        end=26,
        line_text="The legendary Master Sword.",
    )
    dialog = GlossaryDialog(
        entries=[entry],
        occurrence_map={entry.original: [occ]},
        parent=None,
        jump_callback=MagicMock(),
        source_data=None,
    )
    qtbot.addWidget(dialog)
    dialog.focus_term("Master Sword")

    item = dialog._occurrence_list.item(0)
    html = item.data(Qt.ItemDataRole.DisplayRole)
    assert "line <b>2</b>" in html
    assert "The legendary <b style='color: #60a5fa;'>Master Sword</b>." in html


def test_single_long_occurrence_can_scroll_to_bottom(qtbot):
    entry = _entry("Master Sword")
    occ = GlossaryOccurrence(
        entry=entry, block_idx=0, string_idx=0, line_idx=0,
        start=0, end=12, line_text="Master Sword",
    )
    message = "Master Sword\n" + "\n".join(f"Context line {i}" for i in range(30))
    dialog = GlossaryDialog(
        entries=[entry], occurrence_map={entry.original: [occ]},
        parent=None, jump_callback=MagicMock(), source_data={(0, 0): message},
    )
    qtbot.addWidget(dialog)
    dialog.focus_term("Master Sword")
    dialog._occurrence_list.setFixedHeight(100)
    dialog.show()

    bar = dialog._occurrence_list.verticalScrollBar()
    qtbot.waitUntil(lambda: bar.maximum() > 0)
    assert bar.isVisible()
    bar.setValue(bar.maximum())
    assert bar.value() == bar.maximum()
