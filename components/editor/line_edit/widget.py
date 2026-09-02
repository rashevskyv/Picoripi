"""LineNumberedTextEdit composition and core setup."""
from __future__ import annotations

from typing import Optional, List, Tuple

from PyQt6.QtWidgets import QPlainTextEdit, QMainWindow, QMenu
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, pyqtSignal

from components.editor.line_number_area import LineNumberArea
from components.editor.minimap import TextMinimap
from components.editor.text_highlight_manager import TextHighlightManager
from utils.syntax_highlighter import JsonTagHighlighter
from core.glossary_manager import GlossaryEntry

from utils.constants import (
    EDITOR_PLAYER_TAG as EDITOR_PLAYER_TAG_CONST,
    ORIGINAL_PLAYER_TAG as ORIGINAL_PLAYER_TAG_CONST,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
    MONOSPACE_EDITOR_FONT_FAMILY as DEFAULT_EDITOR_FONT_FAMILY_CONST,
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
)
from components.editor.constants import (
    CHARACTER_LIMIT_LINE_POSITION, CHARACTER_LIMIT_LINE_COLOR, CHARACTER_LIMIT_LINE_STYLE, CHARACTER_LIMIT_LINE_WIDTH,
    WIDTH_THRESHOLD_LINE_COLOR, WIDTH_THRESHOLD_LINE_STYLE, WIDTH_THRESHOLD_LINE_WIDTH
)
from components.editor.mouse_handlers import LNETMouseHandlers
from components.editor.highlight_interface import LNETHighlightInterface
from components.editor.paint_helpers import LNETPaintHelpers
from components.editor.paint_event_logic import LNETPaintEventLogic
from components.editor.line_number_area_paint_logic import LNETLineNumberAreaPaintLogic
from components.editor.lnet_context_menu_logic import LNETContextMenuLogic
from components.editor.lnet_spellcheck_logic import LNETSpellcheckLogic
from components.editor.lnet_tooltips import LNETTooltipLogic
from components.editor.lnet_tag_helpers import LNETTagHelpers
from components.editor.lnet_highlight_wrappers import LNETHighlightWrappers
from components.editor.lnet_keyboard_handler import LNETKeyboardHandler
from components.editor import lnet_editor_setup
from components.editor.line_edit.guidelines_mixin import GuidelinesMixin
from components.editor.line_edit.selection_mixin import SelectionMixin
from components.editor.line_edit.layout_mixin import LayoutMixin
from components.editor.line_edit.highlights_mixin import HighlightsMixin
from components.editor.line_edit.context_mixin import ContextMixin


class LineNumberedTextEdit(
    GuidelinesMixin,
    SelectionMixin,
    LayoutMixin,
    HighlightsMixin,
    ContextMixin,
    QPlainTextEdit,
):
    """Line numbered text edit implementation."""
    lineClicked = pyqtSignal(int)
    previewSelectionChanged = pyqtSignal(list)
    addTagMappingRequest = pyqtSignal(str, str)
    calculateLineWidthRequest = pyqtSignal(int)

    def __init__(self, parent=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.widget_id = str(id(self))[-6:]
        
        self._selected_lines = set()
        self._last_clicked_line = -1
        self._previously_selected_lines = set()
        self.drag_start_pos = None

        self.custom_line_numbers = None
        self.custom_subline_numbers = None
        self.override_total_lines = None

        self.editor_player_tag = EDITOR_PLAYER_TAG_CONST
        self.original_player_tag = ORIGINAL_PLAYER_TAG_CONST
        self.font_map = {}
        self._game_dialog_max_width_pixels = DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS
        self._line_width_warning_threshold_pixels = DEFAULT_LINE_WIDTH_WARNING_THRESHOLD
        self._show_width_guideline = True
        self.guideline_positions = {}

        if parent and isinstance(parent, QMainWindow):
            self.editor_player_tag = getattr(parent, 'EDITOR_PLAYER_TAG', EDITOR_PLAYER_TAG_CONST)
            self.original_player_tag = getattr(parent, 'ORIGINAL_PLAYER_TAG', ORIGINAL_PLAYER_TAG_CONST)
            self.font_map = getattr(parent, 'font_map', {})
            self._game_dialog_max_width_pixels = getattr(parent, 'game_dialog_max_width_pixels', DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS)
            self._line_width_warning_threshold_pixels = getattr(parent, 'line_width_warning_threshold_pixels', DEFAULT_LINE_WIDTH_WARNING_THRESHOLD)
            self._show_width_guideline = getattr(parent, 'show_width_guideline', True)
            self.character_limit_line_position = getattr(parent, 'editor_char_limit_line_pos', CHARACTER_LIMIT_LINE_POSITION)

        self.show_minimap = False
        self.lineNumberArea = LineNumberArea(self)
        self.minimap = TextMinimap(self)
        
        main_window_ref = parent if isinstance(parent, QMainWindow) else (self.window() if isinstance(self.window(), QMainWindow) else None)
        lnet_editor_setup.set_theme_colors(self, main_window_ref)

        self.highlightManager = TextHighlightManager(self)
        self.mouse_handler = LNETMouseHandlers(self) 
        self.highlight_interface = LNETHighlightInterface(self)
        
        self.paint_helpers = LNETPaintHelpers(self)
        self.paint_event_logic = LNETPaintEventLogic(self, self.paint_helpers)
        self.lineNumberArea.paint_logic = LNETLineNumberAreaPaintLogic(self, self.paint_helpers, main_window_ref)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.blockCountChanged.connect(lambda: self.highlightManager.schedule_zebra_update() if hasattr(self, 'highlightManager') and self.highlightManager else None)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.verticalScrollBar().valueChanged.connect(self.highlightManager.schedule_zebra_update)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.mouse_handler.showContextMenu)


        if not self.isReadOnly():
            self.cursorPositionChanged.connect(self.highlightManager.updateCurrentLineHighlight)
            self.setUndoRedoEnabled(False)

        self.updateLineNumberAreaWidth(0)

        initial_font = QFont(DEFAULT_EDITOR_FONT_FAMILY_CONST)
        font_size_to_set = 10
        if parent and hasattr(parent, 'current_font_size') and parent.current_font_size > 0:
            font_size_to_set = parent.current_font_size
        initial_font.setPointSize(font_size_to_set)
        self.setFont(initial_font)

        self.highlighter = JsonTagHighlighter(self.document(), main_window_ref=main_window_ref, editor_widget_ref=self)
        self._current_glossary_tooltip: Optional[str] = None
        self._hovered_glossary_entry: Optional[GlossaryEntry] = None
        self._glossary_manager = None
        self.setMouseTracking(True)
        self.ensurePolished()

        self.character_limit_line_position = CHARACTER_LIMIT_LINE_POSITION
        self.character_limit_line_color = CHARACTER_LIMIT_LINE_COLOR
        self.character_limit_line_style = CHARACTER_LIMIT_LINE_STYLE
        self.character_limit_line_width = CHARACTER_LIMIT_LINE_WIDTH
        
        self.width_threshold_line_color = WIDTH_THRESHOLD_LINE_COLOR
        self.width_threshold_line_style = WIDTH_THRESHOLD_LINE_STYLE
        self.width_threshold_line_width = WIDTH_THRESHOLD_LINE_WIDTH

        # Logic delegates
        self.context_menu_logic = LNETContextMenuLogic(self)
        self.spellcheck_logic = LNETSpellcheckLogic(self)
        self.tooltip_logic = LNETTooltipLogic(self)
        self.tag_helpers = LNETTagHelpers(self)
        self.hi_wrappers = LNETHighlightWrappers(self)
        self.keyboard_handler = LNETKeyboardHandler(self)
        self.custom_double_click_handler = None

        lnet_editor_setup.update_auxiliary_widths(self)
        self.highlightManager.update_zebra_stripes()

    def setPlainText(self, text: str):
        # When text is reset entirely, we MUST clear all document-specific highlights
        # because the old cursors will be invalid.
        """Setplaintext."""
        self._selected_lines.clear()
        self._previously_selected_lines.clear()
        self._last_clicked_line = -1
        if hasattr(self, 'highlightManager'):
            self.highlightManager.clearAllHighlights()
        if hasattr(self, 'highlighter') and self.highlighter:
            self.highlighter._async_glossary_matches = None
            self.highlighter._async_translation_matches = None
            self.highlighter._async_spellcheck_matches = None
            
            # Reset cache revisions and local matches maps so a full rebuild is forced
            self.highlighter._glossary_cache_revision = None
            if hasattr(self.highlighter, '_glossary_matches_cache') and self.highlighter._glossary_matches_cache:
                self.highlighter._glossary_matches_cache.clear()
                
            self.highlighter._translation_cache_revision = None
            if hasattr(self.highlighter, '_translation_matches_cache') and self.highlighter._translation_matches_cache:
                self.highlighter._translation_matches_cache.clear()
                
            if hasattr(self.highlighter, '_icon_cache_revision'):
                self.highlighter._icon_cache_revision = None
            if hasattr(self.highlighter, '_icon_sequences_cache') and self.highlighter._icon_sequences_cache:
                self.highlighter._icon_sequences_cache.clear()
                
        super().setPlainText(text)
        # If we have an active glossary, we must re-trigger highlighting
        # because set_glossary_manager ran while the editor was empty,
        # so rehighlight() did nothing at that time. Skip while typing_mode:
        # setPlainText already highlighted with the cheap default format.
        if text and hasattr(self, 'highlighter') and self.highlighter:
            highlighter = self.highlighter
            if getattr(highlighter, '_typing_mode', False):
                return
            if getattr(highlighter, '_glossary_enabled', False) or getattr(highlighter, '_is_translation_mode', False):
                highlighter.rehighlight()
        # Defer guideline recalculation so Qt has time to finalize block layouts.
        # Without this, QTextBlock.layout().lineAt() returns invalid lines immediately
        # after setPlainText, producing empty guideline_positions.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self.recalculate_guidelines)

    def _set_theme_colors(self, main_window_ref):
        """Internal helper to set the theme colors."""
        lnet_editor_setup.set_theme_colors(self, main_window_ref)

    def _create_tag_button(self, parent_widget, display: str, open_tag: str, close_tag: str = None, menu: QMenu = None):
        """Internal helper to create tag button."""
        return lnet_editor_setup.create_tag_button(self, parent_widget, display, open_tag, close_tag, menu)

    def _update_auxiliary_widths(self):
        """Internal helper to update the auxiliary widths."""
        lnet_editor_setup.update_auxiliary_widths(self)

    def setFont(self, font: QFont):
        """Setfont."""
        super().setFont(font)
        if hasattr(self, 'highlighter') and self.highlighter:
            self.highlighter.rehighlight()
        self._update_auxiliary_widths()
        if hasattr(self, 'lineNumberArea'):
             self.lineNumberArea.update()
        self.viewport().update()

    def setReadOnly(self, ro):
        """Setreadonly."""
        super().setReadOnly(ro)
        self.highlightManager.clearAllHighlights()
        if not ro:
             self.highlightManager.updateCurrentLineHighlight()
             self.setUndoRedoEnabled(False)

    def _get_icon_sequences(self) -> List[str]:
        """Internal helper to get the icon sequences."""
        if self.objectName() == 'preview_text_edit':
            return []
        main_window = self.window()
        if isinstance(main_window, QMainWindow):
            sequences = getattr(main_window, 'icon_sequences', None)
            if isinstance(sequences, list):
                return sequences
        return []

    def _find_icon_sequence_in_block(self, block_text: str, sequences: List[str], position_in_block: int) -> Optional[Tuple[int, int, str]]:
        """Internal helper to find icon sequence in block."""
        return self.tag_helpers.find_icon_sequence_in_block(block_text, sequences, position_in_block)

    def _snap_cursor_out_of_icon_sequences(self, move_right: bool) -> bool:
        """Internal helper to snap cursor out of icon sequences."""
        return self.tag_helpers.snap_cursor_out_of_icon_sequences(move_right)
