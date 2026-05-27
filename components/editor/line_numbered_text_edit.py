# --- START OF FILE components/editor/line_numbered_text_edit.py ---
# --- START OF FILE components/line_numbered_text_edit.py ---
# --- START OF FILE components/LineNumberedTextEdit.py ---
from PyQt5.QtWidgets import (QPlainTextEdit, QMainWindow, QMenu, QApplication, QAction,
                             QWidget, QHBoxLayout, QWidgetAction, QToolTip)
from PyQt5.QtGui import (QFont, QPaintEvent, QKeyEvent, QMouseEvent, QTextCursor, QDrag)
from PyQt5.QtCore import Qt, QRect, QRectF, pyqtSignal, QPoint, QMimeData, QByteArray
from typing import Optional, List, Tuple
from pathlib import Path

from .line_number_area import LineNumberArea
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
    lineClicked = pyqtSignal(int)
    previewSelectionChanged = pyqtSignal(list)
    addTagMappingRequest = pyqtSignal(str, str)
    calculateLineWidthRequest = pyqtSignal(int)

    def __init__(self, parent=None):
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

        self.lineNumberArea = LineNumberArea(self)
        
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

        self.setContextMenuPolicy(Qt.CustomContextMenu)
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

        lnet_editor_setup.update_auxiliary_widths(self)
        self.highlightManager.update_zebra_stripes()

    def handle_line_number_click(self, y_pos: int):
        self.mouse_handler.handle_line_number_click(y_pos)

    def handle_line_number_double_click(self, y_pos: int):
        self.mouse_handler.handle_line_number_double_click(y_pos)

    def set_glossary_manager(self, manager) -> None:
        self._glossary_manager = manager
        if hasattr(self, 'highlighter') and self.highlighter:
            self.highlighter.set_glossary_manager(manager)

    def _replace_word_at_cursor(self, word_cursor: QTextCursor, replacement: str) -> None:
        """Replace the word selected by the given cursor with the replacement text."""
        if word_cursor.hasSelection():
            word_cursor.insertText(replacement)

    def _open_spellcheck_dialog_for_selection(self, position_in_widget_coords: QPoint) -> None:
        self.spellcheck_logic.open_dialog_for_selection(position_in_widget_coords)

    def _apply_corrected_text_to_editor(self, corrected_text: str, line_numbers: List[int]) -> None:
        self.spellcheck_logic.apply_corrected_text(corrected_text, line_numbers)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        cursor = self.cursorForPosition(event.pos())
        block = cursor.block()
        entry = self._find_glossary_entry_at(event.pos())
        warning_tooltip = self._find_warning_tooltip_at(event.pos())
        
        tooltip_text = None
        if entry:
            lines = [f"<b>{entry.original}</b> → {entry.translation}"]
            if entry.notes:
                lines.append(f"<i>{entry.notes}</i>")
            tooltip_text = "<br><br>".join(lines)
            
        # USER_REQUEST: Tooltips should be EXCLUSIVELY on the number area.
        # Warning tooltips from the main text area are now handled only by handle_line_number_area_mouse_move
        # for the LineNumberArea. We keep glossary tooltips here if needed, but remove warning_tooltip logic.

        # Tracking state to avoid flickering but allow position updates between lines
        current_state = (tooltip_text, block.blockNumber()) if entry else None
        last_state = getattr(self, '_last_tooltip_state', None)

        if tooltip_text:
            if current_state != last_state:
                QToolTip.showText(self.mapToGlobal(event.pos()), tooltip_text, self)
                self._last_tooltip_state = current_state
                self._current_combined_tooltip = tooltip_text
        elif getattr(self, '_current_combined_tooltip', None):
            QToolTip.hideText()
            self._current_combined_tooltip = None
            self._last_tooltip_state = None

        self._hovered_glossary_entry = entry
        self._hovered_warning_text = warning_tooltip

        if self.objectName() == "preview_text_edit" and event.buttons() == Qt.LeftButton and self._selected_lines:
            if self.drag_start_pos is not None and (event.pos() - self.drag_start_pos).manhattanLength() > QApplication.startDragDistance():
                drag = QDrag(self)
                mime_data = QMimeData()
                
                data = QByteArray()
                data.append(str(sorted(list(self._selected_lines))).encode('utf-8'))
                mime_data.setData("application/x-selected-lines", data)
                
                drag.setMimeData(mime_data)
                drag.exec_(Qt.MoveAction)
                self.drag_start_pos = None

        super().mouseMoveEvent(event)

    def setPlainText(self, text: str):
        # When text is reset entirely, we MUST clear all document-specific highlights
        # because the old cursors will be invalid.
        self._selected_lines.clear()
        self._previously_selected_lines.clear()
        self._last_clicked_line = -1
        if hasattr(self, 'highlightManager'):
            self.highlightManager.clearAllHighlights()
        if hasattr(self, 'highlighter') and self.highlighter:
            self.highlighter._async_glossary_matches = None
            self.highlighter._async_translation_matches = None
            self.highlighter._async_spellcheck_matches = None
        super().setPlainText(text)
        # If we have an active glossary, we must re-trigger highlighting
        # because set_glossary_manager ran while the editor was empty,
        # so rehighlight() did nothing at that time.
        if text and hasattr(self, 'highlighter') and self.highlighter:
            highlighter = self.highlighter
            if getattr(highlighter, '_glossary_enabled', False):
                highlighter.rehighlight()
        # Defer guideline recalculation so Qt has time to finalize block layouts.
        # Without this, QTextBlock.layout().lineAt() returns invalid lines immediately
        # after setPlainText, producing empty guideline_positions.
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, self.recalculate_guidelines)

    def recalculate_guidelines(self) -> None:
        self.guideline_positions = {}
        if not self.show_width_guideline or self.line_width_warning_threshold_pixels <= 0:
            return

        from utils.utils import calculate_string_width, convert_dots_to_spaces_from_editor
        from PyQt5.QtGui import QTextCursor
        
        main_window = self.window()
        font_map = getattr(self, 'font_map', {})
        if not font_map and hasattr(main_window, 'font_map'):
            font_map = main_window.font_map
            
        if hasattr(main_window, 'data_store') and hasattr(main_window, 'helper'):
            block_idx = main_window.data_store.current_block_idx
            string_idx = main_window.data_store.current_string_idx
            if block_idx != -1 and string_idx != -1:
                font_map = main_window.helper.get_font_map_for_string(block_idx, string_idx)
                
        sequences = getattr(main_window, 'icon_sequences', []) if main_window else []
        limit_px = self.line_width_warning_threshold_pixels
        
        block = self.firstVisibleBlock()
        cursor = QTextCursor(self.document())
        
        while block.isValid():
            layout = block.layout()
            if layout:
                block_text_raw = convert_dots_to_spaces_from_editor(block.text())
                block_num = block.blockNumber()
                
                for i in range(layout.lineCount()):
                    line = layout.lineAt(i)
                    if not line.isValid():
                        continue
                        
                    line_start = line.textStart()
                    line_len = line.textLength()
                    line_text = block_text_raw[line_start:line_start + line_len]
                    line_text_stripped = line_text.rstrip()
                    
                    cursor.setPosition(block.position() + line_start)
                    x_start = self.cursorRect(cursor).left()
                    
                    line_game_width = calculate_string_width(line_text_stripped, font_map, icon_sequences=sequences)
                    
                    if line_game_width > 0:
                        if line_game_width < limit_px:
                            # Y < X: відступаємо на X - Y ігрових пікселів вправо від останнього символу
                            cursor.setPosition(block.position() + line_start + len(line_text_stripped))
                            x_end = self.cursorRect(cursor).left()
                            viewport_text_w = x_end - x_start
                            
                            limit_x = x_start + viewport_text_w * (limit_px / line_game_width)
                        else:
                            # Y >= X: заморожуємо на X ігрових пікселях від початку
                            found = False
                            for k in range(1, len(line_text_stripped) + 1):
                                prefix = line_text_stripped[:k]
                                prefix_w = calculate_string_width(prefix, font_map, icon_sequences=sequences)
                                if prefix_w >= limit_px:
                                    prev_prefix = line_text_stripped[:k-1]
                                    prev_w = calculate_string_width(prev_prefix, font_map, icon_sequences=sequences)
                                    
                                    cursor.setPosition(block.position() + line_start + k - 1)
                                    x_prev = self.cursorRect(cursor).left()
                                    
                                    cursor.setPosition(block.position() + line_start + k)
                                    x_curr = self.cursorRect(cursor).left()
                                    
                                    if prefix_w > prev_w:
                                        fraction = (limit_px - prev_w) / (prefix_w - prev_w)
                                    else:
                                        fraction = 0
                                    limit_x = x_prev + fraction * (x_curr - x_prev)
                                    found = True
                                    break
                            if not found:
                                cursor.setPosition(block.position() + line_start + len(line_text_stripped))
                                x_end = self.cursorRect(cursor).left()
                                viewport_text_w = x_end - x_start
                                limit_x = x_start + viewport_text_w * (limit_px / line_game_width)
                    else:
                        fm = self.fontMetrics()
                        char_w = fm.horizontalAdvance('A')
                        limit_x = x_start + limit_px * (char_w / 7.5)
                        
                    self.guideline_positions[(block_num, i)] = limit_x
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
        self.mouse_handler.handle_line_number_area_mouse_move(event)


    def get_selected_lines(self):
        return sorted(list(self._selected_lines))

    def set_selected_lines(self, lines: List[int]):
        # Safeguard multi-selection in preview:
        # If we currently have multiple lines selected (len > 1), and a programmatic call
        # tries to select a single line that is already part of the current selection,
        # we ignore it to prevent lazy-loading or text updates from resetting user's selection.
        if len(lines) == 1 and len(self._selected_lines) > 1 and lines[0] in self._selected_lines:
            return

        new_set = set(lines)
        if self._selected_lines == new_set:
            return
        self._selected_lines = new_set
        self._update_selection_highlight()
        self._emit_selection_changed()

    def clear_selection(self):
        self._selected_lines.clear()
        self._last_clicked_line = -1
        self._update_selection_highlight()
        self._emit_selection_changed()

    def _update_selection_highlight(self):
        lines_to_highlight = self._selected_lines - self._previously_selected_lines
        lines_to_clear = self._previously_selected_lines - self._selected_lines
        
        self.highlightManager.set_background_for_lines(lines_to_highlight, lines_to_clear)
        
        self._previously_selected_lines = self._selected_lines.copy()

    def _emit_selection_changed(self):
        self.previewSelectionChanged.emit(self.get_selected_lines())

    def leaveEvent(self, event) -> None:
        if getattr(self, '_current_combined_tooltip', None):
            QToolTip.hideText()
            self._current_combined_tooltip = None
        self._hovered_glossary_entry = None
        self._hovered_warning_text = None
        super().leaveEvent(event)

    def _find_glossary_entry_at(self, pos):
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
        return self.tooltip_logic.find_warning_tooltip_at(pos)


    def _set_theme_colors(self, main_window_ref):
        lnet_editor_setup.set_theme_colors(self, main_window_ref)

    def _create_tag_button(self, parent_widget, display: str, open_tag: str, close_tag: str = None, menu: QMenu = None):
        return lnet_editor_setup.create_tag_button(self, parent_widget, display, open_tag, close_tag, menu)

    def populateContextMenu(self, menu: QMenu, position_in_widget_coords):
        self.context_menu_logic.populate(menu, position_in_widget_coords)

    def _update_auxiliary_widths(self):
        lnet_editor_setup.update_auxiliary_widths(self)

    def setFont(self, font: QFont):
        super().setFont(font)
        if hasattr(self, 'highlighter') and self.highlighter:
            self.highlighter.rehighlight()
        self._update_auxiliary_widths()
        if hasattr(self, 'lineNumberArea'):
             self.lineNumberArea.update()
        self.viewport().update()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            main_window = self.window()
            if hasattr(main_window, 'handle_zoom'):
                target = 'preview' if self.objectName() == "preview_text_edit" else 'editors'
                main_window.handle_zoom(event.angleDelta().y(), target=target)
                event.accept()
                return
            else:
                # Default zoom for non-main windows (e.g. Review Dialog)
                super().wheelEvent(event)
                self.updateLineNumberAreaWidth(0)
                return

        super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if self.keyboard_handler.handle_key_press(event):
            event.accept()
            return
        super().keyPressEvent(event)

    def setReadOnly(self, ro):
        super().setReadOnly(ro)
        self.highlightManager.clearAllHighlights()
        if not ro:
             self.highlightManager.updateCurrentLineHighlight()
             self.setUndoRedoEnabled(False)
    def lineNumberAreaWidth(self):
        total_blocks = self.override_total_lines if self.override_total_lines is not None else self.blockCount()
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

    def updateLineNumberAreaWidth(self, _):
        new_width = self.lineNumberAreaWidth()
        if self.viewportMargins().left() != new_width:
            self.setViewportMargins(new_width, 0, 0, 0)
        if hasattr(self, 'lineNumberArea'): 
            self.lineNumberArea.updateGeometry()
            self.lineNumberArea.update()

    def updateLineNumberArea(self, rect: QRectF, dy: int):
        if hasattr(self, 'lineNumberArea'): 
            if dy: self.lineNumberArea.scroll(0, dy)
            else: self.lineNumberArea.update(0, 0, self.lineNumberArea.width(), self.lineNumberArea.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        if hasattr(self, 'lineNumberArea'): 
            self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))
        if self.isVisible():
            self.viewport().update()

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        if hasattr(self, 'paint_event_logic'): 
            self.paint_event_logic.execute_paint_event(event)

    def lineNumberAreaPaintEvent(self, event, painter_device):
        if hasattr(self.lineNumberArea, 'paint_logic'):
            self.lineNumberArea.paint_logic.execute_paint_event(event, painter_device)

    def mousePressEvent(self, event: QMouseEvent):
        self.mouse_handler.mousePressEvent(event) 

    def super_mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.mouse_handler.mouseReleaseEvent(event) 

    def super_mouseReleaseEvent(self, event: QMouseEvent):
        super().mouseReleaseEvent(event)

    def _get_icon_sequences(self) -> List[str]:
        if self.objectName() == 'preview_text_edit':
            return []
        main_window = self.window()
        if isinstance(main_window, QMainWindow):
            sequences = getattr(main_window, 'icon_sequences', None)
            if isinstance(sequences, list):
                return sequences
        return []

    def _find_icon_sequence_in_block(self, block_text: str, sequences: List[str], position_in_block: int) -> Optional[Tuple[int, int, str]]:
        return self.tag_helpers.find_icon_sequence_in_block(block_text, sequences, position_in_block)

    def _snap_cursor_out_of_icon_sequences(self, move_right: bool) -> bool:
        return self.tag_helpers.snap_cursor_out_of_icon_sequences(move_right)

    def _momentary_highlight_tag(self, block, start_in_block, length):
        self.highlight_interface._momentary_highlight_tag(block, start_in_block, length)

    def _apply_all_extra_selections(self):
        self.highlight_interface._apply_all_extra_selections()

    def addCriticalProblemHighlight(self, line_number: int):
        self.hi_wrappers.addCriticalProblemHighlight(line_number)

    def removeCriticalProblemHighlight(self, line_number: int) -> bool:
        return self.hi_wrappers.removeCriticalProblemHighlight(line_number)

    def clearCriticalProblemHighlights(self):
        self.hi_wrappers.clearCriticalProblemHighlights()

    def hasCriticalProblemHighlight(self, line_number = None) -> bool:
        return self.hi_wrappers.hasCriticalProblemHighlight(line_number)

    def addWarningLineHighlight(self, line_number: int):
        self.hi_wrappers.addWarningLineHighlight(line_number)

    def removeWarningLineHighlight(self, line_number: int) -> bool:
        return self.hi_wrappers.removeWarningLineHighlight(line_number)

    def clearWarningLineHighlights(self):
        self.hi_wrappers.clearWarningLineHighlights()

    def hasWarningLineHighlight(self, line_number = None) -> bool:
        return self.hi_wrappers.hasWarningLineHighlight(line_number)

    def addWidthExceededHighlight(self, line_number: int):
        self.hi_wrappers.addWidthExceededHighlight(line_number)

    def removeWidthExceededHighlight(self, line_number: int) -> bool:
        return self.hi_wrappers.removeWidthExceededHighlight(line_number)

    def clearWidthExceededHighlights(self):
        self.hi_wrappers.clearWidthExceededHighlights()

    def hasWidthExceededHighlight(self, line_number = None) -> bool:
        return self.hi_wrappers.hasWidthExceededHighlight(line_number)
    
    def addShortLineHighlight(self, line_number: int):
        self.hi_wrappers.addShortLineHighlight(line_number)

    def removeShortLineHighlight(self, line_number: int) -> bool:
        return self.hi_wrappers.removeShortLineHighlight(line_number)

    def clearShortLineHighlights(self):
        self.hi_wrappers.clearShortLineHighlights()

    def hasShortLineHighlight(self, line_number = None) -> bool:
        return self.hi_wrappers.hasShortLineHighlight(line_number)

    def addEmptyOddSublineHighlight(self, block_number: int):
        self.hi_wrappers.addEmptyOddSublineHighlight(block_number)

    def removeEmptyOddSublineHighlight(self, block_number: int) -> bool:
        return self.hi_wrappers.removeEmptyOddSublineHighlight(block_number)

    def clearEmptyOddSublineHighlights(self):
        self.hi_wrappers.clearEmptyOddSublineHighlights()

    def hasEmptyOddSublineHighlight(self, block_number = None) -> bool:
        return self.hi_wrappers.hasEmptyOddSublineHighlight(block_number)

    def clearPreviewSelectedLineHighlight(self):
        self.highlightManager.set_background_for_lines(set(), self._previously_selected_lines)
        self.clear_selection()

    def setLinkedCursorPosition(self, line_number: int, column_number: int):
        self.hi_wrappers.hi.setLinkedCursorPosition(line_number, column_number)

    def applyQueuedHighlights(self):
        self.highlightManager.applyHighlights()

    def clearAllProblemTypeHighlights(self):
        self.highlightManager.clearAllProblemHighlights()

    def addProblemLineHighlight(self, line_number: int):
        self.addCriticalProblemHighlight(line_number)

    def removeProblemLineHighlight(self, line_number: int) -> bool:
        return self.removeCriticalProblemHighlight(line_number)

    def clearProblemLineHighlights(self):
        self.clearAllProblemTypeHighlights()
        
    def hasProblemHighlight(self, line_number = None) -> bool:
        return self.hasCriticalProblemHighlight(line_number)

    def handle_mass_set_font(self):
        selected_lines = self.get_selected_lines()
        if not selected_lines: return

        main_window = self.window()
        dialog = MassFontDialog(main_window)
        if dialog.exec_():
            font_file = dialog.get_selected_font()
            main_window.string_settings_handler.apply_font_to_lines(selected_lines, font_file)

    def handle_mass_set_width(self):
        selected_lines = self.get_selected_lines()
        if not selected_lines: return

        main_window = self.window()
        dialog = MassWidthDialog(main_window)
        if dialog.exec_():
            width = dialog.get_width()
            main_window.string_settings_handler.apply_width_to_lines(selected_lines, width)

    @property
    def game_dialog_max_width_pixels(self):
        main_window = self.window()
        if main_window is not self and isinstance(main_window, QMainWindow) and hasattr(main_window, 'game_dialog_max_width_pixels'):
            return main_window.game_dialog_max_width_pixels
        return getattr(self, '_game_dialog_max_width_pixels', DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS)

    @game_dialog_max_width_pixels.setter
    def game_dialog_max_width_pixels(self, val):
        self._game_dialog_max_width_pixels = val

    @property
    def line_width_warning_threshold_pixels(self):
        main_window = self.window()
        if main_window is not self and isinstance(main_window, QMainWindow) and hasattr(main_window, 'line_width_warning_threshold_pixels'):
            return main_window.line_width_warning_threshold_pixels
        return getattr(self, '_line_width_warning_threshold_pixels', DEFAULT_LINE_WIDTH_WARNING_THRESHOLD)

    @line_width_warning_threshold_pixels.setter
    def line_width_warning_threshold_pixels(self, val):
        self._line_width_warning_threshold_pixels = val

    @property
    def show_width_guideline(self):
        main_window = self.window()
        if main_window is not self and isinstance(main_window, QMainWindow) and hasattr(main_window, 'show_width_guideline'):
            return main_window.show_width_guideline
        return getattr(self, '_show_width_guideline', True)

    @show_width_guideline.setter
    def show_width_guideline(self, val):
        self._show_width_guideline = val
