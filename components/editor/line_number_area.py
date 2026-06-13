from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtGui import QPainter, QColor, QPen, QMouseEvent
from PyQt6.QtCore import Qt, QRect, QSize, QPoint

class LineNumberArea(QWidget):
    """Line number area implementation."""
    def __init__(self, editor):
        """Initialize a new instance."""
        super().__init__(editor)
        self.codeEditor = editor 
        self.setMouseTracking(True)
        
        self.odd_line_background = QColor(Qt.GlobalColor.lightGray).lighter(115) 
        self.even_line_background = QColor(Qt.GlobalColor.white) 
        self.number_color = QColor(Qt.GlobalColor.darkGray) # Використовується, якщо не чорний
        
        self.active_number_color = QColor(Qt.GlobalColor.white) # Не використовується, якщо текст завжди чорний
        self.active_number_background_color = QColor(0, 0, 128) # Використовується для фону активного рядка, якщо ввімкнено

        self.width_indicator_exceeded_color = QColor(Qt.GlobalColor.red).lighter(130) 

        self.preview_critical_indicator_color = QColor(Qt.GlobalColor.yellow).darker(125)
        self.preview_warning_indicator_color = QColor(Qt.GlobalColor.darkGray)
        self.preview_width_exceeded_indicator_color = QColor(255, 120, 120) 
        self.preview_indicator_width = 5 # Ширина смужки індикатора для preview
        self.preview_indicator_spacing = 2

    def sizeHint(self):
        """Sizehint."""
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        """Paintevent."""
        self.codeEditor.lineNumberAreaPaintEvent(event, painter_device=self)

    def mousePressEvent(self, event: QMouseEvent):
        """Mousepressevent."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.codeEditor.mouse_handler.handle_line_number_click(event.pos().y())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Mousedoubleclickevent."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.codeEditor.handle_line_number_double_click(event.pos().y())
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        # Delegate tooltip generation to the mouse handler
        """Mousemoveevent."""
        self.codeEditor.mouse_handler.handle_line_number_area_mouse_move(event)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Leaveevent."""
        QToolTip.hideText()
        super().leaveEvent(event)