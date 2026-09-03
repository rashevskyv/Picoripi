"""Glossary entry details, occurrences, speaker identity, and variants."""
from __future__ import annotations

from html import escape
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidgetItem
from core.glossary_manager import GlossaryEntry
from core.speaker_alias_merge import is_confirmed_speaker_alias
from core.i18n import tr


class DetailsMixin:
    """Glossary entry details, occurrences, speaker identity, and variants."""

    def _activate_selected_occurrence(self, item: Optional[QListWidgetItem] = None) -> None:
        """Internal helper to activate selected occurrence."""
        if not item:
            item = self._occurrence_list.currentItem()
        if not item:
            if self._occurrence_list.count() == 1:
                self._occurrence_list.setCurrentRow(0)
                item = self._occurrence_list.currentItem()
            else:
                return
        occurrence = item.data(Qt.ItemDataRole.UserRole)
        if occurrence:
            self._jump_callback(occurrence)

    def _update_variant_buttons_state(self) -> None:
        """Update enabled state for variant action buttons."""
        has_entry = self._current_entry is not None
        has_selected_item = bool(self._variants_list.currentItem()) if hasattr(self, "_variants_list") else False
        can_apply = has_entry and has_selected_item and (self._update_callback is not None)
        if hasattr(self, "_apply_variant_button"):
            self._apply_variant_button.setEnabled(can_apply)
        if hasattr(self, "_discuss_variant_button"):
            has_discuss = self._discuss_variant_callback is not None
            self._discuss_variant_button.setEnabled(has_entry and has_discuss)

    def _update_occurrences(self, entry: GlossaryEntry) -> None:
        """Internal helper to update the occurrences."""
        occ_list = list(self._occurrences.get(entry.original, []))
        spoken_rows = [o for o in occ_list if getattr(o, "kind", "mention") == "spoken"]
        mention_rows = [o for o in occ_list if getattr(o, "kind", "mention") != "spoken"]
        occ_list = spoken_rows + mention_rows
        self._occurrence_list.clear()
        for index, occ in enumerate(occ_list, start=1):
            preview = occ.line_text.strip()
            if len(preview) > 120:
                preview = f"{preview[:117]}…"
            preview_html = escape(preview).replace('\n', '<br>')
            kind = getattr(occ, "kind", "mention") or "mention"
            kind_label = tr("spoken") if kind == "spoken" else tr("mention")
            header_html = tr(
                '<b>#{index}</b> | {kind} | block <b>{block}</b> | '
                'string <b>{string}</b> | line <b>{line}</b>',
                index=index,
                kind=kind_label,
                block=occ.block_idx,
                string=occ.string_idx + 1,
                line=occ.line_idx + 1,
            )
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, f"{header_html}<br>{preview_html}")
            item.setData(Qt.ItemDataRole.UserRole, occ)
            self._occurrence_list.addItem(item)
        mentions = sum(1 for occ in occ_list if getattr(occ, "kind", "mention") != "spoken")
        spoken = sum(1 for occ in occ_list if getattr(occ, "kind", "mention") == "spoken")
        self._occurrence_label.setText(
            tr('Mentions: {mentions}   Spoken: {spoken}', mentions=mentions, spoken=spoken)
        )

    def _populate_entry_details(self, entry: GlossaryEntry) -> None:
        """Internal helper to populate entry details."""
        self._current_entry = entry
        self._suppress_editor_signals = True
        self._original_label.setText(tr('Term: {original}', original=entry.original))
        self._populate_category_choices(entry)
        self._translation_edit.setText(entry.translation or '')
        self._notes_template = entry.notes or ''
        self._notes_edit.setPlainText(self._rendered_notes())
        self._ai_notes_edit.setPlainText(self._ai_notes_for_entry(entry))
        self._profiled_checkbox.setChecked(entry.profiled)
        self._populate_variants(entry)

        is_provisional_char = self._is_provisional_character(entry)
        speaker_code = entry.original.strip() if is_provisional_char else self._confirmed_speaker_code(entry)
        self._current_speaker_code = speaker_code
        self._current_speaker_is_provisional = is_provisional_char
        if speaker_code:
            self._speaker_identity_pane.setVisible(True)
            state = tr("provisional game code") if is_provisional_char else tr("confirmed game code")
            self._speaker_identity_title.setText(
                tr(
                    '<b>Speaker identity ({state}: {code}):</b>',
                    state=state,
                    code=escape(speaker_code),
                )
            )
            self._apply_speaker_name_button.setText(
                tr('Apply speaker name') if is_provisional_char else tr('Reassign speaker')
            )
            candidates = self._build_speaker_candidates(entry)
            self._speaker_name_combo.blockSignals(True)
            self._speaker_name_combo.clear()
            for cand in candidates:
                self._speaker_name_combo.addItem(cand)

            suggested_name = str(getattr(entry, "suggested_name", "") or "").strip()
            current_name = "" if is_provisional_char else entry.original.strip()
            initial_name = suggested_name or current_name
            if initial_name:
                idx = self._speaker_name_combo.findText(initial_name, Qt.MatchFlag.MatchExactly)
                if idx >= 0:
                    self._speaker_name_combo.setCurrentIndex(idx)
                else:
                    self._speaker_name_combo.setEditText(initial_name)
            else:
                self._speaker_name_combo.setEditText("")
                self._speaker_name_combo.setCurrentIndex(-1)
            self._speaker_name_combo.blockSignals(False)

            suggested_evidence = str(getattr(entry, "suggested_name_evidence", "") or "").strip()
            if is_provisional_char and (suggested_name or suggested_evidence):
                parts = []
                if suggested_name:
                    parts.append(tr('<b>AI Proposal:</b> {name}', name=escape(suggested_name)))
                if suggested_evidence:
                    parts.append(
                        tr('<b>Evidence:</b> {evidence}', evidence=escape(suggested_evidence))
                    )
                self._speaker_evidence_label.setText("<br>".join(parts))
                self._speaker_evidence_label.setVisible(True)
            elif not is_provisional_char:
                self._speaker_evidence_label.setText(
                    tr('Choose another permanent character name to change this mapping.')
                )
                self._speaker_evidence_label.setVisible(True)
            else:
                self._speaker_evidence_label.setText("")
                self._speaker_evidence_label.setVisible(False)

            self._validate_speaker_name()
        else:
            if hasattr(self, '_speaker_identity_pane'):
                self._speaker_identity_pane.setVisible(False)
                self._apply_speaker_name_button.setEnabled(False)
                self._apply_speaker_name_button.setText(tr('Apply speaker name'))

        self._suppress_editor_signals = False
        if hasattr(self, '_notes_variation_button'):
            self._notes_variation_busy = False
            self._notes_variation_button.setText(self._notes_variation_default_text)
        self._mark_editor_dirty(False)
        self._update_editor_enabled_state()

    def _clear_entry_details(self) -> None:
        """Internal helper to remove entry details."""
        self._current_entry = None
        self._suppress_editor_signals = True
        self._original_label.setText(tr('Nothing selected'))
        self._category_combo.clear()
        self._translation_edit.clear()
        self._notes_template = ''
        self._notes_edit.clear()
        self._ai_notes_edit.clear()
        self._profiled_checkbox.setChecked(False)
        self._populate_variants(None)
        if hasattr(self, '_speaker_identity_pane'):
            self._speaker_identity_pane.setVisible(False)
            self._apply_speaker_name_button.setEnabled(False)
            self._apply_speaker_name_button.setText(tr('Apply speaker name'))
        self._current_speaker_code = ""
        self._current_speaker_is_provisional = False
        self._suppress_editor_signals = False
        if hasattr(self, '_notes_variation_button'):
            self._notes_variation_busy = False
            self._notes_variation_button.setText(self._notes_variation_default_text)
            self._notes_variation_button.setEnabled(False)
        self._update_editor_enabled_state()

    def _build_speaker_candidates(self, entry: GlossaryEntry) -> List[str]:
        """Build list of candidate permanent speaker names for a provisional character entry."""
        excluded_lower = set()
        selected_code = (getattr(entry, "original", "") or "").strip().lower()
        if selected_code:
            excluded_lower.add(selected_code)

        for e in self._all_entries:
            orig = (getattr(e, "original", "") or "").strip().lower()
            if self._is_provisional_character(e) and orig:
                excluded_lower.add(orig)

        candidates: List[str] = []
        seen_lower = set()

        def add_candidate(val: str) -> None:
            clean_val = val.strip()
            if not clean_val:
                return
            low = clean_val.lower()
            if low in excluded_lower or low in seen_lower:
                return
            seen_lower.add(low)
            candidates.append(clean_val)

        # 1. Saved suggested_name of selected entry as initial proposal when present
        sug_name = str(getattr(entry, "suggested_name", "") or "").strip()
        if sug_name:
            add_candidate(sug_name)

        # 2. Known permanent speaker names (non-provisional Characters glossary originals)
        for e in self._all_entries:
            if not self._is_provisional_character(e) and (getattr(e, "section", "") or "").strip().lower() == "characters":
                orig = str(getattr(e, "original", "") or "").strip()
                if orig:
                    add_candidate(orig)

        # 3. Distinct non-empty suggested_name values from other entries
        for e in self._all_entries:
            sug = str(getattr(e, "suggested_name", "") or "").strip()
            if sug:
                add_candidate(sug)

        return candidates

    def _validate_speaker_name(self) -> bool:
        """Enable Apply speaker name button only when callback and text form a valid permanent mapping."""
        if not self._current_entry or not self._current_speaker_code:
            self._apply_speaker_name_button.setEnabled(False)
            return False
        callback = (
            self._apply_speaker_name_callback
            if self._current_speaker_is_provisional
            else self._reassign_speaker_callback
        )
        if callback is None:
            self._apply_speaker_name_button.setEnabled(False)
            return False

        proposed = self._speaker_name_combo.currentText().strip()
        if not proposed:
            self._apply_speaker_name_button.setEnabled(False)
            return False
        if not is_confirmed_speaker_alias(proposed):
            self._apply_speaker_name_button.setEnabled(False)
            return False

        code_lower = self._current_speaker_code.lower()
        proposed_lower = proposed.lower()

        if proposed_lower == code_lower:
            self._apply_speaker_name_button.setEnabled(False)
            return False
        if (
            not self._current_speaker_is_provisional
            and proposed_lower == self._current_entry.original.strip().lower()
        ):
            self._apply_speaker_name_button.setEnabled(False)
            return False

        provisional_codes_lower = {
            e.original.strip().lower()
            for e in self._all_entries
            if self._is_provisional_character(e)
        }
        if proposed_lower in provisional_codes_lower:
            self._apply_speaker_name_button.setEnabled(False)
            return False

        self._apply_speaker_name_button.setEnabled(True)
        return True

    def _on_apply_speaker_name_clicked(self) -> None:
        """Handle explicit Apply speaker name button click."""
        if not self._validate_speaker_name() or not self._current_entry:
            return
        permanent_name = self._speaker_name_combo.currentText().strip()
        if self._current_speaker_is_provisional:
            if self._apply_speaker_name_callback:
                self._apply_speaker_name_callback(self._current_speaker_code, permanent_name)
        elif self._reassign_speaker_callback:
            self._reassign_speaker_callback(
                self._current_speaker_code, self._current_entry.original.strip(), permanent_name
            )

    def _confirmed_speaker_code(self, entry: GlossaryEntry) -> str:
        """Return the first confirmed game code that currently names this character."""
        if (getattr(entry, "section", "") or "").strip().lower() != "characters":
            return ""
        callback = self._speaker_codes_callback
        if not callable(callback):
            return ""
        try:
            codes = callback(entry.original) or ()
        except Exception:
            return ""
        return next((str(code).strip() for code in codes if str(code).strip()), "")

    def _is_provisional_character(self, entry: Optional[GlossaryEntry]) -> bool:
        """Whether this Character term is an unresolved game speaker code."""
        if entry is None or (getattr(entry, "section", "") or "").strip().lower() != "characters":
            return False
        if bool(getattr(entry, "provisional", False)):
            return True
        callback = self._placeholder_speaker_callback
        if not callable(callback):
            return False
        try:
            return bool(callback(entry.original))
        except Exception:
            return False

    def _set_variants_visible(self, visible: bool) -> None:
        """Show the variant picker only when there is a decision to make."""
        self._variants_pane.setVisible(visible)
        self._variants_label.setVisible(visible)
        self._variants_list.setVisible(visible)
        if hasattr(self, "_apply_variant_button"):
            self._apply_variant_button.setVisible(visible)
        if hasattr(self, "_discuss_variant_button"):
            self._discuss_variant_button.setVisible(visible)
        if visible and hasattr(self, "_detail_splitter"):
            sizes = self._detail_splitter.sizes()
            if sizes and sizes[0] <= 0:
                sizes[0] = 140
                self._detail_splitter.setSizes(sizes)

    def _populate_variants(self, entry: Optional[GlossaryEntry]) -> None:
        """Fill the variant picker and the confirm button for this entry."""
        self._variants_list.clear()
        variants = list(getattr(entry, "translation_variants", ()) or ()) if entry else []
        # One variant means the AI saw no real ambiguity; nothing to choose.
        has_multiple = len(variants) > 1
        self._set_variants_visible(has_multiple)
        matching_item = None
        for variant in variants:
            label = variant.translation
            if variant.rationale:
                label = f"{variant.translation} — {variant.rationale}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, variant.translation)
            if entry and variant.translation == entry.translation:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                matching_item = item
            self._variants_list.addItem(item)

        if matching_item is not None:
            self._variants_list.setCurrentItem(matching_item)
        elif self._variants_list.count() > 0:
            self._variants_list.setCurrentRow(0)

        can_confirm = bool(entry) and self._needs_review(entry) and bool(self._update_callback)
        self._confirm_button.setVisible(bool(entry) and self._needs_review(entry))
        self._confirm_button.setEnabled(can_confirm)
        self._update_variant_buttons_state()

    def _on_apply_selected_variant(self) -> None:
        """Apply the currently selected proposed variant, confirm it, and advance."""
        item = self._variants_list.currentItem()
        if not item:
            return
        self._apply_variant_item(item, advance=True)

    def _apply_variant_item(self, item: QListWidgetItem, advance: bool = False) -> None:
        """Apply a variant item: update translation edit, refresh notes, and confirm."""
        translation = item.data(Qt.ItemDataRole.UserRole)
        if not translation:
            return
        self._translation_edit.setText(str(translation))
        self._refresh_rendered_notes()
        self._on_confirm_clicked(advance=advance)

    def _on_variant_chosen(self, item: QListWidgetItem) -> None:
        """Apply a chosen variant (alias for _apply_variant_item)."""
        self._apply_variant_item(item, advance=False)

    def _on_discuss_variants_clicked(self) -> None:
        """Handle Discuss with AI... button click."""
        if not self._discuss_variant_callback or not self._current_entry:
            return
        self._discuss_variant_callback(self._current_entry)
