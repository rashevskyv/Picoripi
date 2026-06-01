from PyQt5.QtWidgets import QToolBar, QAction, QStyle, QWidget, QSizePolicy
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont

class ToolBarBuilder:
    def __init__(self, main_window):
        self.mw = main_window
        self.style = main_window.style()

    def build(self):
        self.mw.main_toolbar = QToolBar("Main Toolbar")
        self.mw.addToolBar(self.mw.main_toolbar)
        self.mw.main_toolbar.setIconSize(QSize(24, 24))

        self.mw.open_ai_chat_action = QAction(self.style.standardIcon(QStyle.SP_DialogHelpButton), 'Open AI Chat', self.mw)
        self.mw.open_ai_chat_action.setToolTip("Open a chat window to discuss translations with AI (Ctrl+Shift+C)")
        self.mw.open_ai_chat_action.setShortcut('Ctrl+Shift+C')

        self.mw.main_toolbar.addAction(self.mw.save_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.undo_typing_action)
        self.mw.main_toolbar.addAction(self.mw.redo_typing_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.find_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.toggle_preview_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.open_ai_chat_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.bfn_editor_action)
        self.mw.main_toolbar.addAction(self.mw.recalculate_widths_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.open_settings_action)
        
        # Create a dynamic beautiful icon for External Script with '>_'
        pixmap_cmd = QPixmap(32, 32)
        pixmap_cmd.fill(Qt.transparent)
        painter_cmd = QPainter(pixmap_cmd)
        painter_cmd.setRenderHint(QPainter.Antialiasing, True)
        painter_cmd.setPen(QColor("#0078d7"))
        font_cmd = QFont("Courier New", 18, QFont.Bold)
        painter_cmd.setFont(font_cmd)
        painter_cmd.drawText(pixmap_cmd.rect(), Qt.AlignCenter, ">_")
        painter_cmd.end()
        cmd_icon = QIcon(pixmap_cmd)

        self.mw.run_external_script_action = QAction(cmd_icon, 'Run External Script', self.mw)
        self.mw.run_external_script_action.setToolTip("Run configured external script / build tool")
        
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.run_external_script_action)
        
        # Push Help to the far right
        toolbar_spacer = QWidget()
        toolbar_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.mw.main_toolbar.addWidget(toolbar_spacer)
        
        self.mw.main_toolbar.addAction(self.mw.help_shortcuts_action)
