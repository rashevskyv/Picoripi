# handlers/translation/glossary_occurrence_updater.py
"""
Manages AI-driven retranslation of glossary term occurrences.

Handles both single and batch occurrence updates when a glossary term's
translation changes. Owns the GlossaryTranslationUpdateDialog lifecycle.
"""
import json
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt5.QtWidgets import QMessageBox

from core.glossary_manager import GlossaryEntry, GlossaryOccurrence
from components.glossary_translation_update_dialog import GlossaryTranslationUpdateDialog
from utils.logging_utils import log_debug


class GlossaryOccurrenceUpdater:
    """
    Extracted from GlossaryHandler. Encapsulates all logic for updating
    existing translations when a glossary term's translation is changed.
    """

    def __init__(self, glossary_handler) -> None:
        self._gh = glossary_handler  # parent GlossaryHandler

        # State
        self.translation_update_dialog: Optional[GlossaryTranslationUpdateDialog] = None
        self._pending_ai_occurrences: List[GlossaryOccurrence] = []
        self._current_translation_entry: Optional[GlossaryEntry] = None
        self._previous_translation_value: Optional[str] = None
        self._batch_prompt_override: Optional[Tuple[str, str]] = None

    # ── Convenience accessors ─────────────────────────────────────────────

    @property
    def _mw(self):
        return self._gh.mw

    @property
    def _main_handler(self):
        return self._gh.main_handler

    # ── Dialog lifecycle ──────────────────────────────────────────────────

    def show_translation_update_dialog(
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
            parent=self._mw,
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
        dialog.finished.connect(self._on_dialog_closed)
        dialog.show()
        self.translation_update_dialog = dialog

    def _on_dialog_closed(self, *_args) -> None:
        self.translation_update_dialog = None
        self._pending_ai_occurrences = []
        self._current_translation_entry = None
        self._previous_translation_value = None
        self._batch_prompt_override = None

    # ── Occurrence data helpers ───────────────────────────────────────────

    def _get_occurrence_original_text(self, occurrence: GlossaryOccurrence) -> str:
        return str(self._gh._get_original_string(occurrence.block_idx, occurrence.string_idx) or "")

    def _get_occurrence_translation_text(self, occurrence: GlossaryOccurrence) -> str:
        text, _ = self._main_handler.data_processor.get_current_string_text(
            occurrence.block_idx, occurrence.string_idx
        )
        return str(text or "")

    def _apply_occurrence_translation(self, occurrence: GlossaryOccurrence, new_text: str) -> None:
        self._main_handler.data_processor.update_edited_data(
            occurrence.block_idx, occurrence.string_idx, new_text
        )
        self._mw.ui_updater.populate_strings_for_block(occurrence.block_idx)
        if (self._mw.current_block_idx == occurrence.block_idx
                and self._mw.current_string_idx == occurrence.string_idx):
            self._mw.ui_updater.update_text_views()
        self._mw.ui_updater.update_block_item_text_with_problem_count(occurrence.block_idx)
        if self._mw.statusBar:
            self._mw.statusBar.showMessage(
                f"Updated translation for block {occurrence.block_idx}, string {occurrence.string_idx}", 3000
            )

    # ── Single occurrence AI update ───────────────────────────────────────

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
        provider = self._main_handler.ai_lifecycle_manager._prepare_provider()
        if not provider:
            self._handle_occurrence_ai_error("AI provider is not configured.", from_batch)
            return None

        system_prompt, _ = self._gh.load_prompts()
        if not system_prompt:
            self._handle_occurrence_ai_error("Failed to load prompts.", from_batch)
            return None

        session_state = self._main_handler._session_manager.get_state()
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
        combined_system, user_prompt = self._main_handler.prompt_composer.compose_glossary_occurrence_update_request(**composer_args)

        if prompt_override and all(isinstance(s, str) and s.strip() for s in prompt_override):
            edited_system, edited_user = prompt_override
        else:
            edited = self._main_handler._maybe_edit_prompt(
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
        if not self._main_handler._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt, full_system_prompt=edited_system,
            user_prompt=edited_user, task_type="glossary_occurrence_batch_update",
        ):
            task_details["precomposed_prompt"] = precomposed

        self._main_handler.ui_handler.start_ai_operation(
            "AI Glossary Update", model_name=self._main_handler.ai_lifecycle_manager._active_model_name
        )
        self._main_handler.ai_lifecycle_manager.run_ai_task(provider, task_details)
        return edited_system, edited_user

    # ── Batch occurrence AI update ────────────────────────────────────────

    def _start_ai_occurrence_batch(self, occurrences: List[GlossaryOccurrence]) -> None:
        if not occurrences:
            QMessageBox.information(self._mw, "AI Update", "No occurrences to process.")
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

        provider = self._main_handler.ai_lifecycle_manager._prepare_provider()
        if not provider:
            return False

        system_prompt, _ = self._gh.load_prompts()
        if not system_prompt:
            self._handle_occurrence_ai_error("Failed to load prompts.", True)
            return False

        session_state = self._main_handler._session_manager.get_state()
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

        combined_system, user_prompt = self._main_handler.prompt_composer.compose_glossary_occurrence_batch_request(
            system_prompt=system_prompt, term=term,
            old_translation=old_term_translation, new_translation=new_term_translation,
            batch_items=batch_items, session_state=session_state,
        )

        edited = self._main_handler._maybe_edit_prompt(
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
        if not self._main_handler._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt, full_system_prompt=edited_system,
            user_prompt=edited_user, task_type="glossary_occurrence_batch_update",
        ):
            task_details["precomposed_prompt"] = precomposed

        self._main_handler.ui_handler.start_ai_operation(
            "AI Glossary Update (All)", model_name=self._main_handler.ai_lifecycle_manager._active_model_name
        )
        self._main_handler.ai_lifecycle_manager.run_ai_task(provider, task_details)
        return True

    # ── AI response handlers ──────────────────────────────────────────────

    def handle_occurrence_ai_result(self, *, occurrence, updated_translation, from_batch) -> None:
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

        if occurrence and self._mw.statusBar:
            self._mw.statusBar.showMessage(
                f"AI updated translation for block {occurrence.block_idx}, string {occurrence.string_idx}", 4000
            )

    def handle_occurrence_batch_success(self, *, results, context) -> None:
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
        if applied_count and self._mw.statusBar:
            self._mw.statusBar.showMessage(f"AI updated {applied_count} occurrence(s).", 4000)
        self._pending_ai_occurrences = []
        self._batch_prompt_override = None

    def _handle_occurrence_ai_error(self, message: str, from_batch: bool) -> None:
        dialog = self.translation_update_dialog
        if dialog:
            dialog.on_ai_error(message)
        else:
            QMessageBox.warning(self._mw, "AI Update", message or "AI request failed.")
            if self._mw.statusBar:
                self._mw.statusBar.showMessage("AI glossary update failed.", 4000)
        self._pending_ai_occurrences = []
        self._batch_prompt_override = None

    def handle_glossary_occurrence_update_success(self, response, context: dict) -> None:
        from_batch = context.get("from_batch", False)
        occurrence = context.get("occurrence")
        composer_args = context.get("composer_args") or {}

        self._main_handler.ui_handler.finish_ai_operation()
        cleaned = self._main_handler.ai_lifecycle_manager._clean_model_output(response)
        try:
            payload = json.loads(cleaned) if cleaned else {}
        except json.JSONDecodeError as exc:
            self._handle_occurrence_ai_error(f"Failed to parse AI response: {exc}", from_batch)
            return

        translation_value = payload.get("translation") if isinstance(payload, dict) else None
        if not isinstance(translation_value, str):
            self._handle_occurrence_ai_error("AI response missing string 'translation' field.", from_batch)
            return

        trimmed = self._main_handler.ai_lifecycle_manager._trim_trailing_whitespace_from_lines(translation_value)
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

        self._main_handler.ai_lifecycle_manager._record_session_exchange(
            context=context, assistant_content=cleaned, response=response
        )
        self.handle_occurrence_ai_result(occurrence=occurrence, updated_translation=trimmed, from_batch=from_batch)
        log_debug("Glossary AI occurrence update validated and applied.")

    def handle_glossary_occurrence_batch_success(self, response, context: dict) -> None:
        from_batch = context.get("from_batch", True)
        expected_lines = context.get("expected_lines") or {}
        occurrence_lookup = context.get("occurrence_lookup") or {}

        self._main_handler.ui_handler.finish_ai_operation()
        cleaned = self._main_handler.ai_lifecycle_manager._clean_model_output(response)
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
            trimmed = self._main_handler.ai_lifecycle_manager._trim_trailing_whitespace_from_lines(translation_value)
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

        self._main_handler.ai_lifecycle_manager._record_session_exchange(
            context=context, assistant_content=cleaned, response=response
        )

        if hasattr(self._mw, "undo_manager"):
            self._mw.undo_manager.begin_group()
        self.handle_occurrence_batch_success(results=results, context=context)
        if hasattr(self._mw, "undo_manager"):
            self._mw.undo_manager.end_group("GLOSSARY_UPDATE")

    # ── Notes variation AI ────────────────────────────────────────────────

    def request_glossary_notes_variation(
        self,
        *,
        term: str,
        translation: str,
        current_notes: str,
        context_line: Optional[str],
        dialog,
    ) -> bool:
        provider = self._main_handler.ai_lifecycle_manager._prepare_provider()
        if not provider:
            return False

        system_prompt, _ = self._gh.load_prompts()
        if not system_prompt:
            return False

        session_state = self._main_handler._session_manager.get_state()
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
        combined_system, user_prompt = self._main_handler.prompt_composer.compose_variation_request(**composer_args)
        edited = self._main_handler._maybe_edit_prompt(
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
        if not self._main_handler._attach_session_to_task(
            task_details,
            base_system_prompt=system_prompt, full_system_prompt=edited_system,
            user_prompt=edited_user, task_type="glossary_notes_variation",
        ):
            task_details["precomposed_prompt"] = precomposed

        self._main_handler.ui_handler.start_ai_operation(
            "AI Glossary Notes", model_name=self._main_handler.ai_lifecycle_manager._active_model_name
        )
        self._main_handler.ai_lifecycle_manager.run_ai_task(provider, task_details)
        return True
