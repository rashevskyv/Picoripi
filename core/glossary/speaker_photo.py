"""Bounded, portable speaker photo data and background decoding."""
from __future__ import annotations

import base64
import copy
import binascii
import json
from pathlib import Path
from dataclasses import replace
from datetime import datetime, timezone

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, pyqtSignal
from PyQt6.QtGui import QImage, QImageReader

from core.i18n import tr
from core.glossary.notes import _entry_to_dict
from utils.thread_utils import WorkerThread
from utils.atomic_io import atomic_write_text

MAX_ENCODED_BYTES = 2 * 1024 * 1024
MAX_IMAGE_DIMENSION = 2048


def photo_data_from_bytes(raw: bytes) -> str:
    """Validate image bytes and return a portable data URL for JSON storage."""
    if not raw or len(raw) > MAX_ENCODED_BYTES:
        raise ValueError("Photo must be smaller than 2 MiB.")
    image = _read_image(raw)
    if image.isNull():
        raise ValueError("File is not a supported image.")
    output = QByteArray()
    buffer = QBuffer(output)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG") or output.size() > MAX_ENCODED_BYTES:
        raise ValueError("Photo could not be stored within the size limit.")
    return "data:image/png;base64," + base64.b64encode(bytes(output)).decode("ascii")


def decode_photo_data(data: str) -> QImage:
    """Decode a validated glossary data URL. Call from a worker thread."""
    prefix = "data:image/png;base64,"
    max_data_length = len(prefix) + 4 * ((MAX_ENCODED_BYTES + 2) // 3)
    if not isinstance(data, str) or len(data) > max_data_length or not data.startswith(prefix):
        return QImage()
    try:
        raw = base64.b64decode(data[len(prefix):], validate=True)
    except (binascii.Error, ValueError):
        return QImage()
    if len(raw) > MAX_ENCODED_BYTES:
        return QImage()
    return _read_image(raw)


def _read_image(raw: bytes) -> QImage:
    reader = QImageReader()
    reader.setDecideFormatFromContent(True)
    buffer = QBuffer()
    reader.setDevice(buffer)
    buffer.setData(QByteArray(raw))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    size = reader.size()
    if not size.isValid() or size.width() > MAX_IMAGE_DIMENSION or size.height() > MAX_IMAGE_DIMENSION:
        return QImage()
    return reader.read()


class PhotoDecodeThread(WorkerThread):
    """Decode one bounded photo without blocking the UI thread."""

    loaded = pyqtSignal(str, QImage)

    def __init__(self, token: str, data: str, parent=None):
        super().__init__(parent)
        self.token = token
        self.data = data

    def run(self) -> None:
        if self.isInterruptionRequested():
            return
        image = decode_photo_data(self.data)
        if not self.isInterruptionRequested():
            self.loaded.emit(self.token, image)


class PhotoImportThread(WorkerThread):
    """Read and validate one user-selected photo without blocking the UI."""

    imported = pyqtSignal(str, str, str)

    def __init__(self, token: str, path: str, parent=None):
        super().__init__(parent)
        self.token = token
        self.path = path

    def run(self) -> None:
        if self.isInterruptionRequested():
            return
        try:
            with Path(self.path).open("rb") as source:
                raw = source.read(MAX_ENCODED_BYTES + 1)
            if self.isInterruptionRequested():
                return
            data = photo_data_from_bytes(raw)
            error = ""
        except Exception as exc:
            data = ""
            error = tr(str(exc)) if isinstance(exc, ValueError) else tr(
                "Unable to read the selected photo: {error}", error=exc
            )
        if not self.isInterruptionRequested():
            self.imported.emit(self.token, data, error)


class GlossaryPhotoSaveThread(WorkerThread):
    """Atomically persist a candidate glossary snapshot outside the UI thread."""

    saved = pyqtSignal(int, str, str)

    def __init__(
        self,
        manager,
        entry,
        photo: str,
        *,
        translation: str,
        notes: str,
        profiled: bool,
        section: str,
        user_notes: str,
        parent=None,
    ):
        super().__init__(parent)
        self.manager = manager
        if entry is None:
            raise ValueError("The glossary entry is unavailable.")
        self.original = entry.original
        source_path = manager.glossary_path
        if not source_path:
            raise ValueError("The glossary entry or file is unavailable.")
        self.source_path = source_path
        self.expected_revision = manager._persistence_revision
        self.path = source_path.with_suffix(".json") if source_path.suffix.lower() == ".md" else source_path
        if source_path.suffix.lower() != ".md" and source_path.suffix.lower() != ".json":
            raise ValueError("Photo saving requires a JSON glossary file.")
        source_entries = tuple(manager.get_entries())
        current = next((item for item in source_entries if item.original == self.original), None)
        if current is None:
            raise ValueError("The glossary entry is unavailable.")
        self.entries = tuple(
            replace(
                item,
                translation=translation,
                notes=notes,
                profiled=profiled,
                section=section or None,
                user_notes=user_notes,
                speaker_photo=photo,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            if item.original == self.original else item
            for item in source_entries
        )
        self.tombstones = tuple(dict(item) for item in manager._tombstones)
        self._cache_manager = copy.copy(manager)
        self._cache_manager._entries = list(self.entries)
        self.pattern_cache = None
        self._cancel_requested = False

    def cancel(self) -> None:
        """Request cancellation before the atomic replacement starts."""
        self._cancel_requested = True
        self.requestInterruption()

    def run(self) -> None:
        try:
            raw = json.dumps(
                [_entry_to_dict(entry) for entry in self.entries] + list(self.tombstones),
                ensure_ascii=False,
                indent=2,
            ) + "\n"
            self._cache_manager._build_pattern_cache()
            self.pattern_cache = (
                self._cache_manager._compiled_patterns,
                self._cache_manager._first_word_index,
                self._cache_manager._non_word_patterns,
                self._cache_manager._automaton,
            )
            if self._cancel_requested or self.isInterruptionRequested():
                return
            with self.manager._write_lock:
                if self.manager._persistence_revision != self.expected_revision:
                    raise RuntimeError("The glossary changed before the photo could be saved.")
                if self._cancel_requested or self.isInterruptionRequested():
                    return
                if self.path != self.source_path and self.path.exists():
                    raise RuntimeError("A JSON glossary already exists beside the legacy glossary.")
                if self.path.exists() and self.path != self.manager.glossary_path:
                    raise RuntimeError("A JSON glossary appeared before the photo could be saved.")
                if self.source_path.exists() and self.manager._raw_text:
                    current_disk_text = self.source_path.read_text(encoding="utf-8")
                    current_disk_text = current_disk_text.replace("\ufeff", "")
                    if current_disk_text != self.manager._raw_text:
                        raise RuntimeError("The glossary file changed before the photo could be saved.")
                atomic_write_text(self.path, raw)
                self.manager._persistence_revision += 1
                written_revision = self.manager._persistence_revision
            error = ""
        except Exception as exc:
            raw = ""
            error = tr(str(exc)) if isinstance(exc, (ValueError, RuntimeError)) else tr(
                "Unable to save the glossary photo: {error}", error=exc
            )
            written_revision = self.expected_revision
        if not self._cancel_requested and not self.isInterruptionRequested():
            self.saved.emit(written_revision, raw, error)
