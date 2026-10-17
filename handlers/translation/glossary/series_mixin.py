"""Glossary: the chain of series glossaries of the project — loading, their tabs, copy/promote, link menu."""
import json
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QFileDialog, QMenu, QMessageBox

from components.glossary_dialog import GlossaryDialog
from core.glossary.series import (
    AUTO_KEY,
    entries_from_json,
    find_conflicts,
    folder_glossaries_enabled,
    import_series_glossary,
    linked_series_paths,
    series_chain,
    series_dir,
    series_pair_conflicts,
    set_series_links,
)
from core.glossary_manager import GlossaryEntry, GlossaryManager
from core.i18n import tr
from utils.atomic_io import atomic_write_text
from utils.logging_utils import log_debug


def _sorted_entries(manager) -> List[GlossaryEntry]:
    return sorted(manager.get_entries(), key=lambda e: e.original.lower())


def _read_series_file(path: Path) -> Optional[str]:
    """The text of a series glossary file, or None when it is unreadable or not a glossary.json list."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        log_debug(f"Series glossary {path} is unreadable: {exc}")
        return None
    if text.strip() and not text.lstrip().startswith("["):
        # Not the glossary.json shape: binding it would overwrite the file on the first edit.
        log_debug(f"Series glossary {path} is not a glossary.json list; not loaded")
        return None
    return text


class SeriesMixin:
    # The tab of each loaded series glossary, in chain order (nearest first).
    series_pages: List[GlossaryDialog] = []

    def _open_project(self):
        return getattr(getattr(self.mw, "project_manager", None), "project", None)

    def _project_dir(self) -> Optional[Path]:
        value = getattr(getattr(self.mw, "project_manager", None), "project_dir", None)
        return Path(value) if value else None

    @property
    def series_page(self) -> Optional[GlossaryDialog]:
        """The nearest series glossary tab, or None."""
        return self.series_pages[0] if self.series_pages else None

    @property
    def series_glossary_manager(self) -> Optional[GlossaryManager]:
        """The nearest loaded series glossary, or None."""
        return self.series_glossary_managers[0] if self.series_glossary_managers else None

    def sync_series_glossary(self) -> None:
        """Load the series glossaries of the open project (nearest first) into ``series_glossary_managers``.

        The list object is shared with the prompt composer, so it is changed in place.
        """
        loaded = {manager.glossary_path: manager for manager in self.series_glossary_managers}
        managers = []
        for path in series_chain(self._open_project(), self._project_dir()):
            manager = loaded.get(path)
            if manager is None:
                text = _read_series_file(path)
                if text is None:
                    continue
                manager = GlossaryManager()
                manager.load_from_text(plugin_name=None, glossary_path=path, raw_text=text)
            managers.append(manager)
        self.series_glossary_managers[:] = managers

    def _forget_series_glossaries(self) -> None:
        """Drop the loaded files, so the next sync reads them again."""
        self.series_glossary_managers[:] = []

    # ── The tabs in the Glossary window ─────────────────────────────────

    def _attach_series_page(self) -> None:
        """Put every series glossary of the project in a tab of the open Glossary window (or take them away)."""
        if self.dialog is None:
            return
        self.sync_series_glossary()
        self.series_pages = []
        for manager in self.series_glossary_managers:
            page = GlossaryDialog(
                parent=self.mw,
                entries=_sorted_entries(manager),
                occurrence_map={},
                jump_callback=self._jump_to_occurrence,
                update_callback=partial(self._handle_series_entry_update, manager),
                delete_callback=partial(self._handle_series_entry_delete, manager),
                transfer_callback=self._copy_series_to_project,
                transfer_label=tr('Copy to Project Glossary'),
                embedded=True,
            )
            self.series_pages.append(page)
        self.dialog.set_series_pages([
            (page, tr('Series: {name}', name=self._series_label(manager.glossary_path)))
            for page, manager in zip(self.series_pages, self.series_glossary_managers)
        ])
        self._refresh_series_conflicts()

    @staticmethod
    def _series_label(path: Optional[Path]) -> str:
        """``Zelda`` for ``Zelda/_glossary/glossary.json``, else the file stem."""
        if path is None:
            return ""
        if path.parent.name == "_glossary":
            return path.parent.parent.name or path.stem
        return path.stem

    def _refresh_series_conflicts(self) -> None:
        """Mark, in every tab, the terms the project and a series glossary translate differently, and the terms two
        series glossaries translate differently."""
        if getattr(self, "dialog", None) is None:
            return
        project_conflicts = {}
        page_conflicts: List[Dict[str, str]] = [{} for _ in self.series_pages]
        for index, manager in enumerate(self.series_glossary_managers):
            conflicts = find_conflicts(self.glossary_manager.get_entries(), manager.get_entries())
            for key, (_mine, theirs) in conflicts.items():
                project_conflicts.setdefault(
                    key, tr('Conflict: the series glossary translates this as "{translation}".', translation=theirs)
                )
            page_conflicts[index].update({
                key: tr('Conflict: the project glossary translates this as "{translation}".', translation=mine)
                for key, (mine, _theirs) in conflicts.items()
            })
        managers = self.series_glossary_managers
        for first, second, key, mine, theirs in series_pair_conflicts(managers):
            name_first = self._series_label(managers[first].glossary_path)
            name_second = self._series_label(managers[second].glossary_path)
            page_conflicts[first].setdefault(key, tr(
                'Conflict: the series glossary {name} translates this as "{translation}".',
                name=name_second, translation=theirs))
            page_conflicts[second].setdefault(key, tr(
                'Conflict: the series glossary {name} translates this as "{translation}".',
                name=name_first, translation=mine))
        for page, conflicts in zip(self.series_pages, page_conflicts):
            page.set_conflicts(conflicts)
        self.dialog.set_conflicts(project_conflicts)

    def _handle_series_entry_update(
        self, manager, original, translation, notes, profiled=None, status=None, section=None, user_notes=None
    ):
        """Update callback of a series tab; same contract as the project one."""
        extra = {key: value for key, value in (("section", section), ("user_notes", user_notes)) if value is not None}
        if not manager.update_entry(original, translation, notes, profiled, status=status, **extra):
            return None
        self._refresh_series_conflicts()
        return _sorted_entries(manager), {}

    def _handle_series_entry_delete(self, manager, original: str):
        """Delete callback of a series tab."""
        if not manager.delete_entry(original):
            return None
        self._refresh_series_conflicts()
        return _sorted_entries(manager), {}

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

    def _promote_to_series(self, entries: List[GlossaryEntry], level: Optional[int] = None) -> None:
        """Copy project terms into a series glossary: the only one, the chosen one, or one picked from a menu."""
        if not self.series_glossary_managers:
            return
        if level is None:
            level = 0 if len(self.series_glossary_managers) == 1 else self._ask_series_level()
            if level is None:
                return
        manager = self.series_glossary_managers[level]
        with manager.transaction():
            for entry in entries:
                manager.import_entry(entry)
        self.series_pages[level].reload_data(_sorted_entries(manager), {})
        self._refresh_series_conflicts()
        self._series_status(tr('Copied {count} term(s) into the series glossary.', count=len(entries)))

    def _ask_series_level(self) -> Optional[int]:
        menu = QMenu(self.dialog)
        actions = [menu.addAction(self._series_label(m.glossary_path)) for m in self.series_glossary_managers]
        chosen = menu.exec(QCursor.pos())
        return actions.index(chosen) if chosen in actions else None

    def _series_status(self, message: str) -> None:
        status_bar = getattr(self.mw, "statusBar", None)
        if status_bar:
            status_bar.showMessage(message, 4000)

    # ── Linking ─────────────────────────────────────────────────────────

    def set_series_link(self, path: Optional[Path]) -> None:
        """Link the open project to exactly the series glossary at ``path`` (None unlinks), save, refresh."""
        self._set_series_links([path] if path is not None else [])

    def add_series_link(self, path: Path) -> None:
        """Add ``path`` to the explicit series links of the open project (nearest first), save, refresh."""
        self._set_series_links([path] + [p for p in linked_series_paths(self._open_project()) if p != path])

    def _set_series_links(self, paths: List[Path]) -> None:
        project = self._open_project()
        if project is None:
            return
        set_series_links(project, paths)
        self._save_project_and_refresh()

    def _save_project_and_refresh(self) -> None:
        self.mw.project_manager.save()
        self._forget_series_glossaries()
        self._attach_series_page()

    def _show_series_glossary_menu(self) -> None:
        """The Series Glossary... button: new, link, unlink one, use or ignore the folder glossaries."""
        project = self._open_project()
        if project is None:
            QMessageBox.information(
                self.dialog, tr('Series Glossary'), tr('Open a project first: the link is stored in the project.')
            )
            return
        menu = QMenu(self.dialog)
        new_action = menu.addAction(tr('New Empty Series Glossary...'))
        choose_action = menu.addAction(tr('Link or Import Series Glossary...'))
        unlink_actions = {}
        for path in linked_series_paths(project):
            unlink_actions[menu.addAction(tr('Unlink {name}', name=self._series_label(path)))] = path
        auto_action = menu.addAction(tr('Use the _glossary folders above the project'))
        auto_action.setCheckable(True)
        auto_action.setChecked(folder_glossaries_enabled(project))
        chosen = menu.exec(QCursor.pos())
        if chosen is new_action:
            self._create_series_glossary()
        elif chosen is choose_action:
            self._choose_series_glossary()
        elif chosen in unlink_actions:
            self._set_series_links([p for p in linked_series_paths(project) if p != unlink_actions[chosen]])
        elif chosen is auto_action:
            if auto_action.isChecked():
                project.metadata.pop(AUTO_KEY, None)
            else:
                project.metadata[AUTO_KEY] = False
            self._save_project_and_refresh()

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
        self.add_series_link(target)

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
            self.add_series_link(source)
            return
        target = series_dir() / f"{source.stem}.json"
        if target.exists() and QMessageBox.question(
            self.dialog,
            tr('Series Glossary'),
            tr('{path} already exists. Replace it with a fresh import of {source}?', path=target, source=source.name),
        ) != QMessageBox.StandardButton.Yes:
            return
        import_series_glossary(source, target)
        self.add_series_link(target)
