from PyQt5.QtWidgets import QToolBar, QAction, QStyle, QWidget, QSizePolicy
from PyQt5.QtCore import QSize

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
        self.mw.main_toolbar.addAction(self.mw.open_ai_chat_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.bfn_editor_action)
        self.mw.main_toolbar.addAction(self.mw.recalculate_widths_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.open_settings_action)
        
        # Push Help to the far right
        toolbar_spacer = QWidget()
        toolbar_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.mw.main_toolbar.addWidget(toolbar_spacer)
        
        self.mw.main_toolbar.addAction(self.mw.help_shortcuts_action)
