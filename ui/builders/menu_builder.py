from PyQt6.QtWidgets import QMenu, QStyle, QToolButton, QToolTip
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QIcon, QKeySequence, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QObject, QEvent
from pathlib import Path

class MenuToolTipEventFilter(QObject):
    """Menu tool tip event filter implementation."""
    def eventFilter(self, watched, event):
        """Eventfilter."""
        if isinstance(watched, QMenu):
            if event.type() == QEvent.Type.ToolTip:
                action = watched.actionAt(event.pos())
                if action and not action.isEnabled():
                    tooltip = action.toolTip()
                    if tooltip:
                        QToolTip.showText(event.globalPos(), tooltip, watched)
                        return True
        return super().eventFilter(watched, event)

class MenuBuilder:
    """Menu builder implementation."""
    def __init__(self, main_window):
        """Initialize a new instance."""
        self.mw = main_window
        self.style = main_window.style()
        self.tooltip_filter = MenuToolTipEventFilter(main_window)

    def build_all(self):
        """Create all."""
        menubar = self.mw.menuBar()
        self._build_file_menu(menubar)
        self._build_edit_menu(menubar)
        self._build_view_menu(menubar)
        self._build_tools_menu(menubar)
        self._build_navigation_menu(menubar)
        self._build_bookmarks_menu(menubar)
        self._build_help_menu(menubar)

    def _build_file_menu(self, menubar):
        """Internal helper to create file menu."""
        file_menu = menubar.addMenu('&File')
        file_menu.setToolTipsVisible(True)
        file_menu.installEventFilter(self.tooltip_filter)
        
        open_icon = self.style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        save_icon = self.style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        reload_icon = self.style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        exit_icon = self.style.standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton)
        settings_icon = QIcon.fromTheme('settings', self.style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))

        # Project actions
        self.mw.new_project_action = QAction(QIcon.fromTheme("document-new"), '&New Project...', self.mw)
        self.mw.new_project_action.setShortcut('Ctrl+N')
        file_menu.addAction(self.mw.new_project_action)

        self.mw.open_project_action = QAction(open_icon, '&Open Project...', self.mw)
        self.mw.open_project_action.setShortcut('Ctrl+O')
        file_menu.addAction(self.mw.open_project_action)

        # Recent Projects submenu
        self.mw.recent_projects_menu = QMenu('Recent Projects', self.mw)
        self.mw.recent_projects_menu.installEventFilter(self.tooltip_filter)
        file_menu.addMenu(self.mw.recent_projects_menu)

        self.mw.close_project_action = QAction('&Close Project', self.mw)
        self.mw.close_project_action.setEnabled(False)
        file_menu.addAction(self.mw.close_project_action)
        file_menu.addSeparator()

        # Block actions
        self.mw.import_block_action = QAction(QIcon.fromTheme("document-import"), '&Import Block...', self.mw)
        self.mw.import_block_action.setEnabled(False)
        self.mw.import_block_action.setToolTip("This action is only available in Project mode (within a .uiproj project).")
        file_menu.addAction(self.mw.import_block_action)

        self.mw.import_directory_action = QAction(QIcon.fromTheme("folder-open"), 'Import &Directory...', self.mw)
        self.mw.import_directory_action.setEnabled(False)
        self.mw.import_directory_action.setToolTip("This action is only available in Project mode (within a .uiproj project).")
        file_menu.addAction(self.mw.import_directory_action)
        file_menu.addSeparator()

        self.mw.save_action = QAction(save_icon, '&Save Changes', self.mw)
        self.mw.save_action.setShortcut('Ctrl+S')
        file_menu.addAction(self.mw.save_action)

        self.mw.save_as_action = QAction(QIcon.fromTheme("document-save-as"), 'Save Changes &As...', self.mw)
        file_menu.addAction(self.mw.save_as_action)
        file_menu.addSeparator()

        self.mw.reload_action = QAction(reload_icon, 'Reload Original', self.mw)
        file_menu.addAction(self.mw.reload_action)

        self.mw.revert_action = QAction(QIcon.fromTheme("document-revert"), '&Revert Changes File to Original...', self.mw)
        file_menu.addAction(self.mw.revert_action)
        file_menu.addSeparator()

        self.mw.export_translations_action = QAction(QIcon.fromTheme("document-export"), '&Export Translations to JSON...', self.mw)
        self.mw.export_translations_action.setEnabled(False)
        file_menu.addAction(self.mw.export_translations_action)

        self.mw.export_original_action = QAction(QIcon.fromTheme("document-export"), '&Export Original to JSON...', self.mw)
        self.mw.export_original_action.setEnabled(False)
        file_menu.addAction(self.mw.export_original_action)

        self.mw.import_translations_action = QAction(QIcon.fromTheme("document-import"), '&Import Translations from JSON...', self.mw)
        self.mw.import_translations_action.setEnabled(False)
        file_menu.addAction(self.mw.import_translations_action)
        file_menu.addSeparator()

        self.mw.reload_tag_mappings_action = QAction(QIcon.fromTheme("preferences-system"), 'Reload &Tag Mappings from Settings', self.mw)
        file_menu.addAction(self.mw.reload_tag_mappings_action)
        file_menu.addSeparator()

        self.mw.open_settings_action = QAction(settings_icon, '&Settings...', self.mw)
        self.mw.open_settings_action.setShortcut('Ctrl+P')
        file_menu.addAction(self.mw.open_settings_action)
        file_menu.addSeparator()

        self.mw.exit_action = QAction(exit_icon, 'E&xit', self.mw)
        self.mw.exit_action.triggered.connect(self.mw.close)
        file_menu.addAction(self.mw.exit_action)

    def _build_edit_menu(self, menubar):
        """Internal helper to create edit menu."""
        edit_menu = menubar.addMenu('&Edit')
        edit_menu.setObjectName('&Edit')
        edit_menu.setToolTipsVisible(True)
        edit_menu.installEventFilter(self.tooltip_filter)

        def _icon_path(file_name: str) -> str:
            """Internal helper to icon path."""
            project_root = Path(__file__).resolve().parent.parent.parent
            return str(project_root / 'resources' / 'icons' / file_name)

        undo_local = _icon_path('undo.svg')
        redo_local = _icon_path('redo.svg')

        undo_icon = QIcon(undo_local) if Path(undo_local).exists() else QIcon.fromTheme("edit-undo", self.style.standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        redo_icon = QIcon(redo_local) if Path(redo_local).exists() else QIcon.fromTheme("edit-redo", self.style.standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        find_icon = self.style.standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)

        self.mw.undo_typing_action = QAction(undo_icon, '&Undo Typing', self.mw)
        self.mw.undo_typing_action.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(self.mw.undo_typing_action)

        self.mw.redo_typing_action = QAction(redo_icon, '&Redo Typing', self.mw)
        self.mw.redo_typing_action.setShortcuts([QKeySequence.StandardKey.Redo, QKeySequence('Ctrl+Shift+Z')])
        edit_menu.addAction(self.mw.redo_typing_action)
        edit_menu.addSeparator()

        # Create a dynamic beautiful icon for Restore Translation (document sheet with a blue arrow pointing right)
        pixmap_r = QPixmap(32, 32)
        pixmap_r.fill(Qt.GlobalColor.transparent)
        painter_r = QPainter(pixmap_r)
        painter_r.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter_r.setPen(QColor("#7f8c8d"))
        painter_r.setBrush(QColor("#ffffff"))
        
        from PyQt6.QtGui import QPolygonF
        from PyQt6.QtCore import QPointF
        paper_poly = QPolygonF([
            QPointF(4, 4),
            QPointF(14, 4),
            QPointF(20, 10),
            QPointF(20, 26),
            QPointF(4, 26)
        ])
        painter_r.drawPolygon(paper_poly)
        painter_r.drawLine(14, 4, 14, 10)
        painter_r.drawLine(14, 10, 20, 10)
        painter_r.setPen(QColor("#bdc3c7"))
        painter_r.drawLine(7, 10, 11, 10)
        painter_r.drawLine(7, 14, 15, 14)
        painter_r.drawLine(7, 18, 17, 18)
        painter_r.drawLine(7, 22, 13, 22)
        painter_r.setPen(QColor("#0078d7"))
        painter_r.setBrush(QColor("#0078d7"))
        arrow_pen = painter_r.pen()
        arrow_pen.setColor(QColor("#0078d7"))
        arrow_pen.setWidth(3)
        painter_r.setPen(arrow_pen)
        painter_r.drawLine(10, 15, 23, 15)
        arrow_head = QPolygonF([
            QPointF(19, 10),
            QPointF(26, 15),
            QPointF(19, 20)
        ])
        painter_r.setPen(Qt.PenStyle.NoPen)
        painter_r.setBrush(QColor("#0078d7"))
        painter_r.drawPolygon(arrow_head)
        painter_r.end()
        menu_restore_icon = QIcon(pixmap_r)

        self.mw.save_translated_action = QAction(QIcon.fromTheme("document-save"), '&Save Translated', self.mw)
        self.mw.save_translated_action.setShortcut('Ctrl+T')
        self.mw.save_translated_action.setEnabled(False)
        edit_menu.addAction(self.mw.save_translated_action)

        self.mw.restore_translated_action = QAction(menu_restore_icon, '&Restore Translated', self.mw)
        self.mw.restore_translated_action.setShortcut('Ctrl+Shift+T')
        self.mw.restore_translated_action.setEnabled(False)
        edit_menu.addAction(self.mw.restore_translated_action)
        edit_menu.addSeparator()

        self.mw.undo_paste_action = QAction(undo_icon, 'Undo &Paste Block', self.mw)
        self.mw.undo_paste_action.setEnabled(False)
        edit_menu.addAction(self.mw.undo_paste_action)
        edit_menu.addSeparator()

        self.mw.paste_block_action = QAction(QIcon.fromTheme("edit-paste"), '&Paste Block Text', self.mw)
        self.mw.paste_block_action.setShortcut('Ctrl+Shift+V')
        edit_menu.addAction(self.mw.paste_block_action)
        edit_menu.addSeparator()

        self.mw.find_action = QAction(find_icon, '&Find...', self.mw)
        self.mw.find_action.setShortcut('Ctrl+F')
        edit_menu.addAction(self.mw.find_action)

        self.mw.advanced_search_action = QAction(self.style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), '&Advanced Search...', self.mw)
        self.mw.advanced_search_action.setShortcut('Ctrl+H')
        edit_menu.addAction(self.mw.advanced_search_action)
        edit_menu.addSeparator()
        
        self.mw.auto_fix_action = QAction(QIcon.fromTheme("document-edit"), "Auto-&fix Current String", self.mw)
        self.mw.auto_fix_action.setShortcut(QKeySequence("Ctrl+Shift+A")) 
        self.mw.auto_fix_action.setToolTip("Automatically fix issues in the current string (Ctrl+Shift+A). Ctrl-click to select rules.")
        edit_menu.addAction(self.mw.auto_fix_action)
        edit_menu.addSeparator()

        self.mw.rescan_all_tags_action = QAction(QIcon.fromTheme("system-search"), 'Rescan All Issues', self.mw)
        edit_menu.addAction(self.mw.rescan_all_tags_action)
        edit_menu.addSeparator()

        self.mw.recalculate_widths_action = QAction(self.style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), 'Recalculate Font Widths', self.mw)
        self.mw.recalculate_widths_action.setToolTip("Force recalculate widths and issues for all strings in the project")
        self.mw.recalculate_widths_action.setShortcut('Ctrl+Shift+R')
        edit_menu.addAction(self.mw.recalculate_widths_action)

    def _build_view_menu(self, menubar):
        """Internal helper to create view menu."""
        view_menu = menubar.addMenu('&View')
        view_menu.setToolTipsVisible(True)
        view_menu.installEventFilter(self.tooltip_filter)
        self.mw.view_menu = view_menu

        preview_icon = self.style.standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        self.mw.toggle_preview_action = QAction(preview_icon, '&Preview', self.mw)
        self.mw.toggle_preview_action.setCheckable(True)
        self.mw.toggle_preview_action.setChecked(bool(getattr(self.mw, 'preview_enabled', True)))
        self.mw.toggle_preview_action.setShortcut('Ctrl+Shift+P')
        self.mw.toggle_preview_action.setToolTip("Toggle the visibility of the visual text preview")
        view_menu.addAction(self.mw.toggle_preview_action)

        view_menu.addSeparator()
        self.mw.toggle_hide_tags_action = QAction('&Hide Tags', self.mw)
        self.mw.toggle_hide_tags_action.setShortcut('Ctrl+Q')
        self.mw.toggle_hide_tags_action.setToolTip("Toggle hiding tags in both original and translation texts (Ctrl+Q)")
        view_menu.addAction(self.mw.toggle_hide_tags_action)


    def _build_tools_menu(self, menubar):
        """Internal helper to create tools menu."""
        tools_menu = menubar.addMenu('&Tools')
        tools_menu.setObjectName('&Tools')
        tools_menu.setToolTipsVisible(True)
        tools_menu.installEventFilter(self.tooltip_filter)
        self.mw.tools_menu = tools_menu

        # Create a dynamic beautiful icon for BFN Font Editor with letter 'A'
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # Draw a stylish letter 'A' in accent blue
        painter.setPen(QColor("#0078d7"))
        font = QFont("Arial", 22, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "A")
        painter.end()
        bfn_editor_icon = QIcon(pixmap)

        self.mw.bfn_editor_action = QAction(
            bfn_editor_icon,
            'BFN &Font Editor...',
            self.mw
        )
        self.mw.bfn_editor_action.setToolTip('Open the BFN Font Editor (Nintendo binary font)')
        tools_menu.addAction(self.mw.bfn_editor_action)

        # Create a dynamic beautiful icon for Script Markup Studio with letter 'R'
        pixmap_r2 = QPixmap(32, 32)
        pixmap_r2.fill(Qt.GlobalColor.transparent)
        painter_r2 = QPainter(pixmap_r2)
        painter_r2.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter_r2.setPen(QColor("#8e44ad"))  # Accent purple
        font_r2 = QFont("Arial", 22, QFont.Weight.Bold)
        painter_r2.setFont(font_r2)
        painter_r2.drawText(pixmap_r2.rect(), Qt.AlignmentFlag.AlignCenter, "R")
        painter_r2.end()
        markup_icon = QIcon(pixmap_r2)

        self.mw.script_markup_studio_action = QAction(
            markup_icon,
            'Script Markup &Studio...',
            self.mw
        )
        self.mw.script_markup_studio_action.setToolTip('Convert a raw walkthrough into the standardized script format for MemePalace (Phase 0)')
        tools_menu.addAction(self.mw.script_markup_studio_action)

        # Create a dynamic beautiful icon for MemePalace Context Builder with letter 'M'
        pixmap_m = QPixmap(32, 32)
        pixmap_m.fill(Qt.GlobalColor.transparent)
        painter_m = QPainter(pixmap_m)
        painter_m.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter_m.setPen(QColor("#e81123")) # Stylish accent red/orange
        font_m = QFont("Arial", 22, QFont.Weight.Bold)
        painter_m.setFont(font_m)
        painter_m.drawText(pixmap_m.rect(), Qt.AlignmentFlag.AlignCenter, "M")
        painter_m.end()
        mempalace_icon = QIcon(pixmap_m)

        self.mw.mempalace_builder_action = QAction(
            mempalace_icon,
            'Meme&Palace Context Builder...',
            self.mw
        )
        self.mw.mempalace_builder_action.setToolTip('Weave chronological context walkthrough into your project memory (Ctrl+M)')
        self.mw.mempalace_builder_action.setShortcut('Ctrl+M')
        tools_menu.addAction(self.mw.mempalace_builder_action)

        # Dynamic icon for Build Glossary from Text with letter 'G'
        pixmap_g = QPixmap(32, 32)
        pixmap_g.fill(Qt.GlobalColor.transparent)
        painter_g = QPainter(pixmap_g)
        painter_g.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter_g.setPen(QColor("#107c10"))  # Green: builds new data
        font_g = QFont("Arial", 22, QFont.Weight.Bold)
        painter_g.setFont(font_g)
        painter_g.drawText(pixmap_g.rect(), Qt.AlignmentFlag.AlignCenter, "G")
        painter_g.end()

        self.mw.build_glossary_text_action = QAction(
            QIcon(pixmap_g),
            'Build &Glossary from Text...',
            self.mw
        )
        self.mw.build_glossary_text_action.setToolTip(
            'Sweep project text with AI to collect glossary terms, then describe each term '
            'from the context around every place it appears'
        )
        tools_menu.addAction(self.mw.build_glossary_text_action)

        self.mw.merge_speakers_action = QAction('&Merge Speakers from Script...', self.mw)
        self.mw.merge_speakers_action.setToolTip(
            'Match the marked-up script against the lines the game data already grouped '
            'by speaker, and give those speaker codes their real names'
        )
        tools_menu.addAction(self.mw.merge_speakers_action)

        # Create a dynamic beautiful icon for Inspect Story Context with letter 'S'
        pixmap_s = QPixmap(32, 32)
        pixmap_s.fill(Qt.GlobalColor.transparent)
        painter_s = QPainter(pixmap_s)
        painter_s.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter_s.setPen(QColor("#0078d7")) # Classic Microsoft Blue
        font_s = QFont("Arial", 22, QFont.Weight.Bold)
        painter_s.setFont(font_s)
        painter_s.drawText(pixmap_s.rect(), Qt.AlignmentFlag.AlignCenter, "S")
        painter_s.end()
        story_icon = QIcon(pixmap_s)

        self.mw.inspect_story_context_action = QAction(
            story_icon,
            'Inspect &Story Context...',
            self.mw
        )
        self.mw.inspect_story_context_action.setToolTip('Show timeline, speaker and visual context for the selected row from MemePalace (Ctrl+I)')
        self.mw.inspect_story_context_action.setShortcut('Ctrl+I')
        tools_menu.addAction(self.mw.inspect_story_context_action)

        # Create a dynamic beautiful icon for MemePalace Database Viewer with letter 'V'
        pixmap_v = QPixmap(32, 32)
        pixmap_v.fill(Qt.GlobalColor.transparent)
        painter_v = QPainter(pixmap_v)
        painter_v.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter_v.setPen(QColor("#107c41")) # Accent Green
        font_v = QFont("Arial", 22, QFont.Weight.Bold)
        painter_v.setFont(font_v)
        painter_v.drawText(pixmap_v.rect(), Qt.AlignmentFlag.AlignCenter, "V")
        painter_v.end()
        viewer_icon = QIcon(pixmap_v)

        self.mw.mempalace_viewer_action = QAction(
            viewer_icon,
            'MemePalace Database &Viewer...',
            self.mw
        )
        self.mw.mempalace_viewer_action.setToolTip('Examine and browse full rooms, visual contexts and character graph relations in local database (Ctrl+Shift+I)')
        self.mw.mempalace_viewer_action.setShortcut('Ctrl+Shift+I')
        tools_menu.addAction(self.mw.mempalace_viewer_action)
        tools_menu.addSeparator()

        self.mw.fix_all_strings_action = QAction(
            QIcon.fromTheme("edit-find-replace"),
            'Fix All Strings...',
            self.mw
        )
        self.mw.fix_all_strings_action.setToolTip(
            'Automatically fix selected types of formatting and layout issues across all strings'
        )
        tools_menu.addAction(self.mw.fix_all_strings_action)

        tools_menu.addSeparator()

        self.mw.export_bmg_json_action = QAction(
            self.style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
            'Export Current BMG to &JSON...',
            self.mw
        )
        self.mw.export_bmg_json_action.setToolTip(
            'Export the text content of the currently selected BMG file to a JSON file for inspection'
        )
        self.mw.export_bmg_json_action.setEnabled(False)
        tools_menu.addAction(self.mw.export_bmg_json_action)

        self.mw.import_bmg_json_action = QAction(
            self.style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
            'Import Current BMG from &JSON...',
            self.mw
        )
        self.mw.import_bmg_json_action.setToolTip(
            'Import BMG text content from an exported JSON file into the currently selected block'
        )
        self.mw.import_bmg_json_action.setEnabled(False)
        tools_menu.addAction(self.mw.import_bmg_json_action)


    def _build_navigation_menu(self, menubar):
        """Internal helper to create navigation menu."""
        self.mw.navigation_menu = menubar.addMenu('&Navigation')
        self.mw.navigation_menu.setToolTipsVisible(True)
        self.mw.navigation_menu.installEventFilter(self.tooltip_filter)
        
        self.mw.next_block_nav_action = QAction('Next Block Nav', self.mw)
        self.mw.next_block_nav_action.setShortcut(QKeySequence('Alt+Shift+Down'))
        self.mw.next_block_nav_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.mw.navigation_menu.addAction(self.mw.next_block_nav_action)

        self.mw.prev_block_nav_action = QAction('Previous Block Nav', self.mw)
        self.mw.prev_block_nav_action.setShortcut(QKeySequence('Alt+Shift+Up'))
        self.mw.prev_block_nav_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.mw.navigation_menu.addAction(self.mw.prev_block_nav_action)

        self.mw.next_folder_nav_action = QAction('Next Folder Nav', self.mw)
        self.mw.next_folder_nav_action.setShortcut(QKeySequence('Alt+Shift+Right'))
        self.mw.next_folder_nav_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.mw.navigation_menu.addAction(self.mw.next_folder_nav_action)

        self.mw.prev_folder_nav_action = QAction('Previous Folder Nav', self.mw)
        self.mw.prev_folder_nav_action.setShortcut(QKeySequence('Alt+Shift+Left'))
        self.mw.prev_folder_nav_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.mw.navigation_menu.addAction(self.mw.prev_folder_nav_action)

    def _build_bookmarks_menu(self, menubar):
        """Internal helper to create bookmarks menu."""
        bookmarks_menu = menubar.addMenu('&Bookmarks')
        bookmarks_menu.setToolTipsVisible(True)
        bookmarks_menu.installEventFilter(self.tooltip_filter)
        self.mw.bookmarks_menu = bookmarks_menu

        # Add Bookmark Action
        self.mw.add_bookmark_action = QAction('&Add Bookmark...', self.mw)
        self.mw.add_bookmark_action.setShortcut('Ctrl+B')
        self.mw.add_bookmark_action.setToolTip("Add bookmark at the current line of the active block (Ctrl+B)")
        bookmarks_menu.addAction(self.mw.add_bookmark_action)

        # Clear Bookmarks Action
        self.mw.clear_bookmarks_action = QAction('&Clear All Bookmarks', self.mw)
        self.mw.clear_bookmarks_action.setToolTip("Delete all bookmarks persistently")
        bookmarks_menu.addAction(self.mw.clear_bookmarks_action)

        bookmarks_menu.addSeparator()

    def _build_help_menu(self, menubar):
        """Internal helper to create help menu."""
        self.mw.help_shortcuts_action = QAction(QIcon.fromTheme("input-keyboard", self.style.standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton)), '&Shortcuts Help', self.mw)
        self.mw.help_shortcuts_action.setShortcut('F1')

        help_menu = QMenu('&Help', menubar)
        help_menu.setToolTipsVisible(True)
        help_menu.installEventFilter(self.tooltip_filter)
        help_menu.addAction(self.mw.help_shortcuts_action)
        
        help_button = QToolButton()
        help_button.setText("Help")
        help_button.setMenu(help_menu)
        help_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        help_button.setStyleSheet("QToolButton { border: none; padding: 5px 10px; background: transparent; } QToolButton::menu-indicator { image: none; } QToolButton:hover { background-color: rgba(0,0,0,0.1); }")
        menubar.setCornerWidget(help_button, Qt.Corner.TopRightCorner)
