import pytest
from unittest.mock import MagicMock, call, patch
from PyQt5.QtGui import QColor, QTextDocument, QFont, QTextCharFormat, QPen
from PyQt5.QtCore import Qt
from utils.syntax_highlighter import JsonTagHighlighter
from core.glossary_manager import GlossaryMatch

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.data_store = mw
    mw.theme = 'light'
    mw.current_game_rules = MagicMock()
    mw.current_game_rules.get_syntax_highlighting_rules.return_value = [
        (r"(\[CustomRule\])", QTextCharFormat())
    ]
    mw.icon_sequences = ['[Icon1]', '[Icon2]']
    
    spellchecker = MagicMock()
    spellchecker.enabled = True
    spellchecker.is_misspelled.return_value = False
    mw.spellchecker_manager = spellchecker
    
    return mw

@pytest.fixture
def highlighter(qapp, mock_mw):
    doc = QTextDocument()
    editor_mock = MagicMock()
    editor_mock.objectName.return_value = 'edited_text_edit'
    
    hl = JsonTagHighlighter(doc, main_window_ref=mock_mw, editor_widget_ref=editor_mock)
    hl.setFormat = MagicMock()
    hl.setCurrentBlockState = MagicMock()
    hl.setCurrentBlockUserData = MagicMock()
    return hl, doc

def test_JsonTagHighlighter_init_and_reconfigure(highlighter, mock_mw):
    hl, doc = highlighter
    assert hl.default_text_color.isValid()
    assert len(hl.custom_rules) == 1

def test_JsonTagHighlighter_on_contents_change(highlighter):
    hl, doc = highlighter
    hl._icon_sequences_cache[0] = [(0, 5)]
    hl.on_contents_change(0, 0, 1)
    assert len(hl._icon_sequences_cache) == 0

def test_JsonTagHighlighter_set_glossary_manager(highlighter):
    hl, doc = highlighter
    hl.rehighlight = MagicMock()
    
    gm = MagicMock()
    gm.get_entries.return_value = {"Test": "Test"}
    
    hl.set_glossary_manager(gm)
    assert hl._glossary_enabled is True
    assert hl._glossary_manager == gm
    hl.rehighlight.assert_called_once()

def test_JsonTagHighlighter_set_spellchecker_enabled(highlighter):
    hl, doc = highlighter
    hl.rehighlight = MagicMock()
    
    hl.set_spellchecker_enabled(True)
    assert hl._spellchecker_enabled is True
    hl.rehighlight.assert_called_once()
    
    # Should not rehighlight if state is same
    hl.rehighlight.reset_mock()
    hl.set_spellchecker_enabled(True)
    hl.rehighlight.assert_not_called()

def test_JsonTagHighlighter_apply_css_to_format(highlighter):
    hl, doc = highlighter
    fmt = QTextCharFormat()
    
    hl._apply_css_to_format(fmt, "color: #FF0000; background-color: #00FF00; font-weight: bold; font-style: italic; text-decoration: underline")
    assert fmt.foreground().color().name().upper() == "#FF0000"
    assert fmt.background().color().name().upper() == "#00FF00"
    assert fmt.fontWeight() == QFont.Bold
    assert fmt.fontItalic() is True
    assert fmt.fontUnderline() is True
    
    # test normal and default values
    hl._apply_css_to_format(fmt, "font-weight: normal; font-style: normal; text-decoration: none", base_color=QColor("blue"))
    assert fmt.fontWeight() == QFont.Normal
    assert fmt.fontItalic() is False
    assert fmt.fontUnderline() is False
    assert fmt.foreground().color().name().upper() == "#0000FF"

def test_JsonTagHighlighter_highlightBlock_colors(highlighter):
    hl, doc = highlighter
    
    # Test WW colors
    text_ww = "[Red]Test[/C]"
    hl.highlightBlock(text_ww)
    # Should set red state, then back to default
    
    # Test MC colors
    text_mc = "{Color:Blue}Test"
    hl.highlightBlock(text_mc)
    
def test_JsonTagHighlighter_highlightBlock_rules(highlighter):
    hl, doc = highlighter
    text = "{Tag} [Bracket] \\n [CustomRule]"
    hl.highlightBlock(text)
    # Should find 4 formats matching our rules
    assert hl.setFormat.call_count >= 4

def test_JsonTagHighlighter_icon_cache(highlighter):
    hl, doc = highlighter
    doc.setPlainText("Hello [Icon1] World")
    
    hl._get_icon_sequences = MagicMock(return_value=["[Icon1]"])
    hl._should_highlight_icons = MagicMock(return_value=True)
    hl.currentBlock = MagicMock()
    hl.currentBlock().blockNumber.return_value = 0
    
    matches = hl._get_icon_matches_for_block(["[Icon1]"])
    assert len(matches) == 1
    assert matches[0] == (6, 7) # index 6, length 7

def test_JsonTagHighlighter_glossary_cache(highlighter, mock_mw):
    hl, doc = highlighter
    doc.setPlainText("GlossaryTerm")
    
    mock_entry = MagicMock()
    match = GlossaryMatch(entry=mock_entry, start=0, end=12)
    
    gm = MagicMock()
    gm.get_entries.return_value = {"GlossaryTerm": mock_entry}
    gm.find_matches.return_value = [match]
    
    hl.set_glossary_manager(gm)
    
    hl.currentBlock = MagicMock()
    hl.currentBlock().blockNumber.return_value = 0
    
    hl.highlightBlock("GlossaryTerm")
    
    args, kwargs = hl.setCurrentBlockUserData.call_args
    user_data = args[0]
    assert user_data is not None
    assert len(user_data.matches) == 1

def test_JsonTagHighlighter_spellcheck(highlighter, mock_mw):
    hl, doc = highlighter
    hl.set_spellchecker_enabled(True)
    
    mock_mw.spellchecker_manager.is_misspelled.return_value = True
    
    text = "MisspelledWord"
    hl.highlightBlock(text)
    
    # Set format should be called once for the whole word plus the basic format at the start
    assert hl.setFormat.call_count >= 2

def test_JsonTagHighlighter_theme_dark(qapp):
    doc = QTextDocument()
    mw = MagicMock()
    mw.data_store = mw
    mw.theme = 'dark'
    hl = JsonTagHighlighter(doc, main_window_ref=mw)
    assert hl.default_text_color.name().upper() == "#E0E0E0"

def test_extract_words_from_text(highlighter):
    hl, doc = highlighter
    words = hl._extract_words_from_text("Hello punctuation World")
    assert len(words) == 3
    assert words[0][2] == "Hello" 
    assert words[1][2] == "punctuation"
    assert words[2][2] == "World"

def test_should_highlight_icons_for_preview(highlighter, mock_mw):
    hl, doc = highlighter
    # Set parent to simulate preview_text_edit
    parent_mock = MagicMock()
    parent_mock.objectName.return_value = 'preview_text_edit'
    doc.parent = MagicMock(return_value=parent_mock)
    
    assert hl._should_highlight_icons() is False
    
    parent_mock.objectName.return_value = 'edited_text_edit'
    assert hl._should_highlight_icons() is True
