"""Speaker portrait selection, async persistence, and lifecycle."""
from __future__ import annotations

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from core.glossary_manager import GlossaryEntry
from core.i18n import tr


class SpeakerPhotoMixin:
    """Stage speaker photos and persist glossary snapshots in workers."""

    def _save_speaker_photo_async(
        self, entry: GlossaryEntry, photo: str, **entry_changes
    ) -> None:
        """Persist a portrait snapshot in a worker before changing manager state."""
        callback = getattr(self, "_speaker_photo_save_callback", None)
        if not callable(callback):
            QMessageBox.warning(self, tr("Photo not saved"), tr("Photo saving is unavailable."))
            return
        try:
            worker = callback(entry, photo, **entry_changes)
        except Exception as exc:
            QMessageBox.warning(self, tr("Photo not saved"), tr(str(exc)))
            return
        from PyQt6.QtCore import Qt
        self._speaker_photo_save_worker = worker
        self._photo_save_in_progress = True
        self._speaker_photo_label.setText(tr("Saving photo..."))
        self._update_editor_enabled_state()
        worker.saved.connect(self._speaker_photo_save_finished, Qt.ConnectionType.QueuedConnection)
        worker.start()

    def _speaker_photo_save_finished(self, revision: int, raw_json: str, error: str) -> None:
        worker = getattr(self, "_speaker_photo_save_worker", None)
        manager = getattr(worker, "manager", None) if worker is not None else None
        self._photo_save_in_progress = False
        if error or manager is None or not manager.install_photo_snapshot(
            revision,
            worker.entries,
            raw_json,
            worker.original,
            worker.path,
            worker.pattern_cache,
        ):
            self._speaker_photo_label.setText(tr("Photo ready to save"))
            self._update_editor_enabled_state()
            QMessageBox.warning(
                self,
                tr("Photo not saved"),
                tr(error) if error else tr("The glossary changed before the photo could be saved."),
            )
            self._mark_editor_dirty(True)
            return
        self._all_entries = list(manager.get_entries())
        self._occurrences = manager._occurrence_index
        on_saved = getattr(worker, "on_saved", None)
        if callable(on_saved):
            on_saved(manager.get_entry(worker.original))
        self._speaker_photo_dirty = False
        self._pending_speaker_photo = manager.get_entry(worker.original).speaker_photo
        self._pending_select_term = worker.original
        self._speaker_photo_label.setText(
            tr("Photo attached") if self._pending_speaker_photo else tr("No photo attached")
        )
        self._apply_filter(self._search_field.text())
        self._mark_editor_dirty(False)

    def select_speaker_photo(self) -> None:
        """Read a selected portrait in a bounded worker; persist only on Save."""
        if not self._current_entry or not self._update_callback:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Select speaker photo"),
            "",
            tr("Images (*.png *.jpg *.jpeg *.webp *.bmp)"),
        )
        if not path:
            return
        from core.glossary.speaker_photo import PhotoImportThread
        from utils.thread_utils import safe_shutdown_thread
        previous = getattr(self, "_speaker_photo_import_thread", None)
        if previous is not None:
            safe_shutdown_thread(previous, timeout_ms=250)
        generation = getattr(self, "_speaker_photo_import_generation", 0) + 1
        self._speaker_photo_import_generation = generation
        token = f"{self._current_entry.original}:{generation}"
        worker = PhotoImportThread(token, path)
        worker.imported.connect(self._speaker_photo_imported)
        self._speaker_photo_import_thread = worker
        worker.start()

    def remove_speaker_photo(self) -> None:
        """Stage portrait removal; Cancel or Discard keeps the stored photo."""
        if not self._current_entry or not self._update_callback:
            return
        self._speaker_photo_import_generation = getattr(self, "_speaker_photo_import_generation", 0) + 1
        self._pending_speaker_photo = ""
        self._speaker_photo_dirty = True
        self._speaker_photo_label.setText(tr("No photo selected"))
        self._mark_editor_dirty(True)

    def _speaker_photo_imported(self, term: str, data: str, error: str) -> None:
        if (
            not self._current_entry
            or term != f"{self._current_entry.original}:{getattr(self, '_speaker_photo_import_generation', 0)}"
        ):
            return
        if error:
            QMessageBox.warning(self, tr("Photo not added"), error)
            return
        self._pending_speaker_photo = data
        self._speaker_photo_dirty = True
        self._speaker_photo_label.setText(tr("Photo ready to save"))
        self._mark_editor_dirty(True)

    def _cancel_speaker_photo_import(self) -> None:
        """Invalidate and stop a pending user-photo read."""
        self._speaker_photo_import_generation = getattr(self, "_speaker_photo_import_generation", 0) + 1
        worker = getattr(self, "_speaker_photo_import_thread", None)
        if worker is not None:
            from utils.thread_utils import safe_shutdown_thread
            safe_shutdown_thread(worker, timeout_ms=250)
            self._speaker_photo_import_thread = None
