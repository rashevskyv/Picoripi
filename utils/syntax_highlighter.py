import re
from typing import Dict, List, Optional, Tuple
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QSyntaxHighlighter,
    QTextBlockUserData,
    QTextCharFormat,
    QColor,
    QFont,
    QTextDocument,
    QPalette,
)
from PyQt6.QtWidgets import QWidget

from .logging_utils import log_debug
from .utils import SPACE_DOT_SYMBOL, convert_dots_to_spaces_from_editor, ALL_TAGS_PATTERN, get_tag_width
from plugins.common.markers import P_NEWLINE_MARKER, L_NEWLINE_MARKER, P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER
from core.glossary_manager import GlossaryManager, GlossaryMatch, GlossaryEntry

_COLOR_TAG_PATTERN = re.compile(
    r"(\[(Red|Green|Blue|Yellow|l_Blue|Purple|Silver|Orange|White|Gray|Grey)\])|"
    r"(\[/C\])|"
    r"(\{\s*Color\s*:\s*(Red|Green|Blue|White|Yellow|Purple|Orange|Grey|Gray)\s*\})",
    re.IGNORECASE
)

_PLACEHOLDER_PATTERN = re.compile(r"^\[\d+-\d+\] \d+ empty line\(s\)$")

_WORD_PATTERN = re.compile(r"[a-zA-Zа-яА-ЯіїІїЄєґҐ']+")

_DOUBLE_SPACE_PATTERN = re.compile(r"[ ·]{2,}")
_LEADING_SPACE_PATTERN = re.compile(r"^(?:\{(?!f:|F:)[^}]*\}|\[[^\]]*\])*([ ·]+)")
_TAG_SPLIT_SPACE_PATTERN = re.compile(r"[ ·](?:\{(?!f:|F:)[^}]*\}|\[[^\]]*\])+[ ·]")

class JsonTagHighlighter(QSyntaxHighlighter):
    """Json tag highlighter implementation."""
    class GlossaryBlockData(QTextBlockUserData):
        """Glossary block data implementation."""
        def __init__(self, matches: List[GlossaryMatch]) -> None:
            """Initialize a new instance."""
            super().__init__()
            self.matches = matches

    STATE_DEFAULT = 0
    STATE_RED = 1
    STATE_GREEN = 2
    STATE_BLUE = 3
    STATE_YELLOW = 4
    STATE_LBLUE = 5
    STATE_PURPLE = 6
    STATE_SILVER = 7
    STATE_ORANGE = 8


    def __init__(self, parent: QTextDocument, main_window_ref=None, editor_widget_ref=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.mw = main_window_ref
        self._editor_widget_ref = editor_widget_ref  # Store reference to the editor widget
        self._glossary_manager: Optional[GlossaryManager] = None
        self._glossary_enabled = False
        self._glossary_format = QTextCharFormat()
        self._glossary_matches_cache: Dict[int, List[Tuple[int, int, GlossaryMatch]]] = {}
        self._glossary_cache_revision: Optional[int] = None
        self._translation_matches_cache: Dict[int, List[Tuple[int, int, GlossaryMatch]]] = {}
        self._translation_cache_revision: Optional[int] = None
        self._icon_sequences_cache: Dict[int, List[Tuple[int, int]]] = {}
        self._icon_cache_revision: Optional[int] = None
        self._icon_sequences_snapshot: Tuple[str, ...] = ()

        # Spellchecker support
        self._spellchecker_format = QTextCharFormat()
        self._spellchecker_enabled = False
        self._typing_mode = False

        # Async highlights storage
        self._async_glossary_matches = None
        self._async_translation_matches = None
        self._async_spellcheck_matches = None

        # Translation Glossary Bridge
        self._is_translation_mode = False
        self._source_editor_ref = None
        self.default_text_color = QColor(Qt.GlobalColor.black)
        
        current_theme = getattr(self.mw, 'theme', 'auto')
        if current_theme == 'dark':
            self.default_text_color = QColor("#E0E0E0")
        else:
            editor_widget = parent.parent() if parent else None
            if editor_widget and isinstance(editor_widget, QWidget) and hasattr(editor_widget, 'palette'):
                self.default_text_color = editor_widget.palette().color(QPalette.ColorRole.Text)

        self.custom_rules = []
        self._compiled_custom_rules_all = []
        self._compiled_custom_rules_preview = []
        self._compiled_all_rules_builtin = []
        self.curly_tag_format = QTextCharFormat()
        self.bracket_tag_format = QTextCharFormat()
        self.newline_symbol_format = QTextCharFormat()
        self.literal_newline_format = QTextCharFormat()
        self.space_dot_format = QTextCharFormat()
        self.p_marker_format = QTextCharFormat()
        self.l_marker_format = QTextCharFormat()
        self.bad_spacing_format = QTextCharFormat()
        self.missing_icon_spacing_format = QTextCharFormat()
        self.placeholder_format = QTextCharFormat()

        self.red_text_format = QTextCharFormat()
        self.green_text_format = QTextCharFormat()
        self.blue_text_format = QTextCharFormat()
        self.yellow_text_format = QTextCharFormat()
        self.lblue_text_format = QTextCharFormat()
        self.purple_text_format = QTextCharFormat()
        self.silver_text_format = QTextCharFormat()
        self.orange_text_format = QTextCharFormat()
        self.icon_sequence_format = QTextCharFormat()
        
        self.color_default_format = QTextCharFormat()
        self.color_default_format.setForeground(self.default_text_color)
        
        parent.contentsChange.connect(self.on_contents_change)

        self.reconfigure_styles()
        
    def on_contents_change(self, position, chars_removed, chars_added):
        """Handle the contents change event."""
        self._invalidate_icon_cache()
        self._glossary_cache_revision = None
        self._translation_cache_revision = None
        # QSyntaxHighlighter automatically handles rehighlighting the changed blocks.
        # Calling rehighlight() here can interrupt its internal state and strip colors during setPlainText.

    def set_glossary_manager(self, manager: Optional[GlossaryManager]) -> None:
        """Set the glossary manager."""
        self._glossary_manager = manager
        mw_enabled = getattr(self.mw, 'glossary_enabled', True) if self.mw else True
        
        # Disable glossary highlighting for preview_text_edit to prevent severe UI freezes on large blocks
        is_preview = False
        if self._editor_widget_ref and hasattr(self._editor_widget_ref, 'objectName'):
            if self._editor_widget_ref.objectName() == 'preview_text_edit':
                is_preview = True
                
        self._glossary_enabled = bool(mw_enabled and manager and manager.get_entries() and not is_preview)
        self._glossary_matches_cache.clear()
        self._glossary_cache_revision = None
        self.rehighlight()

    def set_spellchecker_enabled(self, enabled: bool) -> None:
        """Enable or disable spellchecker highlighting."""
        editor_name = 'unknown'
        if self._editor_widget_ref and hasattr(self._editor_widget_ref, 'objectName'):
            editor_name = self._editor_widget_ref.objectName()

        log_debug(f"JsonTagHighlighter ({editor_name}): set_spellchecker_enabled called with enabled={enabled}, current state={self._spellchecker_enabled}")

        if self._spellchecker_enabled != enabled:
            self._spellchecker_enabled = enabled
            log_debug(f"JsonTagHighlighter ({editor_name}): Spellchecker highlighting state changed to {'enabled' if enabled else 'disabled'}, triggering rehighlight")
            self.rehighlight()
        else:
            log_debug(f"JsonTagHighlighter ({editor_name}): Spellchecker state unchanged, no rehighlight needed")

    def set_typing_mode(self, enabled: bool, trigger_rehighlight: bool = True) -> None:
        """Enable or disable typing mode which suppresses heavy checks like glossary and spellchecking."""
        if hasattr(self, '_typing_mode') and self._typing_mode != enabled:
            self._typing_mode = enabled
            if not enabled and trigger_rehighlight:
                self.rehighlight()

    def set_translation_mode(self, enabled: bool, source_editor_ref: Optional[QWidget] = None) -> None:
        """Enable or disable translation-specific glossary highlighting."""
        self._is_translation_mode = enabled
        self._source_editor_ref = source_editor_ref
        self.rehighlight()

    def set_async_highlights(self, glossary_matches: list, translation_matches: list, spellcheck_matches: list) -> None:
        """Sets pre-calculated highlights from the background thread and triggers quick rehighlight."""
        self._async_glossary_matches = glossary_matches
        self._async_translation_matches = translation_matches
        self._async_spellcheck_matches = spellcheck_matches
        self.rehighlight()

    def _apply_css_to_format(self, char_format, css_str, base_color=None):
        """Internal helper to apply css to format."""
        if base_color:
            char_format.setForeground(base_color)

        if not css_str: return
        properties = css_str.split(';')
        for prop in properties:
            prop = prop.strip()
            if not prop: continue
            parts = prop.split(':', 1)
            if len(parts) != 2: continue
            key, value = parts[0].strip().lower(), parts[1].strip().lower()
            try:
                if key == 'color' or key == 'background-color':
                    color = QColor(value)
                    if not color.isValid() and value.startswith('#') and len(value) == 9:
                        # Fallback for #AARRGGBB
                        color = QColor('#' + value[3:])
                    
                    if color.isValid():
                        if key == 'color': char_format.setForeground(color)
                        else: char_format.setBackground(color)
                elif key == 'font-weight':
                    if value == 'bold': char_format.setFontWeight(QFont.Weight.Bold.value)
                    elif value == 'normal': char_format.setFontWeight(QFont.Weight.Normal.value)
                    else: char_format.setFontWeight(int(value))
                elif key == 'font-style':
                    if value == 'italic': char_format.setFontItalic(True)
                    elif value == 'normal': char_format.setFontItalic(False)
                elif key == 'text-decoration':
                    if 'underline' in value: char_format.setFontUnderline(True)
                    else: char_format.setFontUnderline(False)
            except Exception as e: log_debug(f"  Error applying CSS property '{prop}': {e}")

    def reconfigure_styles(self, newline_symbol="↵",
                           newline_css_str="color: #A020F0; font-weight: bold;",
                           tag_css_str="color: #808080; font-style: italic;",
                           show_multiple_spaces_as_dots=True,
                           space_dot_color_hex="#BBBBBB",
                           bracket_tag_color_hex="#FF8C00"):
        """Reconfigure styles."""
        doc = self.document()
        editor_widget = doc.parent() if doc else None
        
        self.newline_char = newline_symbol
        
        current_theme = getattr(self.mw, 'theme', 'auto')
        if current_theme == 'dark':
            self.default_text_color = QColor("#E0E0E0")
        else:
            if editor_widget and hasattr(editor_widget, 'palette'):
                self.default_text_color = editor_widget.palette().color(QPalette.ColorRole.Text)
            else:
                 self.default_text_color = QColor(Qt.GlobalColor.black)
        
        self.color_default_format.setForeground(self.default_text_color)
        
        self.custom_rules = []
        if self.mw and hasattr(self.mw, 'current_game_rules') and self.mw.current_game_rules:
            plugin_rules = self.mw.current_game_rules.get_syntax_highlighting_rules()
            if plugin_rules:
                self.custom_rules = plugin_rules

        self._compiled_custom_rules_all = [(re.compile(p), f) for p, f in self.custom_rules]
        self._compiled_custom_rules_preview = [(re.compile(p), f) for p, f in self.custom_rules if r"(\[\s*[^\]]*?\s*\])" not in p]

        self._apply_css_to_format(self.curly_tag_format, tag_css_str)
        self._apply_css_to_format(self.bracket_tag_format, tag_css_str)
        
        self.hide_tag_format = QTextCharFormat()
        self.hide_tag_format.setFontPointSize(0.1)
        
        font = self.hide_tag_format.font()
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 1.0)
        font.setStretch(1)
        self.hide_tag_format.setFont(font)
        self.hide_tag_format.setForeground(QColor(Qt.GlobalColor.transparent))
        self.hide_tag_format.setFontWeight(QFont.Weight.Normal.value)
        self.hide_tag_format.setFontItalic(False)
        self.hide_tag_format.setFontUnderline(False)
        
        self._apply_css_to_format(self.newline_symbol_format, newline_css_str)
        self._apply_css_to_format(self.literal_newline_format, "color: red; font-weight: bold;")
        
        self.p_marker_format.setForeground(QColor("green"))
        self.p_marker_format.setFontWeight(QFont.Weight.Bold.value)
        self.l_marker_format.setForeground(QColor("orange"))
        self.l_marker_format.setFontWeight(QFont.Weight.Bold.value)

        self.icon_sequence_format = QTextCharFormat()
        icon_bg = QColor("#C8E6C9")
        try:
            icon_bg.setAlpha(180)
        except Exception:
            pass
        self.icon_sequence_format.setBackground(icon_bg)
        self.icon_sequence_format.setFontWeight(QFont.Weight.Bold.value)
        
        # Precompile builtin rules
        self._compiled_all_rules_builtin = [
            (re.compile(r"(\{[^}]*\})"), self.curly_tag_format),
            (re.compile(r"(\[[^\]]*\])"), self.bracket_tag_format),
            (re.compile(r"(\\n)"), self.literal_newline_format),
            (re.compile(re.escape(self.newline_char)), self.newline_symbol_format),
            (re.compile(re.escape(SPACE_DOT_SYMBOL)), self.space_dot_format),
            (re.compile(re.escape(P_NEWLINE_MARKER)), self.p_marker_format),
            (re.compile(re.escape(L_NEWLINE_MARKER)), self.l_marker_format),
            (re.compile(re.escape(P_VISUAL_EDITOR_MARKER)), self.p_marker_format),
            (re.compile(re.escape(L_VISUAL_EDITOR_MARKER)), self.l_marker_format),
        ]

        try: self.space_dot_format.setForeground(QColor(space_dot_color_hex))
        except Exception: self.space_dot_format.setForeground(QColor(Qt.GlobalColor.lightGray))

        self.red_text_format.setForeground(QColor("#FF4C4C"))
        self.green_text_format.setForeground(QColor("#4CAF50"))
        self.blue_text_format.setForeground(QColor("#0958e0"))
        # Improve readability of Yellow in light theme
        if current_theme == 'dark':
            self.yellow_text_format.setForeground(QColor("yellow"))
        else:
            # Darker yellow text with a subtle amber background
            self.yellow_text_format.setForeground(QColor("#b58900"))
            try:
                self.yellow_text_format.setBackground(QColor("#fff4c2"))
            except Exception:
                pass
        self.lblue_text_format.setForeground(QColor("#ADD8E6"))
        self.purple_text_format.setForeground(QColor("#800080"))
        if current_theme == 'dark':
            self.silver_text_format.setForeground(QColor("#a8a8a8"))
        else:
            self.silver_text_format.setForeground(QColor("#555555"))
        self.orange_text_format.setForeground(QColor("#FFA500"))

        self._glossary_format = QTextCharFormat()
        self._glossary_format.setFontUnderline(True)
        self._glossary_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
        underline_color = QColor("#1a73e8") if current_theme != 'dark' else QColor("#8ab4f8")
        try:
            self._glossary_format.setUnderlineColor(underline_color)
        except Exception:
            pass

        # Configure spellchecker format (red wavy underline)
        self._spellchecker_format = QTextCharFormat()
        self._spellchecker_format.setFontUnderline(True)
        self._spellchecker_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        try:
            self._spellchecker_format.setUnderlineColor(QColor("#FF0000"))
        except Exception:
            pass

        # Configure bad spacing format (soft red background + red wavy underline)
        self.bad_spacing_format = QTextCharFormat()
        self.bad_spacing_format.setFontUnderline(True)
        self.bad_spacing_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        if current_theme == 'dark':
            self.bad_spacing_format.setBackground(QColor(255, 80, 80, 50))
            self.bad_spacing_format.setUnderlineColor(QColor(255, 100, 100))
        else:
            self.bad_spacing_format.setBackground(QColor(255, 0, 0, 30))
            self.bad_spacing_format.setUnderlineColor(QColor(255, 0, 0, 150))

        # Configure missing icon spacing format (soft blue background + blue wavy underline)
        self.missing_icon_spacing_format = QTextCharFormat()
        self.missing_icon_spacing_format.setFontUnderline(True)
        self.missing_icon_spacing_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        if current_theme == 'dark':
            self.missing_icon_spacing_format.setBackground(QColor(173, 216, 230, 50))
            self.missing_icon_spacing_format.setUnderlineColor(QColor(135, 206, 250))
        else:
            self.missing_icon_spacing_format.setBackground(QColor(0, 119, 204, 30))
            self.missing_icon_spacing_format.setUnderlineColor(QColor(0, 119, 204, 150))

        self.placeholder_format.setForeground(QColor("#888888"))

        self.newline_char = newline_symbol
        mw_enabled = getattr(self.mw, 'glossary_enabled', True) if self.mw else True
        
        # Disable glossary highlighting for preview_text_edit to prevent severe UI freezes on large blocks
        is_preview = False
        if self._editor_widget_ref and hasattr(self._editor_widget_ref, 'objectName'):
            if self._editor_widget_ref.objectName() == 'preview_text_edit':
                is_preview = True
                
        self._glossary_enabled = bool(mw_enabled and self._glossary_manager and self._glossary_manager.get_entries() and not is_preview)
        self._glossary_matches_cache.clear()
        self._glossary_cache_revision = None
        if self.document():
             self.rehighlight()

    def _invalidate_icon_cache(self) -> None:
        """Internal helper to invalidate icon cache."""
        self._icon_sequences_cache.clear()
        self._icon_cache_revision = None
        self._icon_sequences_snapshot = ()

    def _rebuild_glossary_cache(self) -> None:
        """Internal helper to rebuild glossary cache."""
        doc = self.document()
        if not doc:
            self._glossary_matches_cache.clear()
            self._glossary_cache_revision = None
            return
        revision = doc.revision()
        if self._glossary_cache_revision == revision:
            return

        self._glossary_cache_revision = revision
        self._glossary_matches_cache.clear()

        if not (self._glossary_enabled and self._glossary_manager):
            return

        full_text = doc.toPlainText()
        try:
            matches = self._glossary_manager.find_matches(full_text)
        except Exception as exc:
            log_debug(f"Glossary highlight error: {exc}")
            matches = []

        for match in matches:
            start = match.start
            end = match.end
            if end <= start:
                continue
            block = doc.findBlock(start)
            if not block.isValid():
                continue
            while block.isValid() and start < end:
                block_start = block.position()
                block_length = block.length()
                block_end = block_start + block_length
                overlap_start = max(start, block_start)
                overlap_end = min(end, block_end)
                if overlap_end > overlap_start:
                    local_start = overlap_start - block_start
                    local_length = overlap_end - overlap_start
                    self._glossary_matches_cache.setdefault(block.blockNumber(), []).append(
                        (local_start, local_length, match)
                    )
                if block_end >= end:
                    break
                block = block.next()
                if not block.isValid():
                    break

    def _rebuild_translation_glossary_cache(self) -> None:
        """Rebuilds the bridge translation glossary cache for the whole document."""
        doc = self.document()
        if not doc or not self._is_translation_mode or not self._source_editor_ref or not self._glossary_manager:
            self._translation_matches_cache.clear()
            self._translation_cache_revision = None
            return

        revision = doc.revision()
        if self._translation_cache_revision == revision:
            return

        self._translation_cache_revision = revision
        self._translation_matches_cache.clear()

        source_text_raw = self._source_editor_ref.toPlainText()
        source_text = convert_dots_to_spaces_from_editor(source_text_raw)
        # Find entries that occur in the source document
        source_matches = self._glossary_manager.get_relevant_terms(source_text)
        log_debug(f"Glossary bridge: source text='{source_text}', found relevant source terms={[m.original for m in source_matches]}")
        if not source_matches:
            return

        full_text = doc.toPlainText()
        for entry in source_matches:
            # Build and search for translation regex
            # Note: build_translation_regex handles multi-line/fuzzy Slavic terms
            regex = self._glossary_manager.build_translation_regex(entry.translation)
            if not regex:
                continue
            
            matches = list(regex.finditer(full_text))
            log_debug(f"Glossary bridge: checking translation term='{entry.translation}' via regex='{regex.pattern}' on target text='{full_text}', found matches={len(matches)}")
            
            for match in regex.finditer(full_text):
                start, end = match.start(), match.end()
                if end <= start:
                    continue
                
                block = doc.findBlock(start)
                if not block.isValid():
                    continue
                
                while block.isValid() and start < end:
                    block_start = block.position()
                    block_length = block.length()
                    block_end = block_start + block_length
                    overlap_start = max(start, block_start)
                    overlap_end = min(end, block_end)
                    if overlap_end > overlap_start:
                        local_start = overlap_start - block_start
                        local_length = overlap_end - overlap_start
                        self._translation_matches_cache.setdefault(block.blockNumber(), []).append(
                            (local_start, local_length, GlossaryMatch(entry=entry, start=start, end=end))
                        )
                    if block_end >= end:
                        break
                    block = block.next()
                    if not block.isValid():
                        break

    def _ensure_icon_cache(self, sequences: List[str]) -> None:
        # Keep as no-op for backwards compatibility. Matches are now processed
        # locally for the current block in _get_icon_matches_for_block.
        """Internal helper to ensure icon cache."""
        pass

    def _get_icon_matches_for_text(self, text: str, sequences: List[str]) -> List[Tuple[int, int]]:
        """Internal helper to get the icon matches for text."""
        if not sequences or not text:
            return []
            
        first_char_map: Dict[str, List[str]] = {}
        for token in sequences:
            if not token:
                continue
            first_char_map.setdefault(token[0], []).append(token)
        for token_list in first_char_map.values():
            token_list.sort(key=len, reverse=True)

        matches: List[Tuple[int, int]] = []
        index = 0
        text_length = len(text)
        while index < text_length:
            char = text[index]
            candidates = first_char_map.get(char)
            matched = False
            if candidates:
                for token in candidates:
                    token_len = len(token)
                    if token_len <= 0 or index + token_len > text_length:
                        continue
                    if text.startswith(token, index):
                        matches.append((index, token_len))
                        index += token_len
                        matched = True
                        break
            if not matched:
                index += 1
        return matches

    def _get_icon_matches_for_block(self, sequences: List[str]) -> List[Tuple[int, int]]:
        """Internal helper to get the icon matches for block."""
        if not sequences:
            return []
        block = self.currentBlock()
        if not block or not block.isValid():
            return []
            
        block_text = ""
        # Handle cases where block text is not a callable or doesn't return a string
        if hasattr(block, 'text') and callable(block.text):
            try:
                val = block.text()
                if isinstance(val, str):
                    block_text = val
            except Exception:
                pass
                
        if not block_text:
            doc = self.document()
            if doc:
                try:
                    block_num = block.blockNumber()
                    try:
                        block_num_int = int(block_num)
                    except (TypeError, ValueError):
                        block_num_int = 0
                    block_text = doc.findBlockByNumber(block_num_int).text()
                except Exception:
                    block_text = ""
                    
        return self._get_icon_matches_for_text(block_text, sequences)


    def _get_icon_sequences(self) -> List[str]:
        """Internal helper to get the icon sequences."""
        main_window = self.mw
        sequences = getattr(main_window, 'icon_sequences', None) if main_window else None
        if isinstance(sequences, list):
            return sequences
        return []

    def _should_highlight_icons(self) -> bool:
        """Internal helper to check if should highlight icons."""
        doc = self.document()
        if not doc:
            return False
        editor_widget = doc.parent()
        if hasattr(editor_widget, 'objectName') and editor_widget.objectName() == 'preview_text_edit':
            return False
        return True

    def _should_check_spelling(self) -> bool:
        """Check if spellchecking should be performed for this widget."""
        if not self._spellchecker_enabled:
            return False

        # Use stored editor widget reference
        if self._editor_widget_ref:
            editor_name = self._editor_widget_ref.objectName() if hasattr(self._editor_widget_ref, 'objectName') else 'unknown'
            return editor_name in ('edited_text_edit', 'variations_preview_text_edit', 'comparison_editor_text_edit')

        return False

    def _extract_words_from_text(self, text: str) -> List[Tuple[int, int, str]]:
        """Extract words from text, returning (start, end, word) tuples."""
        # Replace middle dots with spaces for word detection
        text_with_spaces = text.replace('·', ' ')

        words = []
        for match in _WORD_PATTERN.finditer(text_with_spaces):
            words.append((match.start(), match.end(), match.group(0)))
        return words

    def _is_forced_alias(self, tag: str) -> bool:
        """Internal helper to check if is forced alias."""
        if tag.lower().startswith("{f:"):
            return True
        mappings = getattr(self.mw, "default_tag_mappings", {}) if self.mw else {}
        if mappings:
            for alias, original in mappings.items():
                if original == tag and alias.lower().startswith("{f:"):
                    return True
        return False

    def _tag_has_length(self, tag: str) -> bool:
        """Internal helper to tag has length."""
        font_map = getattr(self.mw, 'font_map', {}) if self.mw else {}
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}
        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []
        width = get_tag_width(tag, default_tag_mappings, font_map, icon_sequences=icon_sequences)
        return width > 0

    def _is_visible_tag(self, tag: str) -> bool:
        """Internal helper to check if is visible tag."""
        from utils.utils import is_visible_tag
        font_map = getattr(self.mw, 'font_map', {}) if self.mw else {}
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}
        icon_sequences = self._get_icon_sequences()
        return is_visible_tag(tag, default_tag_mappings, font_map, icon_sequences)

    def highlightBlock(self, text):
        # In preview_text_edit each line is an independent game string,
        # so color must NOT bleed from one string to the next.
        """Highlightblock."""
        _is_preview_widget = (
            self._editor_widget_ref is not None
            and hasattr(self._editor_widget_ref, 'objectName')
            and self._editor_widget_ref.objectName() == 'preview_text_edit'
        )
        if _is_preview_widget and _PLACEHOLDER_PATTERN.match(text):
            self.setFormat(0, len(text), self.placeholder_format)
            self.setCurrentBlockState(self.STATE_DEFAULT)
            return

        if _is_preview_widget:
            previous_color_state = self.STATE_DEFAULT
        else:
            previous_color_state = self.previousBlockState()
            if previous_color_state == -1: previous_color_state = self.STATE_DEFAULT

        format_map = {
            self.STATE_DEFAULT: self.color_default_format,
            self.STATE_RED: self.red_text_format,
            self.STATE_GREEN: self.green_text_format,
            self.STATE_BLUE: self.blue_text_format,
            self.STATE_YELLOW: self.yellow_text_format,
            self.STATE_LBLUE: self.lblue_text_format,
            self.STATE_PURPLE: self.purple_text_format,
            self.STATE_SILVER: self.silver_text_format,
            self.STATE_ORANGE: self.orange_text_format,
        }
        self.setFormat(0, len(text), format_map.get(previous_color_state, self.color_default_format))
        
        last_pos = 0
        current_block_color_state = previous_color_state
        for match in _COLOR_TAG_PATTERN.finditer(text):
            start, end = match.span()
            
            format_to_apply = format_map.get(current_block_color_state, self.color_default_format)
            if start > last_pos:
                self.setFormat(last_pos, start - last_pos, format_to_apply)
            
            ww_color_name = match.group(2)
            ww_closing_tag = match.group(3)
            mc_color_name = match.group(5)

            if ww_color_name:
                color = ww_color_name.lower()
                if color == 'red': current_block_color_state = self.STATE_RED
                elif color == 'green': current_block_color_state = self.STATE_GREEN
                elif color == 'blue': current_block_color_state = self.STATE_BLUE
                elif color == 'yellow': current_block_color_state = self.STATE_YELLOW
                elif color == 'l_blue': current_block_color_state = self.STATE_LBLUE
                elif color == 'purple': current_block_color_state = self.STATE_PURPLE
                elif color in ('silver', 'grey', 'gray'): current_block_color_state = self.STATE_SILVER
                elif color == 'orange': current_block_color_state = self.STATE_ORANGE
                else: current_block_color_state = self.STATE_DEFAULT # White
            elif ww_closing_tag:
                current_block_color_state = self.STATE_DEFAULT
            elif mc_color_name:
                color = mc_color_name.lower()
                if color == 'red': current_block_color_state = self.STATE_RED
                elif color == 'green': current_block_color_state = self.STATE_GREEN
                elif color == 'blue': current_block_color_state = self.STATE_BLUE
                elif color == 'yellow': current_block_color_state = self.STATE_YELLOW
                elif color == 'purple': current_block_color_state = self.STATE_PURPLE
                elif color == 'orange': current_block_color_state = self.STATE_ORANGE
                elif color in ('grey', 'gray'): current_block_color_state = self.STATE_SILVER
                else: current_block_color_state = self.STATE_DEFAULT # White
            
            last_pos = end
        
        if last_pos < len(text):
            final_format = format_map.get(current_block_color_state, self.color_default_format)
            self.setFormat(last_pos, len(text) - last_pos, final_format)

        # Glossary and spellcheck highlighting (run BEFORE tag rules so that tags can clean up formats on top)
        all_matches_for_tooltip = []
        
        block = self.currentBlock()
        if not block or not block.isValid():
            block_pos = 0
            block_number = -1
        else:
            block_pos = block.position()
            block_number = block.blockNumber()
            
        block_len = len(text)
        block_end = block_pos + block_len

        # 1. Glossary highlighting (Aho-Corasick)
        glossary_matches_to_apply = []
        if self._glossary_enabled and block_number != -1:
            if self._async_glossary_matches is not None:
                for m in self._async_glossary_matches:
                    m_start = m['start']
                    m_end = m['end']
                    overlap_start = max(m_start, block_pos)
                    overlap_end = min(m_end, block_end)
                    if overlap_end > overlap_start:
                        local_start = overlap_start - block_pos
                        local_length = overlap_end - overlap_start
                        entry = GlossaryEntry(original=m['original'], translation=m['translation'], notes=m['notes'])
                        glossary_matches_to_apply.append(GlossaryMatch(entry=entry, start=local_start, end=local_start + local_length))
            elif not self._typing_mode:
                # Synchronous fallback for startup and unit tests
                self._rebuild_glossary_cache()
                if block_number in self._glossary_matches_cache:
                    for local_start, local_length, match in self._glossary_matches_cache[block_number]:
                        glossary_matches_to_apply.append(GlossaryMatch(entry=match.entry, start=local_start, end=local_start + local_length))

        if glossary_matches_to_apply:
            underline_style = self._glossary_format.underlineStyle()
            underline_color = self._glossary_format.underlineColor()
            has_custom_color = underline_color.isValid()
            for m in glossary_matches_to_apply:
                existing_format = self.format(m.start)
                existing_format.setFontUnderline(True)
                existing_format.setUnderlineStyle(underline_style)
                if has_custom_color:
                    existing_format.setUnderlineColor(underline_color)
                self.setFormat(m.start, m.end - m.start, existing_format)
                all_matches_for_tooltip.append(m)

        # 2. Translation Glossary Bridge highlighting
        translation_matches_to_apply = []
        if self._is_translation_mode and block_number != -1:
            # log_debug(f"highlightBlock: translation mode active, block_num={block_number}, text={repr(text)}, async_matches={self._async_translation_matches is not None}, typing={self._typing_mode}")
            if self._async_translation_matches is not None:
                for m in self._async_translation_matches:
                    m_start = m['start']
                    m_end = m['end']
                    overlap_start = max(m_start, block_pos)
                    overlap_end = min(m_end, block_end)
                    if overlap_end > overlap_start:
                        local_start = overlap_start - block_pos
                        local_length = overlap_end - overlap_start
                        entry = GlossaryEntry(original=m['original'], translation=m['translation'], notes=m['notes'])
                        translation_matches_to_apply.append(GlossaryMatch(entry=entry, start=local_start, end=local_start + local_length))
            elif not self._typing_mode:
                # Synchronous fallback for startup and unit tests
                self._rebuild_translation_glossary_cache()
                if block_number in self._translation_matches_cache:
                    for local_start, local_length, match in self._translation_matches_cache[block_number]:
                        translation_matches_to_apply.append(GlossaryMatch(entry=match.entry, start=local_start, end=local_start + local_length))

        if translation_matches_to_apply:
            underline_style = self._glossary_format.underlineStyle()
            underline_color = self._glossary_format.underlineColor()
            has_custom_color = underline_color.isValid()
            for m in translation_matches_to_apply:
                existing_format = self.format(m.start)
                existing_format.setFontUnderline(True)
                existing_format.setUnderlineStyle(underline_style)
                if has_custom_color:
                    existing_format.setUnderlineColor(underline_color)
                self.setFormat(m.start, m.end - m.start, existing_format)
                all_matches_for_tooltip.append(m)

        if all_matches_for_tooltip:
            self.setCurrentBlockUserData(self.GlossaryBlockData(all_matches_for_tooltip))
        else:
            self.setCurrentBlockUserData(None)

        # 3. Spellchecker highlighting
        spellcheck_matches_to_apply = []
        if not self._typing_mode and self._should_check_spelling() and block_number != -1:
            if self._async_spellcheck_matches is not None:
                spellcheck_matches_to_apply = self._async_spellcheck_matches
            else:
                editor_name = self._editor_widget_ref.objectName() if (self._editor_widget_ref and hasattr(self._editor_widget_ref, 'objectName')) else ''
                if editor_name in ('variations_preview_text_edit', 'comparison_editor_text_edit'):
                    sm = self.mw.spellchecker_manager if (self.mw and hasattr(self.mw, 'spellchecker_manager')) else None
                    if sm and sm.enabled and sm.hunspell:
                        text_with_spaces = text.replace("·", " ")
                        for match in _WORD_PATTERN.finditer(text_with_spaces):
                            word = match.group(0)
                            cleaned_word = word.strip("'·")
                            if len(cleaned_word) < 3 or cleaned_word.isdigit():
                                continue
                            lower_word = cleaned_word.lower()
                            if lower_word in sm.custom_words:
                                continue
                            
                            if lower_word in sm._spell_cache:
                                is_misspelled = sm._spell_cache[lower_word]
                            else:
                                is_correct = sm.hunspell.lookup(cleaned_word)
                                is_misspelled = not is_correct
                                sm._spell_cache[lower_word] = is_misspelled
                                
                            if is_misspelled:
                                spellcheck_matches_to_apply.append((block_pos + match.start(), match.end() - match.start()))

        if spellcheck_matches_to_apply:
            underline_style = self._spellchecker_format.underlineStyle()
            underline_color = self._spellchecker_format.underlineColor()
            has_custom_color = underline_color.isValid()
            
            for m_start, m_length in spellcheck_matches_to_apply:
                m_end = m_start + m_length
                
                overlap_start = max(m_start, block_pos)
                overlap_end = min(m_end, block_end)
                if overlap_end > overlap_start:
                    local_start = overlap_start - block_pos
                    local_length = overlap_end - overlap_start
                    
                    existing_format = self.format(local_start)
                    existing_format.setFontUnderline(True)
                    existing_format.setUnderlineStyle(underline_style)
                    if has_custom_color:
                        existing_format.setUnderlineColor(underline_color)
                    self.setFormat(local_start, local_length, existing_format)

        # Apply custom rules from the game plugin
        rules_to_apply = self._compiled_custom_rules_all
        
        # Performance optimization for the preview window by not highlighting bracket tags (controller buttons)
        doc = self.document()
        if doc:
            editor_widget = doc.parent()
            if hasattr(editor_widget, 'objectName') and editor_widget.objectName() == 'preview_text_edit':
                rules_to_apply = self._compiled_custom_rules_preview
        
        for compiled_pattern, fmt in rules_to_apply:
            try:
                for match in compiled_pattern.finditer(text):
                    self.setFormat(match.start(), match.end() - match.start(), fmt)
            except Exception as e:
                pass # Already precompiled, shouldn't fail runtime
                
        hide_tags_enabled = False
        if self.mw and hasattr(self.mw, 'data_store'):
            editor_name = ""
            if self._editor_widget_ref and hasattr(self._editor_widget_ref, 'objectName'):
                editor_name = self._editor_widget_ref.objectName()
            
            if editor_name == 'original_text_edit':
                hide_tags_enabled = getattr(self.mw.data_store, 'hide_original_tags', getattr(self.mw.data_store, 'hide_tags', False))
            else:
                hide_tags_enabled = getattr(self.mw.data_store, 'hide_translation_tags', getattr(self.mw.data_store, 'hide_tags', False))
        
        for compiled_pattern, fmt in self._compiled_all_rules_builtin:
            for match in compiled_pattern.finditer(text):
                is_tag_pattern = fmt in (self.curly_tag_format, self.bracket_tag_format)
                if is_tag_pattern and hide_tags_enabled:
                    tag = match.group(1)
                    if not (self._is_visible_tag(tag) or self._tag_has_length(tag) or tag.lower() in ('{*}', '{tab}', '{escape:6:000a}', '{escape:6:000b}')):
                        self.setFormat(match.start(), match.end() - match.start(), self.hide_tag_format)
                        continue
                self.setFormat(match.start(), match.end() - match.start(), fmt)

        icon_sequences = self._get_icon_sequences()
        if icon_sequences and self._should_highlight_icons():
            matches = self._get_icon_matches_for_block(icon_sequences)
            for start, length in matches:
                existing_format = self.format(start)
                combined_format = QTextCharFormat(existing_format)
                icon_bg = self.icon_sequence_format.background()
                if icon_bg.style() != Qt.BrushStyle.NoBrush:
                    combined_format.setBackground(icon_bg)
                if self.icon_sequence_format.fontWeight() != QFont.Weight.Normal.value:
                    combined_format.setFontWeight(self.icon_sequence_format.fontWeight())
                self.setFormat(start, length, combined_format)

        # Highlight bad spacing: double spaces, leading spaces, and spaces split by tags
        # (Only in the editor text edits, not in preview_text_edit)
        if _is_preview_widget is False and not self._typing_mode:
            def apply_bad_spacing_format(start_idx, length):
                for idx in range(start_idx, start_idx + length):
                    char = text[idx]
                    if char == SPACE_DOT_SYMBOL:
                        fmt = QTextCharFormat(self.bad_spacing_format)
                        fmt.setForeground(self.space_dot_format.foreground())
                        self.setFormat(idx, 1, fmt)
                    else:
                        self.setFormat(idx, 1, self.bad_spacing_format)

            # 1. Double spaces
            for match in _DOUBLE_SPACE_PATTERN.finditer(text):
                start, end = match.span()
                apply_bad_spacing_format(start, end - start)
            # 2. Leading spaces
            for match in _LEADING_SPACE_PATTERN.finditer(text):
                start, end = match.span(1)
                prefix = text[:start]
                tags = ALL_TAGS_PATTERN.findall(prefix)
                has_forced = False
                for tag in tags:
                    if self._is_visible_tag(tag):
                        has_forced = True
                        break
                if not has_forced:
                    apply_bad_spacing_format(start, end - start)
            # 3. Tag split spaces
            for match in _TAG_SPLIT_SPACE_PATTERN.finditer(text):
                start, end = match.span()
                match_text = text[start:end]
                tags = ALL_TAGS_PATTERN.findall(match_text)
                has_forced = False
                for tag in tags:
                    if self._is_visible_tag(tag):
                        has_forced = True
                        break
                if not has_forced:
                    apply_bad_spacing_format(start, 1)
                    apply_bad_spacing_format(end - 1, 1)

            # 4. Missing space before/after visible tags
            missing_spacing_id = None
            if self.mw and hasattr(self.mw, 'current_game_rules') and self.mw.current_game_rules:
                missing_spacing_id = getattr(self.mw.current_game_rules, 'PROBLEM_MISSING_ICON_SPACING', None)
            
            if missing_spacing_id:
                enabled = True
                if self.mw and hasattr(self.mw, 'detection_enabled'):
                    enabled = self.mw.detection_enabled.get(missing_spacing_id, True)
                
                if enabled:
                    from utils.utils import find_missing_icon_spacing_spans
                    font_map = getattr(self.mw, "font_map", None) if self.mw else None
                    mappings = getattr(self.mw, "default_tag_mappings", None) if self.mw else None
                    icons = self._get_icon_sequences()
                    spans = find_missing_icon_spacing_spans(text, self._is_visible_tag, font_map, mappings, icons)
                    for start, end in spans:
                        self.setFormat(start, end - start, self.missing_icon_spacing_format)

        # In preview_text_edit, never carry colour state to the next line.
        self.setCurrentBlockState(self.STATE_DEFAULT if _is_preview_widget else current_block_color_state)
