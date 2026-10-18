"""Data folder chooser: asked at first start (before any user data is touched) and from Settings.

The user always confirms the folder. The suggested folder is pre-filled, never used silently.
Copying an old folder runs in a QThread worker with cancel; the pointer file is written only
after the choice is complete, so a cancelled start asks again next time.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton, QRadioButton, QVBoxLayout, QButtonGroup,
)

from core.data_location_choice import (
    OPTION_CUSTOM, OPTION_LEGACY, OPTION_PORTABLE, PROBLEM_INSIDE_SOURCE,
    PROBLEM_NOT_WRITABLE, CopyResult, DataLocationChoice, DataLocationModel, copy_missing,
)
from core.i18n import tr
from utils.thread_utils import WorkerThread
from utils import app_mode
from utils.data_folder_git import (
    GIT_NOT_IGNORED, GitState, data_folder_git_state, ensure_self_ignore, find_work_tree,
)
from utils.data_location import (
    app_root, legacy_dir, resolve_data_location, write_pointer,
)


def _write_test(folder: Path) -> bool:
    """Create and delete a probe file. Catches read-only folders that a permission check misses."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / f".picoripi_write_test_{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _format_bytes(value: Optional[int]) -> str:
    if value is None:
        return "?"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return "?"


class CopyWorker(WorkerThread):
    """Copies the old data folder into the chosen one. Never deletes or moves the source."""
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, source: Path, destination: Path, parent=None):
        super().__init__(parent)
        self._source = source
        self._destination = destination
        self._stop = False

    def cancel(self) -> None:
        self._stop = True

    def run(self) -> None:
        try:
            result: CopyResult = copy_missing(self._source, self._destination, should_stop=lambda: self._stop)
            self.finished_ok.emit(result)
        except (OSError, ValueError) as exc:
            self.failed.emit(str(exc))


class GitCheckWorker(WorkerThread):
    """Asks Git whether a repository ignores the chosen folder. Runs git, so it never runs on the UI thread."""
    finished_ok = pyqtSignal(object)

    def __init__(self, folder: Path, parent=None):
        super().__init__(parent)
        self._folder = folder

    def run(self) -> None:
        self.finished_ok.emit(data_folder_git_state(self._folder))


class DataLocationDialog(QDialog):
    """Shows the options, the resulting folder and its checks; writes the pointer on confirm."""

    def __init__(self, root: Path, current: Optional[Path] = None, legacy: Optional[Path] = None,
                 first_start: bool = True, notice: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Where Picoripi keeps your data") if first_start else tr("Data folder"))
        self.setMinimumWidth(520)
        self._root = root
        self._first_start = first_start
        # In Settings the old folder is the current one; at first start it is the legacy profile folder.
        self._model = DataLocationModel(root, legacy=current if not first_start else legacy)
        self._worker: Optional[CopyWorker] = None
        self._git_worker: Optional[GitCheckWorker] = None
        self._write_ignore = True          # the self-ignoring .gitignore is written unless the user declines it in a repository
        self._gitignore_yes: Optional[QPushButton] = None   # the prompt's buttons, while it is open
        self._gitignore_no: Optional[QPushButton] = None
        self._choice: Optional[DataLocationChoice] = None
        self.result_folder: Optional[Path] = None
        self._build(current, legacy, notice)
        self._refresh()

    # Layout -----------------------------------------------------------------
    def _build(self, current: Optional[Path], legacy: Optional[Path], notice: str) -> None:
        layout = QVBoxLayout(self)
        intro = (tr("Picoripi stores your projects, settings and glossaries in one folder. "
                    "Choose it now. You can change it later in Settings.") if self._first_start
                 else tr("Choose the folder for your data. The current data is copied there; the old folder stays unchanged."))
        layout.addWidget(self._label(intro))
        if notice:
            layout.addWidget(self._label(notice))
        if not self._first_start and current is not None:
            layout.addWidget(self._label(tr("Current folder:") + " " + str(current)))

        self._group = QButtonGroup(self)
        self._radios = {}
        labels = {
            OPTION_PORTABLE: tr("Next to the program, in the data folder (portable, suggested)"),
            OPTION_CUSTOM: tr("Choose a folder"),
            OPTION_LEGACY: tr("My user profile, the existing ~/.picoripi folder"),
        }
        for option in self._model.options():
            if not self._first_start and option == OPTION_LEGACY:
                continue
            radio = QRadioButton(labels[option], self)
            self._group.addButton(radio)
            self._radios[option] = radio
            layout.addWidget(radio)
        self._radios[OPTION_PORTABLE].setChecked(True)

        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit(self)
        self._folder_edit.textChanged.connect(self._refresh)
        self._browse_button = QPushButton(tr("Browse…"), self)
        self._browse_button.clicked.connect(self._browse)
        folder_row.addWidget(self._folder_edit)
        folder_row.addWidget(self._browse_button)
        layout.addLayout(folder_row)

        self._copy_check = QCheckBox(tr("Copy existing data here (the old folder stays unchanged)"), self)
        self._copy_check.setChecked(legacy is not None or not self._first_start)
        self._copy_check.toggled.connect(self._refresh)
        self._copy_check.setVisible(bool(legacy) or not self._first_start)
        layout.addWidget(self._copy_check)

        self._info = self._label("")
        layout.addWidget(self._info)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        buttons = QHBoxLayout()
        if not self._first_start and current is not None:
            open_button = QPushButton(tr("Open current folder"), self)
            open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(current))))
            buttons.addWidget(open_button)
        buttons.addStretch(1)
        self._cancel_copy_button = QPushButton(tr("Cancel copy"), self)
        self._cancel_copy_button.setVisible(False)
        self._cancel_copy_button.clicked.connect(self._cancel_copy)
        buttons.addWidget(self._cancel_copy_button)
        self._ok_button = QPushButton(tr("Use this folder") if self._first_start else tr("Copy and use this folder"), self)
        self._ok_button.clicked.connect(self._confirm)
        self._quit_button = QPushButton(tr("Quit") if self._first_start else tr("Close"), self)
        self._quit_button.clicked.connect(self.reject)
        buttons.addWidget(self._ok_button)
        buttons.addWidget(self._quit_button)
        layout.addLayout(buttons)
        # Connected last: the first refresh needs every widget to exist.
        for radio in self._radios.values():
            radio.toggled.connect(self._refresh)

    def _label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setWordWrap(True)
        return label

    # State ------------------------------------------------------------------
    def _selected_option(self) -> str:
        for option, radio in self._radios.items():
            if radio.isChecked():
                return option
        return OPTION_PORTABLE

    def _custom_folder(self) -> Optional[Path]:
        text = self._folder_edit.text().strip()
        return Path(text).expanduser() if text else None

    def _current_target(self) -> Optional[Path]:
        option = self._selected_option()
        if option == OPTION_CUSTOM:
            return self._custom_folder()
        return self._model.path_for(option)

    def _refresh(self, *_args) -> None:
        option = self._selected_option()
        self._browse_button.setEnabled(option == OPTION_CUSTOM)
        self._folder_edit.setEnabled(option == OPTION_CUSTOM)
        self._copy_check.setEnabled(option != OPTION_LEGACY)
        target = self._current_target()
        lines = []
        if target is None:
            lines.append(tr("Choose a folder first."))
        else:
            lines.append(tr("Folder:") + " " + str(target))
            lines.append(tr("Free space:") + " " + _format_bytes(self._model.free_bytes(target)))
            problems = self._model.problems(target, same_ok=option == OPTION_LEGACY)
            if PROBLEM_NOT_WRITABLE in problems:
                lines.append(tr("The folder cannot be written. Choose another folder."))
            if PROBLEM_INSIDE_SOURCE in problems:
                lines.append(tr("The folder is inside the old profile folder. Choose another folder."))
        if self._first_start and self._model.legacy is not None and option != OPTION_LEGACY:
            lines.append(tr("The old profile folder ~/.picoripi is kept. Nothing is deleted."))
        self._info.setText("\n".join(lines))
        self._ok_button.setEnabled(self._worker is None and self._git_worker is None and self._ready(target))

    def _ready(self, target: Optional[Path]) -> bool:
        return target is not None and not self._model.problems(target, same_ok=self._selected_option() == OPTION_LEGACY)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("Choose a folder"), str(app_root()))
        if folder:
            self._folder_edit.setText(folder)

    # Actions ----------------------------------------------------------------
    def _confirm(self) -> None:
        option = self._selected_option()
        target = self._current_target()
        if not self._ready(target):
            QMessageBox.warning(self, tr("Data folder"), tr("Choose a folder that can be written."))
            return
        if not _write_test(target):
            QMessageBox.warning(self, tr("Data folder"), tr("The folder cannot be written. Choose another folder."))
            return
        custom = self._custom_folder() if option == OPTION_CUSTOM else None
        self._choice = self._model.build_choice(option, custom, copy_legacy=self._copy_check.isChecked())
        if find_work_tree(self._choice.target) is None:
            self._continue_after_git_check()     # no repository: nothing to ask, the folder is not in Git
        else:
            self._start_git_check(self._choice.target)

    def _start_git_check(self, folder: Path) -> None:
        self._git_worker = GitCheckWorker(folder, self)
        self._git_worker.finished_ok.connect(self._git_checked)
        self._ok_button.setEnabled(False)
        self._git_worker.start()

    def _git_checked(self, state: GitState) -> None:
        self._git_worker.wait()
        self._git_worker.deleteLater()
        self._git_worker = None
        if state.state == GIT_NOT_IGNORED:
            self._ask_gitignore(state.repo)     # continues when the user answers
        else:
            self._continue_after_git_check()

    def _ask_gitignore(self, repo: Path) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(tr("Data folder in Git"))
        box.setText(tr("The data folder is inside a Git repository, and Git does not ignore it. "
                       "Your projects and settings could be committed by accident.")
                    + "\n" + tr("Git repository:") + " " + str(repo))
        box.setInformativeText(tr("Write a .gitignore in the data folder? Git then skips that folder only. "
                                  "Files outside it stay unchanged."))
        self._gitignore_yes = box.addButton(tr("Write .gitignore"), QMessageBox.ButtonRole.AcceptRole)
        self._gitignore_no = box.addButton(tr("Continue without it"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(self._gitignore_yes)
        box.setEscapeButton(self._gitignore_no)
        box.finished.connect(lambda _code: self._gitignore_answered(box.clickedButton() is self._gitignore_yes))
        box.open()

    def _gitignore_answered(self, write: bool) -> None:
        self._write_ignore = write
        self._continue_after_git_check()

    def _continue_after_git_check(self) -> None:
        if self._choice.copy_from is not None:
            self._start_copy(self._choice)
        else:
            self._finish(self._choice)

    def _start_copy(self, choice: DataLocationChoice) -> None:
        self._worker = CopyWorker(choice.copy_from, choice.target, self)
        self._worker.finished_ok.connect(self._copy_done)
        self._worker.failed.connect(self._copy_failed)
        self._progress.setVisible(True)
        self._cancel_copy_button.setVisible(True)
        self._ok_button.setEnabled(False)
        self._quit_button.setEnabled(False)
        self._worker.start()

    def _cancel_copy(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._cancel_copy_button.setEnabled(False)

    def _copy_done(self, result: CopyResult) -> None:
        self._stop_worker()
        if result.stopped:
            # Cancelled: no pointer, so the chooser opens again next start.
            self.reject()
            return
        self._finish(self._choice)

    def _copy_failed(self, message: str) -> None:
        self._stop_worker()
        self._progress.setVisible(False)
        self._cancel_copy_button.setVisible(False)
        self._quit_button.setEnabled(True)
        QMessageBox.warning(self, tr("Data folder"), tr("The data could not be copied:") + " " + message)
        self._refresh()

    def _stop_worker(self) -> None:
        if self._worker is not None:
            self._worker.wait()
            self._worker.deleteLater()
            self._worker = None
        self._progress.setVisible(False)
        self._cancel_copy_button.setVisible(False)
        self._quit_button.setEnabled(True)

    def _finish(self, choice: DataLocationChoice) -> None:
        try:
            if self._write_ignore:
                ensure_self_ignore(choice.target)
            write_pointer(choice.target, self._root)
        except OSError as exc:
            QMessageBox.warning(self, tr("Data folder"), tr("Saving the choice failed:") + " " + str(exc))
            self._refresh()
            return
        self.result_folder = choice.target
        self.accept()

    def reject(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait()
        if self._git_worker is not None:
            self._git_worker.wait()    # git ends by its own timeout (GIT_TIMEOUT_S)
        super().reject()


_app: Optional[QApplication] = None   # the application made for the first-start chooser, kept alive for main.py


def ensure_data_location_chosen() -> bool:
    """First start: show the chooser unless an explicit choice exists. False means the user quit."""
    if app_mode.headless:
        return True
    location = resolve_data_location()
    if not location.needs_choice:
        return True
    global _app
    # Keep the reference: a QApplication nobody holds is destroyed at once, and the dialog below then fails with
    # "Must construct a QApplication before a QWidget". main.py reuses this instance through QApplication.instance().
    _app = QApplication.instance() or QApplication(sys.argv)
    current = location.path if location.problem else None
    notice = tr("The saved data folder is missing or read-only. Choose a folder.") if location.problem else ""
    dialog = DataLocationDialog(app_root(), current=current, legacy=legacy_dir(), first_start=True, notice=notice)
    return dialog.exec() == QDialog.DialogCode.Accepted.value


def open_data_location_dialog(parent, current: Path) -> bool:
    """Settings entry: pick a new folder, copy the current data there. True when a new folder was saved."""
    dialog = DataLocationDialog(app_root(), current=current, first_start=False, parent=parent)
    accepted = dialog.exec() == QDialog.DialogCode.Accepted.value
    if accepted:
        QMessageBox.information(parent, tr("Data folder"), tr("Restart Picoripi to use the new folder."))
    return accepted
