"""M2: surfacing translation variants and the review state in the glossary dialog."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from components.glossary_dialog import (
    GlossaryDialog,
    _MULTI_VARIANT_BRUSH,
    _UNREVIEWED_BRUSH,
)
from core.glossary_manager import (
    STATUS_CONFIRMED,
    STATUS_TRANSLATED,
    DescriptionFragment,
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
AMBIGUOUS_2 = _entry(
    "Autumn Goron",
    "Осінній Ґорон",
    status=STATUS_TRANSLATED,
    variants=(
        TranslationVariant("Осінній Ґорон", "autumn"),
        TranslationVariant("Ґорон Осені", "fall"),
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
    reassign_speaker_callback=None,
    speaker_codes_callback=None,
    discuss_variant_callback=None,
    external_reference_callback=None,
    force_retranslate_callback=None,
):
    dialog = GlossaryDialog(
        entries=entries,
        occurrence_map={},
        parent=None,
        jump_callback=MagicMock(),
        update_callback=update_callback,
        placeholder_speaker_callback=placeholder_speaker_callback,
        apply_speaker_name_callback=apply_speaker_name_callback,
        reassign_speaker_callback=reassign_speaker_callback,
        speaker_codes_callback=speaker_codes_callback,
        discuss_variant_callback=discuss_variant_callback,
        external_reference_callback=external_reference_callback,
        force_retranslate_callback=force_retranslate_callback,
    )
    dialog._settings_path = Path(tempfile.gettempdir()) / f"picoripi_test_settings_{id(dialog)}.json"
    qtbot.addWidget(dialog)
    return dialog


class TestTableScroll:
    def test_selecting_the_translation_cell_does_not_pan_sideways(self, qtbot):
        dialog = _dialog(qtbot, [SINGLE, AMBIGUOUS, CONFIRMED])
        table = dialog._active_table()
        table.setColumnWidth(0, 420)
        table.setColumnWidth(1, 420)
        table.setColumnWidth(2, 800)
        table.resize(260, 180)
        bar = table.horizontalScrollBar()
        bar.setValue(0)
        table.setCurrentCell(0, 1)
        assert bar.value() == 0


class TestReviewColours:
    def _row_brush(self, dialog, term):
        table = dialog._active_table()
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item and item.text() == term:
                return item.background()
        raise AssertionError(f"missing row {term}")

    def test_unreviewed_and_ambiguous_rows_are_different_colours(self, qtbot):
        dialog = _dialog(qtbot, [SINGLE, AMBIGUOUS, CONFIRMED, LEGACY])
        assert self._row_brush(dialog, "Ordon") == _UNREVIEWED_BRUSH
        assert self._row_brush(dialog, "Spring Goron") == _MULTI_VARIANT_BRUSH
        assert self._row_brush(dialog, "Ordon") != self._row_brush(dialog, "Spring Goron")

    def test_confirmed_and_legacy_rows_are_not_tinted(self, qtbot):
        dialog = _dialog(qtbot, [SINGLE, AMBIGUOUS, CONFIRMED, LEGACY])
        confirmed = self._row_brush(dialog, "Link")
        legacy = self._row_brush(dialog, "Midna")
        assert confirmed != _UNREVIEWED_BRUSH
        assert confirmed != _MULTI_VARIANT_BRUSH
        assert legacy != _UNREVIEWED_BRUSH
        assert legacy != _MULTI_VARIANT_BRUSH


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
        dialog._filter_timer.stop()
        dialog._apply_filter(dialog._search_field.text())
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

    def test_single_click_selects_variant_without_modifying_or_confirming(self, qtbot):
        from PyQt6.QtCore import Qt
        callback = MagicMock()
        dialog = _dialog(qtbot, [AMBIGUOUS, SINGLE], update_callback=callback)
        dialog.show()
        dialog.focus_term("Spring Goron")
        assert dialog._translation_edit.text() == "Ґорон Джерела"
        assert dialog._current_entry.original == "Spring Goron"

        # Simulate a real single click on the second proposed-variant item
        rect = dialog._variants_list.visualItemRect(dialog._variants_list.item(1))
        qtbot.mouseClick(dialog._variants_list.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())

        # Assert variant is selected in the list
        assert dialog._variants_list.currentRow() == 1
        # Assert callback was NOT called
        callback.assert_not_called()
        # Assert entry status is still STATUS_TRANSLATED (not confirmed)
        assert dialog._current_entry.status == STATUS_TRANSLATED
        assert dialog._current_entry.status != STATUS_CONFIRMED
        # Assert translation edit unchanged
        assert dialog._translation_edit.text() == "Ґорон Джерела"
        # Assert dialog remains on the same glossary term
        assert dialog._current_entry.original == "Spring Goron"

    def test_variant_list_uses_horizontal_separators(self, qtbot):
        from components.glossary_dialog import _VariantItemDelegate
        dialog = _dialog(qtbot, [AMBIGUOUS])
        delegate = dialog._variants_list.itemDelegate()
        assert isinstance(delegate, _VariantItemDelegate)

    def test_rich_text_item_delegate_size_hint_returns_qsize(self, qtbot):
        from PyQt6.QtCore import QSize, Qt
        from PyQt6.QtWidgets import QStyleOptionViewItem
        from components.glossary_dialog import _RichTextItemDelegate
        from core.glossary_manager import GlossaryOccurrence

        occ = GlossaryOccurrence(AMBIGUOUS, 0, 0, 0, 0, 0, "<b>Goron</b> text")
        dialog = _dialog(qtbot, [AMBIGUOUS])
        dialog._occurrences = {AMBIGUOUS.original: [occ]}
        dialog._update_occurrences(AMBIGUOUS)

        delegate = dialog._occurrence_list.itemDelegate()
        assert isinstance(delegate, _RichTextItemDelegate)
        assert dialog._occurrence_list.count() > 0

        item = dialog._occurrence_list.item(0)
        index = dialog._occurrence_list.indexFromItem(item)
        assert index.data(Qt.ItemDataRole.DisplayRole)  # non-empty HTML text

        option = QStyleOptionViewItem()
        option.font = dialog.font()
        option.widget = dialog._occurrence_list
        option.rect.setWidth(300)

        hint = delegate.sizeHint(option, index)
        assert isinstance(hint, QSize)
        assert hint.isValid()
        assert hint.width() > 0
        assert hint.height() > 14


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

    def test_confirm_button_visible_for_settled_entry(self, qtbot):
        dialog = _dialog(qtbot, [CONFIRMED], update_callback=MagicMock())
        dialog._populate_variants(CONFIRMED)
        assert dialog._confirm_button.isVisibleTo(dialog) is True
        assert dialog._confirm_button.isEnabled() is True

    def test_confirm_button_hidden_when_no_entry_selected(self, qtbot):
        dialog = _dialog(qtbot, [CONFIRMED], update_callback=MagicMock())
        dialog._populate_variants(None)
        assert dialog._confirm_button.isVisibleTo(dialog) is False

    def test_confirm_button_click_on_settled_entry_saves_custom_translation_and_advances(self, qtbot):
        first = _entry("Aardvark", "А", status=STATUS_CONFIRMED)
        second = _entry("Bear", "Б", status=STATUS_CONFIRMED)

        def update(original, translation, notes, profiled=None, **kwargs):
            confirmed = _entry(original, translation, notes=notes, status=STATUS_CONFIRMED)
            rest = [e for e in (first, second) if e.original != original]
            return ([confirmed, *rest], {})

        dialog = _dialog(qtbot, [first, second], update_callback=update)
        dialog._show_entry_for_row(0)
        assert dialog._current_entry.original == "Aardvark"
        assert dialog._confirm_button.isVisibleTo(dialog) is True

        dialog._translation_edit.setText("Аардварк новий")
        dialog._confirm_button.click()

        assert dialog._current_entry.original == "Bear"
        assert dialog._all_entries[0].translation == "Аардварк новий"


    def test_confirm_advances_to_the_next_term(self, qtbot):
        first = _entry("Aardvark", "А", status=STATUS_TRANSLATED)
        second = _entry("Bear", "Б", status=STATUS_TRANSLATED)

        def update(original, translation, notes, profiled=None, **kwargs):
            confirmed = _entry(original, translation, notes=notes, status=STATUS_CONFIRMED)
            rest = [e for e in (first, second) if e.original != original]
            return ([confirmed, *rest], {})

        dialog = _dialog(qtbot, [first, second], update_callback=update)
        dialog._show_entry_for_row(0)
        assert dialog._current_entry.original == "Aardvark"
        dialog._on_confirm_clicked()
        assert dialog._current_entry.original == "Bear"

    def test_confirm_button_click_advances_to_the_next_term(self, qtbot):
        first = _entry("Aardvark", "А", status=STATUS_TRANSLATED)
        second = _entry("Bear", "Б", status=STATUS_TRANSLATED)

        def update(original, translation, notes, profiled=None, **kwargs):
            confirmed = _entry(original, translation, notes=notes, status=STATUS_CONFIRMED)
            rest = [e for e in (first, second) if e.original != original]
            return ([confirmed, *rest], {})

        dialog = _dialog(qtbot, [first, second], update_callback=update)
        dialog._show_entry_for_row(0)
        assert dialog._current_entry.original == "Aardvark"
        dialog._confirm_button.click()
        assert dialog._current_entry.original == "Bear"

    def test_confirm_button_click_in_needs_review_mode_advances_to_next(self, qtbot):
        first = _entry("Aardvark", "А", status=STATUS_TRANSLATED)
        second = _entry("Bear", "Б", status=STATUS_TRANSLATED)

        entries_state = [first, second]

        def update(original, translation, notes, profiled=None, **kwargs):
            nonlocal entries_state
            confirmed = _entry(original, translation, notes=notes, status=STATUS_CONFIRMED)
            entries_state = [confirmed if e.original == original else e for e in entries_state]
            return (entries_state, {})

        dialog = _dialog(qtbot, [first, second], update_callback=update)
        dialog._unconfirmed_only_checkbox.setChecked(True)
        assert dialog._active_table().rowCount() == 2
        dialog._show_entry_for_row(0)
        assert dialog._current_entry.original == "Aardvark"

        dialog._confirm_button.click()

        # Aardvark should now be confirmed and filtered out, active selection advances to Bear
        assert dialog._active_table().rowCount() == 1
        assert dialog._current_entry.original == "Bear"

    def test_confirm_button_click_on_last_item_in_needs_review_walks_to_previous(self, qtbot):
        first = _entry("Aardvark", "А", status=STATUS_TRANSLATED)
        second = _entry("Bear", "Б", status=STATUS_TRANSLATED)

        entries_state = [first, second]

        def update(original, translation, notes, profiled=None, **kwargs):
            nonlocal entries_state
            confirmed = _entry(original, translation, notes=notes, status=STATUS_CONFIRMED)
            entries_state = [confirmed if e.original == original else e for e in entries_state]
            return (entries_state, {})

        dialog = _dialog(qtbot, [first, second], update_callback=update)
        dialog._unconfirmed_only_checkbox.setChecked(True)
        dialog._show_entry_for_row(1)
        dialog._active_table().setCurrentCell(1, 0)
        assert dialog._current_entry.original == "Bear"

        dialog._confirm_button.click()

        # Bear is confirmed and filtered out, walks to previous remaining item (Aardvark)
        assert dialog._active_table().rowCount() == 1
        assert dialog._current_entry.original == "Aardvark"

    def test_confirm_on_the_last_term_stays_there(self, qtbot):
        only = _entry("Aardvark", "А", status=STATUS_TRANSLATED)
        confirmed = _entry("Aardvark", "А", status=STATUS_CONFIRMED)

        dialog = _dialog(
            qtbot,
            [only],
            update_callback=lambda *a, **k: ([confirmed], {}),
        )
        dialog._show_entry_for_row(0)
        dialog._on_confirm_clicked()
        assert dialog._current_entry.original == "Aardvark"

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

    def test_choosing_a_variant_applies_to_editor_without_confirming(self, qtbot):
        callback = MagicMock(return_value=([CONFIRMED], {}))
        dialog = _dialog(qtbot, [AMBIGUOUS], update_callback=callback)
        dialog._current_entry = AMBIGUOUS
        dialog._populate_variants(AMBIGUOUS)

        dialog._on_variant_chosen(dialog._variants_list.item(1))

        assert dialog._translation_edit.text() == "Весняний Ґорон"
        callback.assert_not_called()

    def test_apply_selected_variant_button_applies_without_advancing(self, qtbot):
        second = _entry("Ordon", "Ордон", status=STATUS_TRANSLATED)

        def update_cb(orig, trans, notes, profiled=None, status=None, select_after=None):
            c = _entry(orig, trans, notes=notes, status=status)
            return ([c, second], {})

        dialog = _dialog(qtbot, [AMBIGUOUS, second], update_callback=update_cb)
        dialog._show_entry_for_row(0)
        assert dialog._current_entry.original == "Spring Goron"

        dialog._variants_list.setCurrentRow(1)
        assert dialog._apply_variant_button.isEnabled() is True
        dialog._apply_variant_button.click()

        assert dialog._translation_edit.text() == "Весняний Ґорон"
        assert dialog._current_entry.original == "Spring Goron"

        # Explicit confirmation settles and advances to the next entry
        dialog._confirm_button.click()
        assert dialog._current_entry.original == "Ordon"

    def test_double_click_on_variant_applies_variant_without_advancing(self, qtbot):
        from PyQt6.QtCore import Qt

        second = _entry("Ordon", "Ордон", status=STATUS_TRANSLATED)
        callback = MagicMock(return_value=([CONFIRMED, second], {}))
        dialog = _dialog(qtbot, [AMBIGUOUS, second], update_callback=callback)
        dialog.show()
        dialog.focus_term("Spring Goron")
        assert dialog._translation_edit.text() == "Ґорон Джерела"
        assert dialog._current_entry.original == "Spring Goron"
        assert dialog._variants_list.currentRow() == 0

        rect = dialog._variants_list.visualItemRect(dialog._variants_list.item(1))
        qtbot.mouseClick(dialog._variants_list.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
        qtbot.mouseDClick(dialog._variants_list.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())

        assert dialog._variants_list.currentRow() == 1
        callback.assert_not_called()
        assert dialog._translation_edit.text() == "Весняний Ґорон"
        assert dialog._current_entry.original == "Spring Goron"
        assert dialog._current_entry.status == STATUS_TRANSLATED
        assert dialog._current_entry.status != STATUS_CONFIRMED

        # Confirm explicitly to settle and advance
        dialog._on_confirm_clicked(advance=True)
        callback.assert_called_once()

    def test_discuss_with_ai_button_invokes_callback(self, qtbot):
        discuss_cb = MagicMock()
        dialog = _dialog(qtbot, [AMBIGUOUS], discuss_variant_callback=discuss_cb)
        dialog._current_entry = AMBIGUOUS
        dialog._populate_variants(AMBIGUOUS)

        assert dialog._discuss_variant_button.isVisibleTo(dialog) is True
        assert dialog._discuss_variant_button.isEnabled() is True
        dialog._discuss_variant_button.click()
        discuss_cb.assert_called_once_with(AMBIGUOUS)

    def test_discuss_with_ai_button_disabled_without_callback(self, qtbot):
        dialog = _dialog(qtbot, [AMBIGUOUS], discuss_variant_callback=None)
        dialog._current_entry = AMBIGUOUS
        dialog._populate_variants(AMBIGUOUS)

        assert dialog._discuss_variant_button.isEnabled() is False

    def test_discuss_with_ai_button_visible_and_enabled_for_term_without_variants(self, qtbot):
        discuss_cb = MagicMock()
        dialog = _dialog(qtbot, [SINGLE], discuss_variant_callback=discuss_cb)
        dialog.show()
        dialog.focus_term("Ordon")

        # Even though SINGLE has no multiple variants and variants_pane is hidden,
        # the discuss button in trans_box remains visible and enabled.
        assert dialog._variants_pane.isVisibleTo(dialog) is False
        assert dialog._discuss_variant_button.isVisibleTo(dialog) is True
        assert dialog._discuss_variant_button.isEnabled() is True

        dialog._discuss_variant_button.click()
        discuss_cb.assert_called_once()
        passed_entry = discuss_cb.call_args.args[0]
        assert passed_entry.original == "Ordon"

    def test_discuss_with_ai_captures_active_ui_edits(self, qtbot):
        discuss_cb = MagicMock()
        dialog = _dialog(qtbot, [SINGLE], discuss_variant_callback=discuss_cb)
        dialog.show()
        dialog.focus_term("Ordon")

        dialog._translation_edit.setText("Ордонське Село")
        dialog._category_combo.setEditText("Locations")
        dialog._notes_edit.setPlainText("Село, де живе Лінк.")

        dialog._discuss_variant_button.click()
        discuss_cb.assert_called_once()
        passed_entry = discuss_cb.call_args.args[0]
        assert passed_entry.original == "Ordon"
        assert passed_entry.translation == "Ордонське Село"
        assert passed_entry.section == "Locations"
        assert passed_entry.notes == "Село, де живе Лінк."

    def test_table_context_menu_has_discuss_with_ai_action(self, qtbot):
        discuss_cb = MagicMock()
        dialog = _dialog(qtbot, [SINGLE], discuss_variant_callback=discuss_cb)
        dialog.show()

        table = dialog._active_table()
        entry = dialog._entry_for_row(0)
        assert entry is not None
        assert entry.original == "Ordon"

        from unittest.mock import patch
        from PyQt6.QtWidgets import QMenu
        with patch.object(QMenu, "exec") as mock_exec:
            def side_effect(*args, **kwargs):
                menus = dialog.findChildren(QMenu)
                if menus:
                    for action in menus[-1].actions():
                        if "Discuss with AI" in action.text() or "Обговорити" in action.text():
                            return action
                return None
            mock_exec.side_effect = side_effect
            from PyQt6.QtCore import QPoint
            row_y = table.rowViewportPosition(0) + 5
            dialog._on_entry_context_menu(QPoint(10, row_y))

        discuss_cb.assert_called_once()
        assert discuss_cb.call_args.args[0].original == "Ordon"

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

    def test_variants_pane_is_expandable_splitter_child_and_not_collapsed(self, qtbot):
        dialog = _dialog(qtbot, [AMBIGUOUS, SINGLE, AMBIGUOUS_2])
        dialog.show()
        assert hasattr(dialog, "_main_splitter")
        assert dialog._main_splitter.handleWidth() >= 4
        assert hasattr(dialog, "_detail_splitter")
        assert dialog._detail_splitter.widget(0) == dialog._variants_pane
        assert dialog._detail_splitter.handleWidth() >= 4
        assert dialog._lower_detail_splitter.count() == 3
        assert dialog._lower_detail_splitter.handleWidth() >= 4
        assert dialog._variants_pane.sizePolicy().verticalPolicy().name == "Expanding"

        dialog.focus_term("Spring Goron")
        assert dialog._variants_pane.isVisibleTo(dialog) is True
        sizes = dialog._detail_splitter.sizes()
        assert sizes[0] > 0

        # Choose a nonzero custom variants-pane height and record actual size
        dialog._detail_splitter.setSizes([500, 50])
        chosen_height = dialog._detail_splitter.sizes()[0]
        assert chosen_height > sizes[0]

        # Switching between multi-variant terms preserves the chosen size
        dialog.focus_term("Autumn Goron")
        assert abs(dialog._detail_splitter.sizes()[0] - chosen_height) <= 2

        # User chooses a shorter height, and switching terms preserves it
        dialog._detail_splitter.setSizes([60, 600])
        short_height = dialog._detail_splitter.sizes()[0]
        assert short_height < 100
        dialog.focus_term("Spring Goron")
        assert abs(dialog._detail_splitter.sizes()[0] - short_height) <= 2

        # Switch to the single-variant term so the pane is hidden
        dialog.focus_term("Ordon")
        assert dialog._variants_pane.isVisibleTo(dialog) is False

        # Switch back to a multi-variant term and assert size is preserved within tolerance
        dialog.focus_term("Spring Goron")
        assert dialog._variants_pane.isVisibleTo(dialog) is True
        assert abs(dialog._detail_splitter.sizes()[0] - short_height) <= 2

        # If user collapsed the pane to zero, populating or switching restores it with usable nonzero height
        dialog._detail_splitter.setSizes([0, 600])
        assert dialog._detail_splitter.sizes()[0] == 0
        dialog._populate_variants(AMBIGUOUS)
        assert dialog._detail_splitter.sizes()[0] > 0

        # The resize handle belongs to the list, before its action buttons.
        handle = dialog._detail_splitter.handle(1)
        handle_y = handle.mapToGlobal(handle.rect().center()).y()
        list_bottom = dialog._variants_list.mapToGlobal(dialog._variants_list.rect().bottomLeft()).y()
        buttons_top = dialog._apply_variant_button.mapToGlobal(dialog._apply_variant_button.rect().topLeft()).y()
        assert list_bottom <= handle_y < buttons_top

        # Resize the main horizontal splitter in both directions and check variants pane width
        dialog._main_splitter.setSizes([200, 600])
        qtbot.wait_exposed(dialog)
        wide_width = dialog._variants_pane.width()

        dialog._main_splitter.setSizes([600, 200])
        qtbot.wait_exposed(dialog)
        narrow_width = dialog._variants_pane.width()

        assert wide_width > narrow_width


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
        # Stored form keeps the token, so saving/confirming persists it.
        dialog._on_confirm_clicked()
        assert callback.call_args.args[2] == self.TEMPLATE

    def test_hand_edited_notes_are_stored_verbatim(self, qtbot):
        callback = MagicMock(return_value=([], {}))
        dialog, _ = self._dialog_with_template(qtbot, update_callback=callback)
        dialog._notes_edit.setPlainText("Моє власне пояснення.")

        dialog._save_editor_changes()

        assert callback.call_args.args[2] == "Моє власне пояснення."


class TestAiNotesPlaceholder:
    """Sweep fragments keep {{TERM}} stored; the pane shows the chosen name."""

    def _dialog_with_fragments(self, qtbot, update_callback=None):
        entry = GlossaryEntry(
            original="Agitha",
            translation="Агіта",
            notes="{{TERM}} — персонаж, що збирає комах.",
            status=STATUS_TRANSLATED,
            fragments=(
                DescriptionFragment("{{TERM}} — це принцеса жучиного царства."),
                DescriptionFragment("{{TERM}} живе у будинку в Замку Гірул."),
            ),
            translation_variants=(
                TranslationVariant("Агіта", "трансліт"),
                TranslationVariant("Агіта Принцеса", "з титулом"),
            ),
        )
        dialog = _dialog(qtbot, [entry], update_callback=update_callback)
        dialog._current_entry = entry
        dialog._populate_entry_details(entry)
        return dialog, entry

    def test_ai_notes_show_the_active_translation_not_the_token(self, qtbot):
        dialog, _ = self._dialog_with_fragments(qtbot)
        shown = dialog._ai_notes_edit.toPlainText()
        assert "{{TERM}}" not in shown
        assert "Агіта — це принцеса жучиного царства." in shown
        assert "Агіта живе у будинку в Замку Гірул." in shown

    def test_ai_notes_follow_a_newly_picked_variant(self, qtbot):
        callback = MagicMock(return_value=([], {}))
        dialog, entry = self._dialog_with_fragments(qtbot, update_callback=callback)
        dialog._populate_variants(entry)

        dialog._on_variant_chosen(dialog._variants_list.item(1))

        shown = dialog._ai_notes_edit.toPlainText()
        assert "{{TERM}}" not in shown
        assert "Агіта Принцеса — це принцеса жучиного царства." in shown

    def test_ai_notes_follow_a_typed_translation(self, qtbot):
        callback = MagicMock(return_value=([], {}))
        dialog, _ = self._dialog_with_fragments(qtbot, update_callback=callback)

        dialog._translation_edit.setText("Агітка")

        shown = dialog._ai_notes_edit.toPlainText()
        assert "{{TERM}}" not in shown
        assert "Агітка — це принцеса жучиного царства." in shown

    def test_ai_notes_edit_is_editable_and_saves_user_notes(self, qtbot):
        callback = MagicMock(return_value=([], {}))
        dialog, _ = self._dialog_with_fragments(qtbot, update_callback=callback)

        assert not dialog._ai_notes_edit.isReadOnly()

        # Type custom user notes
        dialog._ai_notes_edit.setPlainText("Моя власна замітка про персонажа.")
        assert dialog._editor_dirty is True

        dialog._save_editor_changes()
        assert callback.called
        assert callback.call_args.kwargs.get("user_notes") == "Моя власна замітка про персонажа."

    def test_entry_with_saved_user_notes_displays_user_notes(self, qtbot):
        entry = GlossaryEntry(
            original="Agitha",
            translation="Махаона",
            notes="{{TERM}} — колекціонер жуків.",
            user_notes="Вже збережені нотатки користувача.",
        )
        dialog = _dialog(qtbot, [entry])
        dialog._current_entry = entry
        dialog._populate_entry_details(entry)

        assert dialog._ai_notes_edit.toPlainText() == "Вже збережені нотатки користувача."

    def test_literal_name_in_notes_normalizes_to_placeholder_and_shows_active_translation(self, qtbot):
        entry = GlossaryEntry(
            original="Agitha",
            translation="Махаона",
            notes="Аґіта — персонаж, дівчинка з жуками.",
            translation_variants=(
                TranslationVariant("Аґіта", "трансліт"),
                TranslationVariant("Махаона", "переклад"),
            ),
        )
        dialog = _dialog(qtbot, [entry])
        dialog._current_entry = entry
        dialog._populate_entry_details(entry)

        # The notes editor displays the active translation "Махаона"
        assert dialog._notes_edit.toPlainText().startswith("Махаона — персонаж")
        assert "Аґіта —" not in dialog._notes_edit.toPlainText()
        # The internal template has the token
        assert "{{TERM}}" in dialog._notes_template


class TestGlossarySaveNotesAndNavigationPrompt:
    """Save Note / Save Description buttons and prompt on row switch or close."""

    def _two_entries_dialog(self, qtbot, update_callback=None):
        e1 = GlossaryEntry(original="Agitha", translation="Агіта", notes="{{TERM}} — дівчинка.")
        e2 = GlossaryEntry(original="Barnes", translation="Барнс", notes="{{TERM}} — продавець.")
        dialog = _dialog(qtbot, [e1, e2], update_callback=update_callback)
        dialog.show()
        table = dialog._active_table()
        table.setCurrentCell(0, 0)
        return dialog, e1, e2

    def test_save_term_button_state_and_click(self, qtbot):
        callback = MagicMock(return_value=([GlossaryEntry(original="Agitha", translation="Агіта", notes="Оновлено")], {}))
        dialog, _, _ = self._two_entries_dialog(qtbot, update_callback=callback)

        assert hasattr(dialog, "_save_term_button")
        assert dialog._save_term_button.isEnabled() is False

        # Editing notes enables the button and gives it the accent blue style
        dialog._notes_edit.setPlainText("Оновлено")
        assert dialog._editor_dirty is True
        assert dialog._save_term_button.isEnabled() is True
        assert "#2563eb" in dialog._save_term_button.styleSheet()

        # Clicking saves without advancing the selected row
        table = dialog._active_table()
        assert table.currentRow() == 0
        dialog._save_term_button.click()
        assert callback.called
        assert dialog._editor_dirty is False
        assert dialog._save_term_button.isEnabled() is False
        assert table.currentRow() == 0

    def test_save_notes_button_state_and_click(self, qtbot):
        callback = MagicMock(return_value=([GlossaryEntry(original="Agitha", translation="Агіта", notes="n", user_notes="Моя нотатка")], {}))
        dialog, _, _ = self._two_entries_dialog(qtbot, update_callback=callback)

        assert hasattr(dialog, "_save_notes_button")
        assert dialog._save_notes_button.isEnabled() is False

        # Typing in _ai_notes_edit enables the button
        dialog._ai_notes_edit.setPlainText("Моя нотатка")
        assert dialog._editor_dirty is True
        assert dialog._save_notes_button.isEnabled() is True
        assert "#2563eb" in dialog._save_notes_button.styleSheet()

        # Clicking _save_notes_button saves changes
        dialog._save_notes_button.click()
        assert callback.called
        assert callback.call_args.kwargs.get("user_notes") == "Моя нотатка"
        assert dialog._editor_dirty is False
        assert dialog._save_notes_button.isEnabled() is False

    def test_save_description_button_state_and_click(self, qtbot):
        callback = MagicMock(return_value=([GlossaryEntry(original="Agitha", translation="Агіта", notes="Новий опис")], {}))
        dialog, _, _ = self._two_entries_dialog(qtbot, update_callback=callback)

        assert hasattr(dialog, "_save_description_button")
        assert dialog._save_description_button.isEnabled() is False

        dialog._notes_edit.setPlainText("Новий опис")
        assert dialog._editor_dirty is True
        assert dialog._save_description_button.isEnabled() is True
        assert "#2563eb" in dialog._save_description_button.styleSheet()

        dialog._save_description_button.click()
        assert callback.called
        assert callback.call_args.args[2] == "Новий опис"
        assert dialog._editor_dirty is False
        assert dialog._save_description_button.isEnabled() is False

    def test_switch_row_prompt_save(self, qtbot, monkeypatch):
        callback = MagicMock(return_value=([
            GlossaryEntry(original="Agitha", translation="Агіта", notes="n", user_notes="Зберегти це"),
            GlossaryEntry(original="Barnes", translation="Барнс", notes="n2"),
        ], {}))
        dialog, e1, e2 = self._two_entries_dialog(qtbot, update_callback=callback)

        dialog._ai_notes_edit.setPlainText("Зберегти це")
        assert dialog._editor_dirty is True

        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Save)

        table = dialog._active_table()
        table.setCurrentCell(1, 0)

        assert callback.called
        assert callback.call_args.kwargs.get("user_notes") == "Зберегти це"
        assert dialog._current_entry.original == "Barnes"
        assert dialog._editor_dirty is False

    def test_switch_row_prompt_discard(self, qtbot, monkeypatch):
        callback = MagicMock()
        dialog, e1, e2 = self._two_entries_dialog(qtbot, update_callback=callback)

        dialog._ai_notes_edit.setPlainText("Не зберігати це")
        assert dialog._editor_dirty is True

        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Discard)

        table = dialog._active_table()
        table.setCurrentCell(1, 0)

        assert not callback.called
        assert dialog._current_entry.original == "Barnes"
        assert dialog._editor_dirty is False

    def test_switch_row_prompt_cancel(self, qtbot, monkeypatch):
        callback = MagicMock()
        dialog, e1, e2 = self._two_entries_dialog(qtbot, update_callback=callback)

        dialog._ai_notes_edit.setPlainText("Залишитися тут")
        assert dialog._editor_dirty is True

        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Cancel)

        table = dialog._active_table()
        table.setCurrentCell(1, 0)

        assert not callback.called
        assert dialog._current_entry.original == "Agitha"
        assert dialog._editor_dirty is True
        assert table.currentRow() == 0
        dialog._mark_editor_dirty(False)

    def test_close_event_prompt_cancel(self, qtbot, monkeypatch):
        callback = MagicMock()
        dialog, e1, e2 = self._two_entries_dialog(qtbot, update_callback=callback)

        dialog._ai_notes_edit.setPlainText("Не закривати")
        assert dialog._editor_dirty is True

        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Cancel)

        event = MagicMock()
        dialog.closeEvent(event)
        assert event.ignore.called
        dialog._mark_editor_dirty(False)


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


class TestCategoryAssignment:
    def test_existing_category_is_reused_case_insensitively(self, qtbot):
        entry = GlossaryEntry("Ash", "", "", section="Characters")
        item = GlossaryEntry("Boomerang", "", "", section="Items")
        dialog = _dialog(qtbot, [entry, item], update_callback=MagicMock())

        assert dialog._canonical_category_name("items") == "Items"

    def test_new_category_is_saved_and_becomes_a_tab(self, qtbot):
        entry = GlossaryEntry("Ash", "", "", section="Characters")
        item = GlossaryEntry("Boomerang", "", "", section="Items")
        moved_entry = GlossaryEntry("Ash", "", "", section="Creatures")
        callback = MagicMock(return_value=([moved_entry, item], {}))
        dialog = _dialog(qtbot, [entry, item], update_callback=callback)
        dialog.focus_term("Ash")

        dialog._category_combo.setEditText("Creatures")
        dialog._save_editor_changes()

        assert callback.call_args.kwargs["section"] == "Creatures"
        assert "Creatures" in [
            dialog._tab_widget.tabToolTip(index)
            for index in range(dialog._tab_widget.count())
        ]


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

        dialog._speaker_name_combo.setEditText("Ashei / Telma")
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

    def test_confirmed_character_can_be_reassigned_by_its_game_code(self, qtbot):
        ashei = GlossaryEntry("ASHEI", "", section="Characters")
        telma = GlossaryEntry("TELMA", "", section="Characters")
        reassign = MagicMock()
        dialog = _dialog(
            qtbot,
            [ashei, telma],
            reassign_speaker_callback=reassign,
            speaker_codes_callback=lambda name: ["Ash"] if name == "ASHEI" else [],
        )
        dialog.focus_term("ASHEI")

        assert dialog._speaker_identity_pane.isVisibleTo(dialog) is True
        assert "Ash" in dialog._speaker_identity_title.text()
        assert dialog._apply_speaker_name_button.text() == "Reassign speaker"
        assert dialog._apply_speaker_name_button.isEnabled() is False

        dialog._speaker_name_combo.setEditText("TELMA")
        assert dialog._apply_speaker_name_button.isEnabled() is True
        dialog._apply_speaker_name_button.click()
        reassign.assert_called_once_with("Ash", "ASHEI", "TELMA")


class TestGlossaryOccurrenceDisplayAndNavigation:
    """Occurrence display numbering and activation."""

    def test_occurrence_display_uses_one_based_string_number_and_retains_zero_based_user_role(self, qtbot):
        from PyQt6.QtCore import Qt
        from core.glossary_manager import GlossaryOccurrence

        occ = GlossaryOccurrence(AMBIGUOUS, 2, 743, 3, 0, 0, "Some occurrence text")
        dialog = _dialog(qtbot, [AMBIGUOUS])
        dialog._occurrences = {AMBIGUOUS.original: [occ]}
        dialog._update_occurrences(AMBIGUOUS)

        assert dialog._occurrence_list.count() == 1
        item = dialog._occurrence_list.item(0)

        # 1. An occurrence with string_idx=743 is displayed as string 744 (1-based)
        display_html = item.data(Qt.ItemDataRole.DisplayRole)
        assert "string <b>744</b>" in display_html
        assert "string <b>743</b>" not in display_html
        assert "line <b>4</b>" in display_html
        assert "block <b>2</b>" in display_html

        # 2. The QListWidgetItem UserRole still contains an occurrence whose string_idx is 743 (0-based)
        stored_occ = item.data(Qt.ItemDataRole.UserRole)
        assert isinstance(stored_occ, GlossaryOccurrence)
        assert stored_occ.block_idx == 2
        assert stored_occ.string_idx == 743
        assert stored_occ.line_idx == 3

        # Double click activates jump_callback with the stored 0-based occurrence
        dialog._activate_selected_occurrence(item)
        dialog._jump_callback.assert_called_once_with(stored_occ)


class TestGlossaryLayoutAndControls:
    """Tests for reorganized layout, wiki link, collapsible panes, and occurrence filters."""

    def test_original_edit_shows_term_and_is_readonly(self, qtbot):
        dialog = _dialog(qtbot, [SINGLE])
        dialog._show_entry_for_row(0)
        assert dialog._original_edit.text() == SINGLE.original
        assert dialog._original_edit.isReadOnly() is True

    def test_wiki_button_hidden_when_no_callback_or_url(self, qtbot):
        dialog = _dialog(qtbot, [SINGLE])
        dialog._show_entry_for_row(0)
        assert dialog._wiki_link_button.isVisibleTo(dialog) is False

    def test_wiki_button_shown_when_url_provided(self, qtbot, monkeypatch):
        mock_cb = MagicMock(return_value="https://zeldawiki.wiki/wiki/Ordon_Village")
        dialog = _dialog(qtbot, [SINGLE], external_reference_callback=mock_cb)
        dialog._show_entry_for_row(0)
        assert dialog._wiki_link_button.isVisibleTo(dialog) is True
        mock_cb.assert_called_with(SINGLE.original)

        # Clicking wiki button opens the URL
        opened_urls = []
        monkeypatch.setattr(
            "PyQt6.QtGui.QDesktopServices.openUrl",
            lambda url: opened_urls.append(url.toString()),
        )
        dialog._wiki_link_button.click()
        assert opened_urls == ["https://zeldawiki.wiki/wiki/Ordon_Village"]

    def test_collapsible_panes_toggle_visibility(self, qtbot):
        dialog = _dialog(qtbot, [SINGLE])
        assert not dialog._notes_edit.isHidden()
        assert not dialog._ai_notes_edit.isHidden()
        assert not dialog._occurrence_list.isHidden()

        # Collapse Description
        dialog._notes_collapse_button.click()
        assert dialog._notes_edit.isHidden()
        assert dialog._notes_collapse_button.text() == "▶"

        dialog._notes_collapse_button.click()
        assert not dialog._notes_edit.isHidden()
        assert dialog._notes_collapse_button.text() == "▼"

        # Collapse AI Notes
        dialog._ai_notes_collapse_button.click()
        assert dialog._ai_notes_edit.isHidden()
        assert dialog._ai_notes_collapse_button.text() == "▶"

        # Collapse Occurrences
        dialog._occ_collapse_button.click()
        assert dialog._occurrence_list.isHidden()
        assert dialog._occ_collapse_button.text() == "▶"

    def test_occurrence_filter_by_mentions_and_spoken_checkboxes(self, qtbot):
        from PyQt6.QtCore import Qt
        from core.glossary_manager import GlossaryOccurrence
        occ_mention = GlossaryOccurrence(SINGLE, 0, 10, 1, 0, 0, "Mention text", kind="mention")
        occ_spoken = GlossaryOccurrence(SINGLE, 0, 20, 2, 0, 0, "Spoken text", kind="spoken")

        dialog = _dialog(qtbot, [SINGLE])
        dialog._occurrences = {SINGLE.original: [occ_mention, occ_spoken]}
        dialog._update_occurrences(SINGLE)

        assert dialog._occurrence_list.count() == 2
        assert "Mentions (1)" in dialog._show_mentions_checkbox.text()
        assert "Spoken (1)" in dialog._show_spoken_checkbox.text()

        # Uncheck mentions -> only spoken shown
        dialog._show_mentions_checkbox.setChecked(False)
        assert dialog._occurrence_list.count() == 1
        item = dialog._occurrence_list.item(0)
        assert "spoken" in item.data(Qt.ItemDataRole.DisplayRole)

        # Uncheck spoken too -> 0 shown
        dialog._show_spoken_checkbox.setChecked(False)
        assert dialog._occurrence_list.count() == 0

        # Re-check mentions only -> 1 mention shown
        dialog._show_mentions_checkbox.setChecked(True)
        assert dialog._occurrence_list.count() == 1
        item = dialog._occurrence_list.item(0)
        assert "mention" in item.data(Qt.ItemDataRole.DisplayRole)

    def test_term_and_translation_level_alignment_and_width_constraints(self, qtbot):
        update_cb = MagicMock()
        discuss_cb = MagicMock()
        dialog = _dialog(qtbot, [SINGLE], update_callback=update_cb, discuss_variant_callback=discuss_cb)
        dialog.show()
        qtbot.waitExposed(dialog)

        # 1. Height and vertical level alignment
        assert dialog._original_edit.height() == dialog._translation_edit.height() == 26
        assert dialog._wiki_link_button.height() == 26
        assert dialog._confirm_button.height() == 26

        # Both edits are on the same vertical Y level within the dialog
        orig_global_y = dialog._original_edit.mapTo(dialog, dialog._original_edit.rect().topLeft()).y()
        trans_global_y = dialog._translation_edit.mapTo(dialog, dialog._translation_edit.rect().topLeft()).y()
        assert orig_global_y == trans_global_y

        # Action buttons (Wiki, Save, Confirm, Discuss) are positioned on a row below translation field
        save_global_y = dialog._save_term_button.mapTo(dialog, dialog._save_term_button.rect().topLeft()).y()
        confirm_global_y = dialog._confirm_button.mapTo(dialog, dialog._confirm_button.rect().topLeft()).y()
        discuss_global_y = dialog._discuss_variant_button.mapTo(dialog, dialog._discuss_variant_button.rect().topLeft()).y()
        dialog._wiki_link_button.setVisible(True)
        qtbot.wait(20)
        wiki_global_y = dialog._wiki_link_button.mapTo(dialog, dialog._wiki_link_button.rect().topLeft()).y()
        assert save_global_y > trans_global_y
        assert confirm_global_y > trans_global_y
        assert discuss_global_y > trans_global_y
        assert wiki_global_y == save_global_y == confirm_global_y == discuss_global_y

        # Compact O: and T: labels with tooltips
        assert hasattr(dialog, '_orig_field_label')
        assert hasattr(dialog, '_trans_field_label')
        assert dialog._orig_field_label.text() == "O:"
        assert dialog._orig_field_label.toolTip() == "Original"
        assert dialog._trans_field_label.text() == "T:"
        assert dialog._trans_field_label.toolTip() == "Translation"

        # 2. Horizontal splitter between Original and Translation allowing flexible resizing
        assert hasattr(dialog, '_term_trans_splitter')
        assert dialog._term_trans_splitter.orientation() == Qt.Orientation.Horizontal
        assert dialog._term_trans_splitter.count() == 2
        assert dialog._original_edit.minimumWidth() == 80
        assert dialog._translation_edit.minimumWidth() == 80

        # Verify that moving the splitter resizes the original and translation edits
        orig_w_before = dialog._original_edit.width()
        dialog._term_trans_splitter.setSizes([450, 200])
        qtbot.wait(50)
        assert dialog._original_edit.width() > orig_w_before

        # 3. Lower details splitter default sizes are balanced
        lower_sizes = dialog._lower_detail_splitter.sizes()
        assert len(lower_sizes) == 3
        assert lower_sizes[0] == lower_sizes[1] == lower_sizes[2]

    def test_save_button_keeps_dialog_open_and_saves_in_place(self, qtbot):
        update_cb = MagicMock(return_value=([SINGLE], {}))
        dialog = _dialog(qtbot, [SINGLE], update_callback=update_cb)
        dialog.show()
        qtbot.waitExposed(dialog)

        dialog._translation_edit.setText("Updated Translation")
        assert dialog._save_term_button.isEnabled() is True

        # Click save button
        dialog._save_term_button.click()

        # Dialog remains visible and current entry is retained
        assert dialog.isVisible() is True
        assert update_cb.called
        assert dialog._current_entry.original == SINGLE.original
        assert dialog._save_term_button.isEnabled() is False

    def test_needs_review_checkbox_located_under_terms_table(self, qtbot):
        dialog = _dialog(qtbot, [SINGLE])
        dialog.show()
        qtbot.waitExposed(dialog)

        # Checkbox is located below the tab widget in the left panel
        tab_bottom_y = dialog._tab_widget.mapTo(dialog, dialog._tab_widget.rect().bottomLeft()).y()
        chk_top_y = dialog._unconfirmed_only_checkbox.mapTo(dialog, dialog._unconfirmed_only_checkbox.rect().topLeft()).y()
        assert chk_top_y >= tab_bottom_y

    def test_splitters_persistence(self, qtbot, tmp_path):
        settings_file = tmp_path / "settings.json"
        dialog = _dialog(qtbot, [SINGLE])
        dialog.resize(950, 700)
        dialog.show()
        qtbot.waitExposed(dialog)
        dialog._settings_path = settings_file

        cur_tt = dialog._term_trans_splitter.sizes()
        dialog._term_trans_splitter.setSizes([cur_tt[0] + 30, max(50, cur_tt[1] - 30)])
        expected_tt = dialog._term_trans_splitter.sizes()

        dialog._detail_splitter.setSizes([110, 400])
        expected_detail = dialog._detail_splitter.sizes()

        dialog._lower_detail_splitter.setSizes([130, 140, 150])
        expected_lower = dialog._lower_detail_splitter.sizes()

        dialog._save_dialog_state()

        dialog2 = _dialog(qtbot, [SINGLE])
        dialog2.resize(950, 700)
        dialog2._settings_path = settings_file
        dialog2._load_dialog_state()
        dialog2.show()
        qtbot.waitExposed(dialog2)
        assert dialog2._term_trans_splitter.sizes() == expected_tt
        assert dialog2._detail_splitter.sizes() == expected_detail
        assert dialog2._lower_detail_splitter.sizes() == expected_lower


class TestForceRetranslateButton:
    def test_button_hidden_when_no_callback(self, qtbot):
        dialog = _dialog(qtbot, [SINGLE])
        assert dialog._retranslate_button.isHidden()

    def test_button_visible_when_callback_provided(self, qtbot):
        callback = MagicMock()
        dialog = _dialog(qtbot, [SINGLE], force_retranslate_callback=callback)
        assert not dialog._retranslate_button.isHidden()

    def test_clicking_button_prompts_and_calls_callback_on_yes(self, qtbot, monkeypatch):
        callback = MagicMock()
        dialog = _dialog(qtbot, [SINGLE], force_retranslate_callback=callback)
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )
        dialog._retranslate_button.click()
        assert callback.call_count == 1

    def test_clicking_button_does_not_call_callback_on_no(self, qtbot, monkeypatch):
        callback = MagicMock()
        dialog = _dialog(qtbot, [SINGLE], force_retranslate_callback=callback)
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.No,
        )
        dialog._retranslate_button.click()
        assert callback.call_count == 0


class TestGlossaryReferenceOccurrences:
    def test_occurrence_renders_russian_block_when_reference_data_provided(self, qtbot):
        from core.glossary_manager import GlossaryOccurrence
        entry = _entry("Slingshot", "Рогатка")
        occ = GlossaryOccurrence(entry, 0, 5, 0, 0, 9, "Slingshot is ready.")
        ref_data = {(0, 5): "Рогатка готова к стрельбе."}

        dialog = GlossaryDialog(
            entries=[entry],
            occurrence_map={entry.original: [occ]},
            parent=None,
            jump_callback=MagicMock(),
            reference_data=ref_data,
            reference_language="Russian (RU)",
        )
        qtbot.addWidget(dialog)
        dialog.focus_term("Slingshot")

        assert dialog._occurrence_list.count() == 1
        item = dialog._occurrence_list.item(0)
        display_html = item.data(Qt.ItemDataRole.DisplayRole)

        assert "block <b>0</b>" in display_html
        assert "EN:" in display_html
        assert "RU:" in display_html
        assert "Рогатка" in display_html
        assert "text-decoration: underline;" in display_html

    def test_occurrence_displays_full_russian_phrase_without_truncation_when_no_direct_match(self, qtbot):
        from core.glossary_manager import GlossaryOccurrence
        entry = _entry("Slingshot", "Рогатка")
        occ = GlossaryOccurrence(entry, 1, 2, 0, 0, 9, "Slingshot is here.")
        long_ru = "Возьми это оружие в сундуке возле реки и отправляйся в путь без сомнений."
        ref_data = {(1, 2): long_ru}

        dialog = GlossaryDialog(
            entries=[entry],
            occurrence_map={entry.original: [occ]},
            parent=None,
            jump_callback=MagicMock(),
            reference_data=ref_data,
            reference_language="Russian (RU)",
        )
        qtbot.addWidget(dialog)
        dialog.focus_term("Slingshot")

        assert dialog._occurrence_list.count() == 1
        item = dialog._occurrence_list.item(0)
        display_html = item.data(Qt.ItemDataRole.DisplayRole)

        assert "RU:" in display_html
        assert long_ru in display_html

    def test_occurrence_omits_russian_block_when_no_reference_data(self, qtbot):
        from core.glossary_manager import GlossaryOccurrence
        entry = _entry("Slingshot", "Рогатка")
        occ = GlossaryOccurrence(entry, 0, 5, 0, 0, 9, "Slingshot is ready.")

        dialog = GlossaryDialog(
            entries=[entry],
            occurrence_map={entry.original: [occ]},
            parent=None,
            jump_callback=MagicMock(),
        )
        qtbot.addWidget(dialog)
        dialog.focus_term("Slingshot")

        assert dialog._occurrence_list.count() == 1
        item = dialog._occurrence_list.item(0)
        display_html = item.data(Qt.ItemDataRole.DisplayRole)

        assert "EN:" in display_html
        assert "RU:" not in display_html

    def test_reload_data_updates_reference_data(self, qtbot):
        from core.glossary_manager import GlossaryOccurrence
        entry = _entry("Slingshot", "Рогатка")
        occ = GlossaryOccurrence(entry, 0, 5, 0, 0, 9, "Slingshot is ready.")

        dialog = GlossaryDialog(
            entries=[entry],
            occurrence_map={entry.original: [occ]},
            parent=None,
            jump_callback=MagicMock(),
        )
        qtbot.addWidget(dialog)
        dialog.focus_term("Slingshot")

        item = dialog._occurrence_list.item(0)
        assert "RU:" not in item.data(Qt.ItemDataRole.DisplayRole)

        ref_data = {(0, 5): "Держи рогатку."}
        dialog.reload_data(
            [entry],
            {entry.original: [occ]},
            reference_data=ref_data,
            reference_language="Russian (RU)",
        )

        item = dialog._occurrence_list.item(0)
        assert "RU:" in item.data(Qt.ItemDataRole.DisplayRole)
        assert "Держи" in item.data(Qt.ItemDataRole.DisplayRole)


class TestGlossaryReferenceVariantsAndNotes:
    """Tests for isolating Russian reference variants and context in AI notes."""

    def test_reference_variant_styling_and_non_applicable(self, qtbot):
        from core.glossary.models import TranslationVariant
        from core.glossary_manager import GlossaryEntry

        target_var = TranslationVariant(translation="Зелене драгле", rationale="Класифікація")
        ref_var = TranslationVariant(translation="Желе зелёного чу", rationale="RU патч v2.0")
        entry = GlossaryEntry(
            original="Green Chu",
            translation="Зелений чу",
            notes="",
            profiled=False,
            translation_variants=(target_var, ref_var),
        )

        update_cb = MagicMock()
        dialog = GlossaryDialog(
            entries=[entry],
            occurrence_map={},
            parent=None,
            jump_callback=MagicMock(),
            update_callback=update_cb,
        )
        qtbot.addWidget(dialog)
        dialog.focus_term("Green Chu")

        assert dialog._variants_list.count() == 2
        item_target = dialog._variants_list.item(0)
        item_ref = dialog._variants_list.item(1)

        assert dialog._is_reference_item(item_target) is False
        assert dialog._is_reference_item(item_ref) is True
        assert item_ref.font().italic() is True
        assert "Reference translation variant" in item_ref.toolTip()

        # Selecting reference variant disables apply button
        dialog._variants_list.setCurrentItem(item_ref)
        dialog._update_variant_buttons_state()
        assert dialog._apply_variant_button.isEnabled() is False

        # Double clicking reference variant does NOT apply it
        dialog._on_variant_double_clicked(item_ref)
        assert dialog._translation_edit.text() == "Зелений чу"

        # Calling _on_apply_selected_variant does NOT apply it
        dialog._on_apply_selected_variant()
        assert dialog._translation_edit.text() == "Зелений чу"

        # Selecting target variant enables apply button
        dialog._variants_list.setCurrentItem(item_target)
        dialog._update_variant_buttons_state()
        assert dialog._apply_variant_button.isEnabled() is True

        # Double clicking target variant applies it
        dialog._on_variant_double_clicked(item_target)
        assert dialog._translation_edit.text() == "Зелене драгле"

    def test_ai_notes_separates_reference_variants(self, qtbot):
        from core.glossary.models import TranslationVariant
        from core.glossary_manager import GlossaryEntry

        target_var1 = TranslationVariant(translation="Зелене драгле", rationale="Варіант 1")
        target_var2 = TranslationVariant(translation="Зелений слиз", rationale="Варіант 2")
        ref_var = TranslationVariant(translation="Желе зелёного чу", rationale="RU патч v2.0")
        entry = GlossaryEntry(
            original="Green Chu",
            translation="Зелений чу",
            notes="",
            profiled=False,
            translation_variants=(target_var1, target_var2, ref_var),
        )

        dialog = GlossaryDialog(
            entries=[entry],
            occurrence_map={},
            parent=None,
            jump_callback=MagicMock(),
        )
        qtbot.addWidget(dialog)
        dialog.focus_term("Green Chu")

        ai_notes = dialog._ai_notes_edit.toPlainText()
        assert "Russian reference translation (for context):" in ai_notes
        assert "Желе зелёного чу — RU патч v2.0" in ai_notes
        assert "Defensible translation choices:" in ai_notes
        assert "Зелене драгле — Варіант 1" in ai_notes
        assert "Зелений слиз — Варіант 2" in ai_notes
        # Russian variant is NOT mixed in defensible translation choices
        choices_part = ai_notes.split("Russian reference translation")[0]
        assert "Желе зелёного чу" not in choices_part

    def test_ai_notes_includes_reference_context_from_mention_when_no_variant(self, qtbot):
        from core.glossary_manager import GlossaryEntry, GlossaryOccurrence

        entry = GlossaryEntry(
            original="Green Chu",
            translation="Зелений чу",
            notes="",
            profiled=False,
            translation_variants=(),
        )
        occ = GlossaryOccurrence(entry, 0, 12, 0, 0, 9, "Defeat the Green Chu.")
        ref_data = {(0, 12): "Победите зелёного чу."}

        dialog = GlossaryDialog(
            entries=[entry],
            occurrence_map={entry.original: [occ]},
            parent=None,
            jump_callback=MagicMock(),
            reference_data=ref_data,
        )
        qtbot.addWidget(dialog)
        dialog.focus_term("Green Chu")

        ai_notes = dialog._ai_notes_edit.toPlainText()
        assert "Russian reference context (from mention string):" in ai_notes
        assert "Победите зелёного чу." in ai_notes


class TestGlossaryCompanionSyncButton:
    def test_companion_sync_button_exists_and_visible(self, qtbot):
        dialog = _dialog(qtbot, [CONFIRMED])
        assert hasattr(dialog, "_companion_sync_button")
        assert not dialog._companion_sync_button.isHidden()
        assert "Companion Sync" in dialog._companion_sync_button.text()


class TestCollapsibleDetailPanes:
    def test_children_collapsible_disabled_on_lower_splitter(self, qtbot):
        dialog = _dialog(qtbot, [SINGLE])
        assert dialog._lower_detail_splitter.childrenCollapsible() is False

    def test_collapse_and_expand_rebalance_without_squishing(self, qtbot):
        dialog = _dialog(qtbot, [SINGLE])
        dialog.resize(950, 700)
        dialog.show()
        qtbot.waitExposed(dialog)

        # Initially all three are expanded and have readable height
        sizes = dialog._lower_detail_splitter.sizes()
        assert len(sizes) == 3
        assert all(s >= 80 for s in sizes)

        # Collapse Description
        dialog._notes_collapse_button.click()
        assert dialog._notes_edit.isHidden()
        assert dialog._notes_collapse_button.text() == "▶"
        sizes_after_collapse = dialog._lower_detail_splitter.sizes()
        assert sizes_after_collapse[0] <= 34
        # The other two expanded panes should have received space
        assert sizes_after_collapse[1] >= sizes[1]
        assert sizes_after_collapse[2] >= sizes[2]

        # Collapse Occurrences as well
        dialog._occ_collapse_button.click()
        assert dialog._occurrence_list.isHidden()
        assert dialog._occ_collapse_button.text() == "▶"
        sizes_two_col = dialog._lower_detail_splitter.sizes()
        assert sizes_two_col[0] <= 34
        assert sizes_two_col[2] <= 34
        # AI notes (only expanded pane) should occupy the rest
        assert sizes_two_col[1] > 200

        # Now expand Occurrences back: it must NOT be stuck at 34px!
        dialog._occ_collapse_button.click()
        assert not dialog._occurrence_list.isHidden()
        assert dialog._occ_collapse_button.text() == "▼"
        sizes_reexpanded = dialog._lower_detail_splitter.sizes()
        assert sizes_reexpanded[2] >= 90  # Readable height, not squished!

        # Now expand Description back
        dialog._notes_collapse_button.click()
        assert not dialog._notes_edit.isHidden()
        assert dialog._notes_collapse_button.text() == "▼"
        sizes_all_expanded = dialog._lower_detail_splitter.sizes()
        assert all(s >= 80 for s in sizes_all_expanded)

    def test_collapsed_state_persistence_and_old_state_migration(self, qtbot, tmp_path):
        import json
        settings_file = tmp_path / "settings.json"
        dialog = _dialog(qtbot, [SINGLE])
        dialog.resize(950, 700)
        dialog.show()
        qtbot.waitExposed(dialog)
        dialog._settings_path = settings_file

        # Collapse AI notes and Occurrences
        dialog._ai_notes_collapse_button.click()
        dialog._occ_collapse_button.click()
        assert dialog._notes_collapse_button.text() == "▼"
        assert dialog._ai_notes_collapse_button.text() == "▶"
        assert dialog._occ_collapse_button.text() == "▶"
        dialog._save_dialog_state()

        # Reopen with saved state
        dialog2 = _dialog(qtbot, [SINGLE])
        dialog2.resize(950, 700)
        dialog2._settings_path = settings_file
        dialog2._load_dialog_state()
        dialog2.show()
        qtbot.waitExposed(dialog2)

        assert dialog2._notes_collapsed is False
        assert dialog2._ai_notes_collapsed is True
        assert dialog2._occurrences_collapsed is True
        assert not dialog2._notes_edit.isHidden()
        assert dialog2._ai_notes_edit.isHidden()
        assert dialog2._occurrence_list.isHidden()
        assert dialog2._notes_collapse_button.text() == "▼"
        assert dialog2._ai_notes_collapse_button.text() == "▶"
        assert dialog2._occ_collapse_button.text() == "▶"
        s2 = dialog2._lower_detail_splitter.sizes()
        assert s2[0] >= 100
        assert s2[1] <= 34
        assert s2[2] <= 34

        # Test migration from old format where only sizes [242, 34, 34] were saved without flags
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump({
                "glossary_dialog_state": {
                    "lower_detail_splitter_sizes": [242, 34, 34]
                }
            }, f)

        dialog3 = _dialog(qtbot, [SINGLE])
        dialog3.resize(950, 700)
        dialog3._settings_path = settings_file
        dialog3._load_dialog_state()
        dialog3.show()
        qtbot.waitExposed(dialog3)

        assert dialog3._notes_collapsed is False
        assert dialog3._ai_notes_collapsed is True
        assert dialog3._occurrences_collapsed is True
        assert not dialog3._notes_edit.isHidden()
        assert dialog3._ai_notes_edit.isHidden()
        assert dialog3._occurrence_list.isHidden()
