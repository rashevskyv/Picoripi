from PyQt6.QtWidgets import QStatusBar, QLabel
from PyQt6.QtGui import QFont, QFontMetrics
from core.i18n import tr

class StatusBarBuilder:
    """Status bar builder implementation."""
    def __init__(self, main_window):
        """Initialize a new instance."""
        self.mw = main_window

    def build(self):
        """Create ."""
        self.mw.statusBar = QStatusBar()
        self.mw.setStatusBar(self.mw.statusBar)
        self.mw.original_path_label = QLabel(tr('Original: [not specified]'))
        self.mw.edited_path_label = QLabel(tr('Changes: [not specified]'))
        self.mw.plugin_status_label = QLabel(tr('Plugin: [None]'))
        self.mw.original_path_label.setToolTip(tr('Path to the original text file'))
        self.mw.edited_path_label.setToolTip(tr('Path to the file where changes are saved'))
        self.mw.plugin_status_label.setToolTip(tr('Currently active game plugin'))

        self.mw.status_label_part1 = QLabel(tr('Pos: 000'))
        self.mw.status_label_part2 = QLabel(tr('Line: 000/000'))
        self.mw.status_label_part3 = QLabel(tr('Width: 0000px'))
        self.mw.statistics_status_label = QLabel(tr('Strings: 0 | Unbound: 0'))
        self.mw.statistics_status_label.setToolTip(
            tr('Total game strings and strings with no Story, Speaker, Item, or Window binding')
        )
        
        font_for_metrics = QFont() 
        if self.mw.font() and self.mw.font().family(): 
            font_for_metrics = self.mw.font()

        font_metrics = QFontMetrics(font_for_metrics) 
        self.mw.status_label_part1.setMinimumWidth(font_metrics.horizontalAdvance("Sel: 000/000") + 15) 
        self.mw.status_label_part2.setMinimumWidth(font_metrics.horizontalAdvance("Line: 000/000") + 15) 
        self.mw.status_label_part3.setMinimumWidth(font_metrics.horizontalAdvance("Width: 0000px") + 10)
        
        self.mw.statusBar.addWidget(self.mw.original_path_label)
        self.mw.statusBar.addWidget(QLabel(tr('|')))
        self.mw.statusBar.addWidget(self.mw.edited_path_label)
        self.mw.statusBar.addPermanentWidget(self.mw.plugin_status_label)
        self.mw.statusBar.addPermanentWidget(QLabel(tr('|')))
        self.mw.statusBar.addPermanentWidget(self.mw.statistics_status_label)
        self.mw.statusBar.addPermanentWidget(QLabel(tr('|')))
        self.mw.statusBar.addPermanentWidget(self.mw.status_label_part1)
        self.mw.statusBar.addPermanentWidget(QLabel(tr('|'))) 
        self.mw.statusBar.addPermanentWidget(self.mw.status_label_part2)
        self.mw.statusBar.addPermanentWidget(QLabel(tr('|'))) 
        self.mw.statusBar.addPermanentWidget(self.mw.status_label_part3)
