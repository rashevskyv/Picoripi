"""Settings tab: the key file of each console. Picoripi keeps only where each file is; it never shows its contents.

The tab applies each change at once, like the wizard does. The file checks and the saves run on workers.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from PyQt6.QtWidgets import QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from core.i18n import tr
from core.project_library import console_keys, images
from ui.project_manager.jobs import BackgroundJob
from utils.logging_utils import log_info


class SettingsConsoleKeysMixin:
    """Mixin for the Console keys tab of the settings dialog."""

    def setup_console_keys_tab(self):
        """Build one row per console: the stored path, its state, Browse and Clear."""
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
        layout.addStretch(1)
        self._refresh_console_keys()

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
