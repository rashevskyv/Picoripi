"""Opening the glossary for a speaker must land ON that speaker's entry."""
from core.glossary_manager import (
    DescriptionFragment,
    GlossaryEntry,
    TranslationVariant,
)
from components.glossary_dialog import GlossaryDialog


def _entries():
    return [
        GlossaryEntry(original="WOMAN 1", translation="Жінка 1", notes="", section=""),
        GlossaryEntry(original="ZELDA", translation="Зельда", notes="", section="Main"),
        GlossaryEntry(
            original="TWILIGHT PRINCESS",
            translation="Сутінкова Принцеса",
            notes="",
            section="Main",
        ),
    ]


def _dialog(qtbot, initial_term=None):
    dlg = GlossaryDialog(
        parent=None,
        entries=_entries(),
        occurrence_map={},
        jump_callback=lambda _o: None,
        update_callback=lambda *_a: None,
        initial_term=initial_term,
    )
    qtbot.addWidget(dlg)
    return dlg


def test_glossary_dialog_is_its_own_alt_tab_window(qtbot):
    from PyQt6.QtCore import Qt

    dlg = _dialog(qtbot)
    assert dlg.parent() is None
    assert dlg.windowFlags() & Qt.WindowType.Window
    assert not dlg.isModal()
    assert not dlg.testAttribute(Qt.WidgetAttribute.WA_QuitOnClose)


def test_initial_term_selects_entry_and_switches_section(qtbot):
    dlg = _dialog(qtbot, initial_term="TWILIGHT PRINCESS")
    dlg.focus_term("TWILIGHT PRINCESS")  # deterministic (constructor uses a timer)
    assert dlg._current_entry is not None
    assert dlg._current_entry.original == "TWILIGHT PRINCESS"
    # jumped to the entry's section tab and filtered to it
    assert dlg._tab_widget.tabText(dlg._tab_widget.currentIndex()) == "Main"
    assert dlg._search_field.text() == "TWILIGHT PRINCESS"


def test_focus_term_refocuses_an_open_dialog(qtbot):
    dlg = _dialog(qtbot)
    dlg.focus_term("TWILIGHT PRINCESS")
    assert dlg._current_entry.original == "TWILIGHT PRINCESS"
    dlg.focus_term("ZELDA")
    assert dlg._current_entry.original == "ZELDA"


def test_focus_term_for_speaker_without_entry_shows_empty(qtbot):
    """A speaker with no glossary entry filters to nothing, so it is obvious the
    entry must still be added — not silently opening at some unrelated row."""
    dlg = _dialog(qtbot)
    dlg.focus_term("SOME UNKNOWN GUARD")
    assert dlg._filtered_entries == []
    assert dlg._search_field.text() == "SOME UNKNOWN GUARD"


def test_escape_closes_dialog_without_crashing(qtbot):
    """Regression: Esc used the wrong PyQt6 enum (Qt.Key_Escape) and crashed."""
    from PyQt6.QtCore import Qt, QEvent
    from PyQt6.QtGui import QKeyEvent

    dlg = _dialog(qtbot)
    dlg.show()
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    dlg.keyPressEvent(event)  # must not raise AttributeError
    assert not dlg.isVisible()


def test_ai_notes_are_separate_from_the_clean_description(qtbot):
    entry = GlossaryEntry(
        original="Spring Goron",
        translation="Ґорон Джерела",
        notes="A Goron associated with the hot spring.",
        fragments=(DescriptionFragment("The context may mean a bath, not a season."),),
        translation_variants=(
            TranslationVariant("Ґорон Джерела", "spring means a hot spring"),
            TranslationVariant("Весняний Ґорон", "spring may mean the season"),
        ),
    )
    dialog = GlossaryDialog(
        parent=None,
        entries=[entry],
        occurrence_map={},
        jump_callback=lambda _occurrence: None,
    )
    qtbot.addWidget(dialog)
    dialog.focus_term("Spring Goron")

    assert dialog._notes_edit.toPlainText() == entry.notes
    ai_notes = dialog._ai_notes_edit.toPlainText()
    assert "bath, not a season" in ai_notes
    assert "spring may mean the season" in ai_notes
