"""Selection state, mouse interaction, and glossary/warning tooltips."""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtWidgets import QApplication, QToolTip
from PyQt6.QtGui import QMouseEvent, QDrag
from PyQt6.QtCore import Qt, QPoint, QMimeData, QByteArray

from core.glossary_manager import render_notes


class SelectionMixin:
    """Selection state, mouse interaction, and glossary/warning tooltips."""

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

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Mousemoveevent."""
        cursor = self.cursorForPosition(event.pos())
        block = cursor.block()
        entry = self._find_glossary_entry_at(event.pos())
        tag_tooltip = self.tooltip_logic.find_tag_tooltip_at(event.pos())
        warning_tooltip = self._find_warning_tooltip_at(event.pos())
        
        tooltip_text = None
        if entry:
            main_window = self.window()
            font_size = getattr(main_window, 'tooltip_font_size', 11)
            lines = [f"<div style='font-size: {font_size}px;'><b>{entry.original}</b> → {entry.translation}"]
            # Notes hold a term placeholder; show the term, never the token.
            notes = render_notes(
                entry.notes, translation=entry.translation, original=entry.original
            )
            if notes:
                try:
                    import markdown
                    # Convert markdown to html with nl2br to preserve single newlines
                    notes_html = markdown.markdown(notes, extensions=['nl2br'])
                    notes_html = f"<div style='margin-top: 4px; font-size: {font_size}px;'>{notes_html}</div>"
                except Exception:
                    notes_html = f"<div style='margin-top: 4px; font-style: italic; font-size: {font_size}px;'>{notes}</div>"
                lines.append(notes_html)
            lines.append("</div>")
            tooltip_text = "".join(lines)
        elif tag_tooltip:
            import html
            main_window = self.window()
            font_size = getattr(main_window, 'tooltip_font_size', 11)
            tooltip_text = (
                f"<div style='font-size: {font_size}px;'>"
                f"<b>Game tag</b><br>{html.escape(tag_tooltip)}</div>"
            )
            
        # USER_REQUEST: Tooltips should be EXCLUSIVELY on the number area.
        # Warning tooltips from the main text area are now handled only by handle_line_number_area_mouse_move
        # for the LineNumberArea. We keep glossary tooltips here if needed, but remove warning_tooltip logic.

        # Tracking state to avoid flickering but allow position updates between lines
        current_state = (tooltip_text, block.blockNumber()) if tooltip_text else None
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

    def set_selected_lines(self, lines: List[int], force: bool = False):
        # Safeguard multi-selection in preview:
        # If we currently have multiple lines selected (len > 1), and a programmatic call
        # tries to select a single line that is already part of the current selection,
        # we ignore it to prevent lazy-loading or text updates from resetting user's selection.
        """Set the selected lines."""
        if not force and len(lines) == 1 and len(self._selected_lines) > 1 and lines[0] in self._selected_lines:
            return

        new_set = set(lines)
        if not force and self._selected_lines == new_set:
            return
        self._selected_lines = new_set
        self._update_selection_highlight(force=force)
        self._emit_selection_changed()

    def clear_selection(self):
        """Remove selection."""
        self._selected_lines.clear()
        self._last_clicked_line = -1
        self._update_selection_highlight()
        self._emit_selection_changed()

    def _update_selection_highlight(self, force: bool = False):
        """Internal helper to update the selection highlight."""
        if not hasattr(self, 'highlightManager'):
            return
        if force:
            self.highlightManager.setPreviewSelectedLineHighlight(list(self._selected_lines))
        else:
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
