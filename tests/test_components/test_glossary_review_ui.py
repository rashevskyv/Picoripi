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


def _dialog(
    qtbot,
    entries,
    update_callback=None,
    placeholder_speaker_callback=None,
    apply_speaker_name_callback=None,
):
    dialog = GlossaryDialog(
        entries=entries,
        occurrence_map={},
        parent=None,
        jump_callback=MagicMock(),
        update_callback=update_callback,
        placeholder_speaker_callback=placeholder_speaker_callback,
        apply_speaker_name_callback=apply_speaker_name_callback,
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
        """Confirming must win over the variants still on record.

        The earlier version of this test used an entry with no variants, so it
        passed while the real case -- confirming one of several proposals --
        stayed yellow forever.
        """
        settled = _entry(
            "Spring Goron",
            "Весняний Ґорон",
            status=STATUS_CONFIRMED,
            variants=(
                TranslationVariant("Ґорон Джерела", "spring = bathhouse"),
                TranslationVariant("Весняний Ґорон", "spring = season"),
            ),
        )
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


class TestReviewStateFromContextMenu:
    """Putting an entry back under review, and settling it, by hand."""

    def test_marking_for_review_sends_an_unconfirmed_status(self, qtbot):
        callback = MagicMock(return_value=([CONFIRMED], {}))
        dialog = _dialog(qtbot, [CONFIRMED], update_callback=callback)

        dialog._set_entry_review_state(CONFIRMED, needs_review=True)

        assert callback.call_args.kwargs["status"] == STATUS_TRANSLATED
        assert GlossaryDialog._needs_review(
            _entry("Link", "Лінк", status=STATUS_TRANSLATED)
        ) is True

    def test_marking_as_reviewed_confirms(self, qtbot):
        callback = MagicMock(return_value=([AMBIGUOUS], {}))
        dialog = _dialog(qtbot, [AMBIGUOUS], update_callback=callback)

        dialog._set_entry_review_state(AMBIGUOUS, needs_review=False)

        assert callback.call_args.kwargs["status"] == STATUS_CONFIRMED

    def test_round_trip_keeps_the_variants_on_record(self, qtbot):
        """Re-flagging must not throw away the proposals it is flagging about."""
        callback = MagicMock(return_value=([AMBIGUOUS], {}))
        dialog = _dialog(qtbot, [AMBIGUOUS], update_callback=callback)

        dialog._set_entry_review_state(AMBIGUOUS, needs_review=True)

        # translation and notes are passed through untouched
        assert callback.call_args.args[1] == AMBIGUOUS.translation
        assert callback.call_args.args[2] == AMBIGUOUS.notes


class TestSpeakerIdentityResolution:
    """Provisional speaker identity resolution in the Glossary Characters tab."""

    def test_provisional_row_uses_purple_foreground_and_updates_tooltip(self, qtbot):
        prov_entry = GlossaryEntry(
            original="Ash",
            translation="",
            notes="Game character",
            section="Characters",
            provisional=True,
            status=STATUS_TRANSLATED,
        )
        dialog = _dialog(qtbot, [prov_entry])
        table = dialog._tables.get("Characters") or dialog._tables.get("All")
        assert table is not None

        item0 = table.item(0, 0)
        assert item0.foreground().color().name() == "#6a1b9a"
        assert item0.background().color().alpha() > 0
        assert "Provisional speaker identity" in item0.toolTip()
        assert "game data" in item0.toolTip()

    def test_legacy_game_code_uses_the_plugin_placeholder_callback(self, qtbot):
        """Older glossary entries did not persist ``provisional`` yet."""
        apply = MagicMock()
        legacy_code = GlossaryEntry(
            original="Ash",
            translation="",
            notes="The dialogue calls her Ashei.",
            section="Characters",
        )
        dialog = _dialog(
            qtbot,
            [legacy_code],
            placeholder_speaker_callback=lambda term: term == "Ash",
            apply_speaker_name_callback=apply,
        )
        dialog.show()
        dialog.focus_term("Ash")

        item = dialog._tables["Characters"].item(0, 0)
        assert item.foreground().color().name() == "#6a1b9a"
        assert dialog._speaker_identity_pane.isVisibleTo(dialog) is True
        dialog._speaker_name_combo.setEditText("Ashei")
        assert dialog._apply_speaker_name_button.isEnabled() is True
        dialog._apply_speaker_name_button.click()
        apply.assert_called_once_with("Ash", "Ashei")

    def test_speaker_identity_pane_visibility(self, qtbot):
        prov_char = GlossaryEntry(
            original="Ash",
            translation="",
            notes="",
            section="Characters",
            provisional=True,
        )
        perm_char = GlossaryEntry(
            original="Ashy",
            translation="",
            notes="",
            section="Characters",
            provisional=False,
        )
        prov_term = GlossaryEntry(
            original="CLERK_A",
            translation="",
            notes="",
            section="Terms",
            provisional=True,
        )
        dialog = _dialog(qtbot, [prov_char, perm_char, prov_term])

        dialog.focus_term("Ash")
        assert dialog._speaker_identity_pane.isVisibleTo(dialog) is True

        dialog.focus_term("Ashy")
        assert dialog._speaker_identity_pane.isVisibleTo(dialog) is False

        dialog.focus_term("CLERK_A")
        assert dialog._speaker_identity_pane.isVisibleTo(dialog) is False

    def test_proposal_and_evidence_display(self, qtbot):
        prov_char = GlossaryEntry(
            original="Ash",
            translation="",
            notes="",
            section="Characters",
            provisional=True,
            suggested_name="Ashy",
            suggested_name_evidence="Dialogue lines say 'Ashy!'",
        )
        dialog = _dialog(qtbot, [prov_char])
        dialog.focus_term("Ash")

        assert dialog._speaker_evidence_label.isVisibleTo(dialog) is True
        text = dialog._speaker_evidence_label.text()
        assert "Ashy" in text
        assert "Dialogue lines say" in text

    def test_candidates_building_and_filtering(self, qtbot):
        prov_char = GlossaryEntry(
            original="Ash",
            translation="",
            notes="",
            section="Characters",
            provisional=True,
            suggested_name="Ashy",
        )
        perm_char1 = GlossaryEntry(
            original="Brock",
            translation="",
            notes="",
            section="Characters",
            provisional=False,
        )
        perm_char2 = GlossaryEntry(
            original="Misty",
            translation="",
            notes="",
            section="Characters",
            provisional=False,
        )
        other_prov = GlossaryEntry(
            original="BOY_A",
            translation="Хлопчик",
            notes="",
            section="Characters",
            provisional=True,
            suggested_name="Tommy",
        )
        dialog = _dialog(qtbot, [prov_char, perm_char1, perm_char2, other_prov])

        candidates = dialog._build_speaker_candidates(prov_char)
        assert "Ashy" in candidates
        assert "Brock" in candidates
        assert "Misty" in candidates
        assert "Tommy" in candidates

        assert "Ash" not in candidates
        assert "BOY_A" not in candidates
        assert "Хлопчик" not in candidates

    def test_manual_entry_and_validation(self, qtbot):
        prov_char = GlossaryEntry(
            original="Ash",
            translation="",
            notes="",
            section="Characters",
            provisional=True,
        )
        other_prov = GlossaryEntry(
            original="BOY_A",
            translation="",
            notes="",
            section="Characters",
            provisional=True,
        )
        dialog = GlossaryDialog(
            entries=[prov_char, other_prov],
            occurrence_map={},
            parent=None,
            jump_callback=MagicMock(),
            apply_speaker_name_callback=MagicMock(),
        )
        qtbot.addWidget(dialog)
        dialog.focus_term("Ash")

        dialog._speaker_name_combo.setEditText("Ash")
        assert dialog._apply_speaker_name_button.isEnabled() is False

        dialog._speaker_name_combo.setEditText("   ")
        assert dialog._apply_speaker_name_button.isEnabled() is False

        dialog._speaker_name_combo.setEditText("BOY_A")
        assert dialog._apply_speaker_name_button.isEnabled() is False

        dialog._speaker_name_combo.setEditText("Ashy")
        assert dialog._apply_speaker_name_button.isEnabled() is True

    def test_explicit_apply_callback(self, qtbot):
        callback = MagicMock()
        prov_char = GlossaryEntry(
            original="Ash",
            translation="",
            notes="",
            section="Characters",
            provisional=True,
            suggested_name="Ashy",
        )
        dialog = GlossaryDialog(
            entries=[prov_char],
            occurrence_map={},
            parent=None,
            jump_callback=MagicMock(),
            apply_speaker_name_callback=callback,
        )
        qtbot.addWidget(dialog)
        dialog.focus_term("Ash")

        callback.assert_not_called()

        dialog._speaker_name_combo.setEditText("Ashy")
        dialog._apply_speaker_name_button.click()

        callback.assert_called_once_with("Ash", "Ashy")

    def test_unsafe_prefill_prevented_when_no_suggested_name(self, qtbot):
        prov_char = GlossaryEntry(
            original="Ash",
            translation="",
            notes="",
            section="Characters",
            provisional=True,
            suggested_name="",
        )
        perm_char = GlossaryEntry(
            original="Brock",
            translation="",
            notes="",
            section="Characters",
            provisional=False,
        )
        dialog = GlossaryDialog(
            entries=[prov_char, perm_char],
            occurrence_map={},
            parent=None,
            jump_callback=MagicMock(),
            apply_speaker_name_callback=MagicMock(),
        )
        qtbot.addWidget(dialog)
        dialog.focus_term("Ash")

        assert dialog._speaker_name_combo.currentText() == ""
        assert dialog._apply_speaker_name_button.isEnabled() is False

    def test_legitimate_permanent_original_equals_translation_remains_candidate(self, qtbot):
        prov_char = GlossaryEntry(
            original="GORON_A",
            translation="",
            notes="",
            section="Characters",
            provisional=True,
        )
        perm_char = GlossaryEntry(
            original="Goron",
            translation="",
            notes="",
            section="Characters",
            provisional=False,
        )
        other_term = GlossaryEntry(
            original="Spring",
            translation="Goron",
            notes="",
            section="Terms",
            provisional=False,
        )
        dialog = _dialog(qtbot, [prov_char, perm_char, other_term])

        candidates = dialog._build_speaker_candidates(prov_char)
        assert "Goron" in candidates

    def test_callback_less_dialog_keeps_apply_disabled_and_click_is_noop(self, qtbot):
        prov_char = GlossaryEntry(
            original="Ash",
            translation="",
            notes="",
            section="Characters",
            provisional=True,
            suggested_name="Ashy",
            suggested_name_evidence="Evidence text",
        )
        dialog = GlossaryDialog(
            entries=[prov_char],
            occurrence_map={},
            parent=None,
            jump_callback=MagicMock(),
            apply_speaker_name_callback=None,
        )
        qtbot.addWidget(dialog)
        dialog.focus_term("Ash")

        assert dialog._speaker_identity_pane.isVisibleTo(dialog) is True
        assert dialog._apply_speaker_name_button.isEnabled() is False
        dialog._speaker_name_combo.setEditText("Ashy")
        assert dialog._apply_speaker_name_button.isEnabled() is False

        # Direct click invocation must be no-op and not crash
        dialog._on_apply_speaker_name_clicked()
