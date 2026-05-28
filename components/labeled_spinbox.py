from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QSpinBox, QSizePolicy
from PyQt5.QtGui import QFontMetrics

class LabeledSpinBox(QWidget):
    def __init__(self, label_text: str, min_val: int, max_val: int, initial_val: int, tooltip: str = "", parent=None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel(label_text, self)
        
        self.spin_box = QSpinBox(self)
        self.spin_box.setRange(min_val, max_val)
        self.spin_box.setValue(initial_val)
        
        fm = QFontMetrics(self.spin_box.font())
        min_width = fm.horizontalAdvance(str(max_val)) + 20
        self.spin_box.setMinimumWidth(min_width)
        
        if tooltip:
            self.spin_box.setToolTip(tooltip)
        
        layout.addWidget(self.label)
        layout.addWidget(self.spin_box)
        layout.addStretch(1)

    def value(self) -> int:
        return self.spin_box.value()

    def setValue(self, value: int):
        self.spin_box.setValue(value)