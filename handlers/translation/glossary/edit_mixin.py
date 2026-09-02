import json
from typing import Dict, Optional

from PyQt6.QtWidgets import QDialog, QMessageBox

from core.glossary_manager import GlossaryEntry
from components.glossary_edit_dialog import GlossaryEditDialog
from utils.logging_utils import log_debug
from core.i18n import tr


class EditMixin:
    def add_glossary_entry(self, term: str, context: Optional[str] = None, translation: str = "") -> None:
        """Add glossary entry."""
        self.edit_glossary_entry(term, is_new=True, context=context, translation=translation)

    def edit_glossary_entry(self, term: str, is_new: bool = False, context: Optional[str] = None, translation: str = "") -> None:
        """Edit glossary entry."""
        entry = self.glossary_manager.get_entry(term) if not is_new else None
        old_translation = entry.translation if entry else None
        
        # If we have an initial translation provided (e.g. from context menu)
        # we'll use it if the entry doesn't have one or if we are creating a new one.
        effective_translation = translation or (entry.translation if entry else "")

        dialog = self._create_edit_dialog(term, entry, context, initial_translation=effective_translation)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_translation, new_notes = dialog.get_values()
        
        old_index = self.glossary_manager._occurrence_index.copy() if self.glossary_manager._occurrence_index else {}

        if not new_translation:
            if entry and new_notes != entry.notes:
                if self.glossary_manager.update_entry(term, entry.translation, new_notes):
                    self.glossary_manager._occurrence_index = old_index
                    data_source = getattr(self.mw.data_store, "data", [])
                    updated_entry = self.glossary_manager.get_entry(term)
                    self.glossary_manager.update_occurrences_for_entry(data_source, term, updated_entry)

                    self.glossary_manager.save_to_disk()
                    self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
                    self._update_glossary_highlighting()
            return

        if is_new:
            updated_entry = self.glossary_manager.add_entry(term, new_translation, new_notes)
        else:
            updated_entry = self.glossary_manager.update_entry(term, new_translation, new_notes)

        self.glossary_manager._occurrence_index = old_index
        data_source = getattr(self.mw.data_store, "data", [])
        self.glossary_manager.update_occurrences_for_entry(data_source, term if not is_new else None, updated_entry)

        self.glossary_manager.save_to_disk()
        self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
        self._update_glossary_highlighting()

        if updated_entry and updated_entry.translation.strip() != "":
            occurrences = self.glossary_manager.get_occurrences_for(updated_entry)
            if occurrences:
                log_debug(f"Glossary: Showing update dialog for '{term}'.")
                self._occurrence_updater.show_translation_update_dialog(
                    entry=updated_entry, previous_translation=old_translation or "", occurrences=occurrences
                )


    def _create_edit_dialog(self, term: str, entry: Optional[GlossaryEntry], context: Optional[str], initial_translation: str = "") -> GlossaryEditDialog:
        """Internal helper to create edit dialog."""
        dialog_ref: Dict[str, GlossaryEditDialog] = {}
        
        # Use initial_translation if provided, otherwise fallback to existing entry's translation
        translation_to_use = initial_translation or (entry.translation if entry else "")

        def _ai_fill_wrapper() -> None:
            """Internal helper to ai fill wrapper."""
            d = dialog_ref.get("dialog")
            if d:
                self._ai_fill_glossary_entry(term, context, d)

        def _notes_variation_wrapper() -> None:
            """Internal helper to notes variation wrapper."""
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
        """Internal helper to ai fill glossary entry."""
        provider = self.main_handler._prepare_provider()
        if not provider:
            return

        template, _ = self._get_glossary_prompt_template()
        if not template:
            return

        target_lang = getattr(self.mw, 'target_language', 'Ukrainian')
        if not isinstance(target_lang, str):
            target_lang = 'Ukrainian'
        game_name = self.mw.current_game_rules.get_display_name() if self.mw.current_game_rules else "this game"
        system_prompt = template.replace("{{GAME_NAME}}", game_name)
        from utils.utils import resolve_target_language_prompt
        system_prompt = resolve_target_language_prompt(system_prompt, target_lang)

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
            force_prompt=self.main_handler._is_control_pressed(),
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
            task_details, base_system_prompt=edited_system, full_system_prompt=edited_system, user_prompt=edited_user, task_type="fill_glossary",
        ):
            task_details["precomposed_prompt"] = precomposed

        dialog.set_ai_busy(True)
        self.main_handler.ui_handler.start_ai_operation("AI Glossary Fill", model_name=self.main_handler.ai_lifecycle_manager._active_model_name)
        self.main_handler._run_ai_task(provider, task_details)

    def _handle_ai_fill_success(self, response, context: dict) -> None:
        """Internal helper to handle ai fill success."""
        self.main_handler.ui_handler.finish_ai_operation()
        dialog = context.get("dialog") if isinstance(context, dict) else None
        if not isinstance(dialog, GlossaryEditDialog):
            return
        dialog.set_ai_busy(False)

        cleaned = self.main_handler.ai_lifecycle_manager._clean_model_output(response, expect_json=True)
        translation_value = notes_value = None
        if cleaned:
            try:
                payload = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                log_debug(f"AI Glossary Fill: failed to parse response: {exc}")
                QMessageBox.warning(self.mw, tr('AI Glossary Fill'), tr('Could not parse AI response.'))
                return
            if isinstance(payload, dict):
                if "translation" in payload:
                    translation_value = str(payload.get("translation") or "").strip()
                if "notes" in payload:
                    notes_value = str(payload.get("notes") or "").strip()

        current_translation, current_notes = dialog.get_values()
        if translation_value is None and notes_value is None:
            QMessageBox.information(self.mw, tr('AI Glossary Fill'), tr('AI response did not include translation or notes.'))
            return

        new_translation = translation_value or current_translation
        new_notes = notes_value if notes_value is not None else current_notes
        dialog.set_values(new_translation, new_notes)
        self.main_handler._record_session_exchange(context=context, assistant_content=cleaned)

    def _handle_ai_fill_error(self, error_message: str, context: dict) -> None:
        """Internal helper to handle ai fill error."""
        dialog = context.get("dialog") if isinstance(context, dict) else None
        if isinstance(dialog, GlossaryEditDialog):
            dialog.set_ai_busy(False)
        msg = error_message or "AI request failed."
        QMessageBox.warning(self.mw, tr('AI Glossary Fill'), msg)

    # ── Notes variation ───────────────────────────────────────────────────

    def _set_notes_dialog_busy(self, dialog_obj, busy: bool) -> None:
        """Internal helper to set the notes dialog busy."""
        if not dialog_obj:
            return
        if hasattr(dialog_obj, "set_ai_busy"):
            dialog_obj.set_ai_busy(busy)
        elif hasattr(dialog_obj, "set_notes_variation_busy"):
            dialog_obj.set_notes_variation_busy(busy)

    def _start_glossary_notes_variation(self, *, term, translation, notes, context_line, target_dialog) -> None:
        """Internal helper to start glossary notes variation."""
        self._set_notes_dialog_busy(target_dialog, True)
        started = self._occurrence_updater.request_glossary_notes_variation(
            term=term, translation=translation, current_notes=notes,
            context_line=context_line, dialog=target_dialog,
        )
        if not started:
            self._set_notes_dialog_busy(target_dialog, False)

    def _handle_notes_variation_from_dialog(self, entry: GlossaryEntry) -> None:
        """Internal helper to handle notes variation from dialog."""
        if not entry or not self.dialog:
            return
        context_line: Optional[str] = None
        data_source = getattr(self.mw.data_store, "data", None)
        if isinstance(data_source, list):
            occurrence_map = self.glossary_manager.get_occurrence_map()
            if not occurrence_map:
                occurrence_map = self.glossary_manager.build_occurrence_index(data_source)
            occ_list = occurrence_map.get(entry.original, [])
            if occ_list:
                context_line = getattr(occ_list[0], "line_text", None)
        self._start_glossary_notes_variation(
            term=entry.original, translation=entry.translation or "",
            notes=entry.notes or "", context_line=context_line, target_dialog=self.dialog,
        )

    def _handle_glossary_notes_variation_success(self, response, context: dict) -> None:
        """Internal helper to handle glossary notes variation success."""
        self.main_handler.ui_handler.finish_ai_operation()
        cleaned = self.main_handler.ai_lifecycle_manager._clean_model_output(response, expect_json=True)
        self.main_handler.ai_lifecycle_manager._record_session_exchange(context=context, assistant_content=cleaned, response=response)

        dialog = context.get("dialog")
        self._set_notes_dialog_busy(dialog, False)

        variants = self.main_handler.ui_handler.parse_variation_payload(cleaned)
        if not variants:
            QMessageBox.information(self.mw, tr('AI Glossary Notes'), tr('Failed to parse variations from AI response.'))
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

