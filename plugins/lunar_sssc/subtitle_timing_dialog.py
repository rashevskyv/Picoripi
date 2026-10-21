"""Tools -> Voice subtitles timing: the cues of the opening monologue against its audio.

A strip shows the waveform with one block per cue: drag an edge to retime a cue, drag a block to move it.
The table lists the cues in seconds with the source and translated text. Play runs the clip and shows the
cue that is on in a game-like box. Every job (load, audio, save) runs in a ``VoiceJob`` worker; the dialog
never reads or writes a file on the UI thread. Times are whole frames (60 Hz) in the model; the editor shows
seconds with two decimals.
"""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any, List, Optional

from PyQt6.QtCore import QTimer, QUrl, pyqtSignal, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (QAbstractItemView, QDialog, QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel,
                             QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from core.i18n import tr

from . import subtitle_timing as st
from .subtitle_timing import FPS, Timing
from .voice_dialog import VoiceJob

_TAG = re.compile(r"\{[^}]*\}")
_EDGE_PX = 6
_COLUMNS = ("#", "Start (s)", "End (s)", "Pause after (s)", "Source (English)", "Translation")


def _pad(items: List[str], count: int) -> List[str]:
    return (list(items) + [""] * count)[:count]


class TimingStrip(QWidget):
    """The waveform and one block per cue. Emits the new timing while a block or an edge is dragged."""

    timing_changed = pyqtSignal(object)
    cue_selected = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(130)
        self._peaks: List[float] = []
        self._duration = 0.0          # seconds of audio
        self._timing = st.defaults()
        self._selected = -1
        self._playhead: Optional[float] = None    # absolute frames
        self._drag: Optional[tuple] = None        # (mode, index, grab frames)

    # -- data ------------------------------------------------------------------

    def set_data(self, peaks: List[float], duration: float, timing: Timing) -> None:
        self._peaks, self._duration, self._timing = list(peaks), duration, timing
        self.update()

    def set_timing(self, timing: Timing) -> None:
        self._timing = timing
        self.update()

    def set_selected(self, index: int) -> None:
        self._selected = index
        self.update()

    def set_playhead(self, frame: Optional[float]) -> None:
        self._playhead = frame
        self.update()

    def _total_frames(self) -> int:
        last = max((b for _a, b in self._timing.frames(len(self._timing.cues))), default=0)
        return max(int(self._duration * FPS), last) + FPS

    def _x_of(self, frame: float) -> float:
        return frame * self.width() / self._total_frames()

    def _frame_of(self, x: float) -> float:
        return max(0.0, x * self._total_frames() / max(1, self.width()))

    # -- painting ----------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#15171c"))
        mid = h / 2
        if self._peaks:
            p.setPen(QPen(QColor("#5d6778"), 1))
            for x in range(w):
                level = self._peaks[min(len(self._peaks) - 1, x * len(self._peaks) // max(1, w))]
                half = level * (h / 2 - 4)
                p.drawLine(x, int(mid - half), x, int(mid + half))
        for i, (a, b) in enumerate(self._timing.frames(len(self._timing.cues))):
            x1, x2 = self._x_of(a), self._x_of(b)
            fill = QColor(255, 170, 60, 110) if i == self._selected else QColor(80, 140, 220, 85)
            p.fillRect(int(x1), 0, max(2, int(x2 - x1)), h, fill)
            p.setPen(QPen(QColor("#e8edf5"), 1))
            p.drawLine(int(x1), 0, int(x1), h)
            p.drawLine(int(x2), 0, int(x2), h)
            p.drawText(int(x1) + 4, 14, str(i + 1))
        if self._playhead is not None:
            p.setPen(QPen(QColor("#ff5c5c"), 2))
            x = int(self._x_of(self._playhead))
            p.drawLine(x, 0, x, h)
        p.end()

    # -- dragging -----------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        x = event.position().x()
        for i, (a, b) in enumerate(self._timing.frames(len(self._timing.cues))):
            x1, x2 = self._x_of(a), self._x_of(b)
            if abs(x - x2) <= _EDGE_PX:
                self._drag = ("end", i, 0)
            elif abs(x - x1) <= _EDGE_PX:
                self._drag = ("start", i, 0)
            elif x1 < x < x2:
                self._drag = ("move", i, self._frame_of(x) - a)
            else:
                continue
            self._selected = i
            self.cue_selected.emit(i)
            self.update()
            return

    def mouseMoveEvent(self, event) -> None:
        if self._drag is None:
            return
        mode, i, grab = self._drag
        frame = self._frame_of(event.position().x())
        rel = int(round(frame)) - self._timing.offset
        if mode == "move":
            cue = self._timing.cues[i]
            desired = int(round(frame - grab)) - self._timing.offset
            timing = st.move(self._timing, i, desired - cue.start)
        else:
            timing = st.set_edge(self._timing, i, mode, rel)
        self._timing = timing
        self.update()
        self.timing_changed.emit(timing)

    def mouseReleaseEvent(self, _event) -> None:
        self._drag = None


class SubtitleTimingDialog(QDialog):
    """The timing editor. ``rules`` is the game's plugin rules object (its subtitle methods run in workers)."""

    def __init__(self, rules: Any, project_dir: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Voice subtitles timing"))
        self.resize(1000, 680)
        self._rules = rules
        self._project_dir = project_dir
        self._timing: Timing = st.defaults()
        self._source: List[str] = []
        self._translation: List[str] = []
        self._spans: List[tuple] = []
        self._audio_seconds = 0.0
        self._job: Optional[VoiceJob] = None
        self._dirty = False
        self._updating = False
        self._play_file = ""
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(1.0)
        self._player.setAudioOutput(self._audio)
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(30)
        self._tick_timer.timeout.connect(self._tick)

        root = QVBoxLayout(self)
        self._status = QLabel(tr("Loading..."), self)
        self._status.setWordWrap(True)

        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Clip offset (s):"), self))
        self._offset = QDoubleSpinBox(self)
        self._offset.setRange(0.0, 60.0)
        self._offset.setDecimals(2)
        self._offset.setSingleStep(0.1)
        self._offset.valueChanged.connect(self._offset_changed)
        row.addWidget(self._offset)
        row.addStretch(1)
        self._reset_btn = self._button(row, tr("Reset to speech spans"), self._reset)
        self._split_btn = self._button(row, tr("Split cue"), self._split)
        self._merge_btn = self._button(row, tr("Merge with next"), self._merge)

        self._strip = TimingStrip(self)
        self._strip.timing_changed.connect(self._strip_changed)
        self._strip.cue_selected.connect(self._select_row)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels([tr(c) for c in _COLUMNS])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked
                                    | QAbstractItemView.EditTrigger.SelectedClicked
                                    | QAbstractItemView.EditTrigger.EditKeyPressed)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.itemSelectionChanged.connect(self._on_selection)
        self._table.itemChanged.connect(self._cell_edited)

        nudge = QHBoxLayout()
        self._button(nudge, tr("-1 frame"), lambda: self._nudge(-1))
        self._button(nudge, tr("+1 frame"), lambda: self._nudge(1))
        self._button(nudge, tr("-0.1 s"), lambda: self._nudge(-6))
        self._button(nudge, tr("+0.1 s"), lambda: self._nudge(6))
        nudge.addStretch(1)
        self._play_btn = self._button(nudge, tr("Play"), self._play)
        self._stop_btn = self._button(nudge, tr("Stop"), self._stop)
        self._save_btn = self._button(nudge, tr("Save timing"), self._save)
        self._close_btn = self._button(nudge, tr("Close"), self.close)

        self._box = QLabel("", self)
        self._box.setWordWrap(True)
        self._box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._box.setMinimumHeight(64)
        self._box.setStyleSheet("background:#0b0c14; color:#ffffff; border:2px solid #8fa3c7; "
                                "border-radius:6px; padding:8px; font-size:15px;")
        self._problems = QLabel("", self)
        self._problems.setWordWrap(True)

        for widget in (self._status, row, self._strip, self._table, self._box, nudge, self._problems):
            if isinstance(widget, QWidget):
                root.addWidget(widget)
            else:
                root.addLayout(widget)
        self._set_busy(True)
        self._run(self._rules.subtitle_state, (self._project_dir,), self._loaded)

    # -- helpers ---------------------------------------------------------------

    def _button(self, layout, text: str, slot) -> QPushButton:
        btn = QPushButton(text, self)
        btn.clicked.connect(slot)
        layout.addWidget(btn)
        return btn

    def _set_busy(self, busy: bool) -> None:
        for btn in (self._reset_btn, self._split_btn, self._merge_btn, self._play_btn, self._stop_btn, self._save_btn):
            btn.setEnabled(not busy and bool(self._timing.cues))
        self._table.setEnabled(not busy)
        self._offset.setEnabled(not busy)

    def _run(self, action, args: tuple, on_done) -> None:
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

    def _changed(self, status: str = "") -> None:
        self._dirty = True
        self._refresh()
        if status:
            self._status.setText(status)

    # -- state -----------------------------------------------------------------

    def _loaded(self, state: dict) -> None:
        self._timing = state["timing"]
        self._spans = state["spans"]
        self._audio_seconds = float(state["duration"])
        n = len(self._timing.cues)
        self._source = _pad(state["source"], n)
        self._translation = _pad(state["translation"], n)
        self._updating = True
        self._offset.setValue(st.seconds(self._timing.offset))
        self._updating = False
        self._strip.set_data(state["peaks"], state["duration"], self._timing)
        self._status.setText(tr("Click a block to select a cue. Drag its edges to retime it, or drag the block."))
        self._refresh()

    def _refresh(self) -> None:
        n = len(self._timing.cues)
        self._source = _pad(self._source, n)
        self._translation = _pad(self._translation, n)
        self._strip.set_timing(self._timing)
        current = self._table.currentRow()
        texts = [_TAG.sub("", t).strip() for t in self._translation]
        problems = st.problems(self._timing, texts, self._duration())
        bad = {p[1] for p in problems if len(p) > 1}
        self._updating = True
        self._table.blockSignals(True)
        self._table.setRowCount(n)
        for i, cue in enumerate(self._timing.cues):
            gap = ""
            if i + 1 < n:
                gap = "%.2f" % st.seconds(self._timing.cues[i + 1].start - cue.end)
            values = [str(i + 1), "%.2f" % st.seconds(cue.start), "%.2f" % st.seconds(cue.end), gap,
                      self._source[i], self._translation[i]]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col not in (1, 2):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if i in bad:
                    item.setBackground(QBrush(QColor("#4a2a2a")))
                self._table.setItem(i, col, item)
        if 0 <= current < n:
            self._table.selectRow(current)
        self._table.blockSignals(False)
        self._updating = False
        self._problems.setText("\n".join(self._problem_text(p) for p in problems) or tr("No timing problems."))
        self._split_btn.setEnabled(n > 0)
        self._merge_btn.setEnabled(n > 1)

    def _duration(self) -> Optional[float]:
        return self._audio_seconds or None

    def _problem_text(self, problem: tuple) -> str:
        kind = problem[0]
        if kind == "overlap":
            return tr("Cue {0} starts before the cue above it ends.").format(problem[1] + 1)
        if kind == "short":
            return tr("Cue {0} is too short to read: it needs {1:.2f} s.").format(problem[1] + 1, problem[2])
        if kind == "past_end":
            return tr("Cue {0} ends after the end of the clip.").format(problem[1] + 1)
        return tr("The subtitle block has {0} lines and {1} cues.").format(problem[1], problem[2])

    def _selected_row(self) -> int:
        return self._table.currentRow()

    def _select_row(self, index: int) -> None:
        if 0 <= index < self._table.rowCount():
            self._table.selectRow(index)

    def _on_selection(self) -> None:
        if self._updating:
            return
        self._strip.set_selected(self._selected_row())

    # -- editing -----------------------------------------------------------------

    def _strip_changed(self, timing: Timing) -> None:
        self._timing = timing
        self._changed()

    def _cell_edited(self, item: QTableWidgetItem) -> None:
        if self._updating or item.column() not in (1, 2):
            return
        row = item.row()
        try:
            value = float(item.text().replace(",", "."))
        except ValueError:
            self._refresh()
            return
        edge = "start" if item.column() == 1 else "end"
        self._timing = st.set_edge(self._timing, row, edge, st.frames_of(value))
        self._changed()

    def _offset_changed(self, value: float) -> None:
        if self._updating:
            return
        self._timing = replace(self._timing, offset=st.frames_of(value))
        self._changed()

    def _nudge(self, frames: int) -> None:
        row = self._selected_row()
        if 0 <= row < len(self._timing.cues):
            self._timing = st.move(self._timing, row, frames)
            self._changed()

    def _reset(self) -> None:
        if not self._spans:
            return
        self._timing = st.from_spans(self._spans, self._timing.offset)
        self._changed(tr("Reset to the speech spans of the audio. Save the timing."))

    def _split(self) -> None:
        row = self._selected_row()
        if 0 <= row < len(self._timing.cues):
            self._timing = st.split(self._timing, row)
            self._source.insert(row + 1, "")
            self._translation.insert(row + 1, "")
            self._changed(tr("Cue split. Write the second half's text in the subtitle block, then save the timing."))

    def _merge(self) -> None:
        row = self._selected_row()
        if not (0 <= row < len(self._timing.cues) - 1):
            return
        if self._translation[row + 1].strip():
            self._status.setText(tr("Clear the translated text of cue {0} first, then merge.").format(row + 2))
            return
        self._timing = st.merge(self._timing, row)
        del self._source[row + 1]
        del self._translation[row + 1]
        self._changed(tr("Cues merged. Save the timing."))

    # -- playback ----------------------------------------------------------------

    def _play(self) -> None:
        if self._play_file:
            self._start_playback()
        else:
            self._run(self._rules.subtitle_play_file, (self._project_dir,), self._play_ready)

    def _play_ready(self, path: str) -> None:
        self._play_file = path
        self._player.setSource(QUrl.fromLocalFile(path))
        self._start_playback()

    def _start_playback(self) -> None:
        self._player.setPosition(0)
        self._player.play()
        self._tick_timer.start()

    def _stop(self) -> None:
        self._player.stop()
        self._tick_timer.stop()
        self._strip.set_playhead(None)
        self._box.setText("")

    def _tick(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
            self._stop()
            return
        frame = self._player.position() * FPS / 1000.0
        self._strip.set_playhead(frame)
        texts = [_TAG.sub("", t).strip() for t in self._translation]
        shown = ""
        for i, (a, b) in enumerate(self._timing.frames(len(self._timing.cues))):
            if a <= frame < b and i < len(texts):
                shown = texts[i]
        self._box.setText(shown)

    # -- save --------------------------------------------------------------------

    def _save(self) -> None:
        self._run(self._rules.save_subtitle_timing, (self._project_dir, self._timing), self._saved)

    def _saved(self, path: str) -> None:
        self._dirty = False
        self._status.setText(tr("Saved {0}. Save the project to write the subtitle lines with this timing.")
                             .format(Path(path).name))

    def closeEvent(self, event) -> None:
        if self._dirty and self._job is None and self.isVisible():
            answer = QMessageBox.question(self, tr("Voice subtitles timing"),
                                          tr("The timing has changes that are not saved. Close anyway?"))
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._stop()
        super().closeEvent(event)
