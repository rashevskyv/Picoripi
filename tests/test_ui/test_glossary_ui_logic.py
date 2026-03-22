import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QTextCursor
from PyQt5.QtCore import QPoint, Qt
from components.editor.line_numbered_text_edit import LineNumberedTextEdit
from handlers.translation.glossary_prompt_manager import GlossaryPromptManager
from core.glossary_manager import GlossaryManager, GlossaryEntry

def test_glossary_highlighting_updates_all_editors(mock_mw):
    """
    Test that _update_glossary_highlighting updates all three editors:
    original_text_edit, edited_text_edit, and preview_text_edit.
    Currently, it only updates original_text_edit.
    """
    # Setup mocks for editors
    mock_mw.original_text_edit = MagicMock(spec=LineNumberedTextEdit)
    mock_mw.edited_text_edit = MagicMock(spec=LineNumberedTextEdit)
    mock_mw.preview_text_edit = MagicMock(spec=LineNumberedTextEdit)
    
    # Mock GlossaryManager with some entries
    mock_glossary = MagicMock(spec=GlossaryManager)
    mock_glossary.get_entries.return_value = [GlossaryEntry("Link", "Лінк")]
    
    # Initialize GlossaryPromptManager
    main_handler = MagicMock()
    gpm = GlossaryPromptManager(mock_mw, main_handler, mock_glossary)
    
    # Trigger update
    gpm._update_glossary_highlighting()
    
    # Verify set_glossary_manager was called for ALL editors
    # FAILURE EXPECTED HERE: Currently only original_text_edit is updated
    mock_mw.original_text_edit.set_glossary_manager.assert_called_once_with(mock_glossary)
    mock_mw.edited_text_edit.set_glossary_manager.assert_called_once_with(mock_glossary)
    mock_mw.preview_text_edit.set_glossary_manager.assert_called_once_with(mock_glossary)

def test_glossary_entry_finding_uses_correct_attributes(qapp):
    """
    Test that _find_glossary_entry_at finds the entry via block userData.
    """
    # Create real editor
    editor = LineNumberedTextEdit()
    
    # Mock GlossaryManager
    mock_glossary = MagicMock()
    editor.set_glossary_manager(mock_glossary)
    
    # Simulate text
    editor.setPlainText("Link")
    
    from utils.syntax_highlighter import JsonTagHighlighter
    from core.glossary_manager import GlossaryMatch
    
    # Mock cursorForPosition to return a valid block/position
    mock_cursor = MagicMock()
    block = mock_cursor.block()
    block.isValid.return_value = True
    block.blockNumber.return_value = 0
    mock_cursor.positionInBlock.return_value = 0
    
    # Setup userData matches
    entry = GlossaryEntry("Link", "Лінк")
    matches = [GlossaryMatch(entry=entry, start=0, end=4)]
    block.userData.return_value = JsonTagHighlighter.GlossaryBlockData(matches)
    
    editor.cursorForPosition = MagicMock(return_value=mock_cursor)
    
    # Now it should find the entry via userData
    result = editor._find_glossary_entry_at(QPoint(0, 0))
    assert result is not None
    assert result.original == "Link"

@patch('PyQt5.QtWidgets.QToolTip.showText')
def test_glossary_tooltip_shows_correct_text(mock_show_text, qapp):
    """
    Test that mouseMoveEvent triggers tooltip showing for glossary entry.
    """
    editor = LineNumberedTextEdit()
    entry = GlossaryEntry("Link", "Лінк", "Hero of Time")
    
    # Mock _find_glossary_entry_at to return our entry
    editor._find_glossary_entry_at = MagicMock(return_value=entry)
    
    # Simulate mouse move
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtCore import QEvent
    
    event = QMouseEvent(QEvent.MouseMove, QPoint(5, 5), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
    editor.mouseMoveEvent(event)
    
    # Verify QToolTip.showText was called with correct content
    assert mock_show_text.called
    args = mock_show_text.call_args[0]
    tooltip_text = args[1]
    assert "<b>Link</b> → Лінк" in tooltip_text
    assert "<i>Hero of Time</i>" in tooltip_text


def test_glossary_highlighted_after_set_plain_text(qapp):
    """
    Regression test for the bug:
    When set_glossary_manager() is called BEFORE the editor has text
    (which happens on project open), the rehighlight() inside
    set_glossary_manager runs on an empty document — so no block
    data is stored.  After that, setPlainText() with real text was
    called but nothing triggered a second rehighlight, leaving the
    glossary underlines missing entirely.

    Fix: LineNumberedTextEdit.setPlainText() now calls
    highlighter.rehighlight() when _glossary_enabled is True.

    This test would FAIL without that fix.
    """
    editor = LineNumberedTextEdit()
    from utils.syntax_highlighter import JsonTagHighlighter
    from core.glossary_manager import GlossaryManager

    # 1. Build a real glossary manager with one entry
    glossary_mgr = GlossaryManager()
    glossary_md = "| Original | Translation | Notes |\n|---|---|---|\n| Link | Лінк | |"
    glossary_mgr.load_from_text(
        plugin_name="test",
        glossary_path=None,
        raw_text=glossary_md,
    )
    assert glossary_mgr.get_entries(), "Glossary should have entries after loading"

    # 2. Set glossary manager while the editor is EMPTY (simulates startup)
    editor.set_glossary_manager(glossary_mgr)
    assert editor.highlighter._glossary_enabled, \
        "Highlighter should be enabled after set_glossary_manager with entries"

    # 3. Now set text that contains a glossary term — this is when the bug fired
    editor.setPlainText("Link is the hero.")

    # 4. The first block should now have glossary match data stored by the highlighter
    block = editor.document().firstBlock()
    user_data = block.userData()
    assert user_data is not None, \
        "Block userData should be set by JsonTagHighlighter after setPlainText. " \
        "Without the rehighlight() call in setPlainText this would be None."
    assert hasattr(user_data, 'matches'), "userData should have 'matches' attribute"
    assert len(user_data.matches) > 0, \
        "Block should have at least one glossary match for 'Link'. " \
        "Without the fix (rehighlight after setPlainText) this list would be empty."
