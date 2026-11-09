"""The prompt editor's Notes field: saved per row, prefilled next time, sent at the end of the request."""
from types import SimpleNamespace

from PyQt6.QtWidgets import QDialog

import handlers.translation.facade.session_mixin as session_module
from components.prompt_editor_dialog import PromptEditorDialog
from handlers.translation.facade.session_mixin import SessionMixin
from handlers.translation.prompt_composer.instructions import AI_NOTES, append_translator_notes

KEY = (182, 26)


class _Settings:
    def __init__(self):
        self.saves = 0

    def save_settings(self):
        self.saves += 1


class _Host(SessionMixin):
    def __init__(self, editor_enabled: bool):
        self.mw = SimpleNamespace(
            string_metadata={KEY: {"width": 240}}, prompt_editor_enabled=editor_enabled, settings_manager=_Settings()
        )
        self.glossary_handler = SimpleNamespace(_current_prompts_path=None)


class _FakeDialog:
    """Accepts with the notes the user typed; records what the dialog was opened with."""
    typed = ""
    opened_with = None

    def __init__(self, *, notes=None, **_kwargs):
        type(self).opened_with = notes

    def exec(self):
        return QDialog.DialogCode.Accepted

    def get_user_inputs(self):
        return "sys", "user", False

    def notes(self):
        return type(self).typed


def test_dialog_shows_notes_field_only_for_a_row(qtbot):
    with_notes = PromptEditorDialog(title="t", system_prompt="s", user_prompt="u", notes="keep it short")
    without = PromptEditorDialog(title="t", system_prompt="s", user_prompt="u")
    qtbot.addWidget(with_notes)
    qtbot.addWidget(without)

    assert with_notes._splitter.count() == 3
    assert with_notes.notes() == "keep it short"
    assert without._splitter.count() == 2
    assert without.notes() == ""


def test_notes_are_saved_prefilled_and_sent(monkeypatch):
    monkeypatch.setattr(session_module, "PromptEditorDialog", _FakeDialog)
    host = _Host(editor_enabled=True)

    _FakeDialog.typed = "Use a softer word than «мелодія»."
    _, user = host._maybe_edit_prompt(title="t", system_prompt="s", user_prompt="x", notes_key=KEY)
    assert user == append_translator_notes("user", _FakeDialog.typed)
    assert user.endswith(_FakeDialog.typed)
    assert host.mw.string_metadata[KEY] == {"width": 240, AI_NOTES: _FakeDialog.typed}

    assert host.mw.settings_manager.saves == 1

    # Refresh: the dialog opens again with the same notes; unchanged notes are not saved again.
    host._maybe_edit_prompt(title="t", system_prompt="s", user_prompt="x", notes_key=KEY)
    assert _FakeDialog.opened_with == "Use a softer word than «мелодія»."
    assert host.mw.settings_manager.saves == 1

    # Emptied field: the notes go, the row's other settings stay.
    _FakeDialog.typed = ""
    _, user = host._maybe_edit_prompt(title="t", system_prompt="s", user_prompt="x", notes_key=KEY)
    assert user == "user"
    assert host.mw.string_metadata[KEY] == {"width": 240}


def test_saved_notes_are_sent_when_the_editor_is_off():
    host = _Host(editor_enabled=False)
    host.set_row_notes(KEY, "Keep the pun.")

    _, user = host._maybe_edit_prompt(title="t", system_prompt="s", user_prompt="body", notes_key=KEY)

    assert user == append_translator_notes("body", "Keep the pun.")
    assert host._maybe_edit_prompt(title="t", system_prompt="s", user_prompt="body") == ("s", "body")


def test_last_note_removal_drops_the_row_entry():
    host = _Host(editor_enabled=False)
    host.mw.string_metadata.clear()
    host.set_row_notes(KEY, "x")
    host.set_row_notes(KEY, "")
    assert KEY not in host.mw.string_metadata
