# --- START OF FILE utils/syntax_highlighter.py ---
import sys
import re
from typing import Dict, Iterable, List, Optional, Tuple
from PyQt5.QtCore import QRegExp, Qt
from PyQt5.QtGui import (
    QSyntaxHighlighter,
    QTextBlockUserData,
    QTextCharFormat,
    QColor,
    QFont,
    QPen,
    QTextDocument,
)
from PyQt5.QtWidgets import QWidget, QMainWindow

from .logging_utils import log_debug
from .utils import SPACE_DOT_SYMBOL
from plugins.common.markers import P_NEWLINE_MARKER, L_NEWLINE_MARKER, P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER
from core.glossary_manager import GlossaryManager, GlossaryMatch

class JsonTagHighlighter(QSyntaxHighlighter):
    class GlossaryBlockData(QTextBlockUserData):
        def __init__(self, matches: List[GlossaryMatch]) -> None:
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
        super().__init__(parent)
        self.mw = main_window_ref
        self._editor_widget_ref = editor_widget_ref  # Store reference to the editor widget
        self._glossary_manager: Optional[GlossaryManager] = None
        self._glossary_enabled = False
        self._glossary_format = QTextCharFormat()
        self._glossary_matches_cache: Dict[int, List[Tuple[int, int, GlossaryMatch]]] = {}
        self._glossary_cache_revision: Optional[int] = None
        self._icon_sequences_cache: Dict[int, List[Tuple[int, int]]] = {}
        self._icon_cache_revision: Optional[int] = None
        self._icon_sequences_snapshot: Tuple[str, ...] = ()

        # Spellchecker support
        self._spellchecker_format = QTextCharFormat()
        self._spellchecker_enabled = False

        self.default_text_color = QColor(Qt.black)
        
        current_theme = getattr(self.mw, 'theme', 'auto')
        if current_theme == 'dark':
            self.default_text_color = QColor("#E0E0E0")
        else:
            editor_widget = parent.parent() if parent else None
            if editor_widget and isinstance(editor_widget, QWidget) and hasattr(editor_widget, 'palette'):
                self.default_text_color = editor_widget.palette().color(editor_widget.foregroundRole())

        self.custom_rules = []
        self.curly_tag_format = QTextCharFormat()
        self.bracket_tag_format = QTextCharFormat()
        self.newline_symbol_format = QTextCharFormat()
        self.literal_newline_format = QTextCharFormat()
        self.space_dot_format = QTextCharFormat()
        self.p_marker_format = QTextCharFormat()
        self.l_marker_format = QTextCharFormat()


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
        self._invalidate_icon_cache()
        # QSyntaxHighlighter automatically handles rehighlighting the changed blocks.
        # Calling rehighlight() here can interrupt its internal state and strip colors during setPlainText.

    def set_glossary_manager(self, manager: Optional[GlossaryManager]) -> None:
        self._glossary_manager = manager
        self._glossary_enabled = bool(manager and manager.get_entries())
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

    def _apply_css_to_format(self, char_format, css_str, base_color=None):
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
                    if value == 'bold': char_format.setFontWeight(QFont.Bold)
                    elif value == 'normal': char_format.setFontWeight(QFont.Normal)
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
        
        doc = self.document()
        editor_widget = doc.parent() if doc else None
        
        current_theme = getattr(self.mw, 'theme', 'auto')
        if current_theme == 'dark':
            self.default_text_color = QColor("#E0E0E0")
        else:
            if editor_widget and hasattr(editor_widget, 'palette'):
                self.default_text_color = editor_widget.palette().color(editor_widget.foregroundRole())
            else:
                 self.default_text_color = QColor(Qt.black)
        
        self.color_default_format.setForeground(self.default_text_color)
        
        self.custom_rules = []
        if self.mw and hasattr(self.mw, 'current_game_rules') and self.mw.current_game_rules:
            plugin_rules = self.mw.current_game_rules.get_syntax_highlighting_rules()
            if plugin_rules:
                self.custom_rules = plugin_rules

        self._apply_css_to_format(self.curly_tag_format, tag_css_str)
        self._apply_css_to_format(self.bracket_tag_format, tag_css_str)
        
        self._apply_css_to_format(self.newline_symbol_format, newline_css_str)
        self._apply_css_to_format(self.literal_newline_format, "color: red; font-weight: bold;")
        
        self.p_marker_format.setForeground(QColor("green"))
        self.p_marker_format.setFontWeight(QFont.Bold)
        self.l_marker_format.setForeground(QColor("orange"))
        self.l_marker_format.setFontWeight(QFont.Bold)

        self.icon_sequence_format = QTextCharFormat()
        icon_bg = QColor("#C8E6C9")
        try:
            icon_bg.setAlpha(180)
        except Exception:
            pass
        self.icon_sequence_format.setBackground(icon_bg)
        self.icon_sequence_format.setFontWeight(QFont.Bold)

        try: self.space_dot_format.setForeground(QColor(space_dot_color_hex))
        except Exception: self.space_dot_format.setForeground(QColor(Qt.lightGray))

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
        self.silver_text_format.setForeground(QColor("#C0C0C0"))
        self.orange_text_format.setForeground(QColor("#FFA500"))

        self._glossary_format = QTextCharFormat()
        self._glossary_format.setFontUnderline(True)
        self._glossary_format.setUnderlineStyle(QTextCharFormat.SingleUnderline)
        underline_color = QColor("#1a73e8") if current_theme != 'dark' else QColor("#8ab4f8")
        try:
            self._glossary_format.setUnderlineColor(underline_color)
        except Exception:
            pass

        # Configure spellchecker format (red wavy underline)
        self._spellchecker_format = QTextCharFormat()
        self._spellchecker_format.setFontUnderline(True)
        self._spellchecker_format.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        try:
            self._spellchecker_format.setUnderlineColor(QColor("#FF0000"))
        except Exception:
            pass

        self.newline_char = newline_symbol
        self._glossary_matches_cache.clear()
        self._glossary_cache_revision = None
        if self.document():
             self.rehighlight()

    def _invalidate_icon_cache(self) -> None:
        self._icon_sequences_cache.clear()
        self._icon_cache_revision = None
        self._icon_sequences_snapshot = ()

    def _rebuild_glossary_cache(self) -> None:
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

    def _ensure_icon_cache(self, sequences: List[str]) -> None:
        if not self._should_highlight_icons():
            self._icon_sequences_cache.clear()
            self._icon_cache_revision = None
            self._icon_sequences_snapshot = ()
            return

        doc = self.document()
        if not doc:
            self._icon_sequences_cache.clear()
            self._icon_cache_revision = None
            self._icon_sequences_snapshot = ()
            return

        revision = doc.revision()
        snapshot = tuple(sequences)
        if (self._icon_cache_revision == revision
                and self._icon_sequences_snapshot == snapshot):
            return

        self._icon_cache_revision = revision
        self._icon_sequences_snapshot = snapshot
        self._icon_sequences_cache.clear()

        if not sequences:
            return

        first_char_map: Dict[str, List[str]] = {}
        for token in sequences:
            if not token:
                continue
            first_char_map.setdefault(token[0], []).append(token)
        for token_list in first_char_map.values():
            token_list.sort(key=len, reverse=True)

        block = doc.firstBlock()
        while block.isValid():
            block_text = block.text()
            matches: List[Tuple[int, int]] = []
            index = 0
            text_length = len(block_text)
            while index < text_length:
                char = block_text[index]
                candidates = first_char_map.get(char)
                matched = False
                if candidates:
                    for token in candidates:
                        token_len = len(token)
                        if token_len <= 0 or index + token_len > text_length:
                            continue
                        if block_text.startswith(token, index):
                            matches.append((index, token_len))
                            index += token_len
                            matched = True
                            break
                if not matched:
                    index += 1
            if matches:
                self._icon_sequences_cache[block.blockNumber()] = matches
            block = block.next()

    def _get_icon_matches_for_block(self, sequences: List[str]) -> List[Tuple[int, int]]:
        if not sequences:
            return []
        self._ensure_icon_cache(sequences)
        block_number = self.currentBlock().blockNumber()
        return self._icon_sequences_cache.get(block_number, [])


    def _get_icon_sequences(self) -> List[str]:
        main_window = self.mw
        sequences = getattr(main_window, 'icon_sequences', None) if main_window else None
        if isinstance(sequences, list):
            return sequences
        return []

    def _should_highlight_icons(self) -> bool:
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
            # Only check spelling in edited_text_edit
            return hasattr(self._editor_widget_ref, 'objectName') and self._editor_widget_ref.objectName() == 'edited_text_edit'

        return False

    def _extract_words_from_text(self, text: str) -> List[Tuple[int, int, str]]:
        """Extract words from text, returning (start, end, word) tuples."""
        # Replace middle dots with spaces for word detection
        text_with_spaces = text.replace('·', ' ')

        # Pattern matches word characters including Cyrillic, apostrophes
        word_pattern = re.compile(r"[a-zA-Zа-яА-ЯіїІїЄєґҐ']+")
        words = []
        for match in word_pattern.finditer(text_with_spaces):
            words.append((match.start(), match.end(), match.group(0)))
        return words


    def highlightBlock(self, text):
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
        
        color_tag_pattern = re.compile(
            r"(\[(Red|Green|Blue|Yellow|l_Blue|Purple|Silver|Orange|White)\])|"
            r"(\[/C\])|"
            r"(\{\s*Color\s*:\s*(Red|Green|Blue|White)\s*\})",
            re.IGNORECASE
        )

        last_pos = 0
        current_block_color_state = previous_color_state
        for match in color_tag_pattern.finditer(text):
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
                elif color == 'silver': current_block_color_state = self.STATE_SILVER
                elif color == 'orange': current_block_color_state = self.STATE_ORANGE
                else: current_block_color_state = self.STATE_DEFAULT # White
            elif ww_closing_tag:
                current_block_color_state = self.STATE_DEFAULT
            elif mc_color_name:
                color = mc_color_name.lower()
                if color == 'red': current_block_color_state = self.STATE_RED
                elif color == 'green': current_block_color_state = self.STATE_GREEN
                elif color == 'blue': current_block_color_state = self.STATE_BLUE
                else: current_block_color_state = self.STATE_DEFAULT # White
            
            last_pos = end
        
        if last_pos < len(text):
            final_format = format_map.get(current_block_color_state, self.color_default_format)
            self.setFormat(last_pos, len(text) - last_pos, final_format)

        # Apply custom rules from the game plugin
        rules_to_apply = self.custom_rules
        
        # Performance optimization for the preview window by not highlighting bracket tags (controller buttons)
        doc = self.document()
        if doc:
            editor_widget = doc.parent()
            if hasattr(editor_widget, 'objectName') and editor_widget.objectName() == 'preview_text_edit':
                rules_to_apply = [rule for rule in self.custom_rules if r"(\[\s*[^\]]*?\s*\])" not in rule[0]]

        all_rules = rules_to_apply + [
            (r"(\{[^}]*\})", self.curly_tag_format),
            (r"(\[[^\]]*\])", self.bracket_tag_format),
            (r"(\\n)", self.literal_newline_format),
            (re.escape(self.newline_char), self.newline_symbol_format),
            (re.escape(SPACE_DOT_SYMBOL), self.space_dot_format),
            (re.escape(P_NEWLINE_MARKER), self.p_marker_format),
            (re.escape(L_NEWLINE_MARKER), self.l_marker_format),
            (re.escape(P_VISUAL_EDITOR_MARKER), self.p_marker_format),
            (re.escape(L_VISUAL_EDITOR_MARKER), self.l_marker_format),
        ]
        
        for pattern_str, fmt in all_rules:
            try:
                for match in re.finditer(pattern_str, text):
                    self.setFormat(match.start(), match.end() - match.start(), fmt)
            except Exception as e:
                log_debug(f"Error applying syntax rule (pattern: '{pattern_str}'): {e}")

        icon_sequences = self._get_icon_sequences()
        if icon_sequences and self._should_highlight_icons():
            matches = self._get_icon_matches_for_block(icon_sequences)
            for start, length in matches:
                existing_format = self.format(start)
                combined_format = QTextCharFormat(existing_format)
                icon_bg = self.icon_sequence_format.background()
                if icon_bg.style() != Qt.NoBrush:
                    combined_format.setBackground(icon_bg)
                if self.icon_sequence_format.fontWeight() != QFont.Normal:
                    combined_format.setFontWeight(self.icon_sequence_format.fontWeight())
                self.setFormat(start, length, combined_format)

        glossary_matches_for_block: List[Tuple[int, int, GlossaryMatch]] = []
        if self._glossary_enabled and self._glossary_manager:
            self._rebuild_glossary_cache()
            glossary_matches_for_block = self._glossary_matches_cache.get(
                self.currentBlock().blockNumber(), []
            )
            underline_style = self._glossary_format.underlineStyle()
            underline_color = self._glossary_format.underlineColor()
            has_custom_color = underline_color.isValid()
            for local_start, local_length, match in glossary_matches_for_block:
                if local_length <= 0:
                    continue
                for offset in range(local_length):
                    index = local_start + offset
                    if index >= len(text):
                        break
                    existing_format = self.format(index)
                    existing_format.setFontUnderline(True)
                    existing_format.setUnderlineStyle(underline_style)
                    if has_custom_color:
                        existing_format.setUnderlineColor(underline_color)
                    self.setFormat(index, 1, existing_format)

        if glossary_matches_for_block:
            block_matches = [
                GlossaryMatch(
                    entry=match.entry,
                    start=local_start,
                    end=local_start + local_length,
                )
                for local_start, local_length, match in glossary_matches_for_block
                if local_length > 0
            ]
            self.setCurrentBlockUserData(self.GlossaryBlockData(block_matches))
        else:
            self.setCurrentBlockUserData(None)

        # Spellchecker highlighting
        if self._should_check_spelling() and self.mw:
            spellchecker_manager = getattr(self.mw, 'spellchecker_manager', None)
            if spellchecker_manager and spellchecker_manager.enabled:
                words = self._extract_words_from_text(text)
                for start, end, word in words:
                    if spellchecker_manager.is_misspelled(word):
                        word_length = end - start
                        for offset in range(word_length):
                            index = start + offset
                            if index >= len(text):
                                break
                            existing_format = self.format(index)
                            existing_format.setFontUnderline(True)
                            existing_format.setUnderlineStyle(self._spellchecker_format.underlineStyle())
                            underline_color = self._spellchecker_format.underlineColor()
                            if underline_color.isValid():
                                existing_format.setUnderlineColor(underline_color)
                            self.setFormat(index, 1, existing_format)

        self.setCurrentBlockState(current_block_color_state)