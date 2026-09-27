from pathlib import Path
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLineEdit, QFileDialog, QMenu
from core.i18n import tr


class SettingsPathPickerMixin:
    """Browse/create path selectors for settings dialog."""

    def _create_script_selector(self, line_edit: QLineEdit):
        """Internal helper to create script selector."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(line_edit)
        
        browse_button = QPushButton(tr('...'))
        browse_button.setToolTip(
            tr('<b>Browse</b><br>Click — pick a script or executable (.bat, .cmd, .exe, .py, .sh).<br>You can also type or paste a path into the field on the left.')
        )
        browse_button.setFixedSize(24, 24)
        browse_button.clicked.connect(lambda: self._browse_for_script(line_edit))
        layout.addWidget(browse_button)
        
        return widget

    def _browse_for_script(self, line_edit: QLineEdit):
        """Internal helper to browse for script."""
        start_dir = line_edit.text().strip() if line_edit.text() else ""
        if start_dir:
            try:
                start_dir = str(Path(start_dir).parent.as_posix())
            except Exception:
                start_dir = ""
        
        filter_str = "Scripts/Executables (*.bat *.cmd *.exe *.py *.sh);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select External Script/Tool", start_dir, filter_str)
        if path:
            line_edit.setText(path)

    def _create_path_selector(self, line_edit: QLineEdit):
        """Internal helper to create path selector."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        
        layout.addWidget(line_edit)
        
        browse_button = QPushButton(tr('...'))
        browse_button.setToolTip(
            tr('<b>Browse</b><br>Click — pick a game data file (.json, .arc, .rarc, .bfn, .bmg).<br>With Directory Mode ticked it asks for a folder instead.<br>You can also type or paste a path into the field on the left.')
        )
        browse_button.setFixedSize(24, 24)
        browse_button.clicked.connect(lambda: self._browse_for_file(line_edit))
        layout.addWidget(browse_button)
        
        return widget

    def _browse_for_file(self, line_edit: QLineEdit):
        """Internal helper to browse for file."""
        is_dir_mode = self.dir_mode_checkbox.isChecked()

        start_dir = line_edit.text() if line_edit.text() else ""
        if not is_dir_mode and start_dir:
            try:
                start_dir = str(Path(start_dir).parent.as_posix())
            except Exception:
                start_dir = ""

        if is_dir_mode:
            path = QFileDialog.getExistingDirectory(self, "Select Directory", start_dir)
        else:
            filter_str = "Supported Files (*.json *.arc *.rarc *.bfn *.bmg);;JSON Files (*.json);;Archive Files (*.arc *.rarc);;Font Files (*.bfn);;BMG Files (*.bmg);;All Files (*)"
            path, _ = QFileDialog.getOpenFileName(self, "Select File", start_dir, filter_str)

        if path:
            line_edit.setText(path)

    def _create_dir_selector(self, line_edit: QLineEdit):
        """Internal helper to create dir selector."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        
        layout.addWidget(line_edit)
        
        browse_button = QPushButton(tr('...'))
        browse_button.setToolTip(
            tr('<b>Browse</b><br>Click — pick a folder.<br>You can also type or paste a path into the field on the left.')
        )
        browse_button.setFixedSize(24, 24)
        browse_button.clicked.connect(lambda: self._browse_for_directory(line_edit))
        layout.addWidget(browse_button)
        
        return widget

    def _browse_for_directory(self, line_edit: QLineEdit):
        """Internal helper to browse for directory."""
        start_dir = line_edit.text().strip() if line_edit.text() else ""
        path = QFileDialog.getExistingDirectory(self, "Select Fonts Directory", start_dir)
        if path:
            line_edit.setText(path)

    def _on_fonts_dir_changed(self):
        """Internal helper to handle the fonts dir changed event."""
        self.mw.fonts_dir_path = self.fonts_path_edit.text().strip()
        selected_dir_name = self.plugin_combo.currentData()
        if selected_dir_name:
            self._populate_font_list(selected_dir_name)

    def _on_orig_fonts_dir_changed(self):
        """Internal helper to handle the orig fonts dir changed event."""
        self.mw.orig_fonts_dir_path = self.orig_fonts_path_edit.text().strip()

    def _create_reference_selector(self, line_edit: QLineEdit):
        """Helper to create reference path selector (folder or ISO file)."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit)

        browse_button = QPushButton(tr('...'))
        browse_button.setToolTip(
            tr('<b>Browse</b><br>Click — pick a reference translation folder or game ISO image.<br>You can also type or paste a path into the field on the left.')
        )
        browse_button.setFixedSize(24, 24)
        browse_button.clicked.connect(lambda: self._browse_for_reference(line_edit, browse_button))
        layout.addWidget(browse_button)
        return widget

    def _browse_for_reference(self, line_edit: QLineEdit, anchor_widget: QWidget = None):
        """Prompt to choose a reference directory or ISO image via popup menu."""
        start_dir = line_edit.text().strip() if line_edit.text() else ""
        if start_dir and not Path(start_dir).is_dir():
            try:
                start_dir = str(Path(start_dir).parent.as_posix())
            except Exception:
                start_dir = ""

        browse_menu = QMenu(self)
        folder_act = browse_menu.addAction(tr("Select Folder (Patch or Unpacked ROM)..."))
        iso_act = browse_menu.addAction(tr("Select Game ISO Image (*.iso)..."))
        clear_act = browse_menu.addAction(tr("Clear Path"))

        pos = anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft()) if anchor_widget else self.cursor().pos()
        chosen = browse_menu.exec(pos)

        if chosen == folder_act:
            p = QFileDialog.getExistingDirectory(self, tr("Select Reference Folder"), start_dir)
            if p:
                line_edit.setText(p)
        elif chosen == iso_act:
            p, _ = QFileDialog.getOpenFileName(
                self,
                tr("Select Multi-Language ROM ISO Image"),
                start_dir,
                "Game ISO Images (*.iso);;All Files (*)"
            )
            if p:
                line_edit.setText(p)
        elif chosen == clear_act:
            line_edit.clear()

    def _create_file_selector(self, line_edit: QLineEdit, title: str, filter_str: str, tooltip: str = ""):
        """Helper to create a single file selector."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit)

        browse_button = QPushButton(tr('...'))
        if tooltip:
            browse_button.setToolTip(tooltip)
        browse_button.setFixedSize(24, 24)
        browse_button.clicked.connect(lambda: self._browse_for_single_file(line_edit, title, filter_str))
        layout.addWidget(browse_button)
        return widget

    def _browse_for_single_file(self, line_edit: QLineEdit, title: str, filter_str: str):
        """Browse for a single file."""
        start_dir = line_edit.text().strip() if line_edit.text() else ""
        if start_dir:
            try:
                start_dir = str(Path(start_dir).parent.as_posix())
            except Exception:
                start_dir = ""
        path, _ = QFileDialog.getOpenFileName(self, title, start_dir, filter_str)
        if path:
            line_edit.setText(path)
