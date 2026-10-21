"""The Font Editor window is closed when the project it was opened for is replaced or closed (handlers/project_action)."""
from types import SimpleNamespace

from handlers.project_action.session_mixin import SessionMixin


class _Handler(SessionMixin):
    def __init__(self, editor):
        self.mw = SimpleNamespace(_bfn_editor_window=editor)


class _Editor:
    def __init__(self, closes=True, gone=False):
        self.closes = closes
        self.gone = gone
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        if self.gone:
            raise RuntimeError("wrapped C/C++ object has been deleted")
        return self.closes


def test_an_open_editor_is_closed_and_forgotten():
    editor = _Editor()
    handler = _Handler(editor)
    handler._close_font_editor_of_old_project()
    assert editor.close_calls == 1
    assert handler.mw._bfn_editor_window is None


def test_a_cancelled_close_keeps_the_window():
    editor = _Editor(closes=False)
    handler = _Handler(editor)
    handler._close_font_editor_of_old_project()
    assert handler.mw._bfn_editor_window is editor


def test_a_deleted_qt_window_is_forgotten():
    handler = _Handler(_Editor(gone=True))
    handler._close_font_editor_of_old_project()
    assert handler.mw._bfn_editor_window is None


def test_no_editor_is_fine():
    handler = _Handler(None)
    handler._close_font_editor_of_old_project()
    assert handler.mw._bfn_editor_window is None
