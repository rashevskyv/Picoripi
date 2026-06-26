import os
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QProgressBar, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QSplitter, QWidget, QAbstractItemView
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

class MemePalaceBuilderUiMixin:
    """UI setup and style sheet mixin for MemePalaceBuilderDialog."""

    def _setup_ui(self):
        # Main layout
        """Internal helper to setup ui."""
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
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
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
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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
        self.splitter = QSplitter(Qt.Orientation.Vertical)
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

    def _set_ui_enabled(self, enabled: bool):
        """Internal helper to set the ui enabled."""
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
