"""JsonTagHighlighter composition."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QSyntaxHighlighter,
    QTextBlockUserData,
    QTextCharFormat,
    QColor,
    QTextDocument,
    QPalette,
)
from PyQt6.QtWidgets import QWidget

from utils.logging_utils import log_debug
from core.glossary_manager import GlossaryManager, GlossaryMatch
from utils.syntax.styles_mixin import StylesMixin
from utils.syntax.cache_mixin import CacheMixin
from utils.syntax.highlight_mixin import HighlightMixin


class JsonTagHighlighter(
    HighlightMixin,
    CacheMixin,
    StylesMixin,
    QSyntaxHighlighter,
):
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
        """While True, highlightBlock skips glossary, spellcheck, tags, icons and spacing."""
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
