from PyQt6.QtWidgets import (QPlainTextEdit, QMainWindow, QMenu, QApplication, QWidget, QHBoxLayout, QWidgetAction, QToolTip)
from PyQt6.QtGui import (QAction)
from PyQt6.QtGui import (QFont, QPaintEvent, QKeyEvent, QMouseEvent, QTextCursor, QDrag)
from PyQt6.QtCore import Qt, QRect, QRectF, pyqtSignal, QPoint, QMimeData, QByteArray
from typing import Optional, List, Tuple
from pathlib import Path

from .line_number_area import LineNumberArea
from .minimap import TextMinimap
from .text_highlight_manager import TextHighlightManager
from utils.logging_utils import log_debug, log_error
from utils.syntax_highlighter import JsonTagHighlighter
from core.glossary_manager import GlossaryEntry

from utils.constants import (
    EDITOR_PLAYER_TAG as EDITOR_PLAYER_TAG_CONST,
    ORIGINAL_PLAYER_TAG as ORIGINAL_PLAYER_TAG_CONST,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
    MONOSPACE_EDITOR_FONT_FAMILY as DEFAULT_EDITOR_FONT_FAMILY_CONST,
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS
)
from .constants import (
    CHARACTER_LIMIT_LINE_POSITION, CHARACTER_LIMIT_LINE_COLOR, CHARACTER_LIMIT_LINE_STYLE, CHARACTER_LIMIT_LINE_WIDTH,
    WIDTH_THRESHOLD_LINE_COLOR, WIDTH_THRESHOLD_LINE_STYLE, WIDTH_THRESHOLD_LINE_WIDTH
)
from .mouse_handlers import LNETMouseHandlers
from .highlight_interface import LNETHighlightInterface
from .paint_helpers import LNETPaintHelpers
from .paint_event_logic import LNETPaintEventLogic
from .line_number_area_paint_logic import LNETLineNumberAreaPaintLogic
from .lnet_context_menu_logic import LNETContextMenuLogic
from .lnet_spellcheck_logic import LNETSpellcheckLogic
from .lnet_tooltips import LNETTooltipLogic
from .lnet_dialogs import MassFontDialog, MassWidthDialog
from .lnet_tag_helpers import LNETTagHelpers
from .lnet_highlight_wrappers import LNETHighlightWrappers
from .lnet_keyboard_handler import LNETKeyboardHandler
from . import lnet_editor_setup

class LineNumberedTextEdit(QPlainTextEdit):
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
        self.blockCountChanged.connect(lambda: self.highlightManager.update_zebra_stripes() if hasattr(self, 'highlightManager') and self.highlightManager else None)
        self.updateRequest.connect(self.updateLineNumberArea)

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

    def handle_line_number_click(self, y_pos: int):
        """Handle line number click."""
        self.mouse_handler.handle_line_number_click(y_pos)

    def handle_line_number_double_click(self, y_pos: int):
        """Handle line number double click."""
        self.mouse_handler.handle_line_number_double_click(y_pos)

    def set_glossary_manager(self, manager) -> None:
        """Set the glossary manager."""
        self._glossary_manager = manager
        if hasattr(self, 'highlighter') and self.highlighter:
            self.highlighter.set_glossary_manager(manager)

    def _replace_word_at_cursor(self, word_cursor: QTextCursor, replacement: str) -> None:
        """Replace the word selected by the given cursor with the replacement text."""
        if word_cursor.hasSelection():
            word_cursor.insertText(replacement)

    def _open_spellcheck_dialog_for_selection(self, position_in_widget_coords: QPoint) -> None:
        """Internal helper to open spellcheck dialog for selection."""
        self.spellcheck_logic.open_dialog_for_selection(position_in_widget_coords)

    def _apply_corrected_text_to_editor(self, corrected_text: str, line_numbers: List[int]) -> None:
        """Internal helper to apply corrected text to editor."""
        self.spellcheck_logic.apply_corrected_text(corrected_text, line_numbers)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Mousemoveevent."""
        cursor = self.cursorForPosition(event.pos())
        block = cursor.block()
        entry = self._find_glossary_entry_at(event.pos())
        warning_tooltip = self._find_warning_tooltip_at(event.pos())
        
        tooltip_text = None
        if entry:
            main_window = self.window()
            font_size = getattr(main_window, 'tooltip_font_size', 11)
            lines = [f"<div style='font-size: {font_size}px;'><b>{entry.original}</b> → {entry.translation}"]
            if entry.notes:
                try:
                    import markdown
                    # Convert markdown to html with nl2br to preserve single newlines
                    notes_html = markdown.markdown(entry.notes, extensions=['nl2br'])
                    notes_html = f"<div style='margin-top: 4px; font-size: {font_size}px;'>{notes_html}</div>"
                except Exception:
                    notes_html = f"<div style='margin-top: 4px; font-style: italic; font-size: {font_size}px;'>{entry.notes}</div>"
                lines.append(notes_html)
            lines.append("</div>")
            tooltip_text = "".join(lines)
            
        # USER_REQUEST: Tooltips should be EXCLUSIVELY on the number area.
        # Warning tooltips from the main text area are now handled only by handle_line_number_area_mouse_move
        # for the LineNumberArea. We keep glossary tooltips here if needed, but remove warning_tooltip logic.

        # Tracking state to avoid flickering but allow position updates between lines
        current_state = (tooltip_text, block.blockNumber()) if entry else None
        last_state = getattr(self, '_last_tooltip_state', None)

        if tooltip_text:
            if current_state != last_state or not QToolTip.isVisible():
                QToolTip.showText(self.mapToGlobal(event.pos()), tooltip_text, self)
                self._last_tooltip_state = current_state
                self._current_combined_tooltip = tooltip_text
        elif getattr(self, '_current_combined_tooltip', None):
            QToolTip.hideText()
            self._current_combined_tooltip = None
            self._last_tooltip_state = None

        self._hovered_glossary_entry = entry
        self._hovered_warning_text = warning_tooltip

        if self.objectName() == "preview_text_edit" and event.buttons() == Qt.MouseButton.LeftButton and self._selected_lines:
            if self.drag_start_pos is not None and (event.pos() - self.drag_start_pos).manhattanLength() > QApplication.startDragDistance():
                drag = QDrag(self)
                mime_data = QMimeData()
                
                data = QByteArray()
                data.append(str(sorted(list(self._selected_lines))).encode('utf-8'))
                mime_data.setData("application/x-selected-lines", data)
                
                drag.setMimeData(mime_data)
                drag.exec(Qt.DropAction.MoveAction)
                self.drag_start_pos = None

        super().mouseMoveEvent(event)

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
        # so rehighlight() did nothing at that time.
        if text and hasattr(self, 'highlighter') and self.highlighter:
            highlighter = self.highlighter
            if getattr(highlighter, '_glossary_enabled', False) or getattr(highlighter, '_is_translation_mode', False):
                highlighter.rehighlight()
        # Defer guideline recalculation so Qt has time to finalize block layouts.
        # Without this, QTextBlock.layout().lineAt() returns invalid lines immediately
        # after setPlainText, producing empty guideline_positions.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self.recalculate_guidelines)

    def calculate_block_guidelines(self, block, font_map, sequences, limit_px, default_tag_mappings=None) -> None:
        """Calculate block guidelines."""
        from utils.utils import calculate_string_width, convert_dots_to_spaces_from_editor
        from PyQt6.QtGui import QTextCursor

        if not hasattr(self, 'guideline_positions'):
            self.guideline_positions = {}

        layout = block.layout()
        if not layout:
            return

        block_text_raw = convert_dots_to_spaces_from_editor(block.text())
        block_num = block.blockNumber()

        # Initialize all visual lines of this block to False (default: no guideline)
        for i in range(layout.lineCount()):
            self.guideline_positions[(block_num, i)] = False

        main_win = self.window()
        rules = getattr(main_win, 'current_game_rules', None)

        def get_width(txt):
            """Get the width."""
            if rules and hasattr(rules, 'calculate_string_width_override'):
                override_val = rules.calculate_string_width_override(txt, font_map)
                if isinstance(override_val, (int, float)):
                    return override_val
            return calculate_string_width(txt, font_map, icon_sequences=sequences, default_tag_mappings=default_tag_mappings)

        block_width_px = get_width(block_text_raw.rstrip())
        is_exceeded = (block_width_px > limit_px)

        cursor = QTextCursor(self.document())

        if is_exceeded:
            # Find the exact character index k (1-based) where the threshold is crossed
            found = False
            for k in range(1, len(block_text_raw) + 1):
                prefix = block_text_raw[:k]
                prefix_w = get_width(prefix)
                if prefix_w >= limit_px:
                    prev_prefix = block_text_raw[:k-1]
                    prev_w = get_width(prev_prefix)

                    # Find which visual line contains character index k - 1
                    found_line = -1
                    for i in range(layout.lineCount()):
                        line = layout.lineAt(i)
                        if not line.isValid():
                            continue
                        line_start = line.textStart()
                        line_len = line.textLength()
                        is_last = (i == layout.lineCount() - 1)
                        if line_start <= k - 1 < line_start + line_len or (is_last and k - 1 == line_start + line_len):
                            found_line = i
                            break

                    if found_line != -1:
                        line = layout.lineAt(found_line)

                        cursor.setPosition(block.position() + k - 1)
                        x_prev = self.cursorRect(cursor).left()

                        cursor.setPosition(block.position() + k)
                        x_curr = self.cursorRect(cursor).left()

                        if prefix_w > prev_w:
                            fraction = (limit_px - prev_w) / (prefix_w - prev_w)
                        else:
                            fraction = 0
                        limit_x = x_prev + fraction * (x_curr - x_prev)
                        self.guideline_positions[(block_num, found_line)] = (limit_x, True)
                        found = True
                        break
            # Fallback if somehow not found (should not happen if block_width_px > limit_px)
            if not found and layout.lineCount() > 0:
                last_idx = layout.lineCount() - 1
                line = layout.lineAt(last_idx)
                cursor.setPosition(block.position() + line.textStart() + line.textLength())
                self.guideline_positions[(block_num, last_idx)] = (self.cursorRect(cursor).left(), True)
        else:
            # Not exceeded: green dashed line on the last visual line
            if layout.lineCount() > 0:
                last_idx = layout.lineCount() - 1
                line = layout.lineAt(last_idx)
                if line.isValid():
                    line_start = line.textStart()
                    line_len = line.textLength()
                    line_text = block_text_raw[line_start:line_start + line_len]
                    line_text_stripped = line_text.rstrip()

                    cumulative_width_before_last_line = get_width(block_text_raw[:line_start])
                    last_line_game_width = get_width(line_text_stripped)

                    cursor.setPosition(block.position() + line_start)
                    x_start = self.cursorRect(cursor).left()

                    remaining_px = limit_px - cumulative_width_before_last_line

                    if last_line_game_width > 0:
                        cursor.setPosition(block.position() + line_start + len(line_text_stripped))
                        x_end = self.cursorRect(cursor).left()
                        viewport_text_w = x_end - x_start

                        limit_x = x_start + viewport_text_w * (remaining_px / last_line_game_width)
                    else:
                        fm = self.fontMetrics()
                        char_w = fm.horizontalAdvance('A')
                        limit_x = x_start + remaining_px * (char_w / 7.5)

                    self.guideline_positions[(block_num, last_idx)] = (limit_x, False)

    def recalculate_guidelines(self) -> None:
        """Recalculate guidelines."""
        self.guideline_positions = {}
        if not self.show_width_guideline or self.line_width_warning_threshold_pixels <= 0:
            return

        main_window = self.window()
        font_map = getattr(self, 'font_map', {})
        if not font_map and hasattr(main_window, 'font_map'):
            font_map = main_window.font_map

        limit_px = self.line_width_warning_threshold_pixels

        if hasattr(main_window, 'data_store') and hasattr(main_window, 'helper'):
            block_idx = main_window.data_store.current_block_idx
            string_idx = main_window.data_store.current_string_idx
            if block_idx != -1 and string_idx != -1:
                font_map = main_window.helper.get_font_map_for_string(block_idx, string_idx)
                
                string_meta = getattr(main_window, 'string_metadata', {}).get((block_idx, string_idx), {})
                if "width" in string_meta:
                    custom_w = string_meta["width"]
                    global_max = getattr(main_window, 'game_dialog_max_width_pixels', limit_px)
                    standard_threshold = getattr(main_window, 'line_width_warning_threshold_pixels', limit_px)
                    if global_max > 0:
                        limit_px = int(custom_w * (standard_threshold / global_max))
                    else:
                        limit_px = custom_w

        sequences = getattr(main_window, 'icon_sequences', []) if main_window else []
        default_tag_mappings = getattr(main_window, 'default_tag_mappings', {}) if main_window else {}

        block = self.firstVisibleBlock()

        while block.isValid():
            self.calculate_block_guidelines(block, font_map, sequences, limit_px, default_tag_mappings=default_tag_mappings)
            block = block.next()
        self.viewport().update()

    def reset_selection_state(self):
        """Explicitly reset all selection tracking and visual highlights."""
        self._selected_lines.clear()
        self._previously_selected_lines.clear()
        self._last_clicked_line = -1
        if hasattr(self, 'highlightManager'):
            self.highlightManager.clearAllHighlights()
        self.viewport().update()

    def handle_line_number_area_mouse_move(self, event: QMouseEvent):
        """Handle line number area mouse move."""
        self.mouse_handler.handle_line_number_area_mouse_move(event)


    def get_selected_lines(self):
        """Get the selected lines."""
        return sorted(list(self._selected_lines))

    def set_selected_lines(self, lines: List[int]):
        # Safeguard multi-selection in preview:
        # If we currently have multiple lines selected (len > 1), and a programmatic call
        # tries to select a single line that is already part of the current selection,
        # we ignore it to prevent lazy-loading or text updates from resetting user's selection.
        """Set the selected lines."""
        if len(lines) == 1 and len(self._selected_lines) > 1 and lines[0] in self._selected_lines:
            return

        new_set = set(lines)
        if self._selected_lines == new_set:
            return
        self._selected_lines = new_set
        self._update_selection_highlight()
        self._emit_selection_changed()

    def clear_selection(self):
        """Remove selection."""
        self._selected_lines.clear()
        self._last_clicked_line = -1
        self._update_selection_highlight()
        self._emit_selection_changed()

    def _update_selection_highlight(self):
        """Internal helper to update the selection highlight."""
        lines_to_highlight = self._selected_lines - self._previously_selected_lines
        lines_to_clear = self._previously_selected_lines - self._selected_lines
        
        self.highlightManager.set_background_for_lines(lines_to_highlight, lines_to_clear)
        
        self._previously_selected_lines = self._selected_lines.copy()
        if hasattr(self, 'minimap'):
            self.minimap.update()

    def _emit_selection_changed(self):
        """Internal helper to emit selection changed."""
        self.previewSelectionChanged.emit(self.get_selected_lines())

    def leaveEvent(self, event) -> None:
        """Leaveevent."""
        if getattr(self, '_current_combined_tooltip', None):
            QToolTip.hideText()
            self._current_combined_tooltip = None
        self._last_tooltip_state = None
        self._hovered_glossary_entry = None
        self._hovered_warning_text = None
        super().leaveEvent(event)

    def _find_glossary_entry_at(self, pos):
        """Internal helper to find glossary entry at."""
        if not hasattr(self, '_glossary_manager') or not self._glossary_manager:
            return None
            
        cursor = self.cursorForPosition(pos)
        block = cursor.block()
        if not block.isValid():
            return None
            
        data = block.userData()
        if not data or not hasattr(data, 'matches'):
            return None
            
        pos_in_block = cursor.positionInBlock()
        for match in data.matches:
            if match.start <= pos_in_block < match.end:
                return match.entry
        return None

    def _find_warning_tooltip_at(self, pos: QPoint) -> Optional[str]:
        """Internal helper to find warning tooltip at."""
        return self.tooltip_logic.find_warning_tooltip_at(pos)


    def _set_theme_colors(self, main_window_ref):
        """Internal helper to set the theme colors."""
        lnet_editor_setup.set_theme_colors(self, main_window_ref)

    def _create_tag_button(self, parent_widget, display: str, open_tag: str, close_tag: str = None, menu: QMenu = None):
        """Internal helper to create tag button."""
        return lnet_editor_setup.create_tag_button(self, parent_widget, display, open_tag, close_tag, menu)

    def populateContextMenu(self, menu: QMenu, position_in_widget_coords):
        """Populatecontextmenu."""
        self.context_menu_logic.populate(menu, position_in_widget_coords)

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

    def wheelEvent(self, event):
        """Wheelevent."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            main_window = self.window()
            if hasattr(main_window, 'handle_zoom'):
                target = 'preview' if self.objectName() == "preview_text_edit" else 'editors'
                main_window.handle_zoom(event.angleDelta().y(), target=target)
                event.accept()
                return
            else:
                # Default zoom for non-main windows (e.g. Review Dialog)
                delta = event.angleDelta().y()
                if delta > 0:
                    self.zoomIn(1)
                elif delta < 0:
                    self.zoomOut(1)
                self.updateLineNumberAreaWidth(0)
                event.accept()
                return

        super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Keypressevent."""
        if self.keyboard_handler.handle_key_press(event):
            event.accept()
            return
        super().keyPressEvent(event)

    def setReadOnly(self, ro):
        """Setreadonly."""
        super().setReadOnly(ro)
        self.highlightManager.clearAllHighlights()
        if not ro:
             self.highlightManager.updateCurrentLineHighlight()
             self.setUndoRedoEnabled(False)
    def lineNumberAreaWidth(self):
        """Linenumberareawidth."""
        total_blocks = self.override_total_lines if self.override_total_lines is not None else self.blockCount()
        if hasattr(self, 'custom_line_numbers') and self.custom_line_numbers:
            max_num = max((v for v in self.custom_line_numbers if v is not None), default=1)
            total_blocks = max(total_blocks, max_num)
        digits = 1; max_val = max(1, total_blocks)
        while max_val >= 10: max_val //= 10; digits += 1
        
        # In review dialog, we have dual columns
        is_dual = hasattr(self, 'custom_subline_numbers') and self.custom_subline_numbers is not None
        if is_dual:
            # Add room for second column + separator
            digits += 4

        current_font_metrics = self.fontMetrics()
        # Account for potential "* " prefix for unsaved changes
        asterisk_width = current_font_metrics.horizontalAdvance('* ')
        # Add extra padding for dual column
        padding = 15 if not is_dual else 25
        base_width = asterisk_width + current_font_metrics.horizontalAdvance('9') * (digits) + padding
        additional_width = 0
        if self.objectName() in ["original_text_edit", "edited_text_edit"] and hasattr(self.window(), 'font_map') and self.window().font_map:
            additional_width = self.pixel_width_display_area_width
        elif self.objectName() == "preview_text_edit":
            additional_width = self.preview_indicator_area_width
        return base_width + additional_width

    def minimapAreaWidth(self):
        """Return the right-side minimap margin width."""
        if hasattr(self, 'minimap'):
            return self.minimap.effective_width()
        return 0

    def updateLineNumberAreaWidth(self, _):
        """Updatelinenumberareawidth."""
        new_width = self.lineNumberAreaWidth()
        minimap_width = self.minimapAreaWidth()
        margins = self.viewportMargins()
        if margins.left() != new_width or margins.right() != minimap_width:
            self.setViewportMargins(new_width, 0, minimap_width, 0)
        if hasattr(self, 'lineNumberArea'): 
            self.lineNumberArea.updateGeometry()
            self.lineNumberArea.update()
        if hasattr(self, 'minimap'):
            self.minimap.sync_visibility()
            self._update_minimap_geometry()
            self.minimap.update()

    def updateLineNumberArea(self, rect: QRectF, dy: int):
        """Updatelinenumberarea."""
        if hasattr(self, 'lineNumberArea'): 
            if dy: self.lineNumberArea.scroll(0, dy)
            else: self.lineNumberArea.update(0, 0, self.lineNumberArea.width(), self.lineNumberArea.height())
        if hasattr(self, 'minimap'):
            self._update_minimap_geometry()
            self.minimap.update()

    def _update_minimap_geometry(self):
        """Position the minimap in the right margin before the scrollbar."""
        if not hasattr(self, 'minimap'):
            return

        minimap_width = self.minimapAreaWidth()
        if minimap_width <= 0:
            self.minimap.hide()
            return

        cr = self.contentsRect()
        vbar = self.verticalScrollBar()
        hbar = self.horizontalScrollBar()
        vbar_width = vbar.width() if vbar.isVisible() else 0
        hbar_height = hbar.height() if hbar.isVisible() else 0
        minimap_right = cr.right() - vbar_width
        minimap_height = max(0, cr.height() - hbar_height)
        self.minimap.setGeometry(
            QRect(minimap_right - minimap_width + 1, cr.top(), minimap_width, minimap_height)
        )
        self.minimap.show()

    def resizeEvent(self, event):
        """Resizeevent."""
        super().resizeEvent(event)
        self.updateLineNumberAreaWidth(0)
        cr = self.contentsRect()
        if hasattr(self, 'lineNumberArea'): 
            self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))
        self._update_minimap_geometry()
        if self.isVisible():
            self.viewport().update()
            if hasattr(self, 'minimap'):
                self.minimap.update()

    def paintEvent(self, event: QPaintEvent):
        """Paintevent."""
        super().paintEvent(event)
        if hasattr(self, 'paint_event_logic'): 
            self.paint_event_logic.execute_paint_event(event)

    def lineNumberAreaPaintEvent(self, event, painter_device):
        """Linenumberareapaintevent."""
        if hasattr(self.lineNumberArea, 'paint_logic'):
            self.lineNumberArea.paint_logic.execute_paint_event(event, painter_device)

    def mousePressEvent(self, event: QMouseEvent):
        """Mousepressevent."""
        self.mouse_handler.mousePressEvent(event) 

    def super_mousePressEvent(self, event: QMouseEvent):
        """Super mousepressevent."""
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Mousereleaseevent."""
        self.mouse_handler.mouseReleaseEvent(event) 

    def super_mouseReleaseEvent(self, event: QMouseEvent):
        """Super mousereleaseevent."""
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Mousedoubleclickevent."""
        if self.custom_double_click_handler:
            self.custom_double_click_handler(event)
        else:
            super().mouseDoubleClickEvent(event)

    def super_mouseDoubleClickEvent(self, event: QMouseEvent):
        """Super mousedoubleclickevent."""
        super().mouseDoubleClickEvent(event)

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

    def _momentary_highlight_tag(self, block, start_in_block, length):
        """Internal helper to momentary highlight tag."""
        self.highlight_interface._momentary_highlight_tag(block, start_in_block, length)

    def _apply_all_extra_selections(self):
        """Internal helper to apply all extra selections."""
        self.highlight_interface._apply_all_extra_selections()

    def addCriticalProblemHighlight(self, line_number: int):
        """Addcriticalproblemhighlight."""
        self.hi_wrappers.addCriticalProblemHighlight(line_number)

    def removeCriticalProblemHighlight(self, line_number: int) -> bool:
        """Removecriticalproblemhighlight."""
        return self.hi_wrappers.removeCriticalProblemHighlight(line_number)

    def clearCriticalProblemHighlights(self):
        """Clearcriticalproblemhighlights."""
        self.hi_wrappers.clearCriticalProblemHighlights()

    def hasCriticalProblemHighlight(self, line_number = None) -> bool:
        """Hascriticalproblemhighlight."""
        return self.hi_wrappers.hasCriticalProblemHighlight(line_number)

    def addWarningLineHighlight(self, line_number: int):
        """Addwarninglinehighlight."""
        self.hi_wrappers.addWarningLineHighlight(line_number)

    def removeWarningLineHighlight(self, line_number: int) -> bool:
        """Removewarninglinehighlight."""
        return self.hi_wrappers.removeWarningLineHighlight(line_number)

    def clearWarningLineHighlights(self):
        """Clearwarninglinehighlights."""
        self.hi_wrappers.clearWarningLineHighlights()

    def hasWarningLineHighlight(self, line_number = None) -> bool:
        """Haswarninglinehighlight."""
        return self.hi_wrappers.hasWarningLineHighlight(line_number)

    def addWidthExceededHighlight(self, line_number: int):
        """Addwidthexceededhighlight."""
        self.hi_wrappers.addWidthExceededHighlight(line_number)

    def removeWidthExceededHighlight(self, line_number: int) -> bool:
        """Removewidthexceededhighlight."""
        return self.hi_wrappers.removeWidthExceededHighlight(line_number)

    def clearWidthExceededHighlights(self):
        """Clearwidthexceededhighlights."""
        self.hi_wrappers.clearWidthExceededHighlights()

    def hasWidthExceededHighlight(self, line_number = None) -> bool:
        """Haswidthexceededhighlight."""
        return self.hi_wrappers.hasWidthExceededHighlight(line_number)
    
    def addShortLineHighlight(self, line_number: int):
        """Addshortlinehighlight."""
        self.hi_wrappers.addShortLineHighlight(line_number)

    def removeShortLineHighlight(self, line_number: int) -> bool:
        """Removeshortlinehighlight."""
        return self.hi_wrappers.removeShortLineHighlight(line_number)

    def clearShortLineHighlights(self):
        """Clearshortlinehighlights."""
        self.hi_wrappers.clearShortLineHighlights()

    def hasShortLineHighlight(self, line_number = None) -> bool:
        """Hasshortlinehighlight."""
        return self.hi_wrappers.hasShortLineHighlight(line_number)

    def addEmptyOddSublineHighlight(self, block_number: int):
        """Addemptyoddsublinehighlight."""
        self.hi_wrappers.addEmptyOddSublineHighlight(block_number)

    def removeEmptyOddSublineHighlight(self, block_number: int) -> bool:
        """Removeemptyoddsublinehighlight."""
        return self.hi_wrappers.removeEmptyOddSublineHighlight(block_number)

    def clearEmptyOddSublineHighlights(self):
        """Clearemptyoddsublinehighlights."""
        self.hi_wrappers.clearEmptyOddSublineHighlights()

    def hasEmptyOddSublineHighlight(self, block_number = None) -> bool:
        """Hasemptyoddsublinehighlight."""
        return self.hi_wrappers.hasEmptyOddSublineHighlight(block_number)

    def clearPreviewSelectedLineHighlight(self):
        """Clearpreviewselectedlinehighlight."""
        self.highlightManager.set_background_for_lines(set(), self._previously_selected_lines)
        self.clear_selection()

    def setLinkedCursorPosition(self, line_number: int, column_number: int):
        """Setlinkedcursorposition."""
        self.hi_wrappers.hi.setLinkedCursorPosition(line_number, column_number)

    def applyQueuedHighlights(self):
        """Applyqueuedhighlights."""
        self.highlightManager.applyHighlights()

    def clearAllProblemTypeHighlights(self):
        """Clearallproblemtypehighlights."""
        self.highlightManager.clearAllProblemHighlights()

    def addProblemLineHighlight(self, line_number: int):
        """Addproblemlinehighlight."""
        self.addCriticalProblemHighlight(line_number)

    def removeProblemLineHighlight(self, line_number: int) -> bool:
        """Removeproblemlinehighlight."""
        return self.removeCriticalProblemHighlight(line_number)

    def clearProblemLineHighlights(self):
        """Clearproblemlinehighlights."""
        self.clearAllProblemTypeHighlights()
        
    def hasProblemHighlight(self, line_number = None) -> bool:
        """Hasproblemhighlight."""
        return self.hasCriticalProblemHighlight(line_number)

    def handle_mass_set_font(self):
        """Handle mass set font."""
        selected_lines = self.get_selected_lines()
        if not selected_lines: return

        main_window = self.window()
        displayed_indices = getattr(main_window.data_store, 'displayed_string_indices', [])
        if not displayed_indices and hasattr(main_window, 'displayed_string_indices'):
            displayed_indices = main_window.displayed_string_indices

        if displayed_indices:
            real_indices = [displayed_indices[i] for i in selected_lines if i < len(displayed_indices)]
        else:
            real_indices = selected_lines

        dialog = MassFontDialog(main_window)
        if dialog.exec():
            font_file = dialog.get_selected_font()
            main_window.string_settings_handler.apply_font_to_lines(real_indices, font_file)

    def handle_mass_set_width(self):
        """Handle mass set width."""
        selected_lines = self.get_selected_lines()
        if not selected_lines: return

        main_window = self.window()
        displayed_indices = getattr(main_window.data_store, 'displayed_string_indices', [])
        if not displayed_indices and hasattr(main_window, 'displayed_string_indices'):
            displayed_indices = main_window.displayed_string_indices

        if displayed_indices:
            real_indices = [displayed_indices[i] for i in selected_lines if i < len(displayed_indices)]
        else:
            real_indices = selected_lines

        dialog = MassWidthDialog(main_window)
        if dialog.exec():
            if dialog.is_auto_width():
                main_window.string_settings_handler.apply_auto_width_from_original_to_lines(real_indices)
            else:
                width = dialog.get_width()
                main_window.string_settings_handler.apply_width_to_lines(real_indices, width)


    @property
    def game_dialog_max_width_pixels(self):
        """Game dialog max width pixels."""
        main_window = self.window()
        if main_window is not self and isinstance(main_window, QMainWindow) and hasattr(main_window, 'game_dialog_max_width_pixels'):
            return main_window.game_dialog_max_width_pixels
        return getattr(self, '_game_dialog_max_width_pixels', DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS)

    @game_dialog_max_width_pixels.setter
    def game_dialog_max_width_pixels(self, val):
        """Game dialog max width pixels."""
        self._game_dialog_max_width_pixels = val

    @property
    def line_width_warning_threshold_pixels(self):
        """Line width warning threshold pixels."""
        main_window = self.window()
        if main_window is not self and isinstance(main_window, QMainWindow) and hasattr(main_window, 'line_width_warning_threshold_pixels'):
            return main_window.line_width_warning_threshold_pixels
        return getattr(self, '_line_width_warning_threshold_pixels', DEFAULT_LINE_WIDTH_WARNING_THRESHOLD)

    @line_width_warning_threshold_pixels.setter
    def line_width_warning_threshold_pixels(self, val):
        """Line width warning threshold pixels."""
        self._line_width_warning_threshold_pixels = val

    @property
    def show_width_guideline(self):
        """Show width guideline."""
        main_window = self.window()
        if main_window is not self and isinstance(main_window, QMainWindow) and hasattr(main_window, 'show_width_guideline'):
            return main_window.show_width_guideline
        return getattr(self, '_show_width_guideline', True)

    @show_width_guideline.setter
    def show_width_guideline(self, val):
        """Show width guideline."""
        self._show_width_guideline = val
