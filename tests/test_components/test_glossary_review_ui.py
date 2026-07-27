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
