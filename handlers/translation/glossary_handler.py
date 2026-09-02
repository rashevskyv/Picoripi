# Refactored: GlossaryHandler is now a thin facade delegating to:
#   - GlossaryPromptManager      (prompt I/O and caching)
#   - GlossaryOccurrenceUpdater  (AI retranslation of occurrences)
#   - components/GlossaryEditDialog (entry edit UI)

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from PyQt6.QtWidgets import (QMessageBox, QDialog, QVBoxLayout, QCheckBox, QLineEdit, QLabel, QScrollArea, QWidget, QDialogButtonBox, QProgressDialog)
from PyQt6.QtGui import (QAction)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from .base_translation_handler import BaseTranslationHandler
from .glossary_prompt_manager import GlossaryPromptManager
from .glossary_occurrence_updater import GlossaryOccurrenceUpdater
from core.glossary_manager import GlossaryEntry, GlossaryManager, GlossaryOccurrence
from core.speaker_alias_merge import (
    is_applyable_speaker_alias,
    load_speaker_aliases,
    split_shared_speaker_names,
)
from core.speaker_resolution import build_speaker_pool
from components.glossary_dialog import GlossaryDialog
from components.glossary_edit_dialog import GlossaryEditDialog
from utils.logging_utils import log_debug
from core.i18n import tr


class CategorySelectionDialog(QDialog):
    """Dialog for choosing and adding categories for glossary AI classification."""
    def __init__(self, parent, categories: List[str]):
        """Initialize a new instance."""
        super().__init__(parent)
        self.setWindowTitle(tr('Choose Glossary Categories'))
        self.resize(360, 400)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr('Select categories to organize your glossary:'), self))
        
        # Scroll area for checkboxes
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        self.checkboxes = []
        for cat in categories:
            cb = QCheckBox(cat, self)
            cb.setChecked(True)
            scroll_layout.addWidget(cb)
            self.checkboxes.append(cb)
            
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)
        
        # Custom category input
        layout.addWidget(QLabel(tr('Add custom categories (comma-separated):'), self))
        self.custom_input = QLineEdit(self)
        self.custom_input.setPlaceholderText(tr('e.g. Items, Weapons, Spells'))
        layout.addWidget(self.custom_input)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def get_selected_categories(self) -> List[str]:
        """Get the selected categories."""
        selected = [cb.text() for cb in self.checkboxes if cb.isChecked()]
        custom_text = self.custom_input.text().strip()
        if custom_text:
            for item in custom_text.split(","):
                clean_item = item.strip()
                if clean_item and clean_item not in selected:
                    selected.append(clean_item)
        return selected


class GlossaryOccurrenceWorker(QThread):
    """Glossary occurrence worker implementation."""
    finished_with_result = pyqtSignal(dict)

    def __init__(self, glossary_manager: GlossaryManager, data_source: list, parent: Optional[Any] = None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.glossary_manager = glossary_manager
        self.data_source = data_source

    def run(self):
        """Run."""
        try:
            occurrence_map = self.glossary_manager.build_occurrence_index(
                self.data_source,
                is_cancelled=self.isInterruptionRequested
            )
            if self.isInterruptionRequested():
                return
            self.finished_with_result.emit(occurrence_map)
        except Exception as e:
            from utils.logging_utils import log_error
            log_error(f"GlossaryOccurrenceWorker failed: {e}", exc_info=True)
            if not self.isInterruptionRequested():
                self.finished_with_result.emit({})


class GlossaryHandler(BaseTranslationHandler):
    """Handler for glossary operations."""

    def __init__(self, main_handler):
        """Initialize a new instance."""
        super().__init__(main_handler)
        self.glossary_manager = GlossaryManager()
        self._open_glossary_action: Optional[QAction] = None
        self.dialog: Optional[GlossaryDialog] = None
        # Snapshot of (original, translation) pairs taken when the dialog opens,
        # so closing it only rebuilds the virtual folders if a name actually changed.
        self._glossary_signature_on_open: Optional[tuple] = None

        # Delegates
        self._prompt_manager = GlossaryPromptManager(self.mw, main_handler, self.glossary_manager)
        self._occurrence_updater = GlossaryOccurrenceUpdater(self)



    # ── Public prompt manager proxy (used by TranslationHandler) ─────────

    @property
    def _current_prompts_path(self) -> Optional[Path]:
        """Internal helper to current prompts path."""
        return self._prompt_manager.current_prompts_path

    @property
    def translation_update_dialog(self):
        """Translation update dialog."""
        return self._occurrence_updater.translation_update_dialog

    @translation_update_dialog.setter
    def translation_update_dialog(self, value):
        """Translation update dialog."""
        self._occurrence_updater.translation_update_dialog = value

    def load_prompts(self) -> Tuple[Optional[str], Optional[str]]:
        """Load prompts."""
        return self._prompt_manager.load_prompts()

    def bind_glossary_for_write(self):
        """Bind the glossary to the project file, creating it when absent."""
        return self._prompt_manager.bind_glossary_for_write()

    def save_prompt_section(self, section: str, field: str, value: str) -> bool:
        """Save prompt section."""
        return self._prompt_manager.save_prompt_section(section, field, value)

    def _get_glossary_prompt_template(self) -> Tuple[str, Optional[Path]]:
        """Internal helper to get the glossary prompt template."""
        return self._prompt_manager.get_glossary_prompt_template()

    def _update_glossary_highlighting(self) -> None:
        """Internal helper to update the glossary highlighting."""
        self._prompt_manager._update_glossary_highlighting()

    def _ensure_glossary_loaded(self, *, glossary_text, plugin_name, glossary_path) -> None:
        """Internal helper to ensure glossary loaded."""
        self._prompt_manager._ensure_glossary_loaded(
            glossary_text=glossary_text, plugin_name=plugin_name, glossary_path=glossary_path
        )

    # ── Occurrence updater proxy (used by TranslationHandler success handlers) ──

    def request_glossary_occurrence_update(self, **kwargs):
        """Request glossary occurrence update."""
        return self._occurrence_updater.request_glossary_occurrence_update(**kwargs)

    def request_glossary_occurrence_batch_update(self, **kwargs):
        """Request glossary occurrence batch update."""
        return self._occurrence_updater.request_glossary_occurrence_batch_update(**kwargs)

    def request_glossary_notes_variation(self, **kwargs):
        """Request glossary notes variation."""
        return self._occurrence_updater.request_glossary_notes_variation(**kwargs)

    def _handle_occurrence_ai_result(self, **kwargs):
        """Internal helper to handle occurrence ai result."""
        return self._occurrence_updater.handle_occurrence_ai_result(**kwargs)

    def _handle_occurrence_batch_success(self, **kwargs):
        """Internal helper to handle occurrence batch success."""
        return self._occurrence_updater.handle_occurrence_batch_success(**kwargs)

    def _handle_occurrence_ai_error(self, message, from_batch):
        """Internal helper to handle occurrence ai error."""
        return self._occurrence_updater._handle_occurrence_ai_error(message, from_batch)

    def _handle_glossary_occurrence_update_success(self, response, context):
        """Internal helper to handle glossary occurrence update success."""
        return self._occurrence_updater.handle_glossary_occurrence_update_success(response, context)

    def _handle_glossary_occurrence_batch_success(self, response, context):
        """Internal helper to handle glossary occurrence batch success."""
        return self._occurrence_updater.handle_glossary_occurrence_batch_success(response, context)

    # ── Menu / initialization ─────────────────────────────────────────────

    def install_menu_actions(self) -> None:
        """Install menu actions."""
        tools_menu = getattr(self.mw, "tools_menu", None)
        if not tools_menu:
            return
        if self._open_glossary_action is None:
            action = QAction(tr('Open Glossary...'), self.mw)
            action.setShortcut("Ctrl+G")
            action.setToolTip(tr('Open glossary and jump to occurrences (Ctrl+G)'))
            action.triggered.connect(self.show_glossary_dialog)
            tools_menu.addAction(action)
            self._open_glossary_action = action

        reset_action = getattr(self.main_handler, "_reset_session_action", None)
        if reset_action is None:
            reset_action = QAction(tr('AI Reset Translation Session'), self.mw)
            reset_action.setToolTip(tr('Reset the current AI translation session'))
            reset_action.triggered.connect(self.main_handler.reset_translation_session)
            tools_menu.addAction(reset_action)
            self.main_handler._reset_session_action = reset_action

    def initialize_glossary_highlighting(self) -> None:
        """Initialize glossary highlighting."""
        self._prompt_manager.initialize_highlighting()

    # ── Glossary dialog ───────────────────────────────────────────────────

    def _glossary_signature(self) -> tuple:
        """Order-independent snapshot of the name-affecting glossary fields.

        Only ``original`` and ``translation`` change speaker-folder labels, so
        notes-only edits (or merely viewing the glossary) leave this unchanged.
        """
        try:
            return tuple(sorted(
                (str(getattr(e, "original", "") or ""), str(getattr(e, "translation", "") or ""))
                for e in self.glossary_manager.get_entries()
            ))
        except Exception:
            return ()

    def _on_glossary_dialog_closed(self):
        """Internal helper to handle the glossary dialog closed event."""
        self.dialog = None
        log_debug("Glossary dialog closed and reference cleared.")
        # A changed translation renames speaker folders — but only rebuild them
        # when a name actually changed, not on a view-only visit.
        changed = self._glossary_signature() != self._glossary_signature_on_open
        self._glossary_signature_on_open = None
        if not changed:
            return
        updater = getattr(getattr(self.mw, "ui_updater", None), "block_list_updater", None)
        refresh = getattr(updater, "refresh_virtual_folder_labels", None)
        if callable(refresh):
            try:
                refresh()
            except Exception as exc:
                log_debug(f"Glossary close: folder label refresh failed: {exc}")

    def show_glossary_dialog(self, initial_term: Optional[str] = None) -> None:
        """Show glossary dialog."""
        if self.dialog and self.dialog.isVisible():
            if initial_term and hasattr(self.dialog, "focus_term"):
                self.dialog.focus_term(initial_term)
            self.dialog.raise_()
            self.dialog.activateWindow()
            return

        system_prompt, glossary_text = self.load_prompts()
        if system_prompt is None:
            return

        data_source = self.mw.data_store.data
        if not isinstance(data_source, list):
            QMessageBox.information(self.mw, tr('Glossary'), tr('No data is loaded for analysis.'))
            return

        raw_pool = build_speaker_pool(self.mw, raw=True)
        self.glossary_manager.bind_project_rows(
            getattr(self.mw, "data_store", None),
            getattr(self.mw, "current_game_rules", None),
            speaker_aliases=self._load_speaker_aliases(),
            speaker_pool=raw_pool,
        )
        # Prepare and run GlossaryOccurrenceWorker with QProgressDialog
        progress_dialog = QProgressDialog("Building glossary occurrence index...", "Cancel", 0, 100, self.mw)
        progress_dialog.setWindowTitle(tr('Please Wait'))
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)

        worker = GlossaryOccurrenceWorker(self.glossary_manager, data_source, parent=self.mw)

        self.glossary_progress = progress_dialog
        self.glossary_worker = worker

        # Connect Cancel button to worker requestInterruption
        progress_dialog.canceled.connect(worker.requestInterruption)

        def on_finished(occurrence_map):
            """Handle the finished event."""
            if worker.isInterruptionRequested():
                return
            progress_dialog.close()
            
            self.glossary_progress = None
            self.glossary_worker = None

            entries = sorted(self.glossary_manager.get_entries(), key=lambda e: e.original.lower())
            self._glossary_signature_on_open = self._glossary_signature()
            self.dialog = GlossaryDialog(
                parent=self.mw, entries=entries, occurrence_map=occurrence_map,
                jump_callback=self._jump_to_occurrence,
                update_callback=self._handle_glossary_entry_update,
                delete_callback=self._handle_glossary_entry_delete,
                ai_variation_callback=self._handle_notes_variation_from_dialog,
                ai_classify_callback=self.classify_glossary_via_ai,
                build_callback=self._launch_glossary_build,
                clear_callback=self._handle_glossary_clear,
                global_replace_callback=self.global_replace_glossary,
                apply_speaker_name_callback=self._handle_apply_speaker_name,
                reassign_speaker_callback=self._handle_reassign_speaker_name,
                speaker_codes_callback=self._confirmed_speaker_codes,
                initial_term=initial_term,
                placeholder_speaker_callback=self._placeholder_speaker_callback(),
                discuss_variant_callback=self._handle_discuss_variants_from_dialog,
            )
            self.dialog.finished.connect(self._on_glossary_dialog_closed)
            self.dialog.show()

        def on_worker_finished():
            self.glossary_progress = None
            self.glossary_worker = None

        worker.finished_with_result.connect(on_finished)
        worker.finished.connect(on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        progress_dialog.show()

    def _handle_discuss_variants_from_dialog(self, entry: GlossaryEntry) -> None:
        """Open AI chat with term context to discuss proposed variants."""
        if not entry:
            return
        ai_chat_handler = getattr(self.mw, "ai_chat_handler", None)
        if not ai_chat_handler:
            return
        context_text = self.format_variant_discussion_context(entry)
        ai_chat_handler.show_chat_window(initial_text=context_text)

    def format_variant_discussion_context(self, entry: GlossaryEntry) -> str:
        """Format the exact context and constraints for discussing glossary variants in AI chat."""
        target_lang = getattr(self.mw, "target_language", "Ukrainian")
        if not isinstance(target_lang, str) or not target_lang.strip():
            target_lang = "Ukrainian"
        parts = [
            f"Term: {entry.original}",
            f"Target language: {target_lang}",
        ]
        if entry.notes:
            parts.append(f"Description:\n{entry.notes}")
        fragments = [
            str(getattr(f, "text", "") or str(f)).strip()
            for f in getattr(entry, "fragments", ()) or ()
            if str(getattr(f, "text", "") or str(f)).strip()
        ]
        if fragments:
            parts.append("Description fragments:\n- " + "\n- ".join(fragments))
        variants = getattr(entry, "translation_variants", ()) or ()
        if variants:
            variant_lines = []
            for v in variants:
                line = f"- {v.translation}"
                if getattr(v, "rationale", ""):
                    line += f" (Rationale: {v.rationale})"
                variant_lines.append(line)
            parts.append("Proposed translation candidates:\n" + "\n".join(variant_lines))
        parts.append(
            "Instruction:\n"
            "Analyze the term, description, and proposed translation candidates. "
            "You must recommend exactly one of the displayed candidates above, verbatim. "
            "Choose only from the existing candidates."
        )
        return "\n\n".join(parts)

    def _launch_glossary_build(self) -> None:
        """Open the build/translate launcher from inside the glossary dialog."""
        actions = getattr(self.mw, "actions", None)
        launcher = getattr(actions, "build_glossary_from_text", None)
        if callable(launcher):
            launcher()

    def _placeholder_speaker_callback(self):
        """Classify legacy glossary Character terms from the active game rules."""
        hook = getattr(getattr(self.mw, "current_game_rules", None), "is_placeholder_speaker", None)
        if not callable(hook):
            return None
        aliases = self._load_speaker_aliases()

        def is_placeholder(term: str) -> bool:
            term = str(term or "").strip()
            if not term or is_applyable_speaker_alias(aliases.get(term)):
                return False
            try:
                return bool(hook(term))
            except Exception as exc:
                log_debug(f"Glossary: is_placeholder_speaker failed: {exc}")
                return False

        return is_placeholder

    def _load_speaker_aliases(self) -> dict:
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None)
        try:
            return load_speaker_aliases(project_dir)
        except (TypeError, ValueError):
            return {}

    def _confirmed_speaker_codes(self, permanent_name: str) -> List[str]:
        """Game codes explicitly mapped to this permanent Character term.

        A shared voice counts for each named character: zrSPA assigned to
        ``SPRING ZORA #1 / SPRING ZORA #2`` belongs to both terms.
        """
        target = str(permanent_name or "").strip().casefold()
        if not target:
            return []
        aliases = self._load_speaker_aliases()
        return sorted(
            str(code).strip()
            for code, name in aliases.items()
            if is_applyable_speaker_alias(name)
            and target in {part.casefold() for part in split_shared_speaker_names(name)}
        )

    def _handle_reassign_speaker_name(
        self, speaker_code: str, current_name: str, permanent_name: str
    ) -> None:
        """Change an already-confirmed game code to another character name."""
        merge_handler = getattr(self.mw, "speaker_merge_handler", None)
        reassign = getattr(merge_handler, "reassign_name", None)
        if not callable(reassign):
            return
        if reassign(speaker_code, current_name, permanent_name) and self.dialog:
            self.dialog.focus_term(permanent_name)

    def refresh_open_dialog(self) -> None:
        """Reload the glossary dialog, if open, from the current manager state."""
        if not self.dialog or not self.dialog.isVisible():
            return
        data_source = getattr(self.mw.data_store, "data", None)
        raw_pool = build_speaker_pool(self.mw, raw=True)
        self.glossary_manager.bind_project_rows(
            getattr(self.mw, "data_store", None),
            getattr(self.mw, "current_game_rules", None),
            speaker_aliases=self._load_speaker_aliases(),
            speaker_pool=raw_pool,
        )
        # ponytail: rebuilds the index inline (same cost the open path pays behind
        # a progress dialog); move to GlossaryOccurrenceWorker if it starts to stutter.
        occurrence_map = (
            self.glossary_manager.build_occurrence_index(data_source)
            if isinstance(data_source, list)
            else self.glossary_manager.get_occurrence_map()
        )
        entries = sorted(self.glossary_manager.get_entries(), key=lambda e: e.original.lower())
        self.dialog.reload_data(entries, occurrence_map)

    def prepare_to_close(self) -> None:
        """Gracefully shutdown glossary occurrence worker if running."""
        from utils.thread_utils import safe_shutdown_thread
        if hasattr(self, 'glossary_worker') and self.glossary_worker:
            safe_shutdown_thread(self.glossary_worker, timeout_ms=2000)
            self.glossary_worker = None
        
        if hasattr(self, 'glossary_progress') and self.glossary_progress:
            try:
                self.glossary_progress.close()
            except Exception:
                pass
            self.glossary_progress = None

    # ── Entry CRUD ────────────────────────────────────────────────────────

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

    # ── Navigation & data helpers ─────────────────────────────────────────

    def _get_original_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Internal helper to get the original string."""
        return self.data_processor._get_string_from_source(
            block_idx, string_idx, getattr(self.mw.data_store, "data", None), "original_for_translation"
        )

    def _get_original_block(self, block_idx: int) -> List[str]:
        """Internal helper to get the original block."""
        data_source = getattr(self.mw.data_store, "data", None)
        if not isinstance(data_source, list) or not (0 <= block_idx < len(data_source)):
            return []
        block = data_source[block_idx]
        return [str(item) for item in block] if isinstance(block, list) else []

    def _jump_to_occurrence(self, occurrence: GlossaryOccurrence) -> None:
        """Internal helper to jump to occurrence."""
        if occurrence is None:
            return
        entry = {
            "block_idx": occurrence.block_idx,
            "string_idx": occurrence.string_idx,
            "line_idx": occurrence.line_idx,
        }
        self.main_handler.ui_handler._activate_entry(entry)
        self.mw.ui_updater.highlight_glossary_occurrence(occurrence)
        if self.mw.statusBar:
            self.mw.statusBar.showMessage(f"Navigated to glossary term: {occurrence.entry.original}", 4000)

    # ── Entry update/delete callbacks (called from GlossaryDialog) ────────

    def _handle_glossary_entry_update(
        self,
        original: str,
        translation: str,
        notes: str,
        profiled: Optional[bool] = None,
        status: Optional[str] = None,
        section: Optional[str] = None,
    ):
        """Internal helper to handle glossary entry update.

        ``status`` moves the entry along its lifecycle — the dialog passes
        ``confirmed`` when the user accepts a translation. Left as None the
        existing status is preserved.
        """
        previous_entry = self.glossary_manager.get_entry(original)
        previous_translation = previous_entry.translation if previous_entry else None

        old_index = self.glossary_manager._occurrence_index.copy() if self.glossary_manager._occurrence_index else {}

        update_kwargs = {"profiled": profiled, "status": status}
        if section is not None:
            update_kwargs["section"] = section
        if self.glossary_manager.update_entry(original, translation, notes, **update_kwargs):
            self.glossary_manager._occurrence_index = old_index
            data_source = getattr(self.mw.data_store, "data", [])
            updated_entry = self.glossary_manager.get_entry(original)
            self.glossary_manager.update_occurrences_for_entry(data_source, original, updated_entry)

            self.glossary_manager.save_to_disk()
            occurrence_map = self.glossary_manager.get_occurrence_map()
            entries = sorted(self.glossary_manager.get_entries(), key=lambda e: e.original.lower())
            self._update_glossary_highlighting()
            self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
            if self.mw.statusBar:
                self.mw.statusBar.showMessage(f"Glossary updated: {original}", 4000)

            if (
                updated_entry is not None
                and updated_entry.translation.strip() != ""
            ):
                occurrences = occurrence_map.get(updated_entry.original, [])
                if occurrences:
                    self._occurrence_updater.show_translation_update_dialog(
                        entry=updated_entry,
                        previous_translation=previous_translation or "",
                        occurrences=occurrences,
                    )
            return entries, occurrence_map
        return None

    def _handle_glossary_entry_delete(self, original: str):
        """Internal helper to handle glossary entry delete."""
        old_index = self.glossary_manager._occurrence_index.copy() if self.glossary_manager._occurrence_index else {}
        if self.glossary_manager.delete_entry(original):
            self.glossary_manager._occurrence_index = old_index
            data_source = getattr(self.mw.data_store, "data", [])
            self.glossary_manager.update_occurrences_for_entry(data_source, original, None)

            self.glossary_manager.save_to_disk()
            occurrence_map = self.glossary_manager.get_occurrence_map()
            entries = sorted(self.glossary_manager.get_entries(), key=lambda e: e.original.lower())
            self._update_glossary_highlighting()
            self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
            if self.mw.statusBar:
                self.mw.statusBar.showMessage(f"Glossary deleted: {original}", 4000)
            return entries, occurrence_map
        return None

    def _handle_glossary_clear(self):
        """Internal helper to handle clearing the whole glossary."""
        removed = self.glossary_manager.clear_all()
        if not removed:
            return None
        self.glossary_manager.save_to_disk()
        self._update_glossary_highlighting()
        self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
        if self.mw.statusBar:
            self.mw.statusBar.showMessage(f"Glossary cleared: {removed} entries removed", 4000)
        return [], {}

    def _handle_apply_speaker_name(self, code: str, permanent_name: str) -> None:
        """Route manual resolution of a provisional speaker identity through SpeakerMergeHandler."""
        code = (code or "").strip()
        permanent_name = (permanent_name or "").strip()
        if not code or not permanent_name or code == permanent_name:
            return

        merge_handler = getattr(self.mw, "speaker_merge_handler", None)
        if merge_handler is None:
            from handlers.speaker_merge_handler import SpeakerMergeHandler
            merge_handler = SpeakerMergeHandler(self.mw)

        success = bool(merge_handler.save_names({code: permanent_name}))
        if success and self.dialog and hasattr(self.dialog, "focus_term"):
            self.dialog.focus_term(permanent_name)

    # ── AI Glossary Classification ───────────────────────────────────────

    def classify_glossary_via_ai(self) -> None:
        """Classify glossary via ai."""
        entries = self.glossary_manager.get_entries()
        if not entries:
            QMessageBox.information(self.mw, tr('Glossary'), tr('No glossary entries to classify.'))
            return

        provider = self.mw.translation_handler.ai_lifecycle_manager._prepare_provider()
        if not provider:
            return

        # 1. Start Stage 1: Ask AI to suggest categories
        terms_list = "\n".join(f"- {e.original} -> {e.translation}" for e in entries[:150]) # limit to 150 for safety
        
        system_prompt = (
            "You are an expert game translation director. Your task is to analyze a list of glossary terms "
            "and suggest a set of 4 to 7 highly relevant thematic categories (such as 'Characters', 'Items', "
            "'Locations', 'Magic', 'Other') to organize them."
        )
        user_prompt = f"""
Analyze the following list of glossary terms:
{terms_list}

Suggest 4 to 7 thematic categories to organize these terms. Common categories include: "Characters", "Items", "Locations", "Magic", "Other".
Return the response STRICTLY as a valid JSON list of strings (e.g., ["Characters", "Items", "Locations", "Magic", "Other"]).
Do not write any markdown formatting like ```json, just output raw JSON text.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        task_details = {
            "type": "classify_suggest_types",
            "precomposed_prompt": messages,
            "attempt": 1,
            "max_retries": 1,
            "dialog_steps": ["Analyzing glossary terms...", "Choosing categories...", "Classifying terms...", "Finished!"],
            "entries": entries
        }
        
        self.main_handler.ui_handler.start_ai_operation("AI Glossary Analyze", model_name=self.main_handler.ai_lifecycle_manager._active_model_name)
        self.main_handler.ai_lifecycle_manager.run_ai_task(provider, task_details)

    def _handle_classify_suggest_success(self, response, context: dict) -> None:
        """Internal helper to handle classify suggest success."""
        self.main_handler.ui_handler.finish_ai_operation()
        cleaned = self.mw.translation_handler.ai_lifecycle_manager._clean_model_output(response, expect_json=True)
        
        try:
            suggested_categories = json.loads(cleaned)
            if not isinstance(suggested_categories, list):
                suggested_categories = ["Characters", "Items", "Locations", "Magic", "Other"]
        except Exception:
            suggested_categories = ["Characters", "Items", "Locations", "Magic", "Other"]
            
        # Show Category Selection Dialog
        dialog = CategorySelectionDialog(self.dialog, suggested_categories)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        selected_categories = dialog.get_selected_categories()
        if not selected_categories:
            QMessageBox.information(self.dialog, tr('Glossary'), tr('No categories selected. Operation cancelled.'))
            return
            
        # 2. Start Stage 2: Classify terms into selected categories
        provider = self.mw.translation_handler.ai_lifecycle_manager._prepare_provider()
        if not provider:
            return
            
        entries = context.get("entries", [])
        terms_data = [{"original": e.original, "translation": e.translation, "notes": e.notes} for e in entries]
        terms_json = json.dumps(terms_data, ensure_ascii=False)
        categories_str = ", ".join(f'"{c}"' for c in selected_categories)
        
        system_prompt = (
            "You are an expert game translation director. Your task is to classify a list of glossary terms "
            f"into the following categories: {categories_str}."
        )
        user_prompt = f"""
Classify each of the following glossary terms into exactly one of these categories: {categories_str}.
If a term fits multiple categories, assign it to the most relevant one. If it doesn't fit any of the specific categories, assign it to "Other".

Glossary terms to classify:
{terms_json}

Respond STRICTLY in JSON format as a dictionary where the keys are the original terms and the values are their assigned category from the list.
Do not write any markdown code blocks (like ```json), just output the raw JSON dictionary.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        task_details = {
            "type": "classify_apply",
            "precomposed_prompt": messages,
            "attempt": 1,
            "max_retries": 1,
            "dialog_steps": ["Analyzing glossary terms...", "Choosing categories...", "Classifying terms...", "Finished!"],
            "entries": entries,
            "selected_categories": selected_categories
        }
        
        self.main_handler.ui_handler.start_ai_operation("AI Glossary Classify", model_name=self.main_handler.ai_lifecycle_manager._active_model_name)
        self.main_handler.ai_lifecycle_manager.run_ai_task(provider, task_details)

    def _handle_classify_apply_success(self, response, context: dict) -> None:
        """Internal helper to handle classify apply success."""
        self.main_handler.ui_handler.finish_ai_operation()
        cleaned = self.mw.translation_handler.ai_lifecycle_manager._clean_model_output(response, expect_json=True)
        
        try:
            classification_map = json.loads(cleaned)
        except Exception as e:
            QMessageBox.warning(self.dialog, tr('AI Error'), f"Failed to parse AI classification: {e}")
            return
            
        if not isinstance(classification_map, dict):
            QMessageBox.warning(self.dialog, tr('AI Error'), tr('AI did not return a valid dictionary mapping terms to categories.'))
            return
            
        # Update glossary manager categories (sections)
        updated_count = 0
        entries = context.get("entries", [])
        for entry in entries:
            assigned_cat = classification_map.get(entry.original)
            if assigned_cat:
                self.glossary_manager.update_entry(
                    original=entry.original,
                    translation=entry.translation,
                    notes=entry.notes,
                    section=assigned_cat
                )
                updated_count += 1
                
        # Save updated glossary to disk
        self.glossary_manager.save_to_disk()
        self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()
        self._update_glossary_highlighting()
        
        # Hot-reload in glossary dialog if visible
        if self.dialog:
            new_entries = sorted(self.glossary_manager.get_entries(), key=lambda e: e.original.lower())
            occurrence_map = self.glossary_manager.get_occurrence_map()
            self.dialog.reload_data(new_entries, occurrence_map)
            
        QMessageBox.information(
            self.dialog if self.dialog else self.mw,
            tr('Success'),
            f"Successfully organized {updated_count} glossary terms into categories!"
        )

    def _handle_classify_error(self, error_message: str, context: dict) -> None:
        """Internal helper to handle classify error."""
        self.main_handler.ui_handler.finish_ai_operation()
        msg = error_message or "AI request failed."
        QMessageBox.warning(self.dialog if self.dialog else self.mw, tr('AI Error'), msg)

    def global_replace_glossary(self, find_word: str, replace_word: str) -> None:
        # Build occurrence index BEFORE replacing so we know where old original terms were
        """Global replace glossary."""
        data_source = getattr(self.mw.data_store, "data", [])
        occurrence_map_before = self.glossary_manager.build_occurrence_index(data_source)

        modified_list = self.glossary_manager.global_replace(find_word, replace_word)
        if not modified_list:
            QMessageBox.information(
                self.dialog if self.dialog else self.mw,
                tr('Global Replace'),
                f"No occurrences of '{find_word}' found in the glossary."
            )
            return

        # Hot-reload in glossary dialog if visible
        if self.dialog:
            new_entries = sorted(self.glossary_manager.get_entries(), key=lambda e: e.original.lower())
            # Rebuild index on updated glossary to keep dialog occurrences in sync
            occurrence_map_after = self.glossary_manager.build_occurrence_index(data_source)
            self.dialog.reload_data(new_entries, occurrence_map_after)
            
        self._update_glossary_highlighting()
        self.main_handler._cached_glossary = self.glossary_manager.get_raw_text()

        # Filter and compile valid updates
        valid_updates = []
        for old_entry, previous_translation, updated_entry in modified_list:
            if previous_translation == updated_entry.translation:
                continue
            occurrences = occurrence_map_before.get(old_entry.original, [])
            filtered = [
                occ for occ in occurrences
                if self.data_processor.is_string_translated(occ.block_idx, occ.string_idx)
            ]
            if filtered:
                # Compile updated occurrences pointing to the new entry
                updated_occurrences = []
                for occ in filtered:
                    updated_occ = GlossaryOccurrence(
                        entry=updated_entry,
                        block_idx=occ.block_idx,
                        string_idx=occ.string_idx,
                        line_idx=occ.line_idx,
                        start=occ.start,
                        end=occ.end,
                        line_text=occ.line_text
                    )
                    updated_occurrences.append(updated_occ)
                
                valid_updates.append((updated_entry, previous_translation, updated_occurrences))

        if not valid_updates:
            if self.mw.statusBar:
                self.mw.statusBar.showMessage("Glossary replaced. No translated project occurrences need updating.", 4000)
            return

        # Sequential showing of update dialogs
        def show_next_update():
            """Show next update."""
            if not valid_updates:
                return
            entry, prev_trans, occs = valid_updates.pop(0)
            
            self._occurrence_updater.show_translation_update_dialog(
                entry=entry,
                previous_translation=prev_trans,
                occurrences=occs
            )
            
            if self._occurrence_updater.translation_update_dialog:
                self._occurrence_updater.translation_update_dialog.finished.connect(show_next_update)

        show_next_update()

