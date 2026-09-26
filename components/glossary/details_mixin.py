"""Glossary entry details, occurrences, speaker identity, and variants."""
from __future__ import annotations

import os
import re
import time
from html import escape
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QListWidgetItem
from core.glossary_manager import GlossaryEntry, GlossaryOccurrence
from core.speaker_alias_merge import is_confirmed_speaker_alias
from core.i18n import tr
from utils.logging_utils import log_debug


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

    @staticmethod
    def _is_reference_variant(variant) -> bool:
        """Check whether a variant represents an external reference translation."""
        if not variant:
            return False
        rat = getattr(variant, "rationale", "") or ""
        return bool("RU" in rat or "патч" in rat.lower() or rat.startswith("ref:"))

    @classmethod
    def _is_reference_item(cls, item: Optional[QListWidgetItem]) -> bool:
        """Check whether a QListWidgetItem holds a reference translation variant."""
        if not item:
            return False
        return bool(item.data(Qt.ItemDataRole.UserRole + 1))

    def _update_variant_buttons_state(self) -> None:
        """Update enabled state for variant action buttons."""
        has_entry = self._current_entry is not None
        cur_item = self._variants_list.currentItem() if hasattr(self, "_variants_list") else None
        has_selected_item = bool(cur_item)
        is_ref = self._is_reference_item(cur_item)
        can_apply = has_entry and has_selected_item and (not is_ref) and (self._update_callback is not None)
        if hasattr(self, "_apply_variant_button"):
            self._apply_variant_button.setEnabled(can_apply)
        if hasattr(self, "_discuss_variant_button"):
            has_discuss = self._discuss_variant_callback is not None
            self._discuss_variant_button.setEnabled(has_entry and has_discuss)
            self._discuss_variant_button.setVisible(has_discuss)
        if hasattr(self, "_confirm_button"):
            can_confirm = has_entry and (self._update_callback is not None)
            self._confirm_button.setEnabled(can_confirm)

    def _on_open_wiki_link(self) -> None:
        """Open external wiki reference URL in the default browser."""
        url = getattr(self, "_current_wiki_url", None)
        if url:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(url))

    def _update_occurrences(self, entry: GlossaryEntry) -> None:
        """Internal helper to update the occurrences."""
        occ_list = list(self._occurrences.get(entry.original, []))
        spoken_rows = [o for o in occ_list if getattr(o, "kind", "mention") == "spoken"]
        mention_rows = [o for o in occ_list if getattr(o, "kind", "mention") != "spoken"]
        self._current_entry_occurrences = spoken_rows + mention_rows
        mentions = len(mention_rows)
        spoken = len(spoken_rows)
        self._occurrence_label.setText(
            tr('Mentions: {mentions}   Spoken: {spoken}', mentions=mentions, spoken=spoken)
        )
        if hasattr(self, "_show_mentions_checkbox"):
            self._show_mentions_checkbox.setText(tr('Mentions ({count})', count=mentions))
        if hasattr(self, "_show_spoken_checkbox"):
            self._show_spoken_checkbox.setText(tr('Spoken ({count})', count=spoken))
        self._repopulate_occurrences_filter()

    def _is_russian_reference(self) -> bool:
        """Check whether the active reference data is confirmed to be Russian."""
        lang = getattr(self, "_reference_language", None)
        if not lang:
            return False
        return bool("Russian" in lang or "(RU)" in lang or lang.strip().lower() == "ru")


    def _highlight_russian_term(self, ru_text: str, entry: Optional[GlossaryEntry]) -> str:
        """Highlight direct term match in Russian text if found with 100% confidence.

        Otherwise returns the complete escaped text without truncation to preserve context.
        """
        if not entry:
            return escape(ru_text)

        candidates: List[str] = []
        if entry.translation and entry.translation.strip():
            candidates.append(entry.translation.strip())
        for v in getattr(entry, "translation_variants", ()) or ():
            t = getattr(v, "translation", "")
            if t and t.strip() and t.strip() not in candidates:
                candidates.append(t.strip())

        # 1. Exact case-insensitive word-boundary match
        for cand in candidates:
            if len(cand) < 2:
                continue
            pattern = re.compile(rf"\b{re.escape(cand)}\b", re.IGNORECASE)
            m = pattern.search(ru_text)
            if m:
                start, end = m.span()
                before = escape(ru_text[:start])
                match_txt = escape(ru_text[start:end])
                after = escape(ru_text[end:])
                return f"{before}<b style='color: #f59e0b; text-decoration: underline;'>{match_txt}</b>{after}"

        # 2. Inflected match for single-word Russian terms (length >= 4)
        for cand in candidates:
            words = cand.split()
            if len(words) == 1 and len(cand) >= 4:
                stem = re.sub(r'[аеиоуыэюяйьъ]+$', '', cand, flags=re.IGNORECASE)
                if len(stem) >= 3:
                    pattern = re.compile(rf"\b{re.escape(stem)}[а-яёА-ЯЁ]{{0,3}}\b", re.IGNORECASE)
                    m = pattern.search(ru_text)
                    if m:
                        start, end = m.span()
                        before = escape(ru_text[:start])
                        match_txt = escape(ru_text[start:end])
                        after = escape(ru_text[end:])
                        return f"{before}<b style='color: #f59e0b; text-decoration: underline;'>{match_txt}</b>{after}"

        # If no 100% confident direct match, return full phrase escaped without truncation
        return escape(ru_text)

    def _get_source_message(self, occ: GlossaryOccurrence) -> Optional[str]:
        """Retrieve full original source message for an occurrence if available."""
        source_data = getattr(self, "_source_data", None)
        if source_data is None:
            parent = getattr(self, "_parent", None)
            if parent is not None:
                data_store = getattr(parent, "data_store", None)
                if data_store is not None:
                    source_data = getattr(data_store, "data", None)

        if source_data is None:
            return None

        b_idx = getattr(occ, "block_idx", None)
        s_idx = getattr(occ, "string_idx", None)
        if b_idx is None or s_idx is None:
            return None

        if isinstance(source_data, dict):
            val = source_data.get((b_idx, s_idx))
            return str(val) if val is not None else None

        if isinstance(source_data, (list, tuple)) and 0 <= b_idx < len(source_data):
            block = source_data[b_idx]
            if isinstance(block, (list, tuple)) and 0 <= s_idx < len(block):
                val = block[s_idx]
                return str(val) if val is not None else None

        return None

    def _repopulate_occurrences_filter(self) -> None:
        """Filter the occurrence list according to mentions and spoken checkboxes."""
        self._occurrence_list.clear()
        occ_list = getattr(self, "_current_entry_occurrences", [])
        show_mentions = getattr(self, "_show_mentions_checkbox", None)
        show_spoken = getattr(self, "_show_spoken_checkbox", None)
        can_show_mentions = show_mentions.isChecked() if show_mentions is not None else True
        can_show_spoken = show_spoken.isChecked() if show_spoken is not None else True

        filtered_occs = [
            occ for occ in occ_list
            if (getattr(occ, "kind", "mention") == "spoken" and can_show_spoken)
            or (getattr(occ, "kind", "mention") != "spoken" and can_show_mentions)
        ]

        ref_data = getattr(self, "_reference_data", None) or {}
        entry = getattr(self, "_current_entry", None)
        is_ru_ref = self._is_russian_reference()

        for index, occ in enumerate(filtered_occs, start=1):
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

            source_msg = self._get_source_message(occ)
            if source_msg is not None and str(source_msg).strip():
                en_lines = str(source_msg).replace('\r\n', '\n').replace('\r', '\n').split('\n')
                single_fallback = False
            else:
                en_lines = [occ.line_text or ""]
                single_fallback = True

            rendered_en = []
            is_spoken = getattr(occ, "kind", "mention") == "spoken"
            for l_idx, line_str in enumerate(en_lines):
                should_highlight = (
                    not is_spoken
                    and (
                        l_idx == occ.line_idx
                        or (single_fallback and 0 <= occ.start < occ.end <= len(line_str))
                    )
                    and 0 <= occ.start < occ.end <= len(line_str)
                )
                if should_highlight:
                    en_before = escape(line_str[:occ.start])
                    en_match = escape(line_str[occ.start:occ.end])
                    en_after = escape(line_str[occ.end:])
                    rendered_en.append(f"{en_before}<b style='color: #60a5fa;'>{en_match}</b>{en_after}")
                else:
                    rendered_en.append(escape(line_str))

            en_html = "<br>".join(rendered_en)
            preview_html = f"<div style='margin-top: 2px;'><b style='color: #94a3b8;'>EN:</b> {en_html}</div>"

            ru_block = ""
            if is_ru_ref:
                ru_raw = ref_data.get((occ.block_idx, occ.string_idx))
                if ru_raw is not None and str(ru_raw).strip():
                    ru_lines = str(ru_raw).replace('\r\n', '\n').replace('\r', '\n').split('\n')
                    highlighted_ru = [self._highlight_russian_term(line, entry) for line in ru_lines]
                    ru_html = "<br>".join(highlighted_ru)
                    ru_block = (
                        f"<div style='margin-top: 4px; padding: 3px 6px; "
                        f"background-color: rgba(56, 189, 248, 0.12); border-radius: 3px;'>"
                        f"<b style='color: #0284c7;'>RU:</b> {ru_html}</div>"
                    )
            if ru_block:
                item_content = f"{header_html}<br>{preview_html}{ru_block}"
            else:
                item_content = f"{header_html}<br>{preview_html}"

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, item_content)
            item.setData(Qt.ItemDataRole.UserRole, occ)
            self._occurrence_list.addItem(item)

    def _populate_entry_details(self, entry: GlossaryEntry) -> None:
        """Internal helper to populate entry details."""
        self._current_entry = entry
        self._suppress_editor_signals = True
        self._original_label.setText(tr('Term: {original}', original=entry.original))
        if hasattr(self, "_original_edit"):
            self._original_edit.setText(entry.original)

        url = None
        callback = getattr(self, "_external_reference_callback", None)
        if callable(callback):
            try:
                url = callback(entry.original)
            except Exception:
                url = None
        self._current_wiki_url = url
        if hasattr(self, "_wiki_link_button"):
            self._wiki_link_button.setVisible(bool(url))
            if url:
                self._wiki_link_button.setToolTip(
                    tr("Open external wiki reference for '{term}'", term=entry.original)
                )
        self._populate_category_choices(entry)
        self._translation_edit.setText(entry.translation or '')
        from core.glossary.notes import ensure_term_placeholder
        candidates = [entry.translation] + [
            v.translation for v in (getattr(entry, "translation_variants", ()) or ())
        ]
        self._notes_template = ensure_term_placeholder(
            entry.notes or '', original=entry.original, known_names=candidates
        )
        self._notes_edit.setPlainText(self._rendered_notes())
        if getattr(entry, "user_notes", ""):
            self._ai_notes_edit.setPlainText(entry.user_notes)
        else:
            self._ai_notes_edit.setPlainText(self._ai_notes_for_entry(entry))
        self._initial_ai_notes = self._ai_notes_edit.toPlainText().strip()
        self._user_notes_edited = False
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
        self._current_entry_occurrences = []
        self._suppress_editor_signals = True
        self._original_label.setText(tr('Nothing selected'))
        if hasattr(self, "_original_edit"):
            self._original_edit.clear()
        self._current_wiki_url = None
        if hasattr(self, "_wiki_link_button"):
            self._wiki_link_button.setVisible(False)
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
        if visible and hasattr(self, "_detail_splitter"):
            sizes = self._detail_splitter.sizes()
            if sizes and sizes[0] <= 0:
                sizes[0] = 120
                self._detail_splitter.setSizes(sizes)

    def _populate_variants(self, entry: Optional[GlossaryEntry]) -> None:
        """Fill the variant picker and the confirm button for this entry."""
        self._variants_list.clear()
        variants = list(getattr(entry, "translation_variants", ()) or ()) if entry else []
        # One variant means the AI saw no real ambiguity; nothing to choose.
        has_multiple = len(variants) > 1
        self._set_variants_visible(has_multiple)
        matching_item = None
        is_dark = self.palette().color(self.backgroundRole()).lightness() < 128
        ref_color = QColor("#38bdf8") if is_dark else QColor("#0284c7")

        for variant in variants:
            is_ref = self._is_reference_variant(variant)
            label = variant.translation
            if variant.rationale:
                label = f"{variant.translation} — {variant.rationale}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, variant.translation)
            item.setData(Qt.ItemDataRole.UserRole + 1, is_ref)
            if is_ref:
                item.setForeground(ref_color)
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
                item.setToolTip(
                    tr("Reference translation variant (for context only, not applicable as Ukrainian translation)")
                )
            else:
                if entry and variant.translation == entry.translation:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    matching_item = item
            self._variants_list.addItem(item)

        if matching_item is not None:
            self._variants_list.setCurrentItem(matching_item)
        elif self._variants_list.count() > 0:
            first_target_row = -1
            for row in range(self._variants_list.count()):
                if not self._is_reference_item(self._variants_list.item(row)):
                    first_target_row = row
                    break
            self._variants_list.setCurrentRow(first_target_row if first_target_row >= 0 else 0)

        can_confirm = bool(entry) and bool(self._update_callback)
        self._confirm_button.setVisible(bool(entry))
        self._confirm_button.setEnabled(can_confirm)
        self._update_variant_buttons_state()

    def _update_variant_boldness(self, active_translation: str) -> None:
        """Update font bolding in the variants list to reflect active translation."""
        if not hasattr(self, "_variants_list"):
            return
        for i in range(self._variants_list.count()):
            it = self._variants_list.item(i)
            if self._is_reference_item(it):
                continue
            font = it.font()
            is_active = (it.data(Qt.ItemDataRole.UserRole) == active_translation)
            if font.bold() != is_active:
                font.setBold(is_active)
                it.setFont(font)

    def _on_apply_selected_variant(self) -> None:
        """Apply the currently selected proposed variant to the translation editor."""
        if not self._current_entry or self._update_callback is None:
            return
        item = self._variants_list.currentItem()
        if not item or self._is_reference_item(item):
            return
        self._apply_variant_item(item)

    def _on_variant_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on a proposed variant item."""
        if not item or not self._current_entry or self._update_callback is None:
            return
        if self._is_reference_item(item):
            return
        self._apply_variant_item(item)

    def _apply_variant_item(self, item: QListWidgetItem, advance: bool = False) -> None:
        """Apply a variant item: update translation edit, refresh notes, and highlight."""
        translation = item.data(Qt.ItemDataRole.UserRole)
        if not translation:
            return

        profile_enabled = os.environ.get("PICORIPI_PROFILE_GLOSSARY_VARIANT") == "1"
        profiler = None
        if profile_enabled:
            import cProfile
            profiler = cProfile.Profile()
            profiler.enable()

        t_start = time.perf_counter()
        try:
            self._translation_edit.setText(str(translation))
            self._refresh_rendered_notes()
            self._update_variant_boldness(str(translation))
            if hasattr(self, "_variants_list") and self._variants_list.currentItem() is not item:
                self._variants_list.setCurrentItem(item)
        finally:
            elapsed = time.perf_counter() - t_start
            if profiler is not None:
                profiler.disable()
                import tempfile
                with tempfile.NamedTemporaryFile(
                    suffix=".prof", prefix="picoripi_glossary_variant_", delete=False
                ) as f:
                    prof_path = f.name
                profiler.dump_stats(prof_path)
                print(f"\nGLOSSARY VARIANT WALL TIME: {elapsed:.4f}s")
                print(f"PROFILE: {prof_path}")
                print("To inspect top 30 cumulative functions:")
                print(f"  .\\venv\\Scripts\\python.exe tools\\benchmark_glossary_variant.py --profile \"{prof_path}\"\n")

        log_debug(f"Glossary: variant application took {elapsed:.3f}s")

    def _on_variant_chosen(self, item: QListWidgetItem) -> None:
        """Apply a chosen variant (alias for _apply_variant_item)."""
        self._apply_variant_item(item)

    def _on_discuss_variants_clicked(self) -> None:
        """Handle Discuss with AI... button click."""
        if not self._discuss_variant_callback or not self._current_entry:
            return
        entry = self._current_entry
        from dataclasses import replace
        current_trans = self._translation_edit.text().strip() if hasattr(self, "_translation_edit") else entry.translation
        current_sec = (
            self._canonical_category_name(self._category_combo.currentText())
            if hasattr(self, "_category_combo") and hasattr(self, "_canonical_category_name")
            else (self._category_combo.currentText().strip() if hasattr(self, "_category_combo") else entry.section)
        )
        current_notes = self._notes_for_save() if hasattr(self, "_notes_for_save") else entry.notes
        entry = replace(
            entry,
            translation=current_trans if current_trans else entry.translation,
            section=current_sec if current_sec else entry.section,
            notes=current_notes if current_notes else entry.notes,
        )
        self._discuss_variant_callback(entry)
