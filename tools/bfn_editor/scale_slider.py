from PyQt6 import QtCore, QtWidgets

from core.i18n import tr

class ScaleSliderWidget(QtWidgets.QWidget):
    valueChanged = QtCore.pyqtSignal(int)
    
    def __init__(self, default_val=100, min_val=-200, max_val=400, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # Min spinbox
        self.spin_min = QtWidgets.QSpinBox()
        self.spin_min.setRange(-2000, 2000)
        self.spin_min.setValue(min_val)
        self.spin_min.setToolTip(tr("Minimum scale boundary"))
        self.spin_min.setFixedWidth(55)
        
        # Slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(default_val)
        self.slider.setToolTip(tr("Drag to adjust scale"))
        
        # Max spinbox
        self.spin_max = QtWidgets.QSpinBox()
        self.spin_max.setRange(-2000, 2000)
        self.spin_max.setValue(max_val)
        self.spin_max.setToolTip(tr("Maximum scale boundary"))
        self.spin_max.setFixedWidth(55)
        
        # Value spinbox
        self.spin_val = QtWidgets.QSpinBox()
        self.spin_val.setRange(-2000, 2000)
        self.spin_val.setValue(default_val)
        self.spin_val.setSuffix(" %")
        self.spin_val.setToolTip(tr("Current scale value"))
        self.spin_val.setFixedWidth(70)
        
        layout.addWidget(self.spin_min)
        layout.addWidget(self.slider)
        layout.addWidget(self.spin_max)
        layout.addWidget(self.spin_val)
        
        # Connections
        self.spin_min.valueChanged.connect(self._on_min_changed)
        self.spin_max.valueChanged.connect(self._on_max_changed)
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.spin_val.valueChanged.connect(self._on_spin_changed)
        
    def _on_min_changed(self, val):
        if val >= self.spin_max.value():
            self.spin_max.setValue(val + 1)
        self.slider.setMinimum(val)
        self.slider.setValue(self.spin_val.value())
        
    def _on_max_changed(self, val):
        if val <= self.spin_min.value():
            self.spin_min.setValue(val - 1)
        self.slider.setMaximum(val)
        self.slider.setValue(self.spin_val.value())
        
    def _on_slider_changed(self, val):
        self.spin_val.blockSignals(True)
        self.spin_val.setValue(val)
        self.spin_val.blockSignals(False)
        self.valueChanged.emit(val)
        
    def _on_spin_changed(self, val):
        if val < self.spin_min.value():
            self.spin_min.setValue(val)
        elif val > self.spin_max.value():
            self.spin_max.setValue(val)
            
        self.slider.blockSignals(True)
        self.slider.setValue(val)
        self.slider.blockSignals(False)
        self.valueChanged.emit(val)
        
    def value(self):
        return self.spin_val.value()
        
    def setValue(self, val):
        self.spin_val.setValue(val)

