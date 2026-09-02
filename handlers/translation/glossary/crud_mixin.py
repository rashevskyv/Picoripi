from typing import Optional

from PyQt6.QtWidgets import QMessageBox

from core.glossary_manager import GlossaryOccurrence
from core.i18n import tr


class CrudMixin:
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

