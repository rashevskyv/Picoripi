from PyQt6.QtGui import QPainter, QPaintEvent
from utils.utils import calculate_string_width

class LNETPaintHandlers:
    """L n e t paint handlers implementation."""
    def __init__(self, editor):
        """Initialize a new instance."""
        self.editor = editor

    def paintEvent(self, event: QPaintEvent):
        """Paintevent."""
        self.editor.super_paintEvent(event)
        
        if not hasattr(self.editor, 'lineNumberArea') or not hasattr(self.editor.lineNumberArea, 'paint_logic'):
            return

        painter = QPainter(self.editor.viewport())
        try:
            paint_logic = self.editor.lineNumberArea.paint_logic
            paint_logic.draw_width_threshold_line(painter)
            paint_logic.draw_character_limit_line(painter)
        finally:
            painter.end()

    def lineNumberAreaPaintEvent(self, event, painter_device):
        """Linenumberareapaintevent."""
        if not hasattr(self.editor, 'lineNumberArea') or not hasattr(self.editor.lineNumberArea, 'paint_logic'):
            return
            
        painter = QPainter(painter_device)
        try:
            sequences = self.editor._get_icon_sequences()

            block = self.editor.firstVisibleBlock()
            block_number = block.blockNumber()
            top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
            bottom = top + self.editor.blockBoundingRect(block).height()

            height = self.editor.fontMetrics().height()
            
            paint_logic = self.editor.lineNumberArea.paint_logic

            while block.isValid() and (top <= event.rect().bottom()):
                if block.isVisible() and (bottom >= event.rect().top()):
                    number = str(block_number + 1)
                    
                    width_px = calculate_string_width(block.text(), self.editor.font_map, icon_sequences=sequences)
                    
                    paint_logic.paint_line_number(painter, number, block_number, height)
                    paint_logic.paint_pixel_width(painter, width_px, height)
                    paint_logic.paint_preview_indicators(painter, block_number, height)

                block = block.next()
                top = bottom
                bottom = top + self.editor.blockBoundingRect(block).height()
                block_number += 1
        finally:
            painter.end()
