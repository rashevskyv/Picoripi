"""Glossary notes editor dirty/save/delete/context menu/review state."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QMenu, QMessageBox
from core.glossary_manager import (
    STATUS_CONFIRMED,
    STATUS_TRANSLATED,
    TERM_PLACEHOLDER,
    GlossaryEntry,
    render_notes,
)
from core.i18n import tr


class EditorMixin:
    """Glossary notes editor dirty/save/delete/context menu/review state."""

    def _set_notes_variation_busy(self, busy: bool) -> None:
        """Internal helper to set the notes variation busy."""
        if not hasattr(self, '_notes_variation_button'):
            return
        self._notes_variation_busy = busy
        has_callback = self._ai_variation_callback is not None
        if busy:
            self._notes_variation_button.setText(f"{self._notes_variation_default_text} (working...)")
        else:
            self._notes_variation_button.setText(self._notes_variation_default_text)
        should_enable = has_callback and not busy and self._current_entry is not None
        self._notes_variation_button.setEnabled(should_enable)

    def apply_notes_variation(self, new_notes: str) -> None:
        """Apply notes variation."""
        if not self._current_entry:
            return
        self._suppress_editor_signals = True
        self._notes_edit.setPlainText(new_notes or '')
        self._suppress_editor_signals = False
        self._on_editor_content_changed()

    def _on_notes_variation_clicked(self) -> None:
        """Internal helper to handle the notes variation clicked event."""
        if not self._ai_variation_callback or not self._current_entry:
            return
        self._ai_variation_callback(self._current_entry)

    def _on_editor_content_changed(self) -> None:
        """Internal helper to handle the editor content changed event."""
        if self._suppress_editor_signals:
            return
        if self._current_entry is not None:
            # AI notes are read-only evidence; keep {{TERM}} in sync with Translation.
            self._ai_notes_edit.setPlainText(self._ai_notes_for_entry(self._current_entry))
        if not self._update_callback or not self._current_entry:
            return
        current_translation = self._translation_edit.text().strip()
        current_notes = self._notes_for_save()
        current_profiled = self._profiled_checkbox.isChecked()
        current_section = self._canonical_category_name(self._category_combo.currentText())
        has_changes = (
            current_translation != self._current_entry.translation
            or current_notes != self._current_entry.notes
            or current_profiled != self._current_entry.profiled
            or current_section != (self._current_entry.section or "")
        )
        self._mark_editor_dirty(has_changes)

    def _mark_editor_dirty(self, dirty: bool) -> None:
        """Internal helper to mark editor dirty."""
        self._editor_dirty = bool(dirty) if self._update_callback else False
        self._update_editor_enabled_state()

    def _update_editor_enabled_state(self) -> None:
        """Internal helper to update the editor enabled state."""
        can_edit = self._update_callback is not None and self._current_entry is not None
        self._translation_edit.setReadOnly(not can_edit)
        self._notes_edit.setReadOnly(not can_edit)
        self._profiled_checkbox.setEnabled(can_edit)
        self._category_combo.setEnabled(can_edit)
        if hasattr(self, '_notes_variation_button'):
            has_callback = self._ai_variation_callback is not None
            self._notes_variation_button.setVisible(has_callback)
            should_enable = has_callback and self._current_entry is not None and not getattr(self, '_notes_variation_busy', False)
            self._notes_variation_button.setEnabled(should_enable)
        if hasattr(self, '_save_button'):
            if self._update_callback is None:
                self._save_button.setVisible(False)
                self._save_button.setEnabled(False)
            else:
                self._save_button.setVisible(True)
                self._save_button.setEnabled(can_edit)
        self._update_variant_buttons_state()

    def _save_editor_changes(self) -> None:
        """Internal helper to save editor changes."""
        if self._is_populating or not self._update_callback or not self._current_entry:
            return
        new_translation = self._translation_edit.text().strip()
        new_notes = self._notes_for_save()
        new_profiled = self._profiled_checkbox.isChecked()
        new_section = self._canonical_category_name(self._category_combo.currentText())
        entry = self._current_entry
        section_change = (
            new_section if new_section != (entry.section or "") else None
        )
        if not self._attempt_entry_update(
            entry, new_translation, new_notes, new_profiled, section=section_change
        ):
            self._populate_entry_details(entry)
            return
        self._mark_editor_dirty(False)

    def _attempt_entry_update(
        self,
        entry: GlossaryEntry,
        new_translation: str,
        new_notes: str,
        profiled: Optional[bool] = None,
        status: Optional[str] = None,
        section: Optional[str] = None,
        select_after: Optional[str] = None,
    ) -> bool:
        """Internal helper to attempt entry update.

        ``status`` moves the entry's lifecycle state -- STATUS_CONFIRMED to
        settle it and clear the review highlight, or an unconfirmed status to
        put it back under review. Passed as a keyword so older callbacks that
        do not accept it stay compatible when it is not needed.
        """
        if not self._update_callback:
            return False
        if status or section is not None:
            kwargs = {"section": section} if section is not None else {}
            if status:
                kwargs["status"] = status
            result = self._update_callback(
                entry.original, new_translation, new_notes, profiled, **kwargs
            )
        else:
            result = self._update_callback(entry.original, new_translation, new_notes, profiled)
        if not result:
            return False
        new_entries, new_occurrence_map = result
        self._all_entries = list(new_entries)
        self._occurrences = new_occurrence_map
        self._pending_select_term = select_after if select_after is not None else entry.original
        self._apply_filter(self._search_field.text())
        return True

    def _populate_category_choices(self, entry: GlossaryEntry) -> None:
        """List existing categories and retain the entry's current choice."""
        categories = {}
        for candidate in self._all_entries:
            value = (candidate.section or "").strip()
            if value:
                categories.setdefault(value.casefold(), value)
        self._category_combo.blockSignals(True)
        self._category_combo.clear()
        self._category_combo.addItem(tr(''))
        self._category_combo.addItems(sorted(categories.values(), key=str.casefold))
        self._category_combo.setEditText((entry.section or "").strip())
        self._category_combo.blockSignals(False)

    def _canonical_category_name(self, value: str) -> str:
        """Reuse an existing category spelling; a new name becomes a new tab."""
        text = str(value or "").strip()
        if not text:
            return ""
        for entry in self._all_entries:
            section = (entry.section or "").strip()
            if section and section.casefold() == text.casefold():
                return section
        return text

    def _attempt_entry_delete(self, entry: GlossaryEntry) -> None:
        """Internal helper to attempt entry delete."""
        if not self._delete_callback:
            return
        response = QMessageBox.question(
            self,
            tr('Delete Glossary Entry'),
            f"Remove term \"{entry.original}\" from the glossary?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        result = self._delete_callback(entry.original)
        if not result:
            return
        new_entries, new_occurrence_map = result
        self._all_entries = list(new_entries)
        self._occurrences = new_occurrence_map
        self._current_entry = None
        self._mark_editor_dirty(False)
        self._update_editor_enabled_state()
        self._pending_select_term = None
        self._apply_filter(self._search_field.text())

    def _on_entry_context_menu(self, pos) -> None:
        """Internal helper to handle the entry context menu event."""
        row = self._active_table().rowAt(pos.y())
        if row < 0:
            return
        entry = self._entry_for_row(row)
        if not entry:
            return
        menu = QMenu(self)
        settled = not self._needs_review(entry)
        review_action = menu.addAction(
            "Mark for review" if settled else "Mark as reviewed"
        )
        review_action.setEnabled(self._update_callback is not None)
        menu.addSeparator()
        delete_action = menu.addAction(tr('Delete Entry'))
        delete_action.setEnabled(self._delete_callback is not None)
        selected_action = menu.exec(self._active_table().viewport().mapToGlobal(pos))
        if selected_action == delete_action:
            self._active_table().selectRow(row)
            self._attempt_entry_delete(entry)
        elif selected_action == review_action:
            self._active_table().selectRow(row)
            self._set_entry_review_state(entry, needs_review=settled)

    def _set_entry_review_state(self, entry: GlossaryEntry, *, needs_review: bool) -> None:
        """Flag an entry for review again, or settle it, from the context menu."""
        status = STATUS_TRANSLATED if needs_review else STATUS_CONFIRMED
        self._attempt_entry_update(
            entry, entry.translation, entry.notes, entry.profiled, status=status
        )

    def _ai_notes_for_entry(self, entry: GlossaryEntry) -> str:
        """Render existing AI evidence separately from the clean description."""
        sections = []
        fragments = []
        for fragment in getattr(entry, "fragments", ()) or ():
            text = str(getattr(fragment, "text", "") or "").strip()
            if text and text not in fragments:
                fragments.append(text)
        if fragments:
            sections.append("Observations collected during the text sweep:\n- " + "\n- ".join(fragments))

        variants = getattr(entry, "translation_variants", ()) or ()
        if len(variants) > 1:
            choices = [
                f"{variant.translation} — {variant.rationale}".rstrip(" —")
                for variant in variants
            ]
            sections.append("Defensible translation choices:\n- " + "\n- ".join(choices))

        suggested_name = str(getattr(entry, "suggested_name", "") or "").strip()
        name_evidence = str(getattr(entry, "suggested_name_evidence", "") or "").strip()
        if suggested_name or name_evidence:
            text = f"Possible speaker identity: {suggested_name or '(unknown)'}"
            if name_evidence:
                text += f"\nEvidence: {name_evidence}"
            sections.append(text)
        duplicates = [
            right if left == entry.original else left
            for left, right in self._duplicate_pairs
            if entry.original in (left, right)
        ]
        if duplicates:
            sections.append(
                "Possible duplicate terms (review manually):\n- " + "\n- ".join(duplicates)
            )
        raw = "\n\n".join(sections)
        translation = ""
        if hasattr(self, "_translation_edit"):
            translation = self._translation_edit.text()
        return render_notes(
            raw,
            translation=translation or (entry.translation or ""),
            original=entry.original,
        )

    def _rendered_notes(self) -> str:
        """The stored notes with the term placeholder filled in."""
        entry = self._current_entry
        return render_notes(
            self._notes_template,
            translation=self._translation_edit.text(),
            original=entry.original if entry else "",
        )

    def _refresh_rendered_notes(self) -> None:
        """Re-render description and AI notes after the translation changed."""
        was_suppressed = self._suppress_editor_signals
        self._suppress_editor_signals = True
        if TERM_PLACEHOLDER in (self._notes_template or ""):
            self._notes_edit.setPlainText(self._rendered_notes())
        if self._current_entry is not None:
            self._ai_notes_edit.setPlainText(self._ai_notes_for_entry(self._current_entry))
        self._suppress_editor_signals = was_suppressed

    def _notes_for_save(self) -> str:
        """What to store: the template if untouched, else what the user typed.

        Keeping the placeholder means a later change of variant still updates the
        note; once the user edits the text by hand, their wording wins.
        """
        typed = self._notes_edit.toPlainText().strip()
        template = (self._notes_template or "").strip()
        if template and typed == self._rendered_notes().strip():
            return template
        return typed
