"""Settings tab: the key file of each console. Picoripi keeps only where each file is; it never shows its contents.

The tab applies each change at once, like the wizard does. The file checks and the saves run on workers. The default
key source (download on request, after a confirmation) sits below the rows.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtWidgets import (QCheckBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QVBoxLayout, QWidget)

from core.i18n import tr
from core.project_library import console_keys, images, key_source
from ui.key_source_download import KeyDownloadJob, confirm_download
from ui.project_manager.jobs import BackgroundJob
from utils.logging_utils import log_info


def _source_view() -> Dict[str, Any]:
    """The source settings and which consoles still lack a file of the user's own. Reads files: call it on a worker."""
    config = key_source.config()
    return {"source": key_source.snapshot(), "last_time": config["last_time"], "last_ref": config["last_ref"],
            "missing": [console for console in key_source.SOURCE_CONSOLES if not key_source.own_file(console)]}


class SettingsConsoleKeysMixin:
    """Mixin for the Console keys tab of the settings dialog."""

    def setup_console_keys_tab(self):
        """Build one row per console: the stored path, its state, Browse and Clear. Then the default source."""
        layout = QVBoxLayout(self.console_keys_tab)
        info = QLabel(tr(
            "Picoripi keeps only the path of each key file. It never shows, logs or copies the key contents. "
            "The wizard asks for a key file again when none is stored or the stored file is gone. Changes apply at once."),
            self)
        info.setWordWrap(True)
        layout.addWidget(info)
        form = QFormLayout()
        self._console_key_edits: Dict[str, QLineEdit] = {}
        self._console_key_states: Dict[str, QLabel] = {}
        self._console_key_clears: Dict[str, QPushButton] = {}
        self._console_key_jobs: List[Any] = []
        for console in console_keys.CONSOLES:
            edit = QLineEdit(self)
            edit.setReadOnly(True)
            edit.setPlaceholderText(tr("Not set"))
            state = QLabel(self)
            browse = QPushButton(tr("Browse..."), self)
            browse.clicked.connect(partial(self._console_key_browse, console))
            clear = QPushButton(tr("Clear"), self)
            clear.clicked.connect(partial(self._console_key_clear, console))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(state)
            row.addWidget(browse)
            row.addWidget(clear)
            holder = QWidget(self)
            holder.setLayout(row)
            form.addRow(QLabel(tr(images.CONSOLE_LABEL[console]), self), holder)
            self._console_key_edits[console] = edit
            self._console_key_states[console] = state
            self._console_key_clears[console] = clear
        layout.addLayout(form)
        self._console_key_message = QLabel("", self)
        self._console_key_message.setWordWrap(True)
        layout.addWidget(self._console_key_message)
        layout.addWidget(self._build_source_box())
        layout.addStretch(1)
        self._refresh_console_keys()
        self._refresh_source()

    def _refresh_console_keys(self):
        """Read every stored path and whether its file exists, on a worker."""
        self._run_console_key_job(BackgroundJob(console_keys.states), self._show_console_keys)

    def _show_console_keys(self, states: Dict[str, Tuple[str, bool]]):
        for console, (stored, exists) in states.items():
            if console not in self._console_key_edits:
                continue
            self._console_key_edits[console].setText(stored)
            if not stored:
                text = tr("Not set")
            else:
                text = tr("File found") if exists else tr("File not found")
            self._console_key_states[console].setText(text)
            self._console_key_clears[console].setEnabled(bool(stored))

    def _console_key_browse(self, console: str):
        label = tr(images.CONSOLE_LABEL[console])
        title = (tr("Choose the Oodle library file (oo2core or oo2ext DLL)") if console == "oodle"
                 else tr("Choose the key file for {0}", label))
        path, _filter = QFileDialog.getOpenFileName(self, title, str(Path.home()), tr("All files") + " (*)")
        if not path:
            return
        job = BackgroundJob(console_keys.set_path, console, path)
        self._run_console_key_job(job, lambda _result, c=console: self._console_key_saved(c))

    def _console_key_clear(self, console: str):
        job = BackgroundJob(console_keys.clear_path, console)
        self._run_console_key_job(job, lambda _result, c=console: self._console_key_saved(c))

    def _console_key_saved(self, console: str):
        log_info(f"Key file setting of {console} changed.")
        self._console_key_message.setText("")
        self._refresh_console_keys()

    def _run_console_key_job(self, job: BackgroundJob, on_done: Callable[[Any], None]):
        self._console_key_jobs.append(job)
        job.done.connect(on_done)
        job.done.connect(lambda _result, j=job: self._console_key_jobs.remove(j) if j in self._console_key_jobs else None)
        job.failed.connect(lambda message: self._console_key_message.setText(
            tr("The key file setting could not be saved: {0}", message)))
        job.failed.connect(lambda _message, j=job: self._console_key_jobs.remove(j) if j in self._console_key_jobs else None)
        job.start()

    # ----- the default source -----
    def _build_source_box(self) -> QGroupBox:
        box = QGroupBox(tr("Default source for key files"), self)
        column = QVBoxLayout(box)
        intro = QLabel(tr(
            "Picoripi can download the 3DS, Switch and Wii key files from a source. The default source is the "
            "bios/Nintendo folder of the Abdess/retrobios repository, at one fixed commit. Picoripi ships no keys. "
            "Each download asks you first, and a key file you set yourself always wins."), self)
        intro.setWordWrap(True)
        column.addWidget(intro)
        self._source_on = QCheckBox(tr("Allow downloads from a source"), self)
        self._source_on.toggled.connect(lambda on: self._save_source(enabled=bool(on)))
        column.addWidget(self._source_on)
        address_row = QHBoxLayout()
        address_row.addWidget(QLabel(tr("Source folder:"), self))
        self._source_address = QLineEdit(self)
        self._source_address.setPlaceholderText(key_source.DEFAULT_BASE)
        self._source_address.editingFinished.connect(self._source_address_edited)
        self._source_default = QPushButton(tr("Use the default source"), self)
        self._source_default.clicked.connect(lambda: self._save_source(base_url=""))
        address_row.addWidget(self._source_address, 1)
        address_row.addWidget(self._source_default)
        column.addLayout(address_row)
        action_row = QHBoxLayout()
        self._source_get = QPushButton(tr("Get keys from the default source"), self)
        self._source_get.clicked.connect(self._get_from_source)
        self._source_cancel = QPushButton(tr("Cancel download"), self)
        self._source_cancel.setVisible(False)
        self._source_cancel.clicked.connect(self._cancel_source_download)
        action_row.addWidget(self._source_get)
        action_row.addWidget(self._source_cancel)
        action_row.addStretch(1)
        column.addLayout(action_row)
        self._source_info = QLabel("", self)
        self._source_info.setWordWrap(True)
        column.addWidget(self._source_info)
        self._source_status = QLabel("", self)
        self._source_status.setWordWrap(True)
        column.addWidget(self._source_status)
        self._source_view_data: Optional[Dict[str, Any]] = None
        self._download_job: Optional[KeyDownloadJob] = None
        return box

    def _refresh_source(self):
        """Read the source settings and the missing consoles on a worker."""
        self._run_console_key_job(BackgroundJob(_source_view), self._show_source)

    def _show_source(self, view: Dict[str, Any]):
        self._source_view_data = view
        source = view["source"]
        self._source_on.blockSignals(True)
        self._source_on.setChecked(source.enabled)
        self._source_on.blockSignals(False)
        if not self._source_address.hasFocus():
            self._source_address.setText("" if source.pinned else source.base)
        self._source_default.setEnabled(not source.pinned)
        self._source_get.setText(tr("Download again") if view["last_time"] else
                                 tr("Get keys from the default source") if source.pinned else
                                 tr("Get keys from the source you set"))
        self._source_get.setEnabled(source.enabled and self._download_job is None)
        if view["last_time"] and view["last_ref"]:
            self._source_info.setText(tr("Last download: commit {0}, {1} (UTC).", view["last_ref"][:12], view["last_time"]))
        elif view["last_time"]:
            self._source_info.setText(tr("Last download: {0} (UTC).", view["last_time"]))
        else:
            self._source_info.setText(tr("Nothing has been downloaded yet."))

    def _source_address_edited(self):
        view = self._source_view_data or {}
        current = view.get("source")
        text = self._source_address.text().strip()
        if current is not None and text != ("" if current.pinned else current.base):
            self._save_source(base_url=text)

    def _save_source(self, **changes: Any):
        self._run_console_key_job(BackgroundJob(partial(key_source.set_config, **changes)),
                                  lambda _result: self._refresh_source())

    def _get_from_source(self):
        view = self._source_view_data
        if view is None or self._download_job is not None:
            return
        if not view["missing"]:
            self._source_status.setText(tr("Your own key files are in use for every console."))
            return
        if not confirm_download(self, view["missing"], view["source"]):
            return
        self._source_status.setText("")
        job = KeyDownloadJob(view["missing"], view["source"].base)
        self._download_job = job
        self._console_key_jobs.append(job)
        for signal in (job.done, job.failed, job.cancelled):   # connected first: the state is reset before the messages
            signal.connect(lambda *_args, j=job: self._source_finished(j))
        job.progress.connect(self._source_status.setText)
        job.done.connect(self._source_downloaded)
        job.failed.connect(self._source_status.setText)
        job.cancelled.connect(lambda: self._source_status.setText(tr("Download cancelled. Nothing was kept.")))
        self._source_cancel.setVisible(True)
        self._source_get.setEnabled(False)
        job.start()

    def _cancel_source_download(self):
        if self._download_job is not None:
            self._source_status.setText(tr("Cancelling..."))
            self._download_job.requestInterruption()

    def _source_downloaded(self, outcome: key_source.Outcome):
        parts = []
        if outcome.downloaded:
            parts.append(tr("Downloaded the key files for {0}.", ", ".join(
                tr(images.CONSOLE_LABEL[c]) for c in outcome.downloaded)))
        if outcome.kept:
            parts.append(tr("Kept your own key file for {0}.", ", ".join(
                tr(images.CONSOLE_LABEL[c]) for c in outcome.kept)))
        self._source_status.setText(" ".join(parts))

    def _source_finished(self, job: KeyDownloadJob):
        if self._download_job is job:
            self._download_job = None
        if job in self._console_key_jobs:
            self._console_key_jobs.remove(job)
        self._source_cancel.setVisible(False)
        self._refresh_console_keys()
        self._refresh_source()
