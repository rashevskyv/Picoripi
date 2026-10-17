# components/project_dialogs.py
"""
Dialog windows for project management:
- OpenProjectDialog: Open an existing project
- ImportBlockDialog: Import a new block into the project
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QFileDialog, QDialogButtonBox,
    QMessageBox, QTreeWidget, QTreeWidgetItem, QAbstractItemView, QStyle, QTreeWidgetItemIterator
)
from PyQt6.QtCore import Qt
from utils.logging_utils import log_info
from core import formats
from core.i18n import tr


class OpenProjectDialog(QDialog):
    """
    Dialog for opening an existing project.

    Currently simple: just pick a .uiproj file or project directory.
    Can be extended with recent projects list.
    """

    def __init__(self, parent=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.setWindowTitle(tr('Open Project'))
        self.setMinimumWidth(500)

        self.project_path = None

        self._setup_ui()

    def _setup_ui(self):
        """Internal helper to setup ui."""
        layout = QVBoxLayout(self)

        # Instructions
        info_label = QLabel(
            tr('Select a project file (.uiproj) to open.'),
            self
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Path selection
        path_layout = QHBoxLayout()

        self.path_edit = QLineEdit(self)
        self.path_edit.setPlaceholderText(tr('Select project.uiproj file...'))
        self.path_edit.setReadOnly(True)
        path_layout.addWidget(self.path_edit)

        browse_file_button = QPushButton(tr('Browse...'), self)
        browse_file_button.clicked.connect(self._browse_file)
        path_layout.addWidget(browse_file_button)

        layout.addLayout(path_layout)

        layout.addStretch()

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _browse_file(self):
        """Browse for .uiproj file."""
        # Try to start in a sensible location (user's home or recent projects directory)
        if hasattr(self.parent(), 'last_browse_dir') and self.parent().last_browse_dir:
            start_dir = self.parent().last_browse_dir
        else:
            start_dir = Path.home().as_posix()

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Project File",
            start_dir,
            "Project Files (*.uiproj);;All Files (*)"
        )

        if file_path:
            self.path_edit.setText(file_path)
            # Update last_dir
            if hasattr(self.parent(), 'last_browse_dir'):
                 self.parent().last_browse_dir = Path(file_path).parent.as_posix()
                 if hasattr(self.parent(), 'settings_manager'):
                     self.parent().settings_manager.save_settings()

    def _validate_and_accept(self):
        """Validate selected path before accepting."""
        path = self.path_edit.text().strip()

        if not path:
            QMessageBox.warning(
                self,
                tr('No Project Selected'),
                tr('Please select a .uiproj file.')
            )
            return

        if not Path(path).exists():
            QMessageBox.warning(
                self,
                tr('File Not Found'),
                f"The selected file does not exist:\n{path}"
            )
            return

        # Validate it's a .uiproj file
        if not Path(path).is_file():
            QMessageBox.warning(
                self,
                tr('Invalid Selection'),
                tr('Please select a project file, not a directory.')
            )
            return

        if not path.endswith('.uiproj'):
            QMessageBox.warning(
                self,
                tr('Invalid File'),
                tr('Please select a .uiproj file.')
            )
            return

        self.project_path = path
        log_info(f"OpenProjectDialog: Opening project at {path}")
        self.accept()

    def get_project_path(self):
        """
        Get selected project path after dialog is accepted.

        Returns:
            str: Project path or None if cancelled
        """
        if self.result() == QDialog.DialogCode.Accepted:
            return self.project_path
        return None


class ImportBlockDialog(QDialog):
    """
    Dialog for importing a new block (file) into an existing project.

    Collects:
    - Source file path
    - Translation file path (optional)
    - Block name (optional, defaults to filename)
    - Description (optional)
    """

    def __init__(self, parent=None, project_manager=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.setWindowTitle(tr('Import Block'))
        self.setMinimumWidth(500)

        self.project_manager = project_manager
        self.source_file = None
        self.translation_file = None
        self.block_name = None
        self.description = None

        self._setup_ui()

    def _setup_ui(self):
        """Internal helper to setup ui."""
        layout = QVBoxLayout(self)

        # Info text
        if self.project_manager and self.project_manager.project:
            info = QLabel(
                f"Import a new file into project: {self.project_manager.project.name}",
                self
            )
            info.setStyleSheet("font-weight: bold;")
            layout.addWidget(info)

        # Form layout
        form_layout = QFormLayout()

        # Source file selection
        source_layout = QHBoxLayout()
        self.file_edit = QLineEdit(self)
        self.file_edit.setPlaceholderText(tr('Select source file to import...'))
        self.file_edit.setReadOnly(True)
        self.file_edit.textChanged.connect(self._on_source_file_selected)
        source_layout.addWidget(self.file_edit)

        browse_source_button = QPushButton(tr('Browse...'), self)
        browse_source_button.clicked.connect(self._browse_source_file)
        source_layout.addWidget(browse_source_button)

        form_layout.addRow(tr('Source File:'), source_layout)

        # Translation file selection
        translation_layout = QHBoxLayout()
        self.translation_edit = QLineEdit(self)
        self.translation_edit.setPlaceholderText(tr('Optional: select existing translation file...'))
        self.translation_edit.setReadOnly(True)
        translation_layout.addWidget(self.translation_edit)

        browse_translation_button = QPushButton(tr('Browse...'), self)
        browse_translation_button.clicked.connect(self._browse_translation_file)
        translation_layout.addWidget(browse_translation_button)

        form_layout.addRow(tr('Translation File:'), translation_layout)

        # Block name
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText(tr('Auto-filled from filename'))
        form_layout.addRow(tr('Block Name:'), self.name_edit)

        # Description
        self.description_edit = QTextEdit(self)
        self.description_edit.setPlaceholderText(tr('Optional: Enter block description...'))
        self.description_edit.setMaximumHeight(80)
        form_layout.addRow(tr('Description:'), self.description_edit)

        layout.addLayout(form_layout)

        # Info label
        info_label = QLabel(
            tr("The source file will be copied to the project's 'sources/' directory.\nIf you don't specify a translation file, the source will be copied to 'translation/'."),
            self
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(info_label)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _browse_source_file(self):
        """Browse for source file."""
        if hasattr(self.parent(), 'last_browse_dir') and self.parent().last_browse_dir:
            start_dir = self.parent().last_browse_dir
        else:
            start_dir = Path.home().as_posix()

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Source File",
            start_dir,
            formats.dialog_filter(getattr(self.parent(), "current_game_rules", None))
        )

        if file_path:
            self.file_edit.setText(file_path)
            if hasattr(self.parent(), 'last_browse_dir'):
                 self.parent().last_browse_dir = Path(file_path).parent.as_posix()
                 if hasattr(self.parent(), 'settings_manager'):
                     self.parent().settings_manager.save_settings()

    def _browse_translation_file(self):
        """Browse for translation file."""
        if self.file_edit.text():
            start_dir = Path(self.file_edit.text()).parent.as_posix()
        elif hasattr(self.parent(), 'last_browse_dir') and self.parent().last_browse_dir:
            start_dir = self.parent().last_browse_dir
        else:
            start_dir = Path.home().as_posix()

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Translation File (Optional)",
            start_dir,
            formats.dialog_filter(getattr(self.parent(), "current_game_rules", None))
        )

        if file_path:
            self.translation_edit.setText(file_path)
            if hasattr(self.parent(), 'last_browse_dir'):
                 self.parent().last_browse_dir = Path(file_path).parent.as_posix()
                 if hasattr(self.parent(), 'settings_manager'):
                     self.parent().settings_manager.save_settings()

    def _on_source_file_selected(self, file_path):
        """Auto-fill block name from filename if not already set."""
        if file_path and not self.name_edit.text():
            path_obj = Path(file_path)
            # Make it more readable
            display_name = path_obj.stem.replace('_', ' ').title()
            self.name_edit.setText(display_name)

    def _validate_and_accept(self):
        """Validate inputs before accepting."""
        # Validate file
        file_path = self.file_edit.text().strip()
        if not file_path:
            QMessageBox.warning(
                self,
                tr('No File Selected'),
                tr('Please select a source file to import.')
            )
            return

        if not Path(file_path).exists():
            QMessageBox.warning(
                self,
                tr('File Not Found'),
                f"The selected file does not exist:\n{file_path}"
            )
            return

        # Validate name
        name = self.name_edit.text().strip()
        if not name:
            # Use filename as fallback
            name = Path(file_path).stem
            name = name.replace('_', ' ').title()

        # Store results
        self.source_file = file_path
        self.translation_file = self.translation_edit.text().strip() or None
        self.block_name = name
        self.description = self.description_edit.toPlainText().strip()

        log_info(f"ImportBlockDialog: Importing block '{name}' from {file_path}")
        if self.translation_file:
            log_info(f"  Translation file: {self.translation_file}")
        self.accept()

    def get_block_info(self):
        """
        Get block information after dialog is accepted.

        Returns:
            dict: Block information or None if cancelled
        """
        if self.result() == QDialog.DialogCode.Accepted:
            return {
                'source_file': self.source_file,
                'translation_file': self.translation_file,
                'name': self.block_name,
                'description': self.description
            }
        return None


class MoveToFolderDialog(QDialog):
    """Dialog for moving items to a specific virtual folder using a tree view."""
    def __init__(self, parent=None, project_manager=None, current_folder_id=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.pm = project_manager
        self.current_folder_id = current_folder_id
        self.selected_folder_id = None
        self.new_folder_created = False
        
        self.setWindowTitle(tr('Move Files to folder'))
        self.setMinimumSize(400, 500)
        self._setup_ui()
        self._populate_tree()

    def _setup_ui(self):
        """Internal helper to setup ui."""
        layout = QVBoxLayout(self)
        
        label = QLabel(tr('Select destination folder:'))
        layout.addWidget(label)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.tree)
        
        # New Folder Button
        self.btn_new_folder = QPushButton(tr('New Folder'))
        self.btn_new_folder.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.btn_new_folder.clicked.connect(self._create_new_folder)
        layout.addWidget(self.btn_new_folder)
        
        # Standard Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
        self.tree.itemDoubleClicked.connect(self._validate_and_accept)

    def _populate_tree(self):
        """Internal helper to populate tree."""
        self.tree.clear()
        
        # Root Item
        root_item = QTreeWidgetItem(self.tree, ["(Root Directory)"])
        root_item.setData(0, Qt.UserRole, None)
        root_item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        
        if self.pm and self.pm.project:
            self._add_folders_recursive(root_item, self.pm.project.virtual_folders)
            
        root_item.setExpanded(True)
        self.tree.setCurrentItem(root_item)

    def _add_folders_recursive(self, parent_item, folders):
        """Internal helper to add folders recursive."""
        for folder in folders:
            item = QTreeWidgetItem(parent_item, [folder.name])
            item.setData(0, Qt.UserRole, folder.id)
            item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
            
            # Highlight current folder if we are moving from somewhere
            if folder.id == self.current_folder_id:
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)

            self._add_folders_recursive(item, folder.children)

    def _create_new_folder(self):
        """Internal helper to create new folder."""
        curr = self.tree.currentItem()
        parent_id = curr.data(0, Qt.UserRole) if curr else None
        
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and new_name:
            new_f = self.pm.create_virtual_folder(new_name, parent_id=parent_id)
            if new_f:
                # Refresh tree and select new folder
                self._populate_tree()
                self._select_by_id(new_f.id)
                self.new_folder_created = True

    def _select_by_id(self, folder_id):
        """Internal helper to select by id."""
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) == folder_id:
                self.tree.setCurrentItem(item)
                item.setExpanded(True)
                break
            iterator += 1

    def _validate_and_accept(self):
        """Internal helper to validate and accept."""
        curr = self.tree.currentItem()
        if curr:
            self.selected_folder_id = curr.data(0, Qt.UserRole)
            self.accept()

    def get_selected_folder_id(self):
        """Get the selected folder id."""
        return self.selected_folder_id
