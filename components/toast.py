# components/toast.py
import sys
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect, QApplication
from PyQt6.QtCore import Qt, QPropertyAnimation, QTimer, QPoint, QEasingCurve
from PyQt6.QtGui import QFont, QColor

class ToastNotification(QWidget):
    """Toast notification implementation."""
    _active_toasts = []  # Keep references to prevent garbage collection

    def __init__(self, parent, message: str, duration: int = 2000, toast_type: str = "success"):
        # Safe fallback for non-QWidget parent in testing environments
        """Initialize a new instance."""
        actual_parent = parent if isinstance(parent, QWidget) else None
        super().__init__(actual_parent)
        self.message = message
        self.duration = duration
        self.toast_type = toast_type
        
        # Set frameless, transparent background, always on top and acts like a tooltip
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.ToolTip | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Ensure the background stylesheet is styled/drawn correctly for custom QWidget subclass
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # UI Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(10)
        
        # Size constraints to match block sizes
        self.setMinimumWidth(260)
        self.setMaximumWidth(300)
        
        # Icon/Indicator
        self.icon_label = QLabel()
        icon_font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        self.icon_label.setFont(icon_font)
        
        if toast_type == "success":
            self.icon_label.setText("✓")
            self.icon_label.setStyleSheet("color: #2ecc71; background: transparent; border: none;")
        elif toast_type == "error":
            self.icon_label.setText("✗")
            self.icon_label.setStyleSheet("color: #e74c3c; background: transparent; border: none;")
        elif toast_type == "warning":
            self.icon_label.setText("⚠")
            self.icon_label.setStyleSheet("color: #f1c40f; background: transparent; border: none;")
        else:
            self.icon_label.setText("ℹ")
            self.icon_label.setStyleSheet("color: #3498db; background: transparent; border: none;")
            
        layout.addWidget(self.icon_label)
        
        # Message Text
        self.text_label = QLabel(message)
        self.text_label.setFont(QFont("Segoe UI", 10))
        self.text_label.setStyleSheet("color: #ffffff; background: transparent; border: none;")
        self.text_label.setWordWrap(True)
        layout.addWidget(self.text_label)
        
        # Container Style - darker semi-transparent black
        self.setStyleSheet("""
            ToastNotification {
                background-color: rgba(18, 18, 18, 220);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 8px;
            }
        """)
        
        # Adjust size based on content
        self.adjustSize()
        
        # Position the toast relative to the parent
        self.position_toast(actual_parent)
        
        # Opacity effect for fade animation
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)
        
        # Fade-in animation
        self.anim_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_in.setDuration(200)
        self.anim_in.setStartValue(0.0)
        self.anim_in.setEndValue(1.0)
        self.anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Fade-out animation
        self.anim_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_out.setDuration(250)
        self.anim_out.setStartValue(1.0)
        self.anim_out.setEndValue(0.0)
        self.anim_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self.anim_out.finished.connect(self.close_and_cleanup)
        
        # Timer to trigger fade-out
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.start_fade_out)
        
    def position_toast(self, parent):
        """Position toast."""
        if parent and isinstance(parent, QWidget):
            try:
                # Get geometry of parent
                parent_geom = parent.geometry()
                # If parent is not visible, try active window
                if not parent.isVisible():
                    active_win = QApplication.activeWindow()
                    if active_win and active_win.isVisible():
                        parent = active_win
                        parent_geom = parent.geometry()
                
                # Position at bottom-left of parent window
                global_pos = parent.mapToGlobal(QPoint(0, 0))
                x = global_pos.x() + 20 # 20px margin from the left
                y = global_pos.y() + parent_geom.height() - self.height() - 50 # 50px margin from the bottom
                self.move(x, y)
                return
            except Exception:
                pass
        
        # Bottom-left of the screen fallback (or if parent is None or non-QWidget)
        screen_geom = QApplication.primaryScreen().geometry()
        x = screen_geom.x() + 30
        y = screen_geom.y() + screen_geom.height() - self.height() - 80
        self.move(x, y)

    def paintEvent(self, event):
        """Paintevent."""
        from PyQt6.QtGui import QPainter
        from PyQt6.QtWidgets import QStyleOption, QStyle
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def show_toast_notification(self):
        """Show toast notification."""
        self.show()
        self.anim_in.start()
        self.timer.start(self.duration)
        
    def start_fade_out(self):
        """Start fade out."""
        self.anim_out.start()
        
    def close_and_cleanup(self):
        """Close and cleanup."""
        self.close()
        if self in self.__class__._active_toasts:
            self.__class__._active_toasts.remove(self)
        self.deleteLater()

    @classmethod
    def show_toast(cls, parent, message: str, duration: int = 2000, toast_type: str = "success"):
        """Show toast."""
        if not QApplication.instance():
            return None
        toast = cls(parent, message, duration, toast_type)
        cls._active_toasts.append(toast)
        toast.show_toast_notification()
        return toast
