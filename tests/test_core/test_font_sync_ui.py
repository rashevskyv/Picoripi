"""The copy-changes checkbox and the one-time question of a linked font pair (pytest-qt, a minimal widget)."""
from PyQt6 import QtWidgets

from tools.bfn_editor.io_format_mixin import IoFormatMixin


class Partner:
    label = "file select"


class Source:
    label = "name entry"
    sync_partner = Partner()


class Window(QtWidgets.QWidget, IoFormatMixin):
    """The mixin's candidate methods on a widget with a status bar and a project mapping."""

    def __init__(self):
        super().__init__()
        self.status = QtWidgets.QStatusBar(self)
        self.pairs = {}
        self.saved = 0

    def _sync_pairs(self):
        return self.pairs

    def _save_sync_pairs(self):
        self.saved += 1


def test_the_checkbox_is_off_by_default_and_the_question_is_shown_once(qtbot):
    window = Window()
    qtbot.addWidget(window)
    window._set_sync_candidate(Source(), Source.sync_partner)
    checkbox = window.sync_checkbox
    assert checkbox.text() == "Copy changes to: file select"
    assert checkbox.isChecked() is False
    assert window._sync_prompt.isModal() is False                 # the question does not block the editor
    assert window.pairs["file select|name entry"]["prompted"] is True
    window._sync_prompt = None
    window._set_sync_candidate(Source(), Source.sync_partner)     # the same pair again: no second question
    assert window._sync_prompt is None


def test_ticking_the_checkbox_turns_the_pair_on_and_is_remembered(qtbot):
    window = Window()
    qtbot.addWidget(window)
    window._set_sync_candidate(Source(), Source.sync_partner)
    window._sync_prompt = None
    window.sync_checkbox.setChecked(True)
    assert window.pairs["file select|name entry"]["enabled"] is True
    assert window.saved >= 1
    window._set_sync_candidate(Source(), Source.sync_partner)     # reopened: the checkbox remembers the pair
    assert window.sync_checkbox.isChecked() is True
