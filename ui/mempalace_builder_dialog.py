import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QFileDialog, QComboBox, QProgressBar, QTextEdit, 
    QMessageBox, QCheckBox, QGroupBox, QToolTip
)
from PyQt5.QtGui import QIcon, QFont, QColor
from PyQt5.QtCore import Qt, pyqtSlot
from core.mempalace_client import MemePalaceClient
from core.mempalace_worker import MemePalaceWorker, MemePalaceScriptAnalyzerWorker
from utils.logging_utils import log_info, log_error

class MemePalaceBuilderDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.setWindowTitle("MemePalace Context Builder")
        self.resize(650, 500)
        self.setMinimumSize(550, 400)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        # Styles & Theme
        self.setStyleSheet("""
            QDialog {
                background-color: #fcfcfc;
            }
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #333333;
            }
            QLineEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 6px;
                font-size: 13px;
                background-color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #0078d7;
            }
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 7px 15px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dddddd;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
            QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }
        """)

        self.worker = None
        self.client = None
        self.bmg_strings = []
        self.bmg_ids = []
        # Remember which block was active when dialog was opened
        self._initial_block_idx = -1
        if hasattr(main_window, 'data_store') and main_window.data_store:
            self._initial_block_idx = main_window.data_store.current_block_idx

        self._setup_ui()
        self.load_builder_settings()
        self._load_bmg_strings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Title / Description
        title_label = QLabel("MemePalace Context Builder")
        title_font = QFont("Segoe UI", 16, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #0078d7; margin-bottom: 2px;")
        layout.addWidget(title_label)

        desc_label = QLabel(
            "Map flat game text lines to a chronological walkthrough timeline (e.g. from YouTube) "
            "and use AI to enrich translation context."
        )
        desc_label.setStyleSheet("color: #666666; font-size: 12px; margin-bottom: 10px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # YouTube Import Group
        yt_group = QGroupBox("Import Transcript from YouTube Link (Optional)")
        yt_layout = QVBoxLayout(yt_group)
        yt_layout.setSpacing(8)

        yt_label = QLabel("Enter YouTube Video Link (will fetch captions automatically):")
        yt_layout.addWidget(yt_label)

        yt_row = QHBoxLayout()
        self.yt_url_edit = QLineEdit()
        self.yt_url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        yt_row.addWidget(self.yt_url_edit)

        self.yt_fetch_btn = QPushButton("Fetch Captions")
        self.yt_fetch_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d7;
                color: white;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.yt_fetch_btn.clicked.connect(self._fetch_youtube_captions)
        yt_row.addWidget(self.yt_fetch_btn)
        yt_layout.addLayout(yt_row)

        layout.addWidget(yt_group)

        # Configuration Group
        config_group = QGroupBox("Weaver Settings")
        config_layout = QVBoxLayout(config_group)
        config_layout.setSpacing(10)

        # Transcript File Selection
        file_label = QLabel("Walkthrough / YouTube Transcript File (.json or .txt):")
        config_layout.addWidget(file_label)
        
        file_row = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select chronological transcript file...")
        file_row.addWidget(self.file_path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 4px;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: #eaeaea;
                border-color: #999999;
            }
        """)
        browse_btn.clicked.connect(self._browse_transcript_file)
        file_row.addWidget(browse_btn)

        self.ai_analyze_btn = QPushButton("Analyze via AI")
        self.ai_analyze_btn.setToolTip("Use active AI provider to extract character profiles and social relations from script introduction.")
        self.ai_analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #5c2d91;
                color: white;
                font-weight: normal;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #4b2475;
            }
            QPushButton:pressed {
                background-color: #3a1b5c;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.ai_analyze_btn.clicked.connect(self._pre_analyze_script_via_ai)
        file_row.addWidget(self.ai_analyze_btn)

        config_layout.addLayout(file_row)

        # Wing Name (Game Name ID)
        wing_row = QHBoxLayout()
        wing_label = QLabel("Wing (Game Code ID):")
        self.wing_edit = QLineEdit("Zelda_TP")
        # Pre-fill with active plugin if possible
        if hasattr(self.mw, "active_game_rules") and self.mw.active_game_rules:
            game_name = self.mw.active_game_rules.get_display_name()
            # clean game_name for ID compatibility
            clean_name = "".join([c if c.isalnum() else "_" for c in game_name]).strip("_")
            self.wing_edit.setText(clean_name)
        
        wing_row.addWidget(wing_label)
        wing_row.addWidget(self.wing_edit)
        config_layout.addLayout(wing_row)

        # Scope Selection
        scope_row = QHBoxLayout()
        scope_label = QLabel("Mapping Scope:")
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["Entire Project (All Selected Files)", "Active File Only"])
        self.scope_combo.currentIndexChanged.connect(self._handle_scope_changed)
        scope_row.addWidget(scope_label)
        scope_row.addWidget(self.scope_combo)
        config_layout.addLayout(scope_row)

        # Project Blocks Selection List
        from PyQt5.QtWidgets import QListWidget, QListWidgetItem
        self.blocks_list_label = QLabel("Select Files/Blocks to Map:")
        config_layout.addWidget(self.blocks_list_label)
        
        self.blocks_list_widget = QListWidget()
        self.blocks_list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #ffffff;
                max-height: 100px;
            }
        """)
        config_layout.addWidget(self.blocks_list_widget)

        # Mode Selection
        self.mapping_only_checkbox = QCheckBox("Timeline Mapping Only (Skip AI Visual Scene Generation)")
        self.mapping_only_checkbox.setToolTip("Saves timeline sequences to local Palace without burning AI tokens.")
        self.mapping_only_checkbox.setChecked(False)
        config_layout.addWidget(self.mapping_only_checkbox)

        layout.addWidget(config_group)

        # Progress Section
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #dddddd;
                border-radius: 4px;
                text-align: center;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Log Window
        log_label = QLabel("Execution Log:")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        # Action Buttons
        btn_row = QHBoxLayout()
        
        self.clear_btn = QPushButton("Clear Database")
        self.clear_btn.setToolTip("Completely clear all mapped context, rooms, and knowledge graph relations from the local database.")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #a80000;
                color: white;
                font-weight: normal;
                border: none;
                border-radius: 4px;
                padding: 7px 15px;
            }
            QPushButton:hover {
                background-color: #800000;
            }
            QPushButton:pressed {
                background-color: #500000;
            }
        """)
        self.clear_btn.clicked.connect(self._clear_database)
        btn_row.addWidget(self.clear_btn)
        
        btn_row.addStretch()

        self.start_btn = QPushButton("Start Builder")
        self.start_btn.clicked.connect(self._start_process)
        btn_row.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("Close")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e1dfdd;
                color: #333333;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d2d0ce;
            }
        """)
        self.cancel_btn.clicked.connect(self._handle_close_or_cancel)
        btn_row.addWidget(self.cancel_btn)

        layout.addLayout(btn_row)

    def _handle_scope_changed(self, index):
        is_entire = (index == 0)
        self.blocks_list_widget.setEnabled(True)
        self.blocks_list_label.setEnabled(True)
        
        from PyQt5.QtCore import Qt
        if not is_entire:
            # Active File Only: check only the block that was active when the dialog opened
            for i in range(self.blocks_list_widget.count()):
                item = self.blocks_list_widget.item(i)
                block_idx = item.data(Qt.UserRole)
                if block_idx == self._initial_block_idx:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
        else:
            # Entire Project (All Selected Files): always check all blocks
            for i in range(self.blocks_list_widget.count()):
                self.blocks_list_widget.item(i).setCheckState(Qt.Checked)

    def _load_bmg_strings(self):
        """Populate the block list and load strings from the active main window workspace data store."""
        from PyQt5.QtWidgets import QListWidgetItem
        from PyQt5.QtCore import Qt
        
        try:
            if not hasattr(self.mw, "data_store") or not self.mw.data_store:
                return
            
            store = self.mw.data_store
            self.blocks_list_widget.clear()

            if not store.data or len(store.data) == 0:
                self.append_log("WARNING: No loaded string block found in project. Please open a project or file first.")
                self.start_btn.setEnabled(False)
                return

            # Get saved blocks selection if exists
            pm = getattr(self.mw, 'project_manager', None)
            project = pm.project if pm else None
            selected_blocks = []
            if project:
                selected_blocks = project.metadata.get("mempalace_selected_blocks", [])
            else:
                sm = getattr(self.mw, 'settings_manager', None)
                if sm:
                    selected_blocks = sm.get("mempalace_selected_blocks", [])
            
            if not isinstance(selected_blocks, list):
                selected_blocks = []

            # Populate QListWidget with project blocks
            for idx in range(len(store.data)):
                # Get clean name
                name_key = str(idx)
                block_name = ""
                if hasattr(self.mw, 'project_manager') and self.mw.project_manager and \
                   self.mw.project_manager.project and idx < len(self.mw.project_manager.project.blocks):
                    block_name = self.mw.project_manager.project.blocks[idx].name
                else:
                    block_name = f"Block_{idx}"
                    if store.block_names and name_key in store.block_names:
                        # Extract BMG ID description
                        b_desc = store.block_names[name_key]
                        if "Message ID" in b_desc:
                            block_name = b_desc.partition("(")[0].strip()

                item = QListWidgetItem(f"{block_name} (Idx {idx})")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                
                # Check blocks based on saved selection if present
                if selected_blocks:
                    if idx in selected_blocks or str(idx) in selected_blocks or block_name in selected_blocks:
                        item.setCheckState(Qt.Checked)
                    else:
                        item.setCheckState(Qt.Unchecked)
                else:
                    # Check active block by default, others checked if entire project is selected
                    if idx == store.current_block_idx or store.current_block_idx == -1:
                        item.setCheckState(Qt.Checked)
                    else:
                        item.setCheckState(Qt.Checked) # Check all by default for full mapping
                    
                item.setData(Qt.UserRole, idx) # Keep block index
                self.blocks_list_widget.addItem(item)

            self._handle_scope_changed(self.scope_combo.currentIndex())
            self.append_log(f"Loaded {len(store.data)} files/blocks from current workspace.")
            
        except Exception as e:
            self.append_log(f"Error loading project workspace blocks: {e}")

    def _gather_selected_strings_data(self):
        """Gather all strings from selected blocks in QListWidget and track translation states."""
        from PyQt5.QtCore import Qt
        
        self.bmg_strings = []
        self.bmg_ids = []
        self.bmg_block_names = []
        self.bmg_translation_states = [] # Track if string is already translated
        
        store = self.mw.data_store
        is_entire = (self.scope_combo.currentIndex() == 0)
        
        for i in range(self.blocks_list_widget.count()):
            item = self.blocks_list_widget.item(i)
            block_idx = item.data(Qt.UserRole)
            
            # If active file only, skip if not active block
            if not is_entire and block_idx != store.current_block_idx:
                continue
                
            # If entire, skip if unchecked
            if is_entire and item.checkState() != Qt.Checked:
                continue
                
            # Gather strings from this block (store.data contains original English strings)
            block_strings = store.data[block_idx]
            block_label = item.text().partition("(")[0].strip()
            
            for s_idx, text in enumerate(block_strings):
                # Ignore empty or whitespace-only lines to keep MemePalace clean and save AI tokens
                if not text or not str(text).strip():
                    continue
                
                self.bmg_strings.append(text)
                
                # Build representation ID
                bmg_id = f"{block_label}_Str_{s_idx}"
                self.bmg_ids.append(bmg_id)
                self.bmg_block_names.append(block_label)
                
                # Check if already translated in edited_data
                is_trans = False
                if (block_idx, s_idx) in store.edited_data:
                    is_trans = bool(store.edited_data[(block_idx, s_idx)].strip())
                self.bmg_translation_states.append(is_trans)
                
        self.append_log(f"Gathered total of {len(self.bmg_strings)} strings from selected blocks to weave.")

    @pyqtSlot()
    def _browse_transcript_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Walkthrough Transcript File", "", "Transcript Files (*.json *.txt);;All Files (*)"
        )
        if path:
            self.file_path_edit.setText(path)
            self.append_log(f"Selected file: {os.path.basename(path)}")

    def append_log(self, text: str):
        self.log_text.append(text)
        # Scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @pyqtSlot()
    def _start_process(self):
        # Save current builder settings on start
        self.save_builder_settings()
        
        # Gather data dynamically from checkboxes
        self._gather_selected_strings_data()

        # 1. Validate path
        file_path = self.file_path_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Validation Error", "Please select a valid walkthrough transcript file.")
            return

        # 2. Check if strings exist
        if not self.bmg_strings:
            QMessageBox.warning(self, "Validation Error", "No selected blocks/strings found in workspace to weave.")
            return

        # 3. Parse transcript data
        self.append_log("Parsing transcript file...")
        try:
            transcript_list = []
            rules = getattr(self.mw, "current_game_rules", None)
            if rules and hasattr(rules, "parse_walkthrough_transcript"):
                transcript_list = rules.parse_walkthrough_transcript(file_path)
            else:
                from plugins.base_game_rules import BaseGameRules
                fallback = BaseGameRules(main_window_ref=self.mw)
                transcript_list = fallback.parse_walkthrough_transcript(file_path)

            if not transcript_list:
                QMessageBox.warning(self, "Parse Error", "Transcript file contains no valid timeline entries.")
                return
            
            self.append_log(f"Successfully loaded and structured {len(transcript_list)} dialogue cues into Rooms.")
            
        except Exception as e:
            QMessageBox.critical(self, "Parse Error", f"Failed to parse transcript: {str(e)}")
            return

        # 4. Initialize Client & Worker
        project_dir = self.mw.project_manager.project_dir if (hasattr(self.mw, "project_manager") and self.mw.project_manager) else None
        if not project_dir:
            project_dir = os.path.dirname(self.mw.data_store.project_file) if (hasattr(self.mw, "data_store") and self.mw.data_store and getattr(self.mw.data_store, "project_file", None)) else os.getcwd()

        self.client = MemePalaceClient(project_dir=project_dir)
        
        # Get active translation provider configured in the main window
        ai_provider = None
        if hasattr(self.mw, "translation_handler") and self.mw.translation_handler:
            try:
                ai_provider = self.mw.translation_handler._prepare_provider()
                if ai_provider:
                    self.append_log(f"Successfully loaded configured AI Provider: {ai_provider.__class__.__name__}")
            except Exception as provider_err:
                log_error(f"Failed to prepare AI provider: {provider_err}")
                self.append_log(f"WARNING: Failed to initialize active AI Provider: {provider_err}")

        wing_name = self.wing_edit.text().strip()
        mapping_only = self.mapping_only_checkbox.isChecked()

        # Resolve target language dynamically
        lang_code = getattr(self.mw, 'spellchecker_language', 'uk')
        target_lang = "Ukrainian"
        if lang_code == 'uk':
            target_lang = "Ukrainian"
        elif lang_code == 'ru':
            target_lang = "Russian"
        elif lang_code == 'en':
            target_lang = "English"

        # Resolve active glossary entries dynamically
        glossary_entries = []
        gm = getattr(self.mw, 'glossary_manager', None)
        if not gm:
            gm = getattr(self.mw, '_glossary_manager', None)
        if not gm and hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            gm = getattr(self.mw.translation_handler, '_glossary_manager', None)
            if not gm:
                gh = getattr(self.mw.translation_handler, 'glossary_handler', None)
                if gh:
                    gm = getattr(gh, 'glossary_manager', None)
        if gm and hasattr(gm, 'get_entries'):
            glossary_entries = list(gm.get_entries())

        self.append_log(f"Configured target language for AI annotations: {target_lang}")
        if glossary_entries:
            self.append_log(f"Injected {len(glossary_entries)} glossary terms for character name consistency.")

        # Start QThread Worker
        self.worker = MemePalaceWorker(
            client=self.client,
            bmg_strings=self.bmg_strings,
            bmg_ids=self.bmg_ids,
            transcript_data=transcript_list,
            ai_provider=ai_provider,
            wing_name=wing_name,
            mapping_only=mapping_only,
            bmg_translation_states=self.bmg_translation_states,
            target_lang=target_lang,
            glossary_manager=gm,
            glossary_entries=glossary_entries
        )

        self.worker.progress.connect(self._handle_worker_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self._handle_worker_finished)

        # UI Adjustments during running
        self.start_btn.setEnabled(False)
        self.cancel_btn.setText("Cancel Process")
        self.file_path_edit.setEnabled(False)
        self.wing_edit.setEnabled(False)
        self.mapping_only_checkbox.setEnabled(False)

        self.worker.start()

    def _handle_worker_progress(self, current, total, text):
        self.progress_bar.setValue(int((current / total) * 100))
        self.append_log(f"[{current}/{total}] {text}")

    def _handle_worker_finished(self, success, message):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setText("Close")
        self.file_path_edit.setEnabled(True)
        self.wing_edit.setEnabled(True)
        self.mapping_only_checkbox.setEnabled(True)

        if success:
            QMessageBox.information(self, "MemePalace Builder Status", f"Success!\n\n{message}")
            self.append_log("BUILD SUCCESSFUL!")
        else:
            QMessageBox.warning(self, "MemePalace Builder Status", f"Failed!\n\n{message}")
            self.append_log("BUILD FAILED OR CANCELLED.")

        self.worker = None

    @pyqtSlot()
    def _clear_database(self):
        reply = QMessageBox.question(
            self, "Clear Database", 
            "Are you sure you want to completely clear the local MemePalace database for this game?\n\n"
            "This will erase all mapped contexts, room structures, dialogue timeline mappings, and character relations.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.append_log("Initializing client to clear database...")
        try:
            # Re-initialize client if needed to get correct DB path
            project_dir = self.mw.project_manager.project_dir if (hasattr(self.mw, "project_manager") and self.mw.project_manager) else None
            if not project_dir:
                project_dir = os.path.dirname(self.mw.data_store.project_file) if (hasattr(self.mw, "data_store") and self.mw.data_store and getattr(self.mw.data_store, "project_file", None)) else os.getcwd()

            # Recursively look upwards if it's single-file mode without active project folder
            # to match client fallback search behavior in Story Context Inspector
            if project_dir:
                db_name = "mempalace_local.db"
                # Search up to 4 directory levels to locate the existing DB if any
                curr = project_dir
                found_db_path = None
                for _ in range(4):
                    # Check inside "TwilightPrincess" subdirectory if it exists
                    tp_subdir = os.path.join(curr, "TwilightPrincess")
                    if os.path.isdir(tp_subdir) and os.path.exists(os.path.join(tp_subdir, db_name)):
                        found_db_path = os.path.join(tp_subdir, db_name)
                        project_dir = tp_subdir
                        break
                    if os.path.exists(os.path.join(curr, db_name)):
                        found_db_path = os.path.join(curr, db_name)
                        project_dir = curr
                        break
                    parent = os.path.dirname(curr)
                    if parent == curr:
                        break
                    curr = parent

            client = MemePalaceClient(project_dir=project_dir)
            if client.clear_all_local_data():
                self.append_log(f"SUCCESS: Local MemePalace database at '{client.db_path}' has been completely cleared!")
                QMessageBox.information(
                    self, "Clear Database", 
                    "The local MemePalace database has been successfully cleared.\n\n"
                    "All stored contexts and relations are wiped."
                )
            else:
                self.append_log("ERROR: Failed to clear the database. Check if the database file is write-accessible.")
                QMessageBox.warning(self, "Clear Database Error", "Failed to clear the database. Please see log for details.")
        except Exception as e:
            log_error(f"Error clearing database: {e}")
            self.append_log(f"ERROR: {str(e)}")
            QMessageBox.critical(self, "Clear Database Error", f"An unexpected error occurred:\n\n{str(e)}")

    @pyqtSlot()
    def _pre_analyze_script_via_ai(self):
        # 1. Validate file path
        file_path = self.file_path_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Validation Error", "Please select a valid walkthrough transcript / game script file first.")
            return

        # 2. Get active AI Provider
        ai_provider = None
        if hasattr(self.mw, "translation_handler") and self.mw.translation_handler:
            try:
                ai_provider = self.mw.translation_handler._prepare_provider()
            except Exception as e:
                log_error(f"Failed to prepare AI provider: {e}")
                
        if not ai_provider:
            QMessageBox.warning(
                self, "AI Provider Error", 
                "No active AI Provider configured.\n\n"
                "Please configure your API keys and translation provider in settings first."
            )
            return

        self.append_log("Starting pre-analysis of the script introduction via AI...")
        
        # 3. Setup client with proper folder logic
        project_dir = self.mw.project_manager.project_dir if (hasattr(self.mw, "project_manager") and self.mw.project_manager) else None
        if not project_dir:
            project_dir = os.path.dirname(self.mw.data_store.project_file) if (hasattr(self.mw, "data_store") and self.mw.data_store and getattr(self.mw.data_store, "project_file", None)) else os.getcwd()

        if project_dir:
            db_name = "mempalace_local.db"
            curr = project_dir
            for _ in range(4):
                tp_subdir = os.path.join(curr, "TwilightPrincess")
                if os.path.isdir(tp_subdir) and os.path.exists(os.path.join(tp_subdir, db_name)):
                    project_dir = tp_subdir
                    break
                if os.path.exists(os.path.join(curr, db_name)):
                    project_dir = curr
                    break
                parent = os.path.dirname(curr)
                if parent == curr:
                    break
                curr = parent

        client = MemePalaceClient(project_dir=project_dir)
        wing_name = self.wing_edit.text().strip()

        # Disable UI buttons during running
        self.ai_analyze_btn.setEnabled(False)
        self.ai_analyze_btn.setText("Analyzing...")
        self.start_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.file_path_edit.setEnabled(False)

        # Resolve active glossary entries dynamically
        gm = getattr(self.mw, 'glossary_manager', None)
        if not gm:
            gm = getattr(self.mw, '_glossary_manager', None)
        if not gm and hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            gm = getattr(self.mw.translation_handler, '_glossary_manager', None)
            if not gm:
                gh = getattr(self.mw.translation_handler, 'glossary_handler', None)
                if gh:
                    gm = getattr(gh, 'glossary_manager', None)

        # Resolve target language dynamically based on spellchecker language
        lang_code = getattr(self.mw, 'spellchecker_language', 'uk')
        target_lang = "Ukrainian"
        if lang_code == 'uk':
            target_lang = "Ukrainian"
        elif lang_code == 'ru':
            target_lang = "Russian"
        elif lang_code == 'en':
            target_lang = "English"

        plugin_name = getattr(self.mw, "active_game_plugin", None)

        # 4. Initialize and run Analyzer Worker
        self.analyzer_worker = MemePalaceScriptAnalyzerWorker(
            client=client,
            file_path=file_path,
            ai_provider=ai_provider,
            wing_name=wing_name,
            glossary_manager=gm,
            target_lang=target_lang,
            plugin_name=plugin_name
        )

        self.analyzer_worker.progress.connect(self._handle_worker_progress)
        self.analyzer_worker.log.connect(self.append_log)
        self.analyzer_worker.finished.connect(self._handle_analyzer_finished)

        self.analyzer_worker.start()

    def _handle_analyzer_finished(self, success, message):
        self.ai_analyze_btn.setEnabled(True)
        self.ai_analyze_btn.setText("Analyze via AI")
        self.start_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.file_path_edit.setEnabled(True)

        if success:
            # Refresh glossary manager, highlighting and AI prompts cache in the editors!
            try:
                gh = None
                if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                    gh = getattr(self.mw.translation_handler, 'glossary_handler', None)
                if gh:
                    gh.glossary_manager.refresh_from_disk()
                    gh._update_glossary_highlighting()
                    gh.main_handler._cached_glossary = gh.glossary_manager.get_raw_text()
                    log_info("Successfully reloaded and refreshed glossary highlighting in editors after AI Script pre-analysis.")
            except Exception as ref_err:
                log_error(f"Failed to refresh glossary highlighting after AI analysis: {ref_err}")

            QMessageBox.information(self, "AI Script Analyzer Status", f"Pre-analysis complete!\n\n{message}")
            self.append_log("AI SCRIPT PRE-ANALYSIS SUCCESSFUL!")
        else:
            QMessageBox.warning(self, "AI Script Analyzer Status", f"Failed!\n\n{message}")
            self.append_log("AI SCRIPT PRE-ANALYSIS FAILED OR CANCELLED.")

        self.analyzer_worker = None

    @pyqtSlot()
    def _fetch_youtube_captions(self):
        url = self.yt_url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "YouTube Link Error", "Please enter a valid YouTube video link.")
            return

        import re
        # Extract video_id
        pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
        match = re.search(pattern, url)
        if not match:
            QMessageBox.warning(self, "YouTube Link Error", "Could not extract Video ID from the provided link.")
            return

        video_id = match.group(1)
        self.append_log(f"Extracted YouTube Video ID: {video_id}")
        self.append_log("Fetching subtitles... (Installing dependency 'youtube-transcript-api' if missing, please wait)")

        self.yt_fetch_btn.setEnabled(False)
        self.yt_fetch_btn.setText("Fetching...")

        # We do this in a light processEvents loop to not freeze UI
        from PyQt5.QtCore import QCoreApplication
        QCoreApplication.processEvents()

        try:
            # Try loading or installing dependency dynamically
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
            except ImportError:
                self.append_log("Installing 'youtube-transcript-api' package dynamically via pip...")
                QCoreApplication.processEvents()
                import subprocess
                import sys
                # Run pip install quietly
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "youtube-transcript-api"])
                from youtube_transcript_api import YouTubeTranscriptApi
                self.append_log("Dependency installed successfully!")

            # Fetch transcript (prefer English or auto-generated English)
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US'])
            self.append_log(f"Successfully fetched {len(transcript_list)} caption cues from YouTube.")

            # Format to our format: {"text", "speaker", "timestamp"}
            formatted_list = []
            for item in transcript_list:
                seconds = item.get("start", 0)
                mins = int(seconds // 60)
                secs = int(seconds % 60)
                timestamp = f"{mins:02d}:{secs:02d}"
                formatted_list.append({
                    "text": item.get("text", ""),
                    "speaker": "AutoCaptions",
                    "timestamp": timestamp
                })

            # Save as JSON inside the project/app folder
            project_dir = self.mw.project_manager.project_dir if (hasattr(self.mw, "project_manager") and self.mw.project_manager) else os.getcwd()
            save_name = f"yt_transcript_{video_id}.json"
            save_path = os.path.join(project_dir, save_name)

            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(formatted_list, f, ensure_ascii=False, indent=2)

            self.file_path_edit.setText(save_path)
            self.append_log(f"Chronological transcript saved locally to:\n{save_path}")
            QMessageBox.information(
                self, "YouTube Import Status", 
                f"Successfully imported {len(formatted_list)} captions from YouTube!\n\n"
                "The file path has been set in Weaver Settings. You can now start the builder."
            )

        except Exception as e:
            log_error(f"Failed to fetch YouTube captions: {e}")
            self.append_log(f"ERROR fetching captions: {str(e)}")
            QMessageBox.critical(
                self, "YouTube Import Error", 
                f"Failed to fetch subtitles from YouTube.\n\n"
                "Details: Make sure the video actually has subtitles (auto-generated or manual) and your internet connection is active."
            )
        finally:
            self.yt_fetch_btn.setEnabled(True)
            self.yt_fetch_btn.setText("Fetch Captions")

    def _handle_close_or_cancel(self):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Cancel Process", 
                "Are you sure you want to stop the context weaving process?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.cancel()
        else:
            self.close()

    def load_builder_settings(self):
        """Load MemePalace Builder settings from project metadata or global settings."""
        pm = getattr(self.mw, 'project_manager', None)
        project = pm.project if pm else None
        
        file_path = ""
        wing_name = ""
        scope_idx = 0
        mapping_only = False
        
        if project:
            file_path = project.metadata.get("mempalace_file_path", "")
            wing_name = project.metadata.get("mempalace_wing_name", "")
            scope_idx = project.metadata.get("mempalace_mapping_scope", 0)
            mapping_only = project.metadata.get("mempalace_mapping_only", False)
        else:
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
                file_path = sm.get("mempalace_file_path", "")
                wing_name = sm.get("mempalace_wing_name", "")
                scope_idx = sm.get("mempalace_mapping_scope", 0)
                mapping_only = sm.get("mempalace_mapping_only", False)
                
        if file_path and isinstance(file_path, str):
            self.file_path_edit.setText(file_path)
        if wing_name and isinstance(wing_name, str):
            self.wing_edit.setText(wing_name)
        if isinstance(scope_idx, int) and not isinstance(scope_idx, bool):
            self.scope_combo.setCurrentIndex(scope_idx)
        if isinstance(mapping_only, bool):
            self.mapping_only_checkbox.setChecked(mapping_only)

        # Restore window size if saved
        width = 650
        height = 500
        if project:
            width = project.metadata.get("mempalace_builder_width", 650)
            height = project.metadata.get("mempalace_builder_height", 500)
        else:
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
                width = sm.get("mempalace_builder_width", 650)
                height = sm.get("mempalace_builder_height", 500)
        
        if isinstance(width, int) and isinstance(height, int):
            self.resize(width, height)

    def save_builder_settings(self):
        """Save current MemePalace Builder settings to project metadata or global settings."""
        pm = getattr(self.mw, 'project_manager', None)
        project = pm.project if pm else None
        
        file_path = self.file_path_edit.text().strip()
        wing_name = self.wing_edit.text().strip()
        scope_idx = self.scope_combo.currentIndex()
        mapping_only = self.mapping_only_checkbox.isChecked()
        
        selected_blocks = []
        for i in range(self.blocks_list_widget.count()):
            item = self.blocks_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                block_idx = item.data(Qt.UserRole)
                selected_blocks.append(block_idx)
                
        width = self.width()
        height = self.height()
        if project:
            project.metadata["mempalace_file_path"] = file_path
            project.metadata["mempalace_wing_name"] = wing_name
            project.metadata["mempalace_mapping_scope"] = scope_idx
            project.metadata["mempalace_mapping_only"] = mapping_only
            project.metadata["mempalace_selected_blocks"] = selected_blocks
            project.metadata["mempalace_builder_width"] = width
            project.metadata["mempalace_builder_height"] = height
            try:
                self.mw.project_manager.save()
            except Exception as e:
                log_error(f"Failed to save project metadata: {e}")
        else:
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
                sm.set("mempalace_file_path", file_path)
                sm.set("mempalace_wing_name", wing_name)
                sm.set("mempalace_mapping_scope", scope_idx)
                sm.set("mempalace_mapping_only", mapping_only)
                sm.set("mempalace_selected_blocks", selected_blocks)
                sm.set("mempalace_builder_width", width)
                sm.set("mempalace_builder_height", height)
                try:
                    sm.save_settings()
                except Exception as e:
                    log_error(f"Failed to save global settings: {e}")

    def closeEvent(self, event):
        """Automatically save settings and clear reference in main window when closed."""
        self.save_builder_settings()
        if hasattr(self.mw, 'mempalace_builder_dialog'):
            self.mw.mempalace_builder_dialog = None
        super().closeEvent(event)
