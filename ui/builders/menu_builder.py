from PyQt5.QtWidgets import QMenu, QAction, QStyle, QToolButton
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtCore import Qt
from pathlib import Path

class MenuBuilder:
    def __init__(self, main_window):
        self.mw = main_window
        self.style = main_window.style()

    def build_all(self):
        menubar = self.mw.menuBar()
        self._build_file_menu(menubar)
        self._build_edit_menu(menubar)
        self._build_tools_menu(menubar)
        self._build_navigation_menu(menubar)
        self._build_help_menu(menubar)

    def _build_file_menu(self, menubar):
        file_menu = menubar.addMenu('&File')
        
        open_icon = self.style.standardIcon(QStyle.SP_DialogOpenButton)
        save_icon = self.style.standardIcon(QStyle.SP_DialogSaveButton)
        reload_icon = self.style.standardIcon(QStyle.SP_BrowserReload)
        exit_icon = self.style.standardIcon(QStyle.SP_DialogCloseButton)
        settings_icon = QIcon.fromTheme('settings', self.style.standardIcon(QStyle.SP_FileDialogDetailedView))

        # Project actions
        self.mw.new_project_action = QAction(QIcon.fromTheme("document-new"), '&New Project...', self.mw)
        self.mw.new_project_action.setShortcut('Ctrl+N')
        file_menu.addAction(self.mw.new_project_action)

        self.mw.open_project_action = QAction(open_icon, '&Open Project...', self.mw)
        self.mw.open_project_action.setShortcut('Ctrl+O')
        file_menu.addAction(self.mw.open_project_action)

        # Recent Projects submenu
        self.mw.recent_projects_menu = QMenu('Recent Projects', self.mw)
        file_menu.addMenu(self.mw.recent_projects_menu)

        self.mw.close_project_action = QAction('&Close Project', self.mw)
        self.mw.close_project_action.setEnabled(False)
        file_menu.addAction(self.mw.close_project_action)
        file_menu.addSeparator()

        # Block actions
        self.mw.import_block_action = QAction(QIcon.fromTheme("document-import"), '&Import Block...', self.mw)
        self.mw.import_block_action.setEnabled(False)
        file_menu.addAction(self.mw.import_block_action)

        self.mw.import_directory_action = QAction(QIcon.fromTheme("folder-open"), 'Import &Directory...', self.mw)
        self.mw.import_directory_action.setEnabled(False)
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
        edit_menu = menubar.addMenu('&Edit')
        edit_menu.setObjectName('&Edit')

        def _icon_path(file_name: str) -> str:
            project_root = Path(__file__).resolve().parent.parent.parent
            return str(project_root / 'resources' / 'icons' / file_name)

        undo_local = _icon_path('undo.svg')
        redo_local = _icon_path('redo.svg')

        undo_icon = QIcon(undo_local) if Path(undo_local).exists() else QIcon.fromTheme("edit-undo", self.style.standardIcon(QStyle.SP_ArrowBack))
        redo_icon = QIcon(redo_local) if Path(redo_local).exists() else QIcon.fromTheme("edit-redo", self.style.standardIcon(QStyle.SP_ArrowForward))
        find_icon = self.style.standardIcon(QStyle.SP_FileDialogContentsView)

        self.mw.undo_typing_action = QAction(undo_icon, '&Undo Typing', self.mw)
        self.mw.undo_typing_action.setShortcut(QKeySequence.Undo)
        edit_menu.addAction(self.mw.undo_typing_action)

        self.mw.redo_typing_action = QAction(redo_icon, '&Redo Typing', self.mw)
        self.mw.redo_typing_action.setShortcuts([QKeySequence.Redo, QKeySequence('Ctrl+Shift+Z')])
        edit_menu.addAction(self.mw.redo_typing_action)
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
        edit_menu.addSeparator()
        
        self.mw.auto_fix_action = QAction(QIcon.fromTheme("document-edit"), "Auto-&fix Current String", self.mw)
        self.mw.auto_fix_action.setShortcut(QKeySequence("Ctrl+Shift+A")) 
        self.mw.auto_fix_action.setToolTip("Automatically fix issues in the current string (Ctrl+Shift+A)")
        edit_menu.addAction(self.mw.auto_fix_action)
        edit_menu.addSeparator()

        self.mw.rescan_all_tags_action = QAction(QIcon.fromTheme("system-search"), 'Rescan All Issues', self.mw)
        edit_menu.addAction(self.mw.rescan_all_tags_action)
        edit_menu.addSeparator()

        self.mw.recalculate_widths_action = QAction(self.style.standardIcon(QStyle.SP_BrowserReload), 'Recalculate Font Widths', self.mw)
        self.mw.recalculate_widths_action.setToolTip("Force recalculate widths and issues for all strings in the project")
        self.mw.recalculate_widths_action.setShortcut('Ctrl+Shift+R')
        edit_menu.addAction(self.mw.recalculate_widths_action)

    def _build_tools_menu(self, menubar):
        tools_menu = menubar.addMenu('&Tools')
        tools_menu.setObjectName('&Tools')
        self.mw.tools_menu = tools_menu

        self.mw.bfn_editor_action = QAction(
            self.style.standardIcon(QStyle.SP_DesktopIcon),
            'BFN &Font Editor...',
            self.mw
        )
        self.mw.bfn_editor_action.setToolTip('Open the BFN Font Editor (Nintendo binary font)')
        tools_menu.addAction(self.mw.bfn_editor_action)

    def _build_navigation_menu(self, menubar):
        self.mw.navigation_menu = menubar.addMenu('&Navigation')
        
        self.mw.next_block_nav_action = QAction('Next Block Nav', self.mw)
        self.mw.next_block_nav_action.setShortcut(QKeySequence('Alt+Shift+Down'))
        self.mw.next_block_nav_action.setShortcutContext(Qt.WindowShortcut)
        self.mw.navigation_menu.addAction(self.mw.next_block_nav_action)

        self.mw.prev_block_nav_action = QAction('Previous Block Nav', self.mw)
        self.mw.prev_block_nav_action.setShortcut(QKeySequence('Alt+Shift+Up'))
        self.mw.prev_block_nav_action.setShortcutContext(Qt.WindowShortcut)
        self.mw.navigation_menu.addAction(self.mw.prev_block_nav_action)

        self.mw.next_folder_nav_action = QAction('Next Folder Nav', self.mw)
        self.mw.next_folder_nav_action.setShortcut(QKeySequence('Alt+Shift+Right'))
        self.mw.next_folder_nav_action.setShortcutContext(Qt.WindowShortcut)
        self.mw.navigation_menu.addAction(self.mw.next_folder_nav_action)

        self.mw.prev_folder_nav_action = QAction('Previous Folder Nav', self.mw)
        self.mw.prev_folder_nav_action.setShortcut(QKeySequence('Alt+Shift+Left'))
        self.mw.prev_folder_nav_action.setShortcutContext(Qt.WindowShortcut)
        self.mw.navigation_menu.addAction(self.mw.prev_folder_nav_action)

    def _build_help_menu(self, menubar):
        self.mw.help_shortcuts_action = QAction(QIcon.fromTheme("input-keyboard", self.style.standardIcon(QStyle.SP_DialogHelpButton)), '&Shortcuts Help', self.mw)
        self.mw.help_shortcuts_action.setShortcut('F1')

        help_menu = QMenu('&Help', menubar)
        help_menu.addAction(self.mw.help_shortcuts_action)
        
        help_button = QToolButton()
        help_button.setText("Help")
        help_button.setMenu(help_menu)
        help_button.setPopupMode(QToolButton.InstantPopup)
        help_button.setStyleSheet("QToolButton { border: none; padding: 5px 10px; background: transparent; } QToolButton::menu-indicator { image: none; } QToolButton:hover { background-color: rgba(0,0,0,0.1); }")
        menubar.setCornerWidget(help_button, Qt.TopRightCorner)
