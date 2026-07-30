"""M2: surfacing translation variants and the review state in the glossary dialog."""
from unittest.mock import MagicMock

from components.glossary_dialog import GlossaryDialog
from core.glossary_manager import (
    STATUS_CONFIRMED,
    STATUS_TRANSLATED,
    GlossaryEntry,
    TranslationVariant,
)


def _entry(term, translation="", *, status="", variants=(), notes="n"):
    return GlossaryEntry(
        original=term,
        translation=translation,
        notes=notes,
        section="Terms",
        status=status,
        translation_variants=tuple(variants),
    )


AMBIGUOUS = _entry(
    "Spring Goron",
    "Ґорон Джерела",
    status=STATUS_TRANSLATED,
    variants=(
        TranslationVariant("Ґорон Джерела", "spring = bathhouse"),
        TranslationVariant("Весняний Ґорон", "spring = season"),
    ),
)
SINGLE = _entry("Ordon", "Ордон", status=STATUS_TRANSLATED,
                variants=(TranslationVariant("Ордон", "transliteration"),))
CONFIRMED = _entry("Link", "Лінк", status=STATUS_CONFIRMED)
LEGACY = _entry("Midna", "Мідна")


def _dialog(qtbot, entries, update_callback=None):
    dialog = GlossaryDialog(
        entries=entries,
        occurrence_map={},
        parent=None,
        jump_callback=MagicMock(),
        update_callback=update_callback,
    )
    qtbot.addWidget(dialog)
    return dialog


class TestNeedsReview:
    def test_multiple_variants_need_review(self):
        assert GlossaryDialog._needs_review(AMBIGUOUS) is True

    def test_unconfirmed_status_needs_review(self):
        assert GlossaryDialog._needs_review(SINGLE) is True

    def test_confirmed_does_not(self):
        assert GlossaryDialog._needs_review(CONFIRMED) is False

    def test_legacy_entry_without_status_does_not(self):
        """Otherwise every pre-existing entry would light up and mean nothing."""
        assert GlossaryDialog._needs_review(LEGACY) is False


class TestReviewReason:
    def test_lists_variants(self):
        reason = GlossaryDialog._review_reason(AMBIGUOUS)
        assert "2 translation variants" in reason
        assert "Ґорон Джерела" in reason and "Весняний Ґорон" in reason
        assert "spring = season" in reason

    def test_falls_back_to_status(self):
        assert "translated" in GlossaryDialog._review_reason(SINGLE)


class TestFilter:
    def test_filter_keeps_only_entries_needing_review(self, qtbot):
        dialog = _dialog(qtbot, [AMBIGUOUS, CONFIRMED, LEGACY])
        dialog._unconfirmed_only_checkbox.setChecked(True)
        assert [e.original for e in dialog._filtered_entries] == ["Spring Goron"]

    def test_unchecked_shows_everything(self, qtbot):
        dialog = _dialog(qtbot, [AMBIGUOUS, CONFIRMED, LEGACY])
        dialog._unconfirmed_only_checkbox.setChecked(True)
        dialog._unconfirmed_only_checkbox.setChecked(False)
        assert len(dialog._filtered_entries) == 3

    def test_combines_with_text_search(self, qtbot):
        dialog = _dialog(qtbot, [AMBIGUOUS, SINGLE, CONFIRMED])
        dialog._unconfirmed_only_checkbox.setChecked(True)
        dialog._search_field.setText("ordon")
        assert [e.original for e in dialog._filtered_entries] == ["Ordon"]


class TestVariantPicker:
    def test_shown_only_for_a_real_choice(self, qtbot):
        dialog = _dialog(qtbot, [AMBIGUOUS])
        dialog._populate_variants(AMBIGUOUS)
        assert dialog._variants_list.isVisibleTo(dialog) is True
        assert dialog._variants_list.count() == 2

    def test_hidden_for_single_variant(self, qtbot):
        dialog = _dialog(qtbot, [SINGLE])
        dialog._populate_variants(SINGLE)
        assert dialog._variants_list.isVisibleTo(dialog) is False

    def test_rationale_shown_with_each_variant(self, qtbot):
        dialog = _dialog(qtbot, [AMBIGUOUS])
        dialog._populate_variants(AMBIGUOUS)
        labels = [dialog._variants_list.item(i).text() for i in range(2)]
        assert any("spring = bathhouse" in label for label in labels)

    def test_active_variant_is_bold(self, qtbot):
        dialog = _dialog(qtbot, [AMBIGUOUS])
        dialog._populate_variants(AMBIGUOUS)
        bold = [
            dialog._variants_list.item(i).font().bold()
            for i in range(dialog._variants_list.count())
        ]
        assert bold == [True, False]

    def test_choosing_a_variant_fills_the_field(self, qtbot):
        dialog = _dialog(qtbot, [AMBIGUOUS])
        dialog._populate_variants(AMBIGUOUS)
        dialog._on_variant_chosen(dialog._variants_list.item(1))
        assert dialog._translation_edit.text() == "Весняний Ґорон"


class TestConfirm:
    def test_confirm_sends_confirmed_status(self, qtbot):
        callback = MagicMock(return_value=([CONFIRMED], {}))
        dialog = _dialog(qtbot, [AMBIGUOUS], update_callback=callback)
        dialog._current_entry = AMBIGUOUS
        dialog._translation_edit.setText("Весняний Ґорон")

        dialog._on_confirm_clicked()

        callback.assert_called_once()
        assert callback.call_args.kwargs["status"] == STATUS_CONFIRMED
        assert callback.call_args.args[1] == "Весняний Ґорон"

    def test_confirm_button_hidden_for_settled_entry(self, qtbot):
        dialog = _dialog(qtbot, [CONFIRMED], update_callback=MagicMock())
        dialog._populate_variants(CONFIRMED)
        assert dialog._confirm_button.isVisibleTo(dialog) is False

    def test_confirm_noop_without_callback(self, qtbot):
        dialog = _dialog(qtbot, [AMBIGUOUS])
        dialog._current_entry = AMBIGUOUS
        dialog._on_confirm_clicked()  # must not raise

    def test_plain_edit_does_not_confirm(self, qtbot):
        """An ordinary save keeps the entry in review until confirmed."""
        callback = MagicMock(return_value=([AMBIGUOUS], {}))
        dialog = _dialog(qtbot, [AMBIGUOUS], update_callback=callback)
        dialog._attempt_entry_update(AMBIGUOUS, "x", "y", False)
        assert "status" not in callback.call_args.kwargs


class TestBuildButton:
    """The build/translate launcher reachable from inside the glossary."""

    def test_hidden_without_callback(self, qtbot):
        dialog = _dialog(qtbot, [LEGACY])
        assert dialog._build_button.isVisibleTo(dialog) is False

    def test_visible_and_wired_with_callback(self, qtbot):
        build = MagicMock()
        dialog = GlossaryDialog(
            entries=[LEGACY],
            occurrence_map={},
            parent=None,
            jump_callback=MagicMock(),
            build_callback=build,
        )
        qtbot.addWidget(dialog)
        assert dialog._build_button.isVisibleTo(dialog) is True
        dialog._build_button.click()
        build.assert_called_once_with()


class TestClearButton:
    """Wiping the glossary: confirmed, backed up, and reflected in the UI."""

    def _with_clear(self, qtbot, clear_callback):
        dialog = GlossaryDialog(
            entries=[AMBIGUOUS, CONFIRMED, LEGACY],
            occurrence_map={},
            parent=None,
            jump_callback=MagicMock(),
            clear_callback=clear_callback,
        )
        qtbot.addWidget(dialog)
        return dialog

    def test_hidden_without_callback(self, qtbot):
        dialog = _dialog(qtbot, [LEGACY])
        assert dialog._clear_button.isVisibleTo(dialog) is False

    def test_declining_the_prompt_keeps_entries(self, qtbot, monkeypatch):
        clear = MagicMock(return_value=([], {}))
        dialog = self._with_clear(qtbot, clear)
        monkeypatch.setattr(
            "components.glossary_dialog.QMessageBox.question",
            lambda *a, **k: __import__(
                "PyQt6.QtWidgets", fromlist=["QMessageBox"]
            ).QMessageBox.StandardButton.No,
        )
        dialog._on_clear_clicked()
        clear.assert_not_called()
        assert len(dialog._all_entries) == 3

    def test_accepting_empties_the_dialog(self, qtbot, monkeypatch):
        clear = MagicMock(return_value=([], {}))
        dialog = self._with_clear(qtbot, clear)
        monkeypatch.setattr(
            "components.glossary_dialog.QMessageBox.question",
            lambda *a, **k: __import__(
                "PyQt6.QtWidgets", fromlist=["QMessageBox"]
            ).QMessageBox.StandardButton.Yes,
        )
        dialog._on_clear_clicked()
        clear.assert_called_once_with()
        assert dialog._all_entries == []
        assert dialog._current_entry is None
        assert dialog._active_table().rowCount() == 0


class TestVariantChoiceSettlesTheEntry:
    """Picking from the list is the decision the highlight asks for."""

    def test_choosing_a_variant_confirms_it(self, qtbot):
        callback = MagicMock(return_value=([CONFIRMED], {}))
        dialog = _dialog(qtbot, [AMBIGUOUS], update_callback=callback)
        dialog._current_entry = AMBIGUOUS
        dialog._populate_variants(AMBIGUOUS)

        dialog._on_variant_chosen(dialog._variants_list.item(1))

        assert dialog._translation_edit.text() == "Весняний Ґорон"
        assert callback.call_args.kwargs["status"] == STATUS_CONFIRMED
        assert callback.call_args.args[1] == "Весняний Ґорон"

    def test_confirmed_entry_is_no_longer_highlighted(self):
        settled = _entry("Spring Goron", "Весняний Ґорон", status=STATUS_CONFIRMED)
        assert GlossaryDialog._needs_review(settled) is False

    def test_variant_list_has_no_fixed_height_cap(self, qtbot):
        """It lives in a splitter now, so the user can drag it larger."""
        dialog = _dialog(qtbot, [AMBIGUOUS])
        assert dialog._variants_list.maximumHeight() > 1000


class TestNotesPlaceholder:
    """Notes keep a term placeholder so they follow the chosen variant."""

    TEMPLATE = "{{TERM}} — жуки, яких підривають бумерангом."

    def _dialog_with_template(self, qtbot, update_callback=None):
        entry = GlossaryEntry(
            original="bomb bugs",
            translation="вибухові жуки",
            notes=self.TEMPLATE,
            status=STATUS_TRANSLATED,
            translation_variants=(
                TranslationVariant("вибухові жуки", "прямий"),
                TranslationVariant("бомбожуки", "склейка"),
            ),
        )
        dialog = _dialog(qtbot, [entry], update_callback=update_callback)
        dialog._current_entry = entry
        dialog._populate_entry_details(entry)
        return dialog, entry

    def test_editor_shows_the_active_translation_not_the_token(self, qtbot):
        dialog, _ = self._dialog_with_template(qtbot)
        assert dialog._notes_edit.toPlainText().startswith("вибухові жуки —")
        assert "{{TERM}}" not in dialog._notes_edit.toPlainText()

    def test_notes_follow_a_newly_picked_variant(self, qtbot):
        callback = MagicMock(return_value=([], {}))
        dialog, entry = self._dialog_with_template(qtbot, update_callback=callback)
        dialog._populate_variants(entry)

        dialog._on_variant_chosen(dialog._variants_list.item(1))

        assert dialog._notes_edit.toPlainText().startswith("бомбожуки —")
        # Stored form keeps the token, so a later change of mind still works.
        assert callback.call_args.args[2] == self.TEMPLATE

    def test_hand_edited_notes_are_stored_verbatim(self, qtbot):
        callback = MagicMock(return_value=([], {}))
        dialog, _ = self._dialog_with_template(qtbot, update_callback=callback)
        dialog._notes_edit.setPlainText("Моє власне пояснення.")

        dialog._save_editor_changes()

        assert callback.call_args.args[2] == "Моє власне пояснення."
