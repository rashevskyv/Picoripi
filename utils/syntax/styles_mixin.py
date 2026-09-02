"""Styles mixin for JsonTagHighlighter."""
from __future__ import annotations

import re

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QPalette

from utils.logging_utils import log_debug
from utils.utils import SPACE_DOT_SYMBOL
from plugins.common.markers import (
    P_NEWLINE_MARKER,
    L_NEWLINE_MARKER,
    P_VISUAL_EDITOR_MARKER,
    L_VISUAL_EDITOR_MARKER,
)


class StylesMixin:
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
