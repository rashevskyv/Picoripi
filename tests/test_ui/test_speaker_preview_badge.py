"""Speaker preview badge updates through a real Qt label and worker thread."""
import json
from types import SimpleNamespace

from PyQt6 import sip
from PyQt6.QtCore import QByteArray, QBuffer, QIODevice
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QComboBox, QLabel, QWidget

from core.glossary.manager import GlossaryManager
from core.glossary.speaker_photo import photo_data_from_bytes
from ui.updaters.text_views_mixin import TextViewsMixin
from utils.thread_utils import safe_shutdown_thread


def test_badge_shows_glossary_photo_and_description(qtbot):
    source = QImage(4, 4, QImage.Format.Format_ARGB32)
    source.fill(QColor("#2080d0"))
    raw = QByteArray()
    buffer = QBuffer(raw)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert source.save(buffer, "PNG")
    photo = photo_data_from_bytes(bytes(raw))

    manager = GlossaryManager()
    manager.load_from_text(
        plugin_name=None,
        glossary_path=None,
        raw_text=json.dumps([{
            "original": "Zora", "translation": "Зора", "notes": "Sea dweller",
            "speaker_photo": photo,
        }]),
    )
    window = QWidget()
    badge = QLabel(window)
    combo = QComboBox(window)
    combo.addItem("Зора")
    window.speaker_preview_badge = badge
    window.speaker_combobox = combo
    window.translation_handler = SimpleNamespace(_glossary_manager=manager)
    window.active_game_plugin = "sample"
    class Updater(TextViewsMixin):
        def __init__(self, mw):
            self.mw = mw

    updater = Updater(window)
    qtbot.addWidget(window)

    TextViewsMixin.update_speaker_preview_badge(updater)
    qtbot.waitUntil(lambda: badge.pixmap() is not None and not badge.pixmap().isNull())

    assert "Sea dweller" in badge.toolTip()
    safe_shutdown_thread(updater._speaker_photo_thread, timeout_ms=250)


def test_late_photo_callback_after_window_delete_is_safe(qtbot):
    window = QWidget()
    window.speaker_preview_badge = QLabel(window)

    class Updater(TextViewsMixin):
        def __init__(self, mw):
            self.mw = mw

    updater = Updater(window)
    updater._speaker_photo_token = ("sample", "Zora")
    qtbot.addWidget(window)
    sip.delete(window)
    image = QImage(2, 2, QImage.Format.Format_ARGB32)
    image.fill(QColor("red"))
    updater._speaker_photo_loaded(repr(updater._speaker_photo_token), image)
