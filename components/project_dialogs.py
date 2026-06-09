# components/project_dialogs.py
"""
Dialog windows for project management:
- NewProjectDialog: Create a new translation project
- OpenProjectDialog: Open an existing project
- ImportBlockDialog: Import a new block into the project
"""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QComboBox, QFileDialog, QDialogButtonBox,
    QMessageBox, QGroupBox, QRadioButton, QButtonGroup, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QAbstractItemView, QStyle, QTreeWidgetItemIterator
)
from PyQt6.QtCore import Qt
from utils.logging_utils import log_debug, log_info


class NewProjectDialog(QDialog):
    """
    Dialog for creating a new translation project.

    Collects:
    - Project name
    - Project directory (where to create the project)
    - Active plugin
    - Optional description
    """

    def __init__(self, parent=None, available_plugins=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setMinimumWidth(500)

        self.available_plugins = available_plugins or {}
        self.project_dir = None
        self.project_name = None
        self.plugin_name = None
        self.description = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Form layout for inputs
        form_layout = QFormLayout()

        # Project name
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("e.g., Wind Waker Translation")
        form_layout.addRow("Project Name:", self.name_edit)

        # Project directory
        dir_layout = QHBoxLayout()
        self.dir_edit = QLineEdit(self)
        self.dir_edit.setPlaceholderText("Select where to create the project files (.uiproj)...")
        self.dir_edit.setReadOnly(True)
        dir_layout.addWidget(self.dir_edit)

        browse_button = QPushButton("Browse...", self)
        browse_button.clicked.connect(self._browse_directory)
        dir_layout.addWidget(browse_button)

        form_layout.addRow("Project Location:", dir_layout)

        # Mode selection
        mode_layout = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.radio_folders = QRadioButton("Folders")
        self.radio_files = QRadioButton("Files")
        self.radio_folders.setChecked(True)
        self.mode_group.addButton(self.radio_folders)
        self.mode_group.addButton(self.radio_files)
        mode_layout.addWidget(self.radio_folders)
        mode_layout.addWidget(self.radio_files)
        mode_layout.addStretch()
        form_layout.addRow("Source Type:", mode_layout)

        # Source location
        source_layout = QHBoxLayout()
        self.source_edit = QLineEdit(self)
        self.source_edit.setPlaceholderText("Select source directory...")
        self.source_edit.setReadOnly(True)
        source_layout.addWidget(self.source_edit)
        self.browse_source_btn = QPushButton("Browse...", self)
        self.browse_source_btn.clicked.connect(self._browse_source)
        source_layout.addWidget(self.browse_source_btn)
        form_layout.addRow("Source:", source_layout)

        # Translation location
        trans_layout = QHBoxLayout()
        self.trans_edit = QLineEdit(self)
        self.trans_edit.setPlaceholderText("Select translation directory...")
        self.trans_edit.setReadOnly(True)
        trans_layout.addWidget(self.trans_edit)
        self.browse_trans_btn = QPushButton("Browse...", self)
        self.browse_trans_btn.clicked.connect(self._browse_translation)
        trans_layout.addWidget(self.browse_trans_btn)
        form_layout.addRow("Translation:", trans_layout)

        # Auto-create Checkbox
        self.auto_create_cb = QCheckBox("Auto-create translation files")
        self.auto_create_cb.toggled.connect(self._on_auto_create_toggled)
        form_layout.addRow("", self.auto_create_cb)

        # Plugin selection
        self.plugin_combo = QComboBox(self)
        self._populate_plugins()
        form_layout.addRow("Game Plugin:", self.plugin_combo)

        # Description
        self.description_edit = QTextEdit(self)
        self.description_edit.setPlaceholderText("Optional: Enter project description...")
        self.description_edit.setMaximumHeight(80)
        form_layout.addRow("Description:", self.description_edit)

        layout.addLayout(form_layout)

        # Connect radio buttons
        self.radio_folders.toggled.connect(self._on_mode_changed)
        self.radio_files.toggled.connect(self._on_mode_changed)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_plugins(self):
        """Populate plugin dropdown with available plugins."""
        if not self.available_plugins:
            # Fallback: scan plugins directory
            self.available_plugins = self._scan_plugins()

        # Add placeholder item
        self.plugin_combo.addItem("-- Select a plugin --", None)

        for display_name in sorted(self.available_plugins.keys()):
            plugin_dir = self.available_plugins[display_name]
            self.plugin_combo.addItem(display_name, plugin_dir)

    def _scan_plugins(self):
        """Scan plugins directory to find available plugins."""
        plugins = {}
        plugins_dir = Path("plugins")

        if not plugins_dir.is_dir():
            return plugins

        for item_path in plugins_dir.iterdir():
            config_path = item_path / "config.json"

            if item_path.is_dir() and config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    display_name = config_data.get("display_name", item_path.name)
                    plugins[display_name] = item_path.name
                except Exception as e:
                    log_debug(f"Could not read config for plugin '{item_path.name}': {e}")
                    plugins[item_path.name] = item_path.name

        return plugins

    def _on_mode_changed(self):
        is_folders = self.radio_folders.isChecked()
        self.source_edit.clear()
        self.trans_edit.clear()
        if is_folders:
            self.source_edit.setPlaceholderText("Select source directory...")
            self.trans_edit.setPlaceholderText("Select translation directory...")
        else:
            self.source_edit.setPlaceholderText("Select source file...")
            self.trans_edit.setPlaceholderText("Select translation file...")
            
    def _on_auto_create_toggled(self, checked):
        self.trans_edit.setEnabled(not checked)
        self.browse_trans_btn.setEnabled(not checked)
        if checked:
            self.trans_edit.clear()

    def _get_start_dir(self, current_path_text=None):
        if current_path_text and Path(current_path_text).exists():
            return Path(current_path_text).as_posix() if Path(current_path_text).is_dir() else Path(current_path_text).parent.as_posix()
        
        if hasattr(self.parent(), 'last_browse_dir') and self.parent().last_browse_dir:
            return self.parent().last_browse_dir
        return Path.home().as_posix()

    def _update_last_dir(self, path):
        if not path: return
        p = Path(path)
        last_dir = p.as_posix() if p.is_dir() else p.parent.as_posix()
        if hasattr(self.parent(), 'last_browse_dir'):
            self.parent().last_browse_dir = last_dir
            if hasattr(self.parent(), 'settings_manager'):
                self.parent().settings_manager.save_settings()

    def _browse_directory(self):
        """Open directory picker for project location."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Project Location",
            self._get_start_dir(self.dir_edit.text()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if directory:
            self.dir_edit.setText(directory)
            self._update_last_dir(directory)

    def _browse_source(self):
        start_dir = self._get_start_dir(self.source_edit.text())
        if self.radio_folders.isChecked():
            directory = QFileDialog.getExistingDirectory(
                self, "Select Source Directory", start_dir,
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if directory: 
                self.source_edit.setText(directory)
                self._update_last_dir(directory)
        else:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Source File", start_dir,
                "Supported Files (*.txt *.json *.arc *.rarc *.bfn *.bmg);;JSON Files (*.json);;Text Files (*.txt);;ARC Files (*.arc *.rarc);;BFN Files (*.bfn);;BMG Files (*.bmg);;All Files (*)"
            )
            if file_path: 
                self.source_edit.setText(file_path)
                self._update_last_dir(file_path)

    def _browse_translation(self):
        start_dir = self._get_start_dir(self.trans_edit.text())
        if self.radio_folders.isChecked():
            directory = QFileDialog.getExistingDirectory(
                self, "Select Translation Directory", start_dir,
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if directory: 
                self.trans_edit.setText(directory)
                self._update_last_dir(directory)
        else:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Translation File", start_dir,
                "Supported Files (*.txt *.json *.arc *.rarc *.bfn *.bmg);;JSON Files (*.json);;Text Files (*.txt);;ARC Files (*.arc *.rarc);;BFN Files (*.bfn);;BMG Files (*.bmg);;All Files (*)"
            )
            if file_path: 
                self.trans_edit.setText(file_path)
                self._update_last_dir(file_path)

    def _validate_and_accept(self):
        """Validate inputs before accepting."""
        # Validate project name
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Input", "Please enter a project name.")
            self.name_edit.setFocus()
            return

        # Validate directory
        directory = self.dir_edit.text().strip()
        if not directory or not Path(directory).exists():
            QMessageBox.warning(self, "Invalid Location", "Please select a valid location for the project.")
            return

        source_path = self.source_edit.text().strip()
        if not source_path or not Path(source_path).exists():
            QMessageBox.warning(self, "Invalid Source", "Please select a valid source.")
            return
            
        trans_path = self.trans_edit.text().strip()
        if not self.auto_create_cb.isChecked() and (not trans_path or not Path(trans_path).exists()):
            QMessageBox.warning(self, "Invalid Translation", "Please select a valid translation path or enable auto-create.")
            return

        # Validate plugin selection
        plugin = self.plugin_combo.currentData()
        if plugin is None:
            QMessageBox.warning(self, "Invalid Input", "Please select a game plugin for the project.")
            self.plugin_combo.setFocus()
            return

        # Build full project path
        # Sanitize project name for filesystem
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')

        project_path = (Path(directory) / safe_name).as_posix()

        # Check if project already exists
        if Path(project_path).exists():
            reply = QMessageBox.question(
                self,
                "Project Exists",
                f"A folder named '{safe_name}' already exists at this location.\n\n"
                f"Do you want to use this folder anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Store results
        self.project_name = name
        self.project_dir = project_path
        self.plugin_name = self.plugin_combo.currentData()
        self.description = self.description_edit.toPlainText().strip()
        
        self.source_path = source_path
        self.translation_path = trans_path if trans_path else None
        self.is_directory_mode = self.radio_folders.isChecked()
        self.auto_create_translations = self.auto_create_cb.isChecked()

        log_info(f"NewProjectDialog: Creating project '{name}' at {project_path}")
        self.accept()

    def get_project_info(self):
        """
        Get project information after dialog is accepted.

        Returns:
            dict: Project information or None if cancelled
        """
        if self.result() == QDialog.Accepted:
            return {
                'name': self.project_name,
                'directory': self.project_dir,
                'plugin': self.plugin_name,
                'description': self.description,
                'source_path': self.source_path,
                'translation_path': self.translation_path,
                'is_directory_mode': self.is_directory_mode,
                'auto_create_translations': self.auto_create_translations
            }
        return None


class OpenProjectDialog(QDialog):
    """
    Dialog for opening an existing project.

    Currently simple: just pick a .uiproj file or project directory.
    Can be extended with recent projects list.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Project")
        self.setMinimumWidth(500)

        self.project_path = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Instructions
        info_label = QLabel(
            "Select a project file (.uiproj) to open.",
            self
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Path selection
        path_layout = QHBoxLayout()

        self.path_edit = QLineEdit(self)
        self.path_edit.setPlaceholderText("Select project.uiproj file...")
        self.path_edit.setReadOnly(True)
        path_layout.addWidget(self.path_edit)

        browse_file_button = QPushButton("Browse...", self)
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
                "No Project Selected",
                "Please select a .uiproj file."
            )
            return

        if not Path(path).exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The selected file does not exist:\n{path}"
            )
            return

        # Validate it's a .uiproj file
        if not Path(path).is_file():
            QMessageBox.warning(
                self,
                "Invalid Selection",
                "Please select a project file, not a directory."
            )
            return

        if not path.endswith('.uiproj'):
            QMessageBox.warning(
                self,
                "Invalid File",
                "Please select a .uiproj file."
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
        if self.result() == QDialog.Accepted:
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
        super().__init__(parent)
        self.setWindowTitle("Import Block")
        self.setMinimumWidth(500)

        self.project_manager = project_manager
        self.source_file = None
        self.translation_file = None
        self.block_name = None
        self.description = None

        self._setup_ui()

    def _setup_ui(self):
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
        self.file_edit.setPlaceholderText("Select source file to import...")
        self.file_edit.setReadOnly(True)
        self.file_edit.textChanged.connect(self._on_source_file_selected)
        source_layout.addWidget(self.file_edit)

        browse_source_button = QPushButton("Browse...", self)
        browse_source_button.clicked.connect(self._browse_source_file)
        source_layout.addWidget(browse_source_button)

        form_layout.addRow("Source File:", source_layout)

        # Translation file selection
        translation_layout = QHBoxLayout()
        self.translation_edit = QLineEdit(self)
        self.translation_edit.setPlaceholderText("Optional: select existing translation file...")
        self.translation_edit.setReadOnly(True)
        translation_layout.addWidget(self.translation_edit)

        browse_translation_button = QPushButton("Browse...", self)
        browse_translation_button.clicked.connect(self._browse_translation_file)
        translation_layout.addWidget(browse_translation_button)

        form_layout.addRow("Translation File:", translation_layout)

        # Block name
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("Auto-filled from filename")
        form_layout.addRow("Block Name:", self.name_edit)

        # Description
        self.description_edit = QTextEdit(self)
        self.description_edit.setPlaceholderText("Optional: Enter block description...")
        self.description_edit.setMaximumHeight(80)
        form_layout.addRow("Description:", self.description_edit)

        layout.addLayout(form_layout)

        # Info label
        info_label = QLabel(
            "The source file will be copied to the project's 'sources/' directory.\n"
            "If you don't specify a translation file, the source will be copied to 'translation/'.",
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
            "Supported Files (*.txt *.json *.arc *.rarc *.bfn *.bmg);;Text Files (*.txt);;JSON Files (*.json);;ARC Files (*.arc *.rarc);;BFN Files (*.bfn);;BMG Files (*.bmg);;All Files (*)"
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
            "Supported Files (*.txt *.json *.arc *.rarc *.bfn *.bmg);;Text Files (*.txt);;JSON Files (*.json);;ARC Files (*.arc *.rarc);;BFN Files (*.bfn);;BMG Files (*.bmg);;All Files (*)"
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
                "No File Selected",
                "Please select a source file to import."
            )
            return

        if not Path(file_path).exists():
            QMessageBox.warning(
                self,
                "File Not Found",
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
        if self.result() == QDialog.Accepted:
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
        super().__init__(parent)
        self.pm = project_manager
        self.current_folder_id = current_folder_id
        self.selected_folder_id = None
        self.new_folder_created = False
        
        self.setWindowTitle("Move Files to folder")
        self.setMinimumSize(400, 500)
        self._setup_ui()
        self._populate_tree()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        label = QLabel("Select destination folder:")
        layout.addWidget(label)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.tree)
        
        # New Folder Button
        self.btn_new_folder = QPushButton("New Folder")
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
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) == folder_id:
                self.tree.setCurrentItem(item)
                item.setExpanded(True)
                break
            iterator += 1

    def _validate_and_accept(self):
        curr = self.tree.currentItem()
        if curr:
            self.selected_folder_id = curr.data(0, Qt.UserRole)
            self.accept()

    def get_selected_folder_id(self):
        return self.selected_folder_id
