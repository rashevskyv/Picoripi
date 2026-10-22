"""The consent dialog and the worker for the default key source. Nothing downloads without ``confirm_download``."""
from __future__ import annotations

from typing import Sequence

from PyQt6.QtWidgets import QMessageBox, QWidget
from PyQt6.QtCore import pyqtSignal

from core.i18n import tr
from core.project_library import images, key_source
from utils.logging_utils import log_error
from utils.thread_utils import WorkerThread


def confirm_download(parent: QWidget, consoles: Sequence[str], source: key_source.Source) -> bool:
    """Ask before any network call. Names the address the download reads, where the files go, and who is responsible."""
    labels = ", ".join(tr(images.CONSOLE_LABEL[console]) for console in consoles)
    where = (tr("the default source (Abdess/retrobios, a fixed commit)") if source.pinned
             else tr("the source you set"))
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(tr("Download key files?"))
    box.setText(tr("Picoripi downloads the key files for {0} from {1}:", labels, where))
    box.setInformativeText(tr(
        "Address: {0}\n\nThe files are saved only on this computer, in {1}. The source is a third-party project, "
        "not Picoripi. You are responsible for the legal status of these keys in your country.\n\n"
        "Download now?", source.base, str(key_source.download_root())))
    download = box.addButton(tr("Download"), QMessageBox.ButtonRole.AcceptRole)
    box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(download)
    box.exec()
    return box.clickedButton() is download


class KeyDownloadJob(WorkerThread):
    """Downloads the key files of ``consoles``. Cancel with ``requestInterruption()``; it stops between chunks."""

    progress = pyqtSignal(str)
    done = pyqtSignal(object)      # a key_source.Outcome
    cancelled = pyqtSignal()
    failed = pyqtSignal(str)       # a message for the user

    def __init__(self, consoles: Sequence[str], base: str):
        super().__init__()
        self._consoles = list(consoles)
        self._base = base

    def run(self) -> None:
        try:
            outcome = key_source.download(self._consoles, self._base, self.isInterruptionRequested, self.progress.emit)
        except key_source.KeySourceCancelled:
            self.cancelled.emit()
            return
        except key_source.KeySourceError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # an unexpected failure: log the type only; the message or traceback may hold a path
            log_error(f"Key source download failed: {type(exc).__name__}")
            self.failed.emit(tr("The key files could not be downloaded. Choose a file instead."))
            return
        self.done.emit(outcome)
