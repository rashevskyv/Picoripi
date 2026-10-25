"""Build the main toolbar."""
from PyQt6.QtWidgets import QToolBar, QStyle, QWidget, QSizePolicy
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from html import escape
from core.i18n import tr

class ToolBarBuilder:
    """Tool bar builder implementation."""
    def __init__(self, main_window):
        """Initialize a new instance."""
        self.mw = main_window
        self.style = main_window.style()

    def build(self):
        """Create ."""
        self.mw.main_toolbar = QToolBar("Main Toolbar")
        self.mw.addToolBar(self.mw.main_toolbar)
        self.mw.main_toolbar.setIconSize(QSize(24, 24))

        self.mw.open_ai_chat_action = QAction(self.style.standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton), tr('Open AI Chat'), self.mw)
        self.mw.open_ai_chat_action.setToolTip(
            tr('<b>AI Chat</b><br>Click — open a chat window to discuss translations with the AI (Ctrl+Shift+C).<br>Ctrl+Enter in the chat input sends the message; plain Enter adds a new line.')
        )
        self.mw.open_ai_chat_action.setShortcut('Ctrl+Shift+C')

        # Create a dynamic beautiful icon for AI Batch Translation with 'AI' badge
        pixmap_ai = QPixmap(32, 32)
        pixmap_ai.fill(Qt.GlobalColor.transparent)
        painter_ai = QPainter(pixmap_ai)
        painter_ai.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter_ai.setPen(QColor("#7c3aed"))
        font_ai = QFont("Segoe UI", 13, QFont.Weight.Bold)
        painter_ai.setFont(font_ai)
        painter_ai.drawText(pixmap_ai.rect(), Qt.AlignmentFlag.AlignCenter, "AI")
        painter_ai.end()
        ai_batch_icon = QIcon(pixmap_ai)

        self.mw.ai_batch_translate_action = QAction(ai_batch_icon, tr('AI Batch Translation'), self.mw)
        self.mw.ai_batch_translate_action.setToolTip(
            tr(
                "<b>AI Batch Translation</b><br>"
                "Click — open batch translation dialog to choose translation pipeline "
                "(Story First, Remaining Blocks, Full Pipeline)."
            )
        )

        self.mw.main_toolbar.addAction(self.mw.save_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.undo_typing_action)
        self.mw.main_toolbar.addAction(self.mw.redo_typing_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.find_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.toggle_preview_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.ai_batch_translate_action)
        self.mw.main_toolbar.addAction(self.mw.open_ai_chat_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.bfn_editor_action)
        self.mw.main_toolbar.addAction(self.mw.recalculate_widths_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.open_settings_action)
        
        self.mw.build_rom_action = QAction(tr('Build ROM'), self.mw)
        self.mw.build_rom_action.setToolTip(
            tr('<b>Build ROM</b><br>Click — build the changed game (ROM, ISO or mod folder) from this project.')
        )

        # Push Help and Script to the far right
        toolbar_spacer = QWidget()
        toolbar_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.mw.main_toolbar.addWidget(toolbar_spacer)
        self.mw.external_tool_actions = []
        self.refresh_external_tool_actions()
        
        self.mw.main_toolbar.addAction(self.mw.build_rom_action)
        self.mw.main_toolbar.addSeparator()
        self.mw.main_toolbar.addAction(self.mw.help_shortcuts_action)

    def refresh_external_tool_actions(self):
        """Replace custom script actions with the currently saved tool list."""
        from ui.settings.script_tools_mixin import tool_badge_icon

        toolbar = getattr(self.mw, "main_toolbar", None)
        if toolbar is None:
            return
        for action in getattr(self.mw, "external_tool_actions", []):
            toolbar.removeAction(action)
            action.deleteLater()
        self.mw.external_tool_actions = []
        anchor = self.mw.build_rom_action
        for index, tool in enumerate(getattr(self.mw, "external_tools", []) or []):
            name = tool.get("name", "").strip() or tr("External Tool")
            path = tool.get("path", "").strip()
            action = QAction(tool_badge_icon(tool.get("icon", "B")), name, self.mw)
            action.setToolTip(tr("<b>Run tool: {}</b><br>Path: {}").format(
                escape(name), escape(path),
            ))
            action.triggered.connect(
                lambda _checked=False, tool_index=index: self.mw.actions.run_external_script(tool_index)
            )
            toolbar.insertAction(anchor, action)
            self.mw.external_tool_actions.append(action)
        self.mw.run_external_script_action = (
            self.mw.external_tool_actions[0] if self.mw.external_tool_actions else None
        )
