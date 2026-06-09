from PyQt6.QtWidgets import QStatusBar, QLabel, QStyle
from PyQt6.QtGui import QFont, QFontMetrics

class StatusBarBuilder:
    def __init__(self, main_window):
        self.mw = main_window

    def build(self):
        self.mw.statusBar = QStatusBar()
        self.mw.setStatusBar(self.mw.statusBar)
        self.mw.original_path_label = QLabel("Original: [not specified]")
        self.mw.edited_path_label = QLabel("Changes: [not specified]")
        self.mw.plugin_status_label = QLabel("Plugin: [None]")
        self.mw.original_path_label.setToolTip("Path to the original text file")
        self.mw.edited_path_label.setToolTip("Path to the file where changes are saved")
        self.mw.plugin_status_label.setToolTip("Currently active game plugin")

        self.mw.status_label_part1 = QLabel("Pos: 000")
        self.mw.status_label_part2 = QLabel("Line: 000/000")
        self.mw.status_label_part3 = QLabel("Width: 0000px")
        
        font_for_metrics = QFont() 
        if self.mw.font() and self.mw.font().family(): 
            font_for_metrics = self.mw.font()

        font_metrics = QFontMetrics(font_for_metrics) 
        self.mw.status_label_part1.setMinimumWidth(font_metrics.horizontalAdvance("Sel: 000/000") + 15) 
        self.mw.status_label_part2.setMinimumWidth(font_metrics.horizontalAdvance("Line: 000/000") + 15) 
        self.mw.status_label_part3.setMinimumWidth(font_metrics.horizontalAdvance("Width: 0000px") + 10)
        
        self.mw.statusBar.addWidget(self.mw.original_path_label)
        self.mw.statusBar.addWidget(QLabel("|"))
        self.mw.statusBar.addWidget(self.mw.edited_path_label)
        self.mw.statusBar.addPermanentWidget(self.mw.plugin_status_label)
        self.mw.statusBar.addPermanentWidget(QLabel("|"))
        self.mw.statusBar.addPermanentWidget(self.mw.status_label_part1)
        self.mw.statusBar.addPermanentWidget(QLabel("|")) 
        self.mw.statusBar.addPermanentWidget(self.mw.status_label_part2)
        self.mw.statusBar.addPermanentWidget(QLabel("|")) 
        self.mw.statusBar.addPermanentWidget(self.mw.status_label_part3)
