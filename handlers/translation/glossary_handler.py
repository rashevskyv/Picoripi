# --- START OF FILE handlers/translation/glossary_handler.py ---
# Refactored: GlossaryHandler is now a facade delegating to:
#   - GlossaryPromptManager  (prompt I/O and caching)
#   - components/GlossaryEditDialog (entry edit UI)
# Occurrence-update AI logic remains here (single + batch), earmarked for
# future extraction into GlossaryOccurrenceUpdater if needed.

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PyQt5.QtWidgets import QAction, QMessageBox, QDialog
from PyQt5.QtCore import Qt

from .base_translation_handler import BaseTranslationHandler
from .glossary_prompt_manager import GlossaryPromptManager
from core.glossary_manager import GlossaryEntry, GlossaryManager, GlossaryOccurrence
from components.glossary_dialog import GlossaryDialog
from components.glossary_translation_update_dialog import GlossaryTranslationUpdateDialog
from components.glossary_edit_dialog import GlossaryEditDialog
from utils.logging_utils import log_debug


class GlossaryHandler(BaseTranslationHandler):

    def __init__(self, main_handler):
        super().__init__(main_handler)
        self.glossary_manager = GlossaryManager()
        self._open_glossary_action: Optional[QAction] = None
        self.dialog: Optional[GlossaryDialog] = None
        self.translation_update_dialog: Optional[GlossaryTranslationUpdateDialog] = None

        # State for occurrence-update workflow
        self._pending_ai_occurrences: List[GlossaryOccurrence] = []
        self._current_translation_entry: Optional[GlossaryEntry] = None
        self._previous_translation_value: Optional[str] = None
        self._batch_prompt_override: Optional[Tuple[str, str]] = None

        # Delegate: prompt I/O
        self._prompt_manager = GlossaryPromptManager(self.mw, main_handler, self.glossary_manager)

    # ── Public prompt manager proxy (used by TranslationHandler) ─────────

    @property
    def _current_prompts_path(self) -> Optional[Path]:
        return self._prompt_manager.current_prompts_path

    def load_prompts(self) -> Tuple[Optional[str], Optional[str]]:
        return self._prompt_manager.load_prompts()

    def save_prompt_section(self, section: str, field: str, value: str) -> bool:
        return self._prompt_manager.save_prompt_section(section, field, value)

    def _get_glossary_prompt_template(self) -> Tuple[str, Optional[Path]]:
        return self._prompt_manager.get_glossary_prompt_template()

    def _update_glossary_highlighting(self) -> None:
        self._prompt_manager._update_glossary_highlighting()

    def _ensure_glossary_loaded(self, *, glossary_text, plugin_name, glossary_path) -> None:
        self._prompt_manager._ensure_glossary_loaded(
            glossary_text=glossary_text, plugin_name=plugin_name, glossary_path=glossary_path
        )

    # ── Menu / initialization ─────────────────────────────────────────────

    def install_menu_actions(self) -> None:
        tools_menu = getattr(self.mw, "tools_menu", None)
        if not tools_menu:
            return
        if self._open_glossary_action is None:
            action = QAction("Open Glossary...", self.mw)
            action.setToolTip("Open glossary and jump to occurrences")
            action.triggered.connect(self.show_glossary_dialog)
            tools_menu.addAction(action)
            self._open_glossary_action = action

        reset_action = getattr(self.main_handler, "_reset_session_action", None)
        if reset_action is None:
            reset_action = QAction("AI Reset Translation Session", self.mw)
            reset_action.setToolTip("Reset the current AI translation session")
            reset_action.triggered.connect(self.main_handler.reset_translation_session)
            tools_menu.addAction(reset_action)
            self.main_handler._reset_session_action = reset_action

    def initialize_glossary_highlighting(self) -> None:
        self._prompt_manager.initialize_highlighting()

    # ── Glossary dialog ───────────────────────────────────────────────────

    def _on_glossary_dialog_closed(self):
        self.dialog = None
        log_debug("Glossary dialog closed and reference cleared.")

    def show_glossary_dialog(self, initial_term: Optional[str] = None) -> None:
        if self.dialog and self.dialog.isVisible():
            self.dialog.raise_()
            self.dialog.activateWindow()
            return

        system_prompt, glossary_text = self.load_prompts()
        if system_prompt is None:
            return

        if not self.glossary_manager.get_entries():
            QMessageBox.information(self.mw, "Glossary", "Glossary is empty or not loaded.")
            return

        data_source = getattr(self.mw, "data", None)
        if not isinstance(data_source, list):
            QMessageBox.information(self.mw, "Glossary", "No data is loaded for analysis.")
            return

        occurrence_map = self.glossary_manager.build_occurrence_index(data_source)
        entries = sorted(self.glossary_manager.get_entries(), key=lambda e: e.original.lower())
        self.dialog = GlossaryDialog(
            parent=self.mw, entries=entries, occurrence_map=occurrence_map,
            jump_callback=self._jump_to_occurrence,
            update_callback=self._handle_glossary_entry_update,
            delete_callback=self._handle_glossary_entry_delete,
            ai_variation_callback=self._handle_notes_variation_from_dialog,
            initial_term=initial_term,
        )
        self.dialog.finished.connect(self._on_glossary_dialog_closed)
        self.dialog.show()

    # ── Entry CRUD ────────────────────────────────────────────────────────

    def add_glossary_entry(self, term: str, context: Optional[str] = None) -> None:
        self.edit_glossary_entry(term, is_new=True, context=context)

    def edit_glossary_entry(self, term: str, is_new: bool = False, context: Optional[str] = None) -> None:
        entry = self.glossary_manager.get_entry(term) if not is_new else None
        old_translation = entry.translation if entry else None

        dialog = self._create_edit_dialog(term, entry, context)
        if dialog.exec_() != QDialog.Accepted:
            return

        new_translation, new_notes = dialog.get_values()
        if not new_translation:
            if entry and new_notes != entry.notes:
                if self.glossary_manager.update_entry(term, entry.translation, new_notes):
                    self.glossary_manager.save_to_disk()
                    self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
                    self._update_glossary_highlighting()
            return

        if is_new:
            updated_entry = self.glossary_manager.add_entry(term, new_translation, new_notes)
        else:
            updated_entry = self.glossary_manager.update_entry(term, new_translation, new_notes)

        self.glossary_manager.save_to_disk()
        self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
        self._update_glossary_highlighting()

        if not is_new and updated_entry and old_translation and old_translation.strip() != new_translation.strip():
            data_source = getattr(self.mw, "data", [])
            occurrence_map = self.glossary_manager.build_occurrence_index(data_source)
            occurrences = occurrence_map.get(updated_entry.original, [])
            if occurrences:
                log_debug(f"Glossary: Translation changed for '{term}'. Showing update dialog.")
                self._show_translation_update_dialog(
                    entry=updated_entry, previous_translation=old_translation, occurrences=occurrences
                )

    def _create_edit_dialog(self, term: str, entry: Optional[GlossaryEntry], context: Optional[str]) -> GlossaryEditDialog:
        dialog_ref: Dict[str, GlossaryEditDialog] = {}

        def _ai_fill_wrapper() -> None:
            d = dialog_ref.get("dialog")
            if d:
                self._ai_fill_glossary_entry(term, context, d)

        def _notes_variation_wrapper() -> None:
            d = dialog_ref.get("dialog")
            if not d:
                return
            translation, notes = d.get_values()
            self._start_glossary_notes_variation(
                term=term, translation=translation, notes=notes,
                context_line=context, target_dialog=d,
            )

        dialog = GlossaryEditDialog(
            parent=self.mw,
            term=term,
            translation=entry.translation if entry else "",
            notes=entry.notes if entry else "",
            context=context,
            ai_assist_callback=_ai_fill_wrapper,
            notes_variation_callback=_notes_variation_wrapper,
        )
        dialog_ref["dialog"] = dialog
        return dialog

    # ── AI Fill glossary entry ────────────────────────────────────────────

    def _ai_fill_glossary_entry(self, term: str, context: Optional[str], dialog: GlossaryEditDialog) -> None:
        provider = self.main_handler._prepare_provider()
        if not provider:
            return

        template, _ = self._get_glossary_prompt_template()
        if not template:
            return

        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else "this game"
        system_prompt = template.replace("{{GAME_NAME}}", game_name)

        user_content_parts = [f'Term: "{term}"']
        if context:
            user_content_parts.append(f'Context line: "{context}"')
        user_content = "\n".join(user_content_parts)

        edited = self.main_handler._maybe_edit_prompt(
            title="AI Glossary Fill Prompt",
            system_prompt=system_prompt,
            user_prompt=user_content,
            save_section="glossary",
            save_field="prompt_template",
        )
        if edited is None:
            return
        edited_system, edited_user = edited

        precomposed = [
            {"role": "system", "content": edited_system},
            {"role": "user", "content": edited_user},
        ]
        task_details = {
            "type": "fill_glossary",
            "composer_args": {"system_prompt": edited_system, "user_content": edited_user},
            "attempt": 1, "max_retries": 1,
            "dialog": dialog, "term": term, "context_line": context,
        }
        if not self.main_handler._attach_session_to_task(
            task_details, system_prompt=edited_system, user_prompt=edited_user, task_type="fill_glossary",
        ):
            task_details["precomposed_prompt"] = precomposed

        dialog.set_ai_busy(True)
        self.main_handler.ui_handler.start_ai_operation("AI Glossary Fill", model_name=self.main_handler._active_model_name)
        self.main_handler._run_ai_task(provider, task_details)

    def _handle_ai_fill_success(self, response, context: dict) -> None:
        self.main_handler.ui_handler.finish_ai_operation()
        dialog = context.get("dialog") if isinstance(context, dict) else None
        if not isinstance(dialog, GlossaryEditDialog):
            return
        dialog.set_ai_busy(False)

        cleaned = self.main_handler._clean_model_output(response)
        translation_value = notes_value = None
        if cleaned:
            try:
                payload = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                log_debug(f"AI Glossary Fill: failed to parse response: {exc}")
                QMessageBox.warning(self.mw, "AI Glossary Fill", "Could not parse AI response.")
                return
            if isinstance(payload, dict):
                if "translation" in payload:
                    translation_value = str(payload.get("translation") or "").strip()
                if "notes" in payload:
                    notes_value = str(payload.get("notes") or "").strip()

        current_translation, current_notes = dialog.get_values()
        if translation_value is None and notes_value is None:
            QMessageBox.information(self.mw, "AI Glossary Fill", "AI response did not include translation or notes.")
            return

        new_translation = translation_value or current_translation
        new_notes = notes_value if notes_value is not None else current_notes
        dialog.set_values(new_translation, new_notes)
        self.main_handler._record_session_exchange(context=context, assistant_content=cleaned)

    def _handle_ai_fill_error(self, error_message: str, context: dict) -> None:
        dialog = context.get("dialog") if isinstance(context, dict) else None
        if isinstance(dialog, GlossaryEditDialog):
            dialog.set_ai_busy(False)
        msg = error_message or "AI request failed."
        QMessageBox.warning(self.mw, "AI Glossary Fill", msg)

    # ── Notes variation ───────────────────────────────────────────────────

    def _set_notes_dialog_busy(self, dialog_obj, busy: bool) -> None:
        if not dialog_obj:
            return
        if hasattr(dialog_obj, "set_ai_busy"):
            dialog_obj.set_ai_busy(busy)
        elif hasattr(dialog_obj, "set_notes_variation_busy"):
            dialog_obj.set_notes_variation_busy(busy)

    def _start_glossary_notes_variation(self, *, term, translation, notes, context_line, target_dialog) -> None:
        self._set_notes_dialog_busy(target_dialog, True)
        started = self.request_glossary_notes_variation(
            term=term, translation=translation, current_notes=notes,
            context_line=context_line, dialog=target_dialog,
        )
        if not started:
            self._set_notes_dialog_busy(target_dialog, False)

    def _handle_notes_variation_from_dialog(self, entry: GlossaryEntry) -> None:
        if not entry or not self.dialog:
            return
        context_line: Optional[str] = None
        data_source = getattr(self.mw, "data", None)
        if isinstance(data_source, list):
            occurrence_map = self.glossary_manager.build_occurrence_index(data_source)
            occ_list = occurrence_map.get(entry.original, [])
            if occ_list:
                context_line = getattr(occ_list[0], "line_text", None)
        self._start_glossary_notes_variation(
            term=entry.original, translation=entry.translation or "",
            notes=entry.notes or "", context_line=context_line, target_dialog=self.dialog,
        )

    def _handle_glossary_notes_variation_success(self, response, context: dict) -> None:
        self.main_handler.ui_handler.finish_ai_operation()
        cleaned = self.main_handler.ai_lifecycle_manager._clean_model_output(response)
        self.main_handler.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned, response=response)

        dialog = context.get("dialog")
        self._set_notes_dialog_busy(dialog, False)

        variants = self.main_handler.ui_handler.parse_variation_payload(cleaned)
        if not variants:
            QMessageBox.information(self.mw, "AI Glossary Notes", "Failed to parse variations from AI response.")
            return

        chosen = self.main_handler.ui_handler.show_variations_dialog(variants)
        if not chosen:
            return

        if dialog and hasattr(dialog, "get_values") and hasattr(dialog, "set_values"):
            current_translation, _ = dialog.get_values()
            dialog.set_values(current_translation, chosen)
        elif dialog and hasattr(dialog, "apply_notes_variation"):
            dialog.apply_notes_variation(chosen)
        if self.mw.statusBar:
            self.mw.statusBar.showMessage("Applied AI-generated glossary notes.", 4000)

    # ── Navigation & data helpers ─────────────────────────────────────────

    def _get_original_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return self.data_processor._get_string_from_source(
            block_idx, string_idx, getattr(self.mw, "data", None), "original_for_translation"
        )

    def _get_original_block(self, block_idx: int) -> List[str]:
        data_source = getattr(self.mw, "data", None)
        if not isinstance(data_source, list) or not (0 <= block_idx < len(data_source)):
            return []
        block = data_source[block_idx]
        return [str(item) for item in block] if isinstance(block, list) else []

    def _jump_to_occurrence(self, occurrence: GlossaryOccurrence) -> None:
        if occurrence is None:
            return
        entry = {
            "block_idx": occurrence.block_idx,
            "string_idx": occurrence.string_idx,
            "line_idx": occurrence.line_idx,
        }
        self.main_handler.ui_handler._activate_entry(entry)
        self.mw.ui_updater.highlight_glossary_occurrence(occurrence)
        self.mw.activateWindow()
        self.mw.raise_()
        if self.mw.statusBar:
            self.mw.statusBar.showMessage(f"Navigated to glossary term: {occurrence.entry.original}", 4000)

    # ── Entry update/delete callbacks (called from GlossaryDialog) ────────

    def _handle_glossary_entry_update(self, original: str, translation: str, notes: str):
        previous_entry = self.glossary_manager.get_entry(original)
        previous_translation = previous_entry.translation if previous_entry else None

        if self.glossary_manager.update_entry(original, translation, notes):
            data_source = getattr(self.mw, "data", [])
            occurrence_map = self.glossary_manager.build_occurrence_index(data_source)
            entries = sorted(self.glossary_manager.get_entries(), key=lambda e: e.original.lower())
            self._update_glossary_highlighting()
            self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
            if self.mw.statusBar:
                self.mw.statusBar.showMessage(f"Glossary updated: {original}", 4000)

            updated_entry = self.glossary_manager.get_entry(original)
            if (
                previous_translation is not None
                and updated_entry is not None
                and previous_translation.strip() != updated_entry.translation.strip()
            ):
                occurrences = occurrence_map.get(updated_entry.original, [])
                if occurrences:
                    self._show_translation_update_dialog(
                        entry=updated_entry,
                        previous_translation=previous_translation,
                        occurrences=occurrences,
                    )
            return entries, occurrence_map
        return None

    def _handle_glossary_entry_delete(self, original: str):
        if self.glossary_manager.delete_entry(original):
            data_source = getattr(self.mw, "data", [])
            occurrence_map = self.glossary_manager.build_occurrence_index(data_source)
            entries = sorted(self.glossary_manager.get_entries(), key=lambda e: e.original.lower())
            self._update_glossary_highlighting()
            self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
            if self.mw.statusBar:
                self.mw.statusBar.showMessage(f"Glossary deleted: {original}", 4000)
            return entries, occurrence_map
        return None

    # ── Translation-update dialog (occurrence retranslation) ─────────────

    def _show_translation_update_dialog(
        self,
        *,
        entry: GlossaryEntry,
        previous_translation: str,
        occurrences: Sequence[GlossaryOccurrence],
    ) -> None:
        if self.translation_update_dialog and self.translation_update_dialog.isVisible():
            self.translation_update_dialog.raise_()
            self.translation_update_dialog.activateWindow()
            return

        self._current_translation_entry = entry
        self._previous_translation_value = previous_translation
        self._pending_ai_occurrences = []

        dialog = GlossaryTranslationUpdateDialog(
            parent=self.mw,
            term=entry.original,
            old_translation=previous_translation,
            new_translation=entry.translation,
            occurrences=occurrences,
            get_original_text=self._get_occurrence_original_text,
            get_current_translation=self._get_occurrence_translation_text,
            apply_translation=self._apply_occurrence_translation,
            ai_request_single=lambda occ: self._request_ai_occurrence_update(occ, from_batch=False),
            ai_request_all=self._start_ai_occurrence_batch,
        )
        dialog.finished.connect(self._on_translation_update_dialog_closed)
        dialog.show()
        self.translation_update_dialog = dialog

    def _on_translation_update_dialog_closed(self, *_args) -> None:
        self.translation_update_dialog = None
        self._pending_ai_occurrences = []
        self._current_translation_entry = None
        self._previous_translation_value = None
        self._batch_prompt_override = None

    # ── Occurrence helpers ────────────────────────────────────────────────

    def _get_occurrence_original_text(self, occurrence: GlossaryOccurrence) -> str:
        return str(self._get_original_string(occurrence.block_idx, occurrence.string_idx) or "")

    def _get_occurrence_translation_text(self, occurrence: GlossaryOccurrence) -> str:
        text, _ = self.main_handler.data_processor.get_current_string_text(occurrence.block_idx, occurrence.string_idx)
        return str(text or "")

    def _apply_occurrence_translation(self, occurrence: GlossaryOccurrence, new_text: str) -> None:
        self.main_handler.data_processor.update_edited_data(occurrence.block_idx, occurrence.string_idx, new_text)
        self.mw.ui_updater.populate_strings_for_block(occurrence.block_idx)
        if self.mw.current_block_idx == occurrence.block_idx and self.mw.current_string_idx == occurrence.string_idx:
            self.mw.ui_updater.update_text_views()
        self.mw.ui_updater.update_block_item_text_with_problem_count(occurrence.block_idx)
        if self.mw.statusBar:
            self.mw.statusBar.showMessage(
                f"Updated translation for block {occurrence.block_idx}, string {occurrence.string_idx}", 3000
            )

    # ── Occurrence AI: single ─────────────────────────────────────────────

    def _request_ai_occurrence_update(self, occurrence: GlossaryOccurrence, from_batch: bool) -> None:
        if not self.translation_update_dialog or not self._current_translation_entry:
            return
        dialog = self.translation_update_dialog
        term_entry = self._current_translation_entry
        original_text = self._get_occurrence_original_text(occurrence)
        current_translation = self._get_occurrence_translation_text(occurrence)

        if not from_batch:
            self._pending_ai_occurrences = []

        dialog.set_ai_busy(True)
        if from_batch:
            dialog.set_batch_active(True)

        prompt_override = self._batch_prompt_override if from_batch else None
        result = self.request_glossary_occurrence_update(
            occurrence=occurrence,
            original_text=original_text,
            current_translation=current_translation,
            term=term_entry.original,
            old_term_translation=self._previous_translation_value or "",
            new_term_translation=term_entry.translation,
            dialog=dialog,
            from_batch=from_batch,
            prompt_override=prompt_override,
        )
        if from_batch and result:
            self._batch_prompt_override = result
        elif not from_batch:
            self._batch_prompt_override = None

    def request_glossary_occurrence_update(
        self,
        *,
        occurrence: GlossaryOccurrence,
        original_text: str,
        current_translation: str,
        term: str,
        old_term_translation: str,
        new_term_translation: str,
        dialog,
        from_batch: bool,
        prompt_override: Optional[Tuple[str, str]] = None,
    ) -> Optional[Tuple[str, str]]:
        provider = self.main_handler.ai_lifecycle_manager._prepare_provider()
        if not provider:
            self._handle_occurrence_ai_error("AI provider is not configured.", from_batch)
            return None

        system_prompt, _ = self.load_prompts()
        if not system_prompt:
            self._handle_occurrence_ai_error("Failed to load prompts.", from_batch)
            return None

        session_state = self.main_handler._session_manager.get_state()
        composer_args = {
            "system_prompt": system_prompt,
            "source_text": current_translation or "",
            "current_translation": current_translation or "",
            "original_text": original_text or "",
            "term": term,
            "old_translation": old_term_translation or "",
            "new_translation": new_term_translation or "",
            "expected_lines": max(1, (current_translation or "").count("\n") + 1),
            "session_state": session_state,
        }
        combined_system, user_prompt = self.main_handler.prompt_composer.compose_glossary_occurrence_update_request(**composer_args)

        if prompt_override and all(isinstance(s, str) and s.strip() for s in prompt_override):
            edited_system, edited_user = prompt_override
        else:
            edited = self.main_handler._maybe_edit_prompt(
                title="AI Glossary Update Prompt",
                system_prompt=combined_system,
                user_prompt=user_prompt,
                save_section="glossary_occurrence_update",
            )
            if edited is None:
                if from_batch and hasattr(dialog, "set_ai_busy"):
                    dialog.set_ai_busy(False)
                    dialog.set_batch_active(False)
                return None
            edited_system, edited_user = edited

        precomposed = [
            {"role": "system", "content": edited_system},
            {"role": "user", "content": edited_user},
        ]
        task_details = {
            "type": "glossary_occurrence_update",
            "composer_args": composer_args, "attempt": 1, "max_retries": 1,
            "occurrence": occurrence, "dialog": dialog, "from_batch": from_batch,
        }
        if not self.main_handler._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt, full_system_prompt=edited_system,
            user_prompt=edited_user, task_type="glossary_occurrence_batch_update",
        ):
            task_details["precomposed_prompt"] = precomposed

        self.main_handler.ui_handler.start_ai_operation("AI Glossary Update", model_name=self.main_handler.ai_lifecycle_manager._active_model_name)
        self.main_handler.ai_lifecycle_manager.run_ai_task(provider, task_details)
        return edited_system, edited_user

    # ── Occurrence AI: batch ──────────────────────────────────────────────

    def _start_ai_occurrence_batch(self, occurrences: List[GlossaryOccurrence]) -> None:
        if not occurrences:
            QMessageBox.information(self.mw, "AI Update", "No occurrences to process.")
            return
        if not self.translation_update_dialog or not self._current_translation_entry:
            return
        dialog = self.translation_update_dialog
        dialog.set_batch_active(True)
        dialog.set_ai_busy(True)
        started = self.request_glossary_occurrence_batch_update(
            occurrences=occurrences,
            term=self._current_translation_entry.original,
            old_term_translation=self._previous_translation_value or "",
            new_term_translation=self._current_translation_entry.translation,
            dialog=dialog,
        )
        if not started:
            dialog.set_ai_busy(False)
            dialog.set_batch_active(False)
        self._pending_ai_occurrences = []
        self._batch_prompt_override = None

    def _resume_ai_occurrence_batch(self) -> None:
        if not self._pending_ai_occurrences:
            if self.translation_update_dialog:
                self.translation_update_dialog.set_ai_busy(False)
                self.translation_update_dialog.set_batch_active(False)
            return
        next_occ = self._pending_ai_occurrences.pop(0)
        self._request_ai_occurrence_update(next_occ, from_batch=True)

    def request_glossary_occurrence_batch_update(
        self,
        *,
        occurrences: List[GlossaryOccurrence],
        term: str,
        old_term_translation: str,
        new_term_translation: str,
        dialog,
    ) -> bool:
        if not occurrences:
            self._handle_occurrence_ai_error("No occurrences to process.", True)
            return False

        provider = self.main_handler.ai_lifecycle_manager._prepare_provider()
        if not provider:
            return False

        system_prompt, _ = self.load_prompts()
        if not system_prompt:
            self._handle_occurrence_ai_error("Failed to load prompts.", True)
            return False

        session_state = self.main_handler._session_manager.get_state()
        batch_items = []
        expected_lines_by_id: Dict[str, int] = {}
        occurrence_metadata = []
        occurrence_lookup: Dict[str, object] = {}

        for index, occurrence in enumerate(occurrences):
            occ_id = str(index)
            original_text = self._get_occurrence_original_text(occurrence) or ""
            current_translation = self._get_occurrence_translation_text(occurrence) or ""
            expected = max(1, current_translation.count("\n") + 1)
            expected_lines_by_id[occ_id] = expected
            batch_items.append({
                "id": occ_id,
                "block_index": occurrence.block_idx, "string_index": occurrence.string_idx,
                "line_index": occurrence.line_idx + 1,
                "original_text": original_text, "current_translation": current_translation,
                "expected_lines": expected,
            })
            occurrence_metadata.append({"id": occ_id, "occurrence": occurrence})
            occurrence_lookup[occ_id] = occurrence

        combined_system, user_prompt = self.main_handler.prompt_composer.compose_glossary_occurrence_batch_request(
            system_prompt=system_prompt, term=term,
            old_translation=old_term_translation, new_translation=new_term_translation,
            batch_items=batch_items, session_state=session_state,
        )

        edited = self.main_handler._maybe_edit_prompt(
            title="AI Glossary Batch Update Prompt",
            system_prompt=combined_system, user_prompt=user_prompt,
            save_section="glossary_occurrence_update",
        )
        if edited is None:
            return False
        edited_system, edited_user = edited

        precomposed = [
            {"role": "system", "content": edited_system},
            {"role": "user", "content": edited_user},
        ]
        task_details = {
            "type": "glossary_occurrence_batch_update",
            "composer_args": {"system_prompt": edited_system, "user_prompt": edited_user, "batch_items": batch_items},
            "attempt": 1, "max_retries": 1, "dialog": dialog,
            "occurrence_metadata": occurrence_metadata,
            "occurrence_lookup": occurrence_lookup,
            "expected_lines": expected_lines_by_id,
            "from_batch": True,
        }
        if not self.main_handler._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt, full_system_prompt=edited_system,
            user_prompt=edited_user, task_type="glossary_occurrence_batch_update",
        ):
            task_details["precomposed_prompt"] = precomposed

        self.main_handler.ui_handler.start_ai_operation("AI Glossary Update (All)", model_name=self.main_handler.ai_lifecycle_manager._active_model_name)
        self.main_handler.ai_lifecycle_manager.run_ai_task(provider, task_details)
        return True

    # ── Occurrence AI: result handlers ────────────────────────────────────

    def _handle_occurrence_ai_result(self, *, occurrence, updated_translation, from_batch) -> None:
        dialog = self.translation_update_dialog
        if dialog:
            dialog.on_ai_result(occurrence, updated_translation)
            if from_batch:
                if self._pending_ai_occurrences:
                    self._resume_ai_occurrence_batch()
                else:
                    dialog.set_ai_busy(False)
                    dialog.set_batch_active(False)
                    self._batch_prompt_override = None
            else:
                dialog.set_ai_busy(False)
                dialog.set_batch_active(False)
                self._pending_ai_occurrences = []
                self._batch_prompt_override = None
        else:
            if occurrence:
                self._apply_occurrence_translation(occurrence, updated_translation)
            self._pending_ai_occurrences = []
            self._batch_prompt_override = None

        if occurrence and self.mw.statusBar:
            self.mw.statusBar.showMessage(
                f"AI updated translation for block {occurrence.block_idx}, string {occurrence.string_idx}", 4000
            )

    def _handle_occurrence_batch_success(self, *, results, context) -> None:
        dialog = self.translation_update_dialog
        occurrence_lookup = context.get("occurrence_lookup") or {}
        applied_count = 0
        for occ_id, occurrence in occurrence_lookup.items():
            if not isinstance(occurrence, GlossaryOccurrence):
                continue
            new_translation = results.get(occ_id)
            if new_translation is None:
                continue
            if dialog:
                dialog.on_ai_result(occurrence, new_translation)
            else:
                self._apply_occurrence_translation(occurrence, new_translation)
            applied_count += 1

        if dialog:
            dialog.set_ai_busy(False)
            dialog.set_batch_active(False)
        if applied_count and self.mw.statusBar:
            self.mw.statusBar.showMessage(f"AI updated {applied_count} occurrence(s).", 4000)
        self._pending_ai_occurrences = []
        self._batch_prompt_override = None

    def _handle_occurrence_ai_error(self, message: str, from_batch: bool) -> None:
        dialog = self.translation_update_dialog
        if dialog:
            dialog.on_ai_error(message)
        else:
            QMessageBox.warning(self.mw, "AI Update", message or "AI request failed.")
            if self.mw.statusBar:
                self.mw.statusBar.showMessage("AI glossary update failed.", 4000)
        self._pending_ai_occurrences = []
        self._batch_prompt_override = None

    def _handle_glossary_occurrence_update_success(self, response, context: dict) -> None:
        from_batch = context.get("from_batch", False)
        occurrence = context.get("occurrence")
        composer_args = context.get("composer_args") or {}

        self.main_handler.ui_handler.finish_ai_operation()
        cleaned = self.main_handler.ai_lifecycle_manager._clean_model_output(response)
        try:
            payload = json.loads(cleaned) if cleaned else {}
        except json.JSONDecodeError as exc:
            self._handle_occurrence_ai_error(f"Failed to parse AI response: {exc}", from_batch)
            return

        translation_value = payload.get("translation") if isinstance(payload, dict) else None
        if not isinstance(translation_value, str):
            self._handle_occurrence_ai_error("AI response missing string 'translation' field.", from_batch)
            return

        trimmed = self.main_handler.ai_lifecycle_manager._trim_trailing_whitespace_from_lines(translation_value)
        expected_lines = composer_args.get("expected_lines") if isinstance(composer_args, dict) else None
        if isinstance(expected_lines, int) and expected_lines > 0:
            actual = trimmed.count("\n") + 1
            if actual != expected_lines:
                self._handle_occurrence_ai_error(
                    f"AI response returned {actual} lines (expected {expected_lines}).", from_batch
                )
                return

        if occurrence is None:
            self._handle_occurrence_ai_error("Glossary update is missing occurrence context.", from_batch)
            return

        self.main_handler.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned, response=response)
        self._handle_occurrence_ai_result(occurrence=occurrence, updated_translation=trimmed, from_batch=from_batch)
        log_debug("Glossary AI occurrence update validated and applied.")

    def _handle_glossary_occurrence_batch_success(self, response, context: dict) -> None:
        from_batch = context.get("from_batch", True)
        expected_lines = context.get("expected_lines") or {}
        occurrence_lookup = context.get("occurrence_lookup") or {}

        self.main_handler.ui_handler.finish_ai_operation()
        cleaned = self.main_handler.ai_lifecycle_manager._clean_model_output(response)
        try:
            payload = json.loads(cleaned) if cleaned else {}
        except json.JSONDecodeError as exc:
            self._handle_occurrence_ai_error(f"Failed to parse AI response: {exc}", from_batch)
            return

        updates = None
        if isinstance(payload, dict):
            updates = payload.get("occurrences") or payload.get("translations") or payload.get("updated_translations")
        if not isinstance(updates, list):
            self._handle_occurrence_ai_error("AI response missing 'occurrences' array.", from_batch)
            return

        results: Dict[str, str] = {}
        for item in updates:
            if not isinstance(item, dict):
                continue
            occ_id = item.get("id") or item.get("occurrence_id")
            translation_value = item.get("translation")
            if occ_id is None or not isinstance(translation_value, str):
                continue
            occ_id = str(occ_id)
            trimmed = self.main_handler.ai_lifecycle_manager._trim_trailing_whitespace_from_lines(translation_value)
            expected = expected_lines.get(occ_id)
            if isinstance(expected, int) and expected > 0:
                actual = trimmed.count("\n") + 1
                if actual != expected:
                    self._handle_occurrence_ai_error(
                        f"AI response for occurrence {occ_id} returned {actual} lines (expected {expected}).", from_batch
                    )
                    return
            results[occ_id] = trimmed

        missing = [k for k in occurrence_lookup if k not in results]
        if missing:
            self._handle_occurrence_ai_error(
                f"AI response missing translations for occurrences: {', '.join(missing)}.", from_batch
            )
            return

        self.main_handler.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned, response=response)

        if hasattr(self.mw, "undo_manager"):
            self.mw.undo_manager.begin_group()
        self._handle_occurrence_batch_success(results=results, context=context)
        if hasattr(self.mw, "undo_manager"):
            self.mw.undo_manager.end_group("GLOSSARY_UPDATE")

    def request_glossary_notes_variation(
        self,
        *,
        term: str,
        translation: str,
        current_notes: str,
        context_line: Optional[str],
        dialog,
    ) -> bool:
        provider = self.main_handler.ai_lifecycle_manager._prepare_provider()
        if not provider:
            return False

        system_prompt, _ = self.load_prompts()
        if not system_prompt:
            return False

        session_state = self.main_handler._session_manager.get_state()
        source_sections = [f"Term: {term}", f"Translation: {translation or '[empty]'}"]
        if context_line:
            source_sections.append(f"Context: {context_line}")
        source_text = "\n".join(source_sections)

        composer_args = {
            "system_prompt": system_prompt,
            "source_text": source_text,
            "block_idx": None, "string_idx": None,
            "expected_lines": max(1, (current_notes or "").count("\n") + 1),
            "current_translation": current_notes or "",
            "mode_description": "glossary_notes",
            "request_type": "glossary_notes_variation",
            "session_state": session_state,
        }
        combined_system, user_prompt = self.main_handler.prompt_composer.compose_variation_request(**composer_args)
        edited = self.main_handler._maybe_edit_prompt(
            title="AI Glossary Notes Prompt",
            system_prompt=combined_system, user_prompt=user_prompt,
        )
        if edited is None:
            return False
        edited_system, edited_user = edited

        precomposed = [
            {"role": "system", "content": edited_system},
            {"role": "user", "content": edited_user},
        ]
        task_details = {
            "type": "glossary_notes_variation",
            "composer_args": composer_args, "attempt": 1, "max_retries": 1,
            "dialog": dialog, "term": term, "translation": translation, "current_notes": current_notes,
        }
        if not self.main_handler._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt, full_system_prompt=edited_system,
            user_prompt=edited_user, task_type="glossary_notes_variation",
        ):
            task_details["precomposed_prompt"] = precomposed

        self.main_handler.ui_handler.start_ai_operation("AI Glossary Notes", model_name=self.main_handler.ai_lifecycle_manager._active_model_name)
        self.main_handler.ai_lifecycle_manager.run_ai_task(provider, task_details)
        return True
