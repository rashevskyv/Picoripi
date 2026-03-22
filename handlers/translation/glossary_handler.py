# --- START OF FILE handlers/translation/glossary_handler.py ---
# Refactored: GlossaryHandler is now a thin facade delegating to:
#   - GlossaryPromptManager      (prompt I/O and caching)
#   - GlossaryOccurrenceUpdater  (AI retranslation of occurrences)
#   - components/GlossaryEditDialog (entry edit UI)

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt5.QtWidgets import QAction, QMessageBox, QDialog
from PyQt5.QtCore import Qt

from .base_translation_handler import BaseTranslationHandler
from .glossary_prompt_manager import GlossaryPromptManager
from .glossary_occurrence_updater import GlossaryOccurrenceUpdater
from core.glossary_manager import GlossaryEntry, GlossaryManager, GlossaryOccurrence
from components.glossary_dialog import GlossaryDialog
from components.glossary_edit_dialog import GlossaryEditDialog
from utils.logging_utils import log_debug


class GlossaryHandler(BaseTranslationHandler):

    def __init__(self, main_handler):
        super().__init__(main_handler)
        self.glossary_manager = GlossaryManager()
        self._open_glossary_action: Optional[QAction] = None
        self.dialog: Optional[GlossaryDialog] = None

        # Delegates
        self._prompt_manager = GlossaryPromptManager(self.mw, main_handler, self.glossary_manager)
        self._occurrence_updater = GlossaryOccurrenceUpdater(self)

    # ── Public prompt manager proxy (used by TranslationHandler) ─────────

    @property
    def _current_prompts_path(self) -> Optional[Path]:
        return self._prompt_manager.current_prompts_path

    @property
    def translation_update_dialog(self):
        return self._occurrence_updater.translation_update_dialog

    @translation_update_dialog.setter
    def translation_update_dialog(self, value):
        self._occurrence_updater.translation_update_dialog = value

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

    # ── Occurrence updater proxy (used by TranslationHandler success handlers) ──

    def request_glossary_occurrence_update(self, **kwargs):
        return self._occurrence_updater.request_glossary_occurrence_update(**kwargs)

    def request_glossary_occurrence_batch_update(self, **kwargs):
        return self._occurrence_updater.request_glossary_occurrence_batch_update(**kwargs)

    def request_glossary_notes_variation(self, **kwargs):
        return self._occurrence_updater.request_glossary_notes_variation(**kwargs)

    def _handle_occurrence_ai_result(self, **kwargs):
        return self._occurrence_updater.handle_occurrence_ai_result(**kwargs)

    def _handle_occurrence_batch_success(self, **kwargs):
        return self._occurrence_updater.handle_occurrence_batch_success(**kwargs)

    def _handle_occurrence_ai_error(self, message, from_batch):
        return self._occurrence_updater._handle_occurrence_ai_error(message, from_batch)

    def _handle_glossary_occurrence_update_success(self, response, context):
        return self._occurrence_updater.handle_glossary_occurrence_update_success(response, context)

    def _handle_glossary_occurrence_batch_success(self, response, context):
        return self._occurrence_updater.handle_glossary_occurrence_batch_success(response, context)

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

    def add_glossary_entry(self, term: str, context: Optional[str] = None, translation: str = "") -> None:
        self.edit_glossary_entry(term, is_new=True, context=context, translation=translation)

    def edit_glossary_entry(self, term: str, is_new: bool = False, context: Optional[str] = None, translation: str = "") -> None:
        entry = self.glossary_manager.get_entry(term) if not is_new else None
        old_translation = entry.translation if entry else None
        
        # If we have an initial translation provided (e.g. from context menu)
        # we'll use it if the entry doesn't have one or if we are creating a new one.
        effective_translation = translation or (entry.translation if entry else "")

        dialog = self._create_edit_dialog(term, entry, context, initial_translation=effective_translation)
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
                self._occurrence_updater.show_translation_update_dialog(
                    entry=updated_entry, previous_translation=old_translation, occurrences=occurrences
                )

    def _create_edit_dialog(self, term: str, entry: Optional[GlossaryEntry], context: Optional[str], initial_translation: str = "") -> GlossaryEditDialog:
        dialog_ref: Dict[str, GlossaryEditDialog] = {}
        
        # Use initial_translation if provided, otherwise fallback to existing entry's translation
        translation_to_use = initial_translation or (entry.translation if entry else "")

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
            translation=translation_to_use,
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
        started = self._occurrence_updater.request_glossary_notes_variation(
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
                    self._occurrence_updater.show_translation_update_dialog(
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
