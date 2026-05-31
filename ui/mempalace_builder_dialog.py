import os
import json
import sqlite3
import ctypes
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QFileDialog, QProgressBar, QTextEdit, 
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QSplitter, QWidget
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, pyqtSlot

from core.mempalace_client import MemePalaceClient
from core.mempalace_worker import (
    MemePalaceScriptAnalyzerWorker, MemePalaceChapterMapperWorker, 
    MemePalaceChapterAIAnalyzerWorker, MemePalaceCharacterProfilerWorker
)
from utils.logging_utils import log_info, log_error

def prevent_sleep():
    if os.name == 'nt':
        try:
            # ES_CONTINUOUS = 0x80000000, ES_SYSTEM_REQUIRED = 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
            log_info("System sleep prevention activated.")
        except Exception as e:
            log_error(f"Failed to set sleep prevention: {e}")

def restore_sleep():
    if os.name == 'nt':
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            log_info("System sleep prevention deactivated.")
        except Exception as e:
            log_error(f"Failed to restore sleep state: {e}")

def put_to_sleep():
    if os.name == 'nt':
        try:
            # SetSuspendState(False, True, False) -> sleep
            ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
            log_info("System suspended successfully.")
        except Exception as e:
            log_error(f"Failed to suspend system: {e}")
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

class MemePalaceBuilderDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.setWindowTitle("MemePalace Context Builder")
        self.resize(750, 600)
        self.setMinimumSize(650, 500)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        self.worker = None
        self.client = None
        self.composer = None
        self.analysis_queue = []
        self.analysis_total_count = 0
        self.analysis_completed_count = 0
        self.current_analysis_idx = -1
        self.user_cancelled = False
        self.should_sleep_after = False
        self.pipeline_running = False
        self.pipeline_step = 0
        self.saved_pipeline_running = False
        self.saved_pipeline_step = 0
        self.saved_pipeline_wing = ""
        self.saved_pipeline_script = ""

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
                color: #333333;
            }
            QLineEdit:focus {
                border: 1px solid #0078d7;
            }
            QLineEdit:disabled {
                background-color: #f3f3f3;
                color: #a19f9d;
                border: 1px solid #e1dfdd;
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
            QTableWidget {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }
            QTableWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
            QHeaderView::section {
                background-color: #f3f3f3;
                border: 1px solid #cccccc;
                padding: 4px;
                font-weight: bold;
            }
            QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }
            QSplitter::handle {
                background-color: #e1dfdd;
            }
            QSplitter::handle:vertical {
                height: 5px;
            }
            QSplitter::handle:hover {
                background-color: #0078d7;
            }
        """)

        self._init_composer_and_client()
        self._setup_ui()
        self.load_builder_settings()
        
        # Auto-fill script path if empty
        if not self.file_path_edit.text().strip():
            script_path = self.composer._find_script_path() if self.composer else None
            if isinstance(script_path, str) and script_path:
                self.file_path_edit.setText(script_path)
                self.append_log(f"Auto-discovered game script file: {os.path.basename(script_path)}")
                
        self.refresh_chapters_list()

    def _init_composer_and_client(self):
        """Prepare local DB client and script composer."""
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

        self.client = MemePalaceClient(project_dir=project_dir)

        if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            self.composer = getattr(self.mw.translation_handler, 'prompt_composer', None)
        if not self.composer:
            from handlers.translation.ai_prompt_composer import AIPromptComposer
            class DummyHandler:
                def __init__(self, mw):
                    self.mw = mw
                    self.data_processor = mw.data_processor
                    self.ui_updater = mw.ui_updater
                    self._glossary_manager = None
                    if hasattr(mw, 'translation_handler') and mw.translation_handler:
                        self._glossary_manager = getattr(mw.translation_handler, '_glossary_manager', None)
                def __getattr__(self, name):
                    return getattr(self.mw, name)
            self.composer = AIPromptComposer(DummyHandler(self.mw))

    def _save_pipeline_state(self):
        """Persist current pipeline session variables into global settings."""
        try:
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
                sm.set("mempalace_pipeline_running", self.pipeline_running)
                sm.set("mempalace_pipeline_step", self.pipeline_step)
                sm.set("mempalace_pipeline_wing", self.wing_edit.text().strip())
                sm.set("mempalace_pipeline_script", self.file_path_edit.text().strip())
                sm.save_settings()
                
                # Keep local variables in sync
                self.saved_pipeline_running = self.pipeline_running
                self.saved_pipeline_step = self.pipeline_step
                self.saved_pipeline_wing = self.wing_edit.text().strip()
                self.saved_pipeline_script = self.file_path_edit.text().strip()
        except Exception as e:
            log_error(f"Failed to save pipeline state: {e}")

    def _update_pipeline_btn_text(self):
        """Update Complete Pipeline button label based on saved session state."""
        has_saved = getattr(self, "saved_pipeline_running", False) and getattr(self, "saved_pipeline_step", 0) > 0
        if has_saved:
            step = self.saved_pipeline_step
            self.pipeline_btn.setText(f"Continue Pipeline (Step {step}/4)")
            self.pipeline_btn.setToolTip(f"Continue incomplete pipeline session from Step {step} or start a new one.")
        else:
            self.pipeline_btn.setText("Start Complete Pipeline")
            self.pipeline_btn.setToolTip("Sequentially execute all MemePalace steps step-by-step automatically.")

    def _setup_ui(self):
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Upper Container QWidget
        upper_widget = QWidget()
        upper_layout = QVBoxLayout(upper_widget)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(10)

        # Title
        title_label = QLabel("MemePalace Context Builder")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setStyleSheet("color: #0078d7; margin-bottom: 2px;")
        upper_layout.addWidget(title_label)

        desc_label = QLabel(
            "Extract characters and terms from script introduction, map BMG translation strings, "
            "and generate AI Chapter summaries to enrich translation models."
        )
        desc_label.setStyleSheet("color: #666666; font-size: 12px; margin-bottom: 5px;")
        desc_label.setWordWrap(True)
        upper_layout.addWidget(desc_label)

        # Configuration Row
        config_layout = QHBoxLayout()
        config_layout.setSpacing(8)

        file_label = QLabel("Game Script File (.txt):")
        config_layout.addWidget(file_label)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Path to zelda_tp_script.txt...")
        config_layout.addWidget(self.file_path_edit)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f3f3;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 4px;
                font-weight: normal;
                padding: 5px 12px;
            }
            QPushButton:hover {
                background-color: #eaeaea;
            }
            QPushButton:disabled {
                background-color: #f3f3f3;
                color: #a19f9d;
                border: 1px solid #e1dfdd;
            }
        """)
        self.browse_btn.clicked.connect(self._browse_script_file)
        config_layout.addWidget(self.browse_btn)

        self.wing_edit = QLineEdit("Zelda_TP")
        self.wing_edit.setMaximumWidth(120)
        if hasattr(self.mw, "active_game_rules") and self.mw.active_game_rules:
            game_name = self.mw.active_game_rules.get_display_name()
            clean_name = "".join([c if c.isalnum() else "_" for c in game_name]).strip("_")
            self.wing_edit.setText(clean_name)
        config_layout.addWidget(QLabel("Wing:"))
        config_layout.addWidget(self.wing_edit)

        upper_layout.addLayout(config_layout)

        # Character mining row
        char_mine_layout = QHBoxLayout()
        char_mine_layout.addWidget(QLabel("<b>Character Profiling:</b>"))
        
        self.ai_analyze_btn = QPushButton("Mine Characters & Terms via AI")
        self.ai_analyze_btn.setToolTip("Extract character profiles and relationship rules from script intro via AI.")
        self.ai_analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #5c2d91;
                color: white;
                font-weight: bold;
                padding: 6px 15px;
            }
            QPushButton:hover {
                background-color: #4b2475;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.ai_analyze_btn.clicked.connect(self._pre_analyze_script_via_ai)
        char_mine_layout.addWidget(self.ai_analyze_btn)

        self.ai_profile_speech_btn = QPushButton("AI Profile Characters Speech")
        self.ai_profile_speech_btn.setToolTip("Analyze character speeches from mapped dialogue database using AI.")
        self.ai_profile_speech_btn.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: white;
                font-weight: bold;
                padding: 6px 15px;
            }
            QPushButton:hover {
                background-color: #7c3aed;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.ai_profile_speech_btn.clicked.connect(self._profile_characters_speech_via_ai)
        char_mine_layout.addWidget(self.ai_profile_speech_btn)

        char_mine_layout.addStretch()
        upper_layout.addLayout(char_mine_layout)

        # Chapters section title
        upper_layout.addWidget(QLabel("<b>Script Chapters & Bidirectional Mapping:</b>"))

        # Table for chapters list
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Chapter", "Title", "Lines range", "Mapped lines", "AI Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setMinimumHeight(150)
        upper_layout.addWidget(self.table)

        # Chapter Action Row
        ch_action_row = QHBoxLayout()
        
        self.map_chapters_btn = QPushButton("Map BMG to Script")
        self.map_chapters_btn.setToolTip("Segment script file and map project dialogue lines to script chapters.")
        self.map_chapters_btn.clicked.connect(self._start_chapters_mapping)
        ch_action_row.addWidget(self.map_chapters_btn)

        self.analyze_chapter_btn = QPushButton("AI Analyze Selected Chapters")
        self.analyze_chapter_btn.setStyleSheet("""
            QPushButton {
                background-color: #5c2d91;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 7px 15px;
            }
            QPushButton:hover {
                background-color: #4b2475;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.analyze_chapter_btn.clicked.connect(self._analyze_selected_chapter)
        ch_action_row.addWidget(self.analyze_chapter_btn)

        self.analyze_all_chapters_btn = QPushButton("AI Analyze All Chapters")
        self.analyze_all_chapters_btn.setStyleSheet("""
            QPushButton {
                background-color: #5c2d91;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 7px 15px;
            }
            QPushButton:hover {
                background-color: #4b2475;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.analyze_all_chapters_btn.clicked.connect(self._analyze_all_chapters)
        ch_action_row.addWidget(self.analyze_all_chapters_btn)
        
        ch_action_row.addStretch()
        upper_layout.addLayout(ch_action_row)

        # Sleep options
        sleep_layout = QHBoxLayout()
        self.prevent_sleep_checkbox = QCheckBox("Prevent computer sleep during analysis")
        self.prevent_sleep_checkbox.setToolTip("Keep the computer awake while AI analysis is running.")
        self.prevent_sleep_checkbox.setChecked(True)
        self.prevent_sleep_checkbox.toggled.connect(self._handle_prevent_sleep_toggled)
        
        self.sleep_after_checkbox = QCheckBox("Put computer to sleep when finished")
        self.sleep_after_checkbox.setToolTip("Suspend/Sleep the computer automatically after all tasks complete.")
        self.sleep_after_checkbox.setChecked(False)
        self.sleep_after_checkbox.toggled.connect(self._handle_sleep_after_toggled)
        
        sleep_layout.addWidget(self.prevent_sleep_checkbox)
        sleep_layout.addWidget(self.sleep_after_checkbox)
        sleep_layout.addStretch()
        upper_layout.addLayout(sleep_layout)

        # Progress Bar
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
        upper_layout.addWidget(self.progress_bar)

        # Lower Container QWidget
        lower_widget = QWidget()
        lower_layout = QVBoxLayout(lower_widget)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(5)

        # Log Window
        lower_layout.addWidget(QLabel("Execution Log:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(60)
        lower_layout.addWidget(self.log_text)

        # QSplitter
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(upper_widget)
        self.splitter.addWidget(lower_widget)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([430, 110])
        layout.addWidget(self.splitter)

        # Bottom Buttons
        btn_row = QHBoxLayout()
        
        self.clear_btn = QPushButton("Clear Database")
        self.clear_btn.setToolTip("Completely clear all mapped context, rooms, chapters, and relations from local DB.")
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
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.clear_btn.clicked.connect(self._clear_database)
        btn_row.addWidget(self.clear_btn)
        
        self.pipeline_btn = QPushButton("Start Complete Pipeline")
        self.pipeline_btn.setToolTip("Sequentially execute all MemePalace steps step-by-step automatically.")
        self.pipeline_btn.setStyleSheet("""
            QPushButton {
                background-color: #107c41;
                color: white;
                font-weight: bold;
                padding: 7px 20px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0b5930;
            }
            QPushButton:pressed {
                background-color: #083d21;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.pipeline_btn.clicked.connect(self._start_complete_pipeline)
        btn_row.addWidget(self.pipeline_btn)

        btn_row.addStretch()

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

    def _maybe_prevent_sleep(self):
        if self.prevent_sleep_checkbox.isChecked():
            prevent_sleep()

    def _finish_and_maybe_sleep(self):
        restore_sleep()
        if self.sleep_after_checkbox.isChecked() and not getattr(self, "user_cancelled", False):
            self.append_log("[System] All tasks completed! Suspending system in 5 seconds...")
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(5000, put_to_sleep)

    def _handle_prevent_sleep_toggled(self, checked: bool):
        # Save settings immediately
        self.save_builder_settings()
        
        # If execution is currently active (worker is running), apply sleep state change immediately!
        if self.worker and self.worker.isRunning():
            if checked:
                prevent_sleep()
                self.append_log("[System] Sleep prevention activated dynamically during execution.")
            else:
                restore_sleep()
                self.append_log("[System] Sleep prevention deactivated dynamically during execution.")

    def _handle_sleep_after_toggled(self, checked: bool):
        # Save settings immediately
        self.save_builder_settings()
        if self.worker and self.worker.isRunning():
            if checked:
                self.append_log("[System] Scheduled computer sleep upon task completion.")
            else:
                self.append_log("[System] Cancelled scheduled computer sleep upon task completion.")

    def refresh_chapters_list(self):
        """Reload chapters from local DB."""
        if not self.composer or not self.client:
            return
        wing_name = self.composer._get_wing_name()
        chapters = self.client.get_all_chapters(wing_name)
        
        self.table.setRowCount(0)
        for idx, ch in enumerate(chapters):
            self.table.insertRow(idx)
            
            num_item = QTableWidgetItem(f"Chapter {ch['num']}")
            num_item.setData(Qt.UserRole, ch['id']) # Store ID
            
            title_item = QTableWidgetItem(ch['title'])
            lines_item = QTableWidgetItem(f"{ch['start_line']} - {ch['end_line']}")
            mapped_item = QTableWidgetItem(str(ch['mapped_count']))
            
            status_text = "Analyzed" if ch['ai_summary'] else "Not Analyzed"
            status_item = QTableWidgetItem(status_text)
            
            for item in (num_item, title_item, lines_item, mapped_item, status_item):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                
            self.table.setItem(idx, 0, num_item)
            self.table.setItem(idx, 1, title_item)
            self.table.setItem(idx, 2, lines_item)
            self.table.setItem(idx, 3, mapped_item)
            self.table.setItem(idx, 4, status_item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    @pyqtSlot()
    def _browse_script_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Game Script File", "", "Text Files (*.txt);;All Files (*)"
        )
        if path:
            self.file_path_edit.setText(path)
            self.append_log(f"Selected script file: {os.path.basename(path)}")

    def append_log(self, text: str):
        self.log_text.append(text)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _get_ai_provider_or_warn(self):
        ai_provider = None
        if hasattr(self.mw, "translation_handler") and self.mw.translation_handler:
            try:
                ai_provider = self.mw.translation_handler._prepare_provider()
            except Exception as e:
                log_error(f"Failed to prepare AI provider: {e}")
                
        if not ai_provider:
            QMessageBox.warning(
                self, "AI Provider Error", 
                "No active AI Provider configured. Please check your API settings."
            )
        return ai_provider

    @pyqtSlot()
    def _pre_analyze_script_via_ai(self):
        """Mine characters and terminology from script introduction."""
        self.save_builder_settings()
        self._maybe_prevent_sleep()
        
        file_path = self.file_path_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Validation Error", "Please select a valid game script file first.")
            return

        ai_provider = self._get_ai_provider_or_warn()
        if not ai_provider:
            return

        self._pre_analyze_script_via_ai_core(file_path, ai_provider)

    def _pre_analyze_script_via_ai_core(self, file_path, ai_provider):
        self.append_log("Starting pre-analysis of script characters via AI...")
        self._set_ui_enabled(False)

        wing_name = self.wing_edit.text().strip()
        
        gm = getattr(self.mw, 'glossary_manager', None)
        if not gm:
            gm = getattr(self.mw, '_glossary_manager', None)
        if not gm and hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            gm = getattr(self.mw.translation_handler, '_glossary_manager', None)

        lang_code = getattr(self.mw, 'spellchecker_language', 'uk')
        target_lang = "Ukrainian" if lang_code == 'uk' else "Russian" if lang_code == 'ru' else "English"

        self.worker = MemePalaceScriptAnalyzerWorker(
            client=self.client,
            file_path=file_path,
            ai_provider=ai_provider,
            wing_name=wing_name,
            glossary_manager=gm,
            target_lang=target_lang,
            plugin_name=getattr(self.mw, "active_game_plugin", None),
            mw=self.mw
        )

        self.worker.progress.connect(self._handle_worker_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self._handle_char_mining_finished)
        self.worker.start()

    def _handle_char_mining_finished(self, success, message):
        self._set_ui_enabled(True)
        self.worker = None
        self.progress_bar.setValue(100 if success else 0)

        if success:
            self.append_log("CHARACTER MINING COMPLETED SUCCESSFULLY!")
            
            # Hot-reload glossary highlighting
            try:
                gh = None
                if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                    gh = getattr(self.mw.translation_handler, 'glossary_handler', None)
                if gh:
                    gh.glossary_manager.refresh_from_disk()
                    gh._update_glossary_highlighting()
            except Exception as e:
                log_error(f"Failed to refresh glossary after mining: {e}")

            if getattr(self, "pipeline_running", False):
                self._advance_pipeline()
            else:
                self._finish_and_maybe_sleep()
                QMessageBox.information(self, "Success", f"Character profiling completed!\n\n{message}")
        else:
            if getattr(self, "user_cancelled", False):
                self.append_log("Character mining stopped by user.")
                self.pipeline_running = False
                self._finish_and_maybe_sleep()
                self.user_cancelled = False
                self._update_pipeline_btn_text()
            else:
                self.append_log("CHARACTER MINING FAILED.")
                if getattr(self, "pipeline_running", False):
                    self._abort_pipeline(message)
                else:
                    self._finish_and_maybe_sleep()
                    QMessageBox.warning(self, "Failed", f"Character profiling failed:\n{message}")

    @pyqtSlot()
    def _profile_characters_speech_via_ai(self):
        """Analyze character speech patterns and build rich glossary profiles via AI."""
        self.save_builder_settings()
        self._maybe_prevent_sleep()

        ai_provider = self._get_ai_provider_or_warn()
        if not ai_provider:
            return

        self._profile_characters_speech_via_ai_core(ai_provider)

    def _profile_characters_speech_via_ai_core(self, ai_provider):
        self.append_log("Starting AI character speech profiling...")
        self._set_ui_enabled(False)

        wing_name = self.wing_edit.text().strip()

        gm = getattr(self.mw, 'glossary_manager', None)
        if not gm:
            gm = getattr(self.mw, '_glossary_manager', None)
        if not gm and hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            gm = getattr(self.mw.translation_handler, '_glossary_manager', None)

        lang_code = getattr(self.mw, 'spellchecker_language', 'uk')
        target_lang = "Ukrainian" if lang_code == 'uk' else "Russian" if lang_code == 'ru' else "English"

        self.worker = MemePalaceCharacterProfilerWorker(
            client=self.client,
            ai_provider=ai_provider,
            wing_name=wing_name,
            glossary_manager=gm,
            target_lang=target_lang,
            plugin_name=getattr(self.mw, "active_game_plugin", None),
            composer=self.composer,
            mw=self.mw
        )

        self.worker.progress.connect(self._handle_worker_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self._handle_speech_profiling_finished)
        self.worker.start()

    def _handle_speech_profiling_finished(self, success, message):
        self._set_ui_enabled(True)
        self.worker = None
        self.progress_bar.setValue(100 if success else 0)

        if success:
            self.append_log("CHARACTER SPEECH PROFILING COMPLETED SUCCESSFULLY!")
            
            # Hot-reload glossary highlighting in UI
            try:
                gh = None
                if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                    gh = getattr(self.mw.translation_handler, 'glossary_handler', None)
                if gh:
                    gh.glossary_manager.refresh_from_disk()
                    gh._update_glossary_highlighting()
                    if gh.dialog and gh.dialog.isVisible():
                        entries = sorted(gh.glossary_manager.get_entries(), key=lambda e: e.original.lower())
                        data_source = getattr(self.mw.data_store, "data", [])
                        occurrence_map = gh.glossary_manager.build_occurrence_index(data_source)
                        gh.dialog.reload_data(entries, occurrence_map)
            except Exception as e:
                log_error(f"Failed to refresh glossary after speech profiling: {e}")

            if getattr(self, "pipeline_running", False):
                self._advance_pipeline()
            else:
                self._finish_and_maybe_sleep()
                QMessageBox.information(self, "Success", f"Character speech profiling completed!\n\n{message}")
        else:
            if getattr(self, "user_cancelled", False):
                self.append_log("Character speech profiling stopped by user.")
                self.pipeline_running = False
                self._finish_and_maybe_sleep()
                self.user_cancelled = False
                self._update_pipeline_btn_text()
            else:
                self.append_log("CHARACTER SPEECH PROFILING FAILED.")
                if getattr(self, "pipeline_running", False):
                    self._abort_pipeline(message)
                else:
                    self._finish_and_maybe_sleep()
                    QMessageBox.warning(self, "Failed", f"Character speech profiling failed:\n{message}")

    @pyqtSlot()
    def _start_chapters_mapping(self):
        """Map BMG text items to chapters."""
        self.save_builder_settings()
        
        file_path = self.file_path_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Validation Error", "Please select a valid game script file first.")
            return

        self._start_chapters_mapping_core(file_path)

    def _start_chapters_mapping_core(self, file_path):
        wing_name = self.wing_edit.text().strip()
        self._set_ui_enabled(False)

        self.worker = MemePalaceChapterMapperWorker(
            client=self.client,
            composer=self.composer,
            wing_name=wing_name
        )
        self.worker.progress.connect(self._handle_worker_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self._handle_chapters_mapping_finished)
        self.worker.start()

    def _handle_chapters_mapping_finished(self, success, message):
        self._set_ui_enabled(True)
        self.worker = None
        self.progress_bar.setValue(100 if success else 0)

        if success:
            self.refresh_chapters_list()
            if getattr(self, "pipeline_running", False):
                self._advance_pipeline()
            else:
                QMessageBox.information(self, "Success", f"Chapters mapped successfully!\n\n{message}")
        else:
            if getattr(self, "user_cancelled", False):
                self.append_log("Chapters mapping stopped by user.")
                self.user_cancelled = False
                self.pipeline_running = False
                self._update_pipeline_btn_text()
            else:
                if getattr(self, "pipeline_running", False):
                    self._abort_pipeline(message)
                else:
                    QMessageBox.warning(self, "Failed", f"Chapters mapping failed:\n{message}")

    @pyqtSlot()
    def _analyze_selected_chapter(self):
        """Generate AI overview for the selected chapters."""
        selected_items = self.table.selectedItems()
        selected_rows = sorted(list(set(item.row() for item in selected_items)))
        if not selected_rows:
            QMessageBox.warning(self, "No selection", "Please select one or more chapters to analyze from the table.")
            return

        self.save_builder_settings()
        self._maybe_prevent_sleep()

        self.analysis_queue = []
        for row in selected_rows:
            chapter_id = self.table.item(row, 0).data(Qt.UserRole)
            self.analysis_queue.append(chapter_id)

        self.analysis_total_count = len(self.analysis_queue)
        self.analysis_completed_count = 0

        self._set_ui_enabled(False)
        self._process_analysis_queue()

    def _handle_chapter_analysis_finished(self, success, message):
        self.worker = None

        if success:
            self.append_log(message)
            self.refresh_chapters_list()
            self.analysis_completed_count += 1
            # If queue running, proceed to next chapter
            if self.analysis_queue:
                self._process_analysis_queue()
            else:
                self._set_ui_enabled(True)
                self.progress_bar.setValue(100)
                if getattr(self, "pipeline_running", False):
                    self._advance_pipeline()
                else:
                    QMessageBox.information(self, "Finished", "All selected chapters successfully analyzed via AI!")
                    self._finish_and_maybe_sleep()
        else:
            self._set_ui_enabled(True)
            self.refresh_chapters_list()
            if getattr(self, "user_cancelled", False):
                self.append_log("Chapter analysis stopped by user.")
                self.pipeline_running = False
                self._finish_and_maybe_sleep()
                self.user_cancelled = False
                self._update_pipeline_btn_text()
            else:
                if getattr(self, "pipeline_running", False):
                    self._abort_pipeline(message)
                else:
                    QMessageBox.warning(self, "AI Error", f"Chapter analysis failed:\n{message}")
                    self._finish_and_maybe_sleep()
            self.analysis_queue = []
            self.analysis_total_count = 0
            self.analysis_completed_count = 0

    @pyqtSlot()
    def _analyze_all_chapters(self):
        """Setup queue to analyze all chapters."""
        reply = QMessageBox.question(
            self, "Analyze All Chapters",
            "This will analyze all chapters one by one using the AI provider. It may take several minutes.\n\n"
            "Do you want to proceed?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.save_builder_settings()
        self._maybe_prevent_sleep()
        self._analyze_all_chapters_core()

    def _analyze_all_chapters_core(self):
        self.analysis_queue = []
        wing_name = self.composer._get_wing_name()
        chapters = self.client.get_all_chapters(wing_name)
        
        for ch in chapters:
            self.analysis_queue.append(ch['id'])

        if not self.analysis_queue:
            self.append_log("No chapters found to analyze. Proceeding in pipeline...")
            if getattr(self, "pipeline_running", False):
                self._advance_pipeline()
            else:
                QMessageBox.information(self, "Finished", "No chapters found to analyze.")
            return

        self.analysis_total_count = len(self.analysis_queue)
        self.analysis_completed_count = 0

        self.current_analysis_idx = 0
        self._set_ui_enabled(False)
        self._process_analysis_queue()

    @pyqtSlot()
    def _start_complete_pipeline(self):
        """Start or resume the complete MemePalace orchestration pipeline sequentially."""
        file_path = self.file_path_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Validation Error", "Please select a valid game script file first.")
            return

        ai_provider = self._get_ai_provider_or_warn()
        if not ai_provider:
            return

        has_saved = getattr(self, "saved_pipeline_running", False) and getattr(self, "saved_pipeline_step", 0) > 0
        
        if has_saved:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Resume Pipeline Session")
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setText(
                f"An incomplete MemePalace pipeline session was found at Step {self.saved_pipeline_step}/4.\n\n"
                f"Do you want to continue the session from Step {self.saved_pipeline_step} or start a new session from the beginning?"
            )
            
            continue_btn = msg_box.addButton("Continue", QMessageBox.AcceptRole)
            start_over_btn = msg_box.addButton("Start Over", QMessageBox.DestructiveRole)
            cancel_btn = msg_box.addButton("Cancel", QMessageBox.RejectRole)
            
            msg_box.setDefaultButton(continue_btn)
            msg_box.exec_()
            
            clicked = msg_box.clickedButton()
            if clicked == cancel_btn:
                return
            elif clicked == start_over_btn:
                self.pipeline_running = True
                self.pipeline_step = 1
            else:
                self.pipeline_running = True
                self.pipeline_step = self.saved_pipeline_step
                if getattr(self, "saved_pipeline_wing", ""):
                    self.wing_edit.setText(self.saved_pipeline_wing)
                if getattr(self, "saved_pipeline_script", "") and os.path.exists(self.saved_pipeline_script):
                    self.file_path_edit.setText(self.saved_pipeline_script)
        else:
            reply = QMessageBox.question(
                self, "Run Complete Pipeline",
                "This will sequentially execute all MemePalace steps step-by-step:\n"
                "1. Mine Characters & Terms via AI\n"
                "2. Map BMG to Script Chapters\n"
                "3. AI Analyze All Chapters\n"
                "4. AI Profile Characters Speech\n\n"
                "This process can take several minutes. Do you want to start the complete pipeline?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            self.pipeline_running = True
            self.pipeline_step = 1

        self.append_log(">>> STARTING COMPLETE MEMEPALACE PIPELINE <<<")
        self._maybe_prevent_sleep()
        self._save_pipeline_state()
        self._run_pipeline_current_step()

    def _run_pipeline_current_step(self):
        if not self.pipeline_running:
            return

        file_path = self.file_path_edit.text().strip()
        ai_provider = self._get_ai_provider_or_warn()
        if not ai_provider:
            self._abort_pipeline("AI Provider unavailable.")
            return

        # Reset chapter analysis counts for other steps to prevent progress calculations bug (100% bug)
        if self.pipeline_step != 3:
            self.analysis_total_count = 0
            self.analysis_completed_count = 0

        if self.pipeline_step == 1:
            self.append_log("--- STEP 1/4: Mining Characters & Terms via AI ---")
            self._pre_analyze_script_via_ai_core(file_path, ai_provider)
        elif self.pipeline_step == 2:
            self.append_log("--- STEP 2/4: Mapping BMG to Script Chapters ---")
            self._start_chapters_mapping_core(file_path)
        elif self.pipeline_step == 3:
            self.append_log("--- STEP 3/4: Analyzing All Chapters via AI ---")
            self._analyze_all_chapters_core()
        elif self.pipeline_step == 4:
            self.append_log("--- STEP 4/4: Profiling Characters Speech via AI ---")
            self._profile_characters_speech_via_ai_core(ai_provider)

    def _advance_pipeline(self):
        if not getattr(self, "pipeline_running", False):
            return

        self.pipeline_step += 1
        if self.pipeline_step <= 4:
            self._save_pipeline_state()
            self._run_pipeline_current_step()
        else:
            self.pipeline_running = False
            self.pipeline_step = 0
            self._save_pipeline_state()
            self._set_ui_enabled(True)
            self.progress_bar.setValue(100)
            self.append_log(">>> COMPLETE MEMEPALACE PIPELINE FINISHED SUCCESSFULLY! <<<")
            QMessageBox.information(
                self, "Pipeline Success",
                "Congratulations! The complete MemePalace context orchestration pipeline completed successfully!\n\n"
                "All characters mined, dialogue lines mapped to story chapters, AI chapter summaries generated, "
                "and character speech profiles fully synthesized and loaded into the Glossary!"
            )
            self._finish_and_maybe_sleep()
            self._update_pipeline_btn_text()

    def _abort_pipeline(self, error_message):
        step = getattr(self, "pipeline_step", 1)
        
        # Save session as interrupted but recoverable
        try:
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
                sm.set("mempalace_pipeline_running", True)
                sm.set("mempalace_pipeline_step", step)
                sm.set("mempalace_pipeline_wing", self.wing_edit.text().strip())
                sm.set("mempalace_pipeline_script", self.file_path_edit.text().strip())
                sm.save_settings()
                
                self.saved_pipeline_running = True
                self.saved_pipeline_step = step
                self.saved_pipeline_wing = self.wing_edit.text().strip()
                self.saved_pipeline_script = self.file_path_edit.text().strip()
        except Exception:
            pass

        self.pipeline_running = False
        self.pipeline_step = 0
        self._set_ui_enabled(True)
        self.progress_bar.setValue(0)
        self.append_log(f">>> PIPELINE ABORTED DUE TO ERROR AT STEP {step}: {error_message} <<<")
        QMessageBox.warning(
            self, "Pipeline Failed",
            f"MemePalace Pipeline aborted at Step {step} due to error:\n{error_message}"
        )
        self._finish_and_maybe_sleep()
        self._update_pipeline_btn_text()

    def _process_analysis_queue(self):
        """Process queue sequentially."""
        if not self.analysis_queue:
            self._set_ui_enabled(True)
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Finished", "All chapters successfully analyzed via AI!")
            self._finish_and_maybe_sleep()
            return

        chapter_id = self.analysis_queue.pop(0)
        
        try:
            conn_db = sqlite3.connect(self.client.db_path)
            cursor = conn_db.cursor()
            cursor.execute("SELECT num, title, start_line, content FROM script_chapters WHERE id = ?", (chapter_id,))
            row_data = cursor.fetchone()
            conn_db.close()
        except Exception as e:
            self.append_log(f"Failed to fetch chapter {chapter_id}: {e}")
            self.analysis_completed_count += 1  # count as processed to avoid progress calculation stuck
            self._process_analysis_queue()
            return

        if not row_data:
            self.analysis_completed_count += 1
            self._process_analysis_queue()
            return

        num, title, start_line, content = row_data
        
        ai_provider = None
        if hasattr(self.mw, "translation_handler") and self.mw.translation_handler:
            ai_provider = self.mw.translation_handler._prepare_provider()

        if not ai_provider:
            self.append_log("AI provider missing, stopping queue.")
            self._set_ui_enabled(True)
            return

        self.worker = MemePalaceChapterAIAnalyzerWorker(
            client=self.client,
            ai_provider=ai_provider,
            chapter_id=chapter_id,
            num=num,
            title=title,
            content=content,
            start_line=start_line,
            mw=self.mw
        )
        self.worker.progress.connect(self._handle_worker_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self._handle_chapter_analysis_finished)
        self.worker.start()

    def _handle_worker_progress(self, current, total, text):
        if total > 0:
            if getattr(self, "analysis_total_count", 0) > 0:
                completed = getattr(self, "analysis_completed_count", 0)
                sub_progress = current / total
                overall_progress = int(((completed + sub_progress) / self.analysis_total_count) * 100)
                self.progress_bar.setValue(min(overall_progress, 100))
            else:
                self.progress_bar.setValue(int((current / total) * 100))
        self.append_log(text)

        # Hot-reload glossary dialog if it is visible during profiling updates in real time
        try:
            gh = None
            if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                gh = getattr(self.mw.translation_handler, 'glossary_handler', None)
            if gh and gh.dialog and gh.dialog.isVisible():
                entries = sorted(gh.glossary_manager.get_entries(), key=lambda e: e.original.lower())
                data_source = getattr(self.mw.data_store, "data", [])
                occurrence_map = gh.glossary_manager.build_occurrence_index(data_source)
                gh.dialog.reload_data(entries, occurrence_map)
        except Exception as e:
            log_error(f"Failed to hot-reload glossary dialog during worker progress: {e}")


    def _set_ui_enabled(self, enabled: bool):
        self.ai_analyze_btn.setEnabled(enabled)
        self.ai_profile_speech_btn.setEnabled(enabled)
        self.map_chapters_btn.setEnabled(enabled)
        self.analyze_chapter_btn.setEnabled(enabled)
        self.analyze_all_chapters_btn.setEnabled(enabled)
        self.pipeline_btn.setEnabled(enabled)
        self.table.setEnabled(enabled)
        self.file_path_edit.setEnabled(enabled)
        self.wing_edit.setEnabled(enabled)
        self.clear_btn.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        if enabled:
            self.cancel_btn.setText("Close")
            self.cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e1dfdd;
                    color: #333333;
                    border: none;
                    border-radius: 4px;
                    padding: 7px 15px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #d2d0ce;
                }
            """)
        else:
            self.cancel_btn.setText("Stop")
            self.cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #a80000;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 7px 15px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #800000;
                }
                QPushButton:pressed {
                    background-color: #600000;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #666666;
                }
            """)

    @pyqtSlot()
    def _clear_database(self):
        """Clear mapped data from local database."""
        reply = QMessageBox.question(
            self, "Clear Database", 
            "Are you sure you want to completely clear the local MemePalace database?\n\n"
            "This will delete all mapped rooms, dialogues, relations, script chapters, and chapter summaries.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.append_log("Clearing local database...")
        try:
            if self.client.clear_all_local_data():
                # Also delete chapters mapping records
                try:
                    conn = sqlite3.connect(self.client.db_path)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM script_chapters")
                    cursor.execute("DELETE FROM script_mappings")
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
                    
                self.append_log("SUCCESS: Local database cleared successfully!")
                QMessageBox.information(self, "Clear Database", "Local database cleared successfully.")
                self.refresh_chapters_list()
            else:
                self.append_log("ERROR: Failed to clear the database.")
        except Exception as e:
            log_error(f"Error clearing database: {e}")
            self.append_log(f"ERROR: {e}")

    @pyqtSlot()
    def _handle_close_or_cancel(self):
        self.should_sleep_after = False
        restore_sleep()
        if self.worker and self.worker.isRunning():
            self.user_cancelled = True
            
            # Save pipeline session as interrupted if it was running!
            if getattr(self, "pipeline_running", False) and getattr(self, "pipeline_step", 0) > 0:
                try:
                    sm = getattr(self.mw, 'settings_manager', None)
                    if sm:
                        sm.set("mempalace_pipeline_running", True)
                        sm.set("mempalace_pipeline_step", self.pipeline_step)
                        sm.set("mempalace_pipeline_wing", self.wing_edit.text().strip())
                        sm.set("mempalace_pipeline_script", self.file_path_edit.text().strip())
                        sm.save_settings()
                        
                        self.saved_pipeline_running = True
                        self.saved_pipeline_step = self.pipeline_step
                        self.saved_pipeline_wing = self.wing_edit.text().strip()
                        self.saved_pipeline_script = self.file_path_edit.text().strip()
                except Exception:
                    pass

            self.analysis_queue = []
            self.analysis_total_count = 0
            self.analysis_completed_count = 0
            self.worker.cancel()
            self.append_log("Worker cancellation requested...")
            self.cancel_btn.setEnabled(False)
            self._update_pipeline_btn_text()
        else:
            self.save_builder_settings()
            self.close()

    def load_builder_settings(self):
        """Load recent dialog preferences from settings.json."""
        try:
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
                script_path = sm.get("mempalace_script_path", "")
                wing_name = sm.get("mempalace_wing_name", "")
                if isinstance(script_path, str) and script_path:
                    self.file_path_edit.setText(script_path)
                if isinstance(wing_name, str) and wing_name:
                    self.wing_edit.setText(wing_name)
                prevent_sleep_val = sm.get("mempalace_prevent_sleep", True)
                if isinstance(prevent_sleep_val, bool):
                    self.prevent_sleep_checkbox.setChecked(prevent_sleep_val)
                sleep_after_val = sm.get("mempalace_sleep_after_finish", False)
                if isinstance(sleep_after_val, bool):
                    self.sleep_after_checkbox.setChecked(sleep_after_val)
                
                # Load saved pipeline session
                self.saved_pipeline_running = sm.get("mempalace_pipeline_running", False)
                self.saved_pipeline_step = sm.get("mempalace_pipeline_step", 0)
                self.saved_pipeline_wing = sm.get("mempalace_pipeline_wing", "")
                self.saved_pipeline_script = sm.get("mempalace_pipeline_script", "")
                self._update_pipeline_btn_text()
        except Exception as e:
            log_error(f"Failed to load builder settings: {e}")

    def save_builder_settings(self):
        """Save dialog preferences into settings.json."""
        try:
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
                sm.set("mempalace_script_path", self.file_path_edit.text().strip())
                sm.set("mempalace_wing_name", self.wing_edit.text().strip())
                sm.set("mempalace_prevent_sleep", self.prevent_sleep_checkbox.isChecked())
                sm.set("mempalace_sleep_after_finish", self.sleep_after_checkbox.isChecked())
                sm.save_settings()
        except Exception as e:
            log_error(f"Failed to save builder settings: {e}")
