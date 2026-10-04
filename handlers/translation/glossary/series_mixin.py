"""Glossary: the series glossary the project links to — loading, its tab, copy/promote, link menu."""
import json
from pathlib import Path
from typing import List, Optional

from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QFileDialog, QMenu, QMessageBox

from components.glossary_dialog import GlossaryDialog
from core.glossary.series import (
    entries_from_json,
    find_conflicts,
    import_series_glossary,
    link_series,
    linked_series_path,
    series_dir,
)
from core.glossary_manager import GlossaryEntry
from core.i18n import tr
from utils.atomic_io import atomic_write_text
from utils.logging_utils import log_debug


def _sorted_entries(manager) -> List[GlossaryEntry]:
    return sorted(manager.get_entries(), key=lambda e: e.original.lower())


class SeriesMixin:
    series_page: Optional[GlossaryDialog] = None

    def _open_project(self):
        return getattr(getattr(self.mw, "project_manager", None), "project", None)

    def sync_series_glossary(self) -> None:
        """Load the series glossary the open project links to (nothing when unlinked) into its manager."""
        path = linked_series_path(self._open_project())
        manager = self.series_glossary_manager
        if path == manager.glossary_path:
            return
        text = ""
        if path is not None:
            try:
                text = path.read_text(encoding="utf-8-sig")
            except OSError as exc:
                log_debug(f"Series glossary {path} is unreadable: {exc}")
                path, text = None, ""
            if text.strip() and not text.lstrip().startswith("["):
                # Not the glossary.json shape: binding it would overwrite the file on the first edit.
                log_debug(f"Series glossary {path} is not a glossary.json list; not loaded")
                path, text = None, ""
        manager.load_from_text(plugin_name=None, glossary_path=path, raw_text=text)

    # ── The tab in the Glossary window ──────────────────────────────────

    def _attach_series_page(self) -> None:
        """Put the linked series glossary in a tab of the open Glossary window (or take it away)."""
        if self.dialog is None:
            return
        self.sync_series_glossary()
        path = linked_series_path(self._open_project())
        if path != self.series_glossary_manager.glossary_path:
            path = None  # linked, but unreadable or not a glossary.json list
        self.series_page = None
        if path is not None:
            self.series_page = GlossaryDialog(
                parent=self.mw,
                entries=_sorted_entries(self.series_glossary_manager),
                occurrence_map={},
                jump_callback=self._jump_to_occurrence,
                update_callback=self._handle_series_entry_update,
                delete_callback=self._handle_series_entry_delete,
                transfer_callback=self._copy_series_to_project,
                transfer_label=tr('Copy to Project Glossary'),
                embedded=True,
            )
        self.dialog.set_series_page(self.series_page, tr('Series: {name}', name=path.stem) if path else "")
        self._refresh_series_conflicts()

    def _refresh_series_conflicts(self) -> None:
        """Mark, in both tabs, the terms the project and the series glossary translate differently."""
        if getattr(self, "dialog", None) is None:
            return
        if self.series_page is None:
            self.dialog.set_conflicts({})
            return
        conflicts = find_conflicts(self.glossary_manager.get_entries(), self.series_glossary_manager.get_entries())
        self.dialog.set_conflicts({
            key: tr('Conflict: the series glossary translates this as "{translation}".', translation=theirs)
            for key, (_mine, theirs) in conflicts.items()
        })
        self.series_page.set_conflicts({
            key: tr('Conflict: the project glossary translates this as "{translation}".', translation=mine)
            for key, (mine, _theirs) in conflicts.items()
        })

    def _handle_series_entry_update(
        self, original, translation, notes, profiled=None, status=None, section=None, user_notes=None
    ):
        """Update callback of the series tab; same contract as the project one."""
        extra = {key: value for key, value in (("section", section), ("user_notes", user_notes)) if value is not None}
        if not self.series_glossary_manager.update_entry(original, translation, notes, profiled, status=status, **extra):
            return None
        self._refresh_series_conflicts()
        return _sorted_entries(self.series_glossary_manager), {}

    def _handle_series_entry_delete(self, original: str):
        """Delete callback of the series tab."""
        if not self.series_glossary_manager.delete_entry(original):
            return None
        self._refresh_series_conflicts()
        return _sorted_entries(self.series_glossary_manager), {}

    def _copy_series_to_project(self, entries: List[GlossaryEntry]) -> None:
        """Copy series terms into the project glossary (a term it has takes the series translation)."""
        manager = self.glossary_manager
        with manager.transaction():
            copied = [manager.import_entry(entry) for entry in entries]
        data_source = getattr(getattr(self.mw, "data_store", None), "data", None) or []
        for entry in filter(None, copied):
            manager.update_occurrences_for_entry(data_source, entry.original, entry)
        self.main_handler._cached_glossary = manager.get_raw_text()
        self._update_glossary_highlighting()
        if self.dialog is not None:
            self.dialog.reload_data(_sorted_entries(manager), manager.get_occurrence_map())
        self._refresh_series_conflicts()
        self._series_status(tr('Copied {count} term(s) into the project glossary.', count=len(entries)))

    def _promote_to_series(self, entries: List[GlossaryEntry]) -> None:
        """Copy project terms into the linked series glossary."""
        if self.series_page is None:
            return
        manager = self.series_glossary_manager
        with manager.transaction():
            for entry in entries:
                manager.import_entry(entry)
        self.series_page.reload_data(_sorted_entries(manager), {})
        self._refresh_series_conflicts()
        self._series_status(tr('Copied {count} term(s) into the series glossary.', count=len(entries)))

    def _series_status(self, message: str) -> None:
        status_bar = getattr(self.mw, "statusBar", None)
        if status_bar:
            status_bar.showMessage(message, 4000)

    # ── Linking ─────────────────────────────────────────────────────────

    def set_series_link(self, path: Optional[Path]) -> None:
        """Link the open project to the series glossary at ``path`` (None unlinks), save the project, refresh."""
        project = self._open_project()
        if project is None:
            return
        link_series(project, path)
        self.mw.project_manager.save()
        # Forget the loaded file, so a re-import into the same path is read again.
        self.series_glossary_manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
        self._attach_series_page()

    def _show_series_glossary_menu(self) -> None:
        """The Series Glossary... button: new, choose (importing other shapes), unlink."""
        project = self._open_project()
        if project is None:
            QMessageBox.information(
                self.dialog, tr('Series Glossary'), tr('Open a project first: the link is stored in the project.')
            )
            return
        menu = QMenu(self.dialog)
        new_action = menu.addAction(tr('New Empty Series Glossary...'))
        choose_action = menu.addAction(tr('Link or Import Series Glossary...'))
        unlink_action = menu.addAction(tr('Unlink Series Glossary'))
        unlink_action.setEnabled(linked_series_path(project) is not None)
        chosen = menu.exec(QCursor.pos())
        if chosen is new_action:
            self._create_series_glossary()
        elif chosen is choose_action:
            self._choose_series_glossary()
        elif chosen is unlink_action:
            self.set_series_link(None)

    def _create_series_glossary(self) -> None:
        folder = series_dir()
        path, _ = QFileDialog.getSaveFileName(
            self.dialog, tr('New Series Glossary'), str(folder / "series_glossary.json"), tr('Glossary JSON (*.json)')
        )
        if not path:
            return
        target = Path(path)
        if not target.exists():
            atomic_write_text(target, "[]\n")
        self.set_series_link(target)

    def _choose_series_glossary(self) -> None:
        """Link a glossary.json-shaped file as is; convert any other glossary JSON into the series folder first."""
        path, _ = QFileDialog.getOpenFileName(
            self.dialog, tr('Link or Import Series Glossary'), str(series_dir()), tr('Glossary JSON (*.json)')
        )
        if not path:
            return
        source = Path(path)
        try:
            data = json.loads(source.read_text(encoding="utf-8-sig"))
            entries_from_json(data)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self.dialog, tr('Series Glossary'), tr('Cannot read this glossary: {error}', error=exc))
            return
        if isinstance(data, list):
            self.set_series_link(source)
            return
        target = series_dir() / f"{source.stem}.json"
        if target.exists() and QMessageBox.question(
            self.dialog,
            tr('Series Glossary'),
            tr('{path} already exists. Replace it with a fresh import of {source}?', path=target, source=source.name),
        ) != QMessageBox.StandardButton.Yes:
            return
        import_series_glossary(source, target)
        self.set_series_link(target)
