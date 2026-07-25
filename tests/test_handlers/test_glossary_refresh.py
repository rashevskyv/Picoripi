"""Closing the glossary rebuilds virtual folders only when a name changed."""
from unittest.mock import MagicMock

from handlers.translation.glossary_handler import GlossaryHandler
from core.glossary_manager import GlossaryEntry


def _handler():
    handler = GlossaryHandler(MagicMock())
    return handler


def _set_entries(handler, entries):
    handler.glossary_manager.get_entries = MagicMock(return_value=entries)


def _refresh_mock(handler):
    return handler.mw.ui_updater.block_list_updater.refresh_virtual_folder_labels


def test_no_change_does_not_rebuild(qapp):
    handler = _handler()
    _set_entries(handler, [GlossaryEntry("WOMAN 1", "Жінка 1", "", "")])
    handler._glossary_signature_on_open = handler._glossary_signature()
    handler.dialog = MagicMock()

    _refresh_mock(handler).reset_mock()
    handler._on_glossary_dialog_closed()
    _refresh_mock(handler).assert_not_called()


def test_translation_change_rebuilds(qapp):
    handler = _handler()
    handler._glossary_signature_on_open = (("WOMAN 1", "Жінка 1"),)
    _set_entries(handler, [GlossaryEntry("WOMAN 1", "Жінка 001", "", "")])
    handler.dialog = MagicMock()

    _refresh_mock(handler).reset_mock()
    handler._on_glossary_dialog_closed()
    _refresh_mock(handler).assert_called_once()


def test_notes_only_change_does_not_rebuild(qapp):
    handler = _handler()
    handler._glossary_signature_on_open = (("WOMAN 1", "Жінка 1"),)
    _set_entries(handler, [GlossaryEntry("WOMAN 1", "Жінка 1", "new note", "")])
    handler.dialog = MagicMock()

    _refresh_mock(handler).reset_mock()
    handler._on_glossary_dialog_closed()
    _refresh_mock(handler).assert_not_called()
