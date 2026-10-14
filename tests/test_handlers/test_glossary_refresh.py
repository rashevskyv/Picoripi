"""Closing the glossary rebuilds virtual folders only when a name changed."""
from unittest.mock import MagicMock

from handlers.translation.glossary_handler import GlossaryHandler
from core.glossary_manager import GlossaryEntry


def _handler():
    handler = GlossaryHandler(MagicMock())
    return handler


def _set_entries(handler, entries):
    handler.glossary_manager.get_entries = MagicMock(return_value=entries)


def _record_refreshes(handler):
    """Replace the virtual folder label refresh with a recorder; return the list of calls."""
    calls = []
    handler.mw.ui_updater.block_list_updater.refresh_virtual_folder_labels = lambda *args, **kwargs: calls.append(True)
    return calls


def test_no_change_does_not_rebuild(qapp):
    handler = _handler()
    _set_entries(handler, [GlossaryEntry("WOMAN 1", "Жінка 1", "", "")])
    handler._glossary_signature_on_open = handler._glossary_signature()
    handler.dialog = MagicMock()

    refreshes = _record_refreshes(handler)
    handler._on_glossary_dialog_closed()
    assert refreshes == []


def test_translation_change_rebuilds(qapp):
    handler = _handler()
    handler._glossary_signature_on_open = (("WOMAN 1", "Жінка 1"),)
    _set_entries(handler, [GlossaryEntry("WOMAN 1", "Жінка 001", "", "")])
    handler.dialog = MagicMock()

    refreshes = _record_refreshes(handler)
    handler._on_glossary_dialog_closed()
    assert refreshes == [True]


def test_notes_only_change_does_not_rebuild(qapp):
    handler = _handler()
    handler._glossary_signature_on_open = (("WOMAN 1", "Жінка 1"),)
    _set_entries(handler, [GlossaryEntry("WOMAN 1", "Жінка 1", "new note", "")])
    handler.dialog = MagicMock()

    refreshes = _record_refreshes(handler)
    handler._on_glossary_dialog_closed()
    assert refreshes == []
