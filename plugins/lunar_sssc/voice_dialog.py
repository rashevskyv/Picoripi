"""Tools -> Voice clips: a list of the game's voice clips with export, import and play.

Each action runs in a ``VoiceJob`` worker (a clip encodes or decodes in tens of seconds, never on the UI
thread). The buttons are disabled while a job runs. The dialog talks to the game's rules through the voice
hooks (``get_voice_clips``, ``export_voice_clip``, ``import_voice_clip``); it knows no game layout.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout,
                             QWidget)

from core.i18n import tr
from utils.thread_utils import WorkerThread


class VoiceJob(WorkerThread):
    """Runs one action off the UI thread and reports its result or its error message."""

    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, action: Callable[..., Any], *args: Any):
        super().__init__()
        self._action = action
        self._args = args

    def run(self) -> None:
        try:
            result = self._action(*self._args)
        except Exception as exc:          # every failure is shown to the user, none stops the editor
            self.failed.emit(str(exc))
            return
        self.done.emit(result)


class VoiceClipsDialog(QDialog):
    """The clips list and its three actions. ``rules`` is the game's plugin rules object."""

    def __init__(self, rules: Any, project_dir: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Voice clips"))
        self.setMinimumWidth(480)
        self._rules = rules
        self._clips: List[Dict[str, Any]] = list(rules.get_voice_clips(project_dir))
        self._job: Optional[VoiceJob] = None
        self._sound: Optional[QSoundEffect] = None

        layout = QVBoxLayout(self)
        self._list = QListWidget(self)
        for clip in self._clips:
            self._list.addItem(clip["title"])
        if not self._clips:
            self._list.addItem(tr("This game has no voice clips."))
        layout.addWidget(self._list)

        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        row = QHBoxLayout()
        self._export_btn = QPushButton(tr("Export original WAV..."), self)
        self._import_btn = QPushButton(tr("Import translated WAV..."), self)
        self._play_btn = QPushButton(tr("Play"), self)
        self._close_btn = QPushButton(tr("Close"), self)
        for btn in (self._export_btn, self._import_btn, self._play_btn):
            row.addWidget(btn)
        row.addStretch(1)
        row.addWidget(self._close_btn)
        layout.addLayout(row)

        self._export_btn.clicked.connect(self._export)
        self._import_btn.clicked.connect(self._import)
        self._play_btn.clicked.connect(self._play)
        self._close_btn.clicked.connect(self.accept)
        self._set_busy(False)                 # the action buttons need at least one clip

    # ------------------------------------------------------------ helpers

    def _current(self) -> Optional[Dict[str, Any]]:
        row = self._list.currentRow()
        if 0 <= row < len(self._clips):
            return self._clips[row]
        return None

    def _set_busy(self, busy: bool) -> None:
        for btn in (self._export_btn, self._import_btn, self._play_btn):
            btn.setEnabled(not busy and bool(self._clips))
        self._close_btn.setEnabled(not busy)

    def _run(self, action: Callable[..., Any], args: tuple, on_done: Callable[[Any], None]) -> None:
        if self._job is not None:
            return
        self._status.setText(tr("Working..."))
        self._set_busy(True)
        job = VoiceJob(action, *args)
        job.done.connect(on_done)
        job.failed.connect(self._failed)
        job.finished.connect(self._job_finished)
        self._job = job
        job.start()

    def _job_finished(self) -> None:
        self._job = None
        self._set_busy(False)

    def _failed(self, message: str) -> None:
        self._status.setText(tr("Failed: {0}").format(message))

    # ------------------------------------------------------------ actions

    def _export(self) -> None:
        clip = self._current()
        if clip is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, tr("Export original WAV"), f"{clip['id']}.wav", "WAV (*.wav)")
        if not path:
            return
        self._run(self._rules.export_voice_clip, (clip["id"], clip["disc"], path),
                  lambda seconds: self._status.setText(tr("Exported {0:.2f} s to {1}").format(seconds, path)))

    def _import(self) -> None:
        clip = self._current()
        if clip is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("Import translated WAV"), "", "WAV (*.wav)")
        if not path:
            return
        self._run(self._rules.import_voice_clip, (clip["id"], clip["disc"], path, clip["voice_dir"]),
                  lambda seconds: self._status.setText(tr("Imported {0:.2f} s").format(seconds)))

    def _play(self) -> None:
        clip = self._current()
        if clip is None:
            return
        wav = Path(clip["voice_dir"]) / f"{clip['id']}.wav"
        if not wav.is_file():
            self._status.setText(tr("No translated WAV yet: export the original, translate it, then import."))
            return
        self._sound = QSoundEffect(self)
        self._sound.setSource(QUrl.fromLocalFile(str(wav)))
        self._sound.play()
        self._status.setText(tr("Playing {0}").format(wav.name))
