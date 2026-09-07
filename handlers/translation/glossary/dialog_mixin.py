from typing import List, Optional

from PyQt6.QtWidgets import QMessageBox, QProgressDialog
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

from core.speaker_resolution import build_speaker_pool
from components.glossary_dialog import GlossaryDialog
from handlers.translation.glossary.dialogs import GlossaryOccurrenceWorker
from core.glossary_manager import GlossaryOccurrence
from utils.logging_utils import log_debug
from core.i18n import tr


class DialogMixin:
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
                external_reference_callback=self._get_external_reference_url,
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

    def _get_external_reference_url(self, term: str) -> Optional[str]:
        """Look up external wiki or guide URL for ``term`` via the current plugin rules."""
        rules = getattr(self.mw, "current_game_rules", None)
        getter = getattr(rules, "get_external_reference_url", None)
        if callable(getter):
            try:
                return getter(term)
            except Exception:
                return None
        return None

    def _launch_glossary_build(self) -> None:
        """Open the build/translate launcher from inside the glossary dialog."""
        actions = getattr(self.mw, "actions", None)
        launcher = getattr(actions, "build_glossary_from_text", None)
        if callable(launcher):
            launcher()

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

