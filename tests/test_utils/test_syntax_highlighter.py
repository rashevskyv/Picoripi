import pytest
from unittest.mock import MagicMock
from PyQt6.QtGui import QColor, QTextDocument, QFont, QTextCharFormat
from utils.syntax_highlighter import JsonTagHighlighter

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
    assert fmt.fontWeight() == QFont.Weight.Bold.value
    assert fmt.fontItalic() is True
    assert fmt.fontUnderline() is True

    # test normal and default values
    hl._apply_css_to_format(fmt, "font-weight: normal; font-style: normal; text-decoration: none", base_color=QColor("blue"))
    assert fmt.fontWeight() == QFont.Weight.Normal.value
    assert fmt.fontItalic() is False
    assert fmt.fontUnderline() is False
    assert fmt.foreground().color().name().upper() == "#0000FF"

def test_JsonTagHighlighter_highlightBlock_colors(highlighter):
    hl, doc = highlighter

    # Test WW colors
    hl.setFormat.reset_mock()
    text_ww = "[Red]Test[/C]"
    hl.highlightBlock(text_ww)
    # Should set red state for "Test" (index 5, length 4)
    red_calls = [args for args, _ in hl.setFormat.call_args_list if args[0] == 5 and args[1] == 4 and args[2] == hl.red_text_format]
    assert len(red_calls) == 1

    # Test MC colors
    hl.setFormat.reset_mock()
    text_mc = "{Color:Blue}Test"
    hl.highlightBlock(text_mc)
    # Should set blue state for "Test" (index 12, length 4)
    blue_calls = [args for args, _ in hl.setFormat.call_args_list if args[0] == 12 and args[1] == 4 and args[2] == hl.blue_text_format]
    assert len(blue_calls) == 1

def test_JsonTagHighlighter_highlightBlock_rules(highlighter):
    hl, doc = highlighter
    text = "{Tag} [Bracket] \\n [CustomRule]"
    hl.highlightBlock(text)
    # Should find 4 formats matching our rules
    assert hl.setFormat.call_count >= 4

def test_JsonTagHighlighter_forced_alias_spacing(highlighter):
    hl, doc = highlighter
    hl._editor_widget_ref.objectName.return_value = 'edited_text_edit'
    hl.setFormat.reset_mock()
    hl.highlightBlock("{F:Link} safely along it.")
    for call_args in hl.setFormat.call_args_list:
        start, length, fmt = call_args[0]
        assert fmt != hl.bad_spacing_format

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
    mock_entry.original = "GlossaryTerm"
    mock_entry.translation = "Translation"
    mock_entry.notes = "Notes"

    hl._glossary_enabled = True
    hl.set_async_highlights(
        glossary_matches=[{
            'start': 0,
            'end': 12,
            'original': "GlossaryTerm",
            'translation': "Translation",
            'notes': "Notes"
        }],
        translation_matches=[],
        spellcheck_matches=[]
    )

    hl.currentBlock = MagicMock()
    hl.currentBlock().blockNumber.return_value = 0
    hl.currentBlock().position.return_value = 0

    hl.highlightBlock("GlossaryTerm")

    args, kwargs = hl.setCurrentBlockUserData.call_args
    user_data = args[0]
    assert user_data is not None
    assert len(user_data.matches) == 1

def test_JsonTagHighlighter_spellcheck(highlighter, mock_mw):
    hl, doc = highlighter
    hl.set_spellchecker_enabled(True)

    hl.set_async_highlights(
        glossary_matches=[],
        translation_matches=[],
        spellcheck_matches=[(0, 14)]
    )

    hl.currentBlock = MagicMock()
    hl.currentBlock().position.return_value = 0

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

def test_JsonTagHighlighter_translation_glossary_bridge(qapp, mock_mw):
    from core.glossary_manager import GlossaryManager, GlossaryEntry

    # 1. Setup glossary manager with a term
    gm = GlossaryManager()
    entry = GlossaryEntry(original="Hyrule", translation="Гайрул", notes="World")
    gm._entries = [entry]
    gm._build_pattern_cache()

    doc = QTextDocument()

    # 2. Setup original editor with text containing dot representations of spaces
    orig_editor = MagicMock()
    orig_editor.toPlainText.return_value = "Kingdom·of·Hyrule"

    edited_editor_mock = MagicMock()
    edited_editor_mock.objectName.return_value = 'edited_text_edit'

    hl = JsonTagHighlighter(doc, main_window_ref=mock_mw, editor_widget_ref=edited_editor_mock)
    hl.set_glossary_manager(gm)

    # Enable translation mode
    hl.set_translation_mode(True, source_editor_ref=orig_editor)

    # Mocking block methods for highlightBlock
    hl.currentBlock = MagicMock()
    hl.currentBlock().blockNumber.return_value = 0
    hl.currentBlock().position.return_value = 0

    hl.setFormat = MagicMock()
    hl.setCurrentBlockUserData = MagicMock()

    # Trigger rebuild translation glossary cache manually
    hl._rebuild_translation_glossary_cache()

    # Verify the cache has correctly matched "Гайрул" in the translation text "королівство Гайрул"
    text_trans = "королівство Гайрул"
    doc.setPlainText(text_trans)
    hl.highlightBlock(text_trans)

    # Should find translation matches and apply formats
    args, kwargs = hl.setCurrentBlockUserData.call_args
    user_data = args[0]
    assert user_data is not None
    assert len(user_data.matches) == 1
    assert user_data.matches[0].entry.original == "Hyrule"
    assert user_data.matches[0].entry.translation == "Гайрул"

    # Verify setFormat was called with format having fontUnderline == True
    underline_calls = []
    for c in hl.setFormat.call_args_list:
        args, kwargs = c
        if len(args) >= 3 and args[2].fontUnderline():
            underline_calls.append(args)
    assert len(underline_calls) == 1
    assert underline_calls[0][0] == 12  # "Гайрул" index in "королівство Гайрул"
    assert underline_calls[0][1] == 6   # Length of "Гайрул"

def test_translation_glossary_underlining_lifecycle(qapp, mock_mw):
    from core.glossary_manager import GlossaryManager, GlossaryEntry
    from components.editor.line_numbered_text_edit import LineNumberedTextEdit

    # 1. Setup glossary
    gm = GlossaryManager()
    entry = GlossaryEntry(original="Castle", translation="Замок", notes="Location")
    gm._entries = [entry]
    gm._build_pattern_cache()

    # Setup mock window with fields needed by LineNumberedTextEdit
    mw = mock_mw
    mw.original_text_edit = LineNumberedTextEdit(parent=None)
    mw.original_text_edit.highlighter.mw = mw
    mw.original_text_edit.setObjectName("original_text_edit")
    mw.original_text_edit.setPlainText("Castle")

    edited_edit = LineNumberedTextEdit(parent=None)
    edited_edit.highlighter.mw = mw
    edited_edit.setObjectName("edited_text_edit")
    mw.edited_text_edit = edited_edit

    # Set glossary and translation mode
    edited_edit.set_glossary_manager(gm)
    edited_edit.highlighter.set_translation_mode(True, source_editor_ref=mw.original_text_edit)

    # 2. Simulate text change / typing lifecycle - First setPlainText
    edited_edit.setPlainText("Тут є Замок")
    edited_edit.highlighter.rehighlight()

    # Verify that the word "Замок" is marked for underlining in block user data
    block = edited_edit.document().firstBlock()
    user_data = block.userData()
    assert user_data is not None
    assert len(user_data.matches) == 1
    assert user_data.matches[0].entry.original == "Castle"
    assert user_data.matches[0].entry.translation == "Замок"

    # Verify that underline is actually applied in document layout formats
    formats = block.layout().formats()
    underlined_formats = [f for f in formats if f.format.fontUnderline()]
    assert len(underlined_formats) >= 1
    assert any(f.format.underlineStyle() == QTextCharFormat.UnderlineStyle.SingleUnderline for f in underlined_formats)

    # 3. Simulate second setPlainText to verify cache revision invalidation works flawlessly
    edited_edit.setPlainText("Великий Замок стоїть")
    edited_edit.highlighter.rehighlight()

    block = edited_edit.document().firstBlock()
    user_data = block.userData()
    assert user_data is not None, "Cache should be invalidated and rebuilt on subsequent setPlainText"
    assert len(user_data.matches) == 1
    assert user_data.matches[0].entry.translation == "Замок"

    formats = block.layout().formats()
    underlined_formats = [f for f in formats if f.format.fontUnderline()]
    assert len(underlined_formats) >= 1
    assert any(f.format.underlineStyle() == QTextCharFormat.UnderlineStyle.SingleUnderline for f in underlined_formats)

    # 4. Simulate typing mode (typing bypasses synchronous highlights)
    edited_edit.highlighter.set_typing_mode(True)
    edited_edit.setPlainText("Замок знову")
    edited_edit.highlighter.rehighlight()

    block = edited_edit.document().firstBlock()
    user_data = block.userData()
    # In typing mode with no async matches yet, the synchronous fallback is bypassed
    assert user_data is None or len(user_data.matches) == 0

    # 5. Simulate asynchronous scan results coming in
    async_matches = [
        {
            'start': 0,
            'end': 5,
            'original': 'Castle',
            'translation': 'Замок',
            'notes': 'Location'
        }
    ]
    edited_edit.highlighter._async_translation_matches = async_matches
    edited_edit.highlighter.set_typing_mode(False)  # Exiting typing mode triggers rehighlight
    edited_edit.highlighter.rehighlight()

    block = edited_edit.document().firstBlock()
    user_data = block.userData()
    assert user_data is not None, "Async matches should be successfully applied and reflected in block user data"
    assert len(user_data.matches) == 1
    assert user_data.matches[0].entry.translation == "Замок"

def test_translation_glossary_underlining_with_glossary_disabled(qapp, mock_mw):
    from core.glossary_manager import GlossaryManager, GlossaryEntry
    from components.editor.line_numbered_text_edit import LineNumberedTextEdit

    # 1. Setup glossary
    gm = GlossaryManager()
    entry = GlossaryEntry(original="Castle", translation="Замок", notes="Location")
    gm._entries = [entry]
    gm._build_pattern_cache()

    # Setup mock window with fields needed by LineNumberedTextEdit
    mw = mock_mw
    mw.original_text_edit = LineNumberedTextEdit(parent=None)
    mw.original_text_edit.highlighter.mw = mw
    mw.original_text_edit.setObjectName("original_text_edit")
    mw.original_text_edit.setPlainText("Castle")

    edited_edit = LineNumberedTextEdit(parent=None)
    edited_edit.highlighter.mw = mw
    edited_edit.setObjectName("edited_text_edit")
    mw.edited_text_edit = edited_edit

    # Set glossary and translation mode
    edited_edit.set_glossary_manager(gm)
    # Manually disable general glossary highlighting
    edited_edit.highlighter._glossary_enabled = False

    edited_edit.highlighter.set_translation_mode(True, source_editor_ref=mw.original_text_edit)

    # 2. Simulate text change - setPlainText
    # Since _glossary_enabled is False, but _is_translation_mode is True,
    # setPlainText should still trigger rehighlight() and underline "Замок"
    edited_edit.setPlainText("Замок")
    edited_edit.highlighter.rehighlight()

    block = edited_edit.document().firstBlock()
    user_data = block.userData()
    assert user_data is not None
    assert len(user_data.matches) == 1
    assert user_data.matches[0].entry.translation == "Замок"

    # Verify that underline format is applied
    formats = block.layout().formats()
    underlined_formats = [f for f in formats if f.format.fontUnderline()]
    assert len(underlined_formats) >= 1

def test_JsonTagHighlighter_placeholder_highlighting(highlighter):
    hl, doc = highlighter

    # 1. Test when it IS preview_text_edit and matches pattern
    hl._editor_widget_ref.objectName.return_value = 'preview_text_edit'
    hl.setFormat.reset_mock()
    text = "[198-200] 3 empty line(s)"
    hl.highlightBlock(text)

    # setFormat should be called exactly once for the whole length
    hl.setFormat.assert_called_once_with(0, len(text), hl.placeholder_format)

    # 2. Test when it IS preview_text_edit but does NOT match pattern
    hl.setFormat.reset_mock()
    text_normal = "[198-200] 3 line(s)"
    hl.highlightBlock(text_normal)
    # should be called for basic color and possibly bracket rules
    assert hl.setFormat.call_count >= 2

    # 3. Test when it is NOT preview_text_edit but matches pattern
    hl._editor_widget_ref.objectName.return_value = 'edited_text_edit'
    hl.setFormat.reset_mock()
    text_other = "[198-200] 3 empty line(s)"
    hl.highlightBlock(text_other)
    # placeholder_format should NOT be used
    for call_args in hl.setFormat.call_args_list:
        fmt = call_args[0][2]
        assert fmt != hl.placeholder_format


def test_JsonTagHighlighter_length_tags_spacing(highlighter):
    hl, doc = highlighter
    hl._editor_widget_ref.objectName.return_value = 'edited_text_edit'

    hl.mw.font_map = {
        "{(Y)}": {"width": 50}
    }
    hl.mw.default_tag_mappings = {
        "{(Y)}": "{escape:0:0010}"
    }

    hl.setFormat.reset_mock()
    hl.highlightBlock("на {(Y)} або")

    for call_args in hl.setFormat.call_args_list:
        start, length, fmt = call_args[0]
        assert fmt != hl.bad_spacing_format

def test_JsonTagHighlighter_hide_tags(highlighter):
    hl, doc = highlighter

    hl._is_forced_alias = MagicMock(side_effect=lambda tag: "f:" in tag.lower())
    hl._tag_has_length = MagicMock(side_effect=lambda tag: "escape:" in tag.lower())

    text = "{color:red} text {f:Link} text {escape:3:0001}"

    # 1. When hide_tags is DISABLED (default)
    hl._editor_widget_ref.objectName.return_value = 'edited_text_edit'
    hl.mw.data_store.hide_translation_tags = False
    hl.mw.data_store.hide_original_tags = False
    hl.setFormat.reset_mock()

    hl.highlightBlock(text)
    for call_args in hl.setFormat.call_args_list:
        fmt = call_args[0][2]
        assert fmt != hl.hide_tag_format

    # 2. When hide_translation_tags is ENABLED on edited_text_edit
    hl._editor_widget_ref.objectName.return_value = 'edited_text_edit'
    hl.mw.data_store.hide_translation_tags = True
    hl.mw.data_store.hide_original_tags = False
    hl.setFormat.reset_mock()
    hl.highlightBlock(text)

    hide_tag_calls = [call_args[0] for call_args in hl.setFormat.call_args_list if call_args[0][2] == hl.hide_tag_format]
    curly_tag_calls = [call_args[0] for call_args in hl.setFormat.call_args_list if call_args[0][2] == hl.curly_tag_format]

    assert any(c[0] == 0 and c[1] == 11 for c in hide_tag_calls)
    assert any(c[0] == 17 and c[1] == 8 for c in curly_tag_calls)

    # 3. When hide_translation_tags is ENABLED on edited_text_edit but we process original_text_edit (should NOT hide)
    hl._editor_widget_ref.objectName.return_value = 'original_text_edit'
    hl.setFormat.reset_mock()
    hl.highlightBlock(text)
    for call_args in hl.setFormat.call_args_list:
        fmt = call_args[0][2]
        assert fmt != hl.hide_tag_format

    # 4. When hide_original_tags is ENABLED on original_text_edit
    hl._editor_widget_ref.objectName.return_value = 'original_text_edit'
    hl.mw.data_store.hide_original_tags = True
    hl.mw.data_store.hide_translation_tags = False
    hl.setFormat.reset_mock()
    hl.highlightBlock(text)

    hide_tag_calls = [call_args[0] for call_args in hl.setFormat.call_args_list if call_args[0][2] == hl.hide_tag_format]
    assert any(c[0] == 0 and c[1] == 11 for c in hide_tag_calls)

def test_JsonTagHighlighter_double_space_dot_color(highlighter):
    from utils.utils import SPACE_DOT_SYMBOL
    hl, doc = highlighter
    hl._editor_widget_ref.objectName.return_value = 'edited_text_edit'

    # Text with double space containing space dot symbol
    text = f"word{SPACE_DOT_SYMBOL}{SPACE_DOT_SYMBOL}word"
    hl.setFormat.reset_mock()
    hl.highlightBlock(text)

    # We should have applied a format to each dot that merges bad_spacing_format with space_dot_format's foreground
    found_space_dot_with_bad_spacing = False
    for call_args in hl.setFormat.call_args_list:
        start, length, fmt = call_args[0]
        if start in (4, 5) and length == 1:
            cond_style = fmt.underlineStyle() == QTextCharFormat.UnderlineStyle.SpellCheckUnderline
            cond_fg = fmt.foreground().color().name().lower() == hl.space_dot_format.foreground().color().name().lower()
            if cond_style and cond_fg:
                found_space_dot_with_bad_spacing = True

    assert found_space_dot_with_bad_spacing is True

def test_JsonTagHighlighter_get_icon_matches_for_text(highlighter):
    hl, doc = highlighter

    # 1. Simple matching
    matches = hl._get_icon_matches_for_text("Hello [Icon1] and [Icon2] World", ["[Icon1]", "[Icon2]"])
    assert len(matches) == 2
    assert matches[0] == (6, 7)
    assert matches[1] == (18, 7)

    # 2. Overlapping tokens (should match longer token first due to sorting)
    matches_overlap = hl._get_icon_matches_for_text("[IconLonger] [Icon]", ["[Icon]", "[IconLonger]"])
    assert len(matches_overlap) == 2
    assert matches_overlap[0] == (0, 12)
    assert matches_overlap[1] == (13, 6)


def test_JsonTagHighlighter_hide_tags_selective_visibility(highlighter, mock_mw):
    hl, doc = highlighter
    hl._editor_widget_ref.objectName.return_value = 'edited_text_edit'

    # Enable hiding translation tags
    mock_mw.hide_translation_tags = True

    # Configure mock game rules and widths
    mock_mw.font_map = {"{large_tag}": {"width": 12}}
    mock_mw.default_tag_mappings = {}
    mock_mw.icon_sequences = ["{icon_tag}"]

    text = "{color:red} {tab} {large_tag} {icon_tag} {*} {escape:6:000a}"

    hl.setFormat.reset_mock()
    hl.highlightBlock(text)

    # Collect formats set on matches
    set_formats = []
    for call_args in hl.setFormat.call_args_list:
        start, length, fmt = call_args[0]
        tag_substring = text[start:start+length]
        set_formats.append((tag_substring, fmt))

    # {color:red} should be hidden
    color_hidden = False
    for tag_str, fmt in set_formats:
        if tag_str == "{color:red}" and fmt == hl.hide_tag_format:
            color_hidden = True

    assert color_hidden is True, "Regular tag should be hidden"

    # The others should NOT be hidden
    for tag_str, fmt in set_formats:
        if tag_str in ("{tab}", "{large_tag}", "{icon_tag}", "{*}", "{escape:6:000a}"):
            assert fmt != hl.hide_tag_format, f"{tag_str} should not be hidden"


def test_JsonTagHighlighter_missing_tag_spacing_width_alias(highlighter, mock_mw):
    hl, doc = highlighter
    hl._editor_widget_ref.objectName.return_value = 'edited_text_edit'

    # Configure mock game rules and widths
    mock_mw.current_game_rules.PROBLEM_MISSING_ICON_SPACING = "PROBLEM_MISSING_ICON_SPACING"
    mock_mw.detection_enabled = {"PROBLEM_MISSING_ICON_SPACING": True}

    mock_mw.font_map = {"[L-Stick]": {"width": 10}}
    mock_mw.default_tag_mappings = {"[L-Stick]": "{escape:0:0008}"}
    mock_mw.icon_sequences = []

    text = "A[L-Stick]B"

    # Override is_visible_tag to return False so that [L-Stick] behaves as a non-icon width tag
    hl._is_visible_tag = lambda tag: False

    # Case 1: with default_tag_mappings, [L-Stick] has width 10, so it's a kept tag.
    # Since it's not a visible icon, it requires no space boundaries (like {tab}).
    # Therefore, no missing spacing is reported.
    hl.setFormat.reset_mock()
    hl.highlightBlock(text)

    missing_spacing_calls = [c[0] for c in hl.setFormat.call_args_list if c[0][2] == hl.missing_icon_spacing_format]
    assert len(missing_spacing_calls) == 0, "No spacing issue should be reported when mappings resolve [L-Stick] as width tag"

    # Case 2: without default_tag_mappings, [L-Stick] is considered zero-width.
    # The text behaves like 'AB' separated by tag, which triggers a spacing error.
    mock_mw.default_tag_mappings = {}
    hl.setFormat.reset_mock()
    hl.highlightBlock(text)

    missing_spacing_calls = [c[0] for c in hl.setFormat.call_args_list if c[0][2] == hl.missing_icon_spacing_format]
    assert len(missing_spacing_calls) == 1, "Spacing issue should be reported when mapping is missing and tag resolves as zero-width"
    # The span should be the tag region: start=1, length=9 (indices 1..10)
    assert missing_spacing_calls[0][0] == 1
    assert missing_spacing_calls[0][1] == 9
