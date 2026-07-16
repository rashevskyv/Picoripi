import os
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QProgressBar, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QWidget, QAbstractItemView, QTabWidget, QGroupBox, QFormLayout,
    QTreeWidget, QComboBox, QSplitter,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt


WORKFLOW_BUTTON_STYLE = """
    QPushButton {
        background-color: #0f6cbd;
        color: white;
        font-weight: bold;
        border: none;
        border-radius: 4px;
        padding: 7px 15px;
    }
    QPushButton:hover { background-color: #115ea3; }
    QPushButton:pressed { background-color: #0e4775; }
    QPushButton:disabled {
        background-color: #cccccc;
        color: #666666;
    }
"""

SECONDARY_BUTTON_STYLE = """
    QPushButton {
        background-color: #f3f3f3;
        color: #333333;
        border: 1px solid #cccccc;
        border-radius: 4px;
        padding: 7px 15px;
    }
    QPushButton:hover { background-color: #eaeaea; }
    QPushButton:pressed { background-color: #dedede; }
    QPushButton:disabled {
        background-color: #f3f3f3;
        color: #a19f9d;
        border-color: #e1dfdd;
    }
"""

DANGER_BUTTON_STYLE = """
    QPushButton {
        background-color: #a80000;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 7px 15px;
    }
    QPushButton:hover { background-color: #800000; }
    QPushButton:pressed { background-color: #600000; }
    QPushButton:disabled {
        background-color: #cccccc;
        color: #666666;
    }
"""

PIPELINE_BUTTON_STYLE = """
    QPushButton {
        background-color: #0f6cbd;
        color: white;
        font-weight: bold;
        border: none;
        border-radius: 4px;
        padding: 7px 20px;
    }
    QPushButton:hover { background-color: #115ea3; }
    QPushButton:pressed { background-color: #0e4775; }
    QPushButton:disabled {
        background-color: #cccccc;
        color: #666666;
    }
"""

class MemePalaceBuilderUiMixin:
    """UI setup and style sheet mixin for MemePalaceBuilderDialog."""

    def _setup_ui(self):
        """Build the gated source-to-context workflow."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        title_label = QLabel("MemPalace Context Builder")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #0f6cbd;")
        layout.addWidget(title_label)

        desc_label = QLabel(
            "Follow the steps from a validated script source to chapter mapping and AI analysis."
        )
        desc_label.setStyleSheet("color: #666666; font-size: 12px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        self.workflow_tabs = QTabWidget()
        self.workflow_tabs.setDocumentMode(True)
        self.workflow_tabs.setStyleSheet("""
            QTabBar::tab { padding: 9px 16px; min-width: 110px; }
            QTabBar::tab:selected { color: #0f6cbd; font-weight: bold; }
            QTabBar::tab:disabled { color: #999999; }
        """)
        layout.addWidget(self.workflow_tabs, 1)

        # Step 1: source
        source_tab = QWidget()
        source_layout = QVBoxLayout(source_tab)
        source_layout.setContentsMargins(14, 14, 14, 14)
        source_layout.setSpacing(10)
        source_intro = QLabel(
            "Choose the structured Markup Studio project. Import/Sync validates it and "
            "unlocks the next steps."
        )
        source_intro.setWordWrap(True)
        source_layout.addWidget(source_intro)

        markup_group = QGroupBox("Markup Studio Project")
        markup_layout = QVBoxLayout(markup_group)
        hierarchy_layout = QHBoxLayout()
        self.hierarchy_project_path_edit = QLineEdit()
        self.hierarchy_project_path_edit.setReadOnly(True)
        self.hierarchy_project_path_edit.setPlaceholderText("Select script_markup_project.json...")
        hierarchy_layout.addWidget(self.hierarchy_project_path_edit, 1)
        self.hierarchy_project_browse_btn = QPushButton("Select project…")
        self.hierarchy_project_browse_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.hierarchy_project_browse_btn.clicked.connect(self._browse_hierarchy_project)
        hierarchy_layout.addWidget(self.hierarchy_project_browse_btn)
        self.hierarchy_project_import_btn = QPushButton("Import/Sync")
        self.hierarchy_project_import_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.hierarchy_project_import_btn.setEnabled(False)
        self.hierarchy_project_import_btn.clicked.connect(self._import_sync_hierarchy_project)
        hierarchy_layout.addWidget(self.hierarchy_project_import_btn)
        markup_layout.addLayout(hierarchy_layout)
        self.hierarchy_project_status_label = QLabel("Status: Not imported")
        self.hierarchy_project_status_label.setStyleSheet("color: #666666; font-weight: bold;")
        markup_layout.addWidget(self.hierarchy_project_status_label)
        self.hierarchy_project_preview_label = QLabel(
            "Select a Markup Studio project to preview its nodes."
        )
        self.hierarchy_project_preview_label.setWordWrap(True)
        self.hierarchy_project_preview_label.setStyleSheet("color: #666666; font-size: 11px;")
        markup_layout.addWidget(self.hierarchy_project_preview_label)
        source_layout.addWidget(markup_group)

        project_group = QGroupBox("Project")
        project_form = QFormLayout(project_group)
        self.wing_edit = QLineEdit("Zelda_TP")
        if hasattr(self.mw, "active_game_rules") and self.mw.active_game_rules:
            game_name = self.mw.active_game_rules.get_display_name()
            if isinstance(game_name, str) and game_name.strip():
                clean_name = "".join(c if c.isalnum() else "_" for c in game_name).strip("_")
                if clean_name:
                    self.wing_edit.setText(clean_name)
        self.wing_edit.textChanged.connect(self._refresh_wizard_state)
        project_form.addRow("Wing name:", self.wing_edit)
        source_layout.addWidget(project_group)

        # Retained as internal compatibility fields while the old pipeline is removed.
        # They are intentionally not added to the visible layout.
        self.legacy_fallback_checkbox = QCheckBox()
        self.legacy_fallback_checkbox.toggled.connect(self._on_legacy_fallback_toggled)
        self.legacy_fallback_checkbox.setVisible(False)
        self.legacy_script_label = QLabel()
        self.legacy_script_label.setVisible(False)
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setEnabled(False)
        self.file_path_edit.setVisible(False)
        self.file_path_edit.textChanged.connect(self._refresh_wizard_state)
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setEnabled(False)
        self.browse_btn.setVisible(False)
        self.browse_btn.clicked.connect(self._browse_script_file)

        self.source_readiness_label = QLabel("Complete the source selection to continue.")
        self.source_readiness_label.setStyleSheet("color: #666666;")
        source_layout.addWidget(self.source_readiness_label)
        source_layout.addStretch()
        source_nav = QHBoxLayout()
        source_nav.addStretch()
        self.source_next_btn = QPushButton("Continue to Story Context →")
        self.source_next_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.source_next_btn.setEnabled(False)
        self.source_next_btn.clicked.connect(lambda: self._go_to_wizard_step(1))
        source_nav.addWidget(self.source_next_btn)
        source_layout.addLayout(source_nav)
        self.workflow_tabs.addTab(source_tab, "1. Source")

        # Step 2: connect game text to its story context
        chapters_tab = QWidget()
        chapters_layout = QVBoxLayout(chapters_tab)
        chapters_layout.setContentsMargins(14, 14, 14, 14)
        chapters_layout.setSpacing(10)
        chapters_intro = QLabel(
            "Connect game text to marked script context; only uncertain cases appear below."
        )
        chapters_intro.setWordWrap(True)
        chapters_layout.addWidget(chapters_intro)
        self.toggle_story_btn = QPushButton("Show imported structure")
        self.toggle_story_btn.setCheckable(True)
        self.toggle_story_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.toggle_story_btn.toggled.connect(self._toggle_story_structure)
        self.story_group = QGroupBox("Imported script structure")
        story_layout = QVBoxLayout(self.story_group)
        self.story_tree_status_label = QLabel("Import a Markup Studio project to build the tree.")
        self.story_tree_status_label.setStyleSheet("color: #666666;")
        story_layout.addWidget(self.story_tree_status_label)
        self.story_tree = QTreeWidget()
        self.story_tree.setColumnCount(3)
        self.story_tree.setHeaderLabels(["Type", "Title / text", "Source lines"])
        self.story_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.story_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.story_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.story_tree.setMinimumHeight(160)
        story_layout.addWidget(self.story_tree)
        self.dialogue_mapping_group = QGroupBox("Find story context")
        dialogue_mapping_layout = QVBoxLayout(self.dialogue_mapping_group)
        dialogue_mapping_help = QLabel(
            "The program will connect clear matches by itself. Menu text, system messages, "
            "and anything without a reliable place in the story will not be sent to you for review."
        )
        dialogue_mapping_help.setWordWrap(True)
        dialogue_mapping_help.setVisible(False)
        dialogue_mapping_actions = QHBoxLayout()
        self.match_dialogue_btn = QPushButton("Find Context Automatically")
        self.match_dialogue_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.match_dialogue_btn.clicked.connect(self._start_dialogue_node_mapping)
        dialogue_mapping_actions.addWidget(self.match_dialogue_btn)
        dialogue_mapping_actions.addWidget(self.toggle_story_btn)
        self.dialogue_mapping_summary_label = QLabel(
            "Ready. Start the automatic search; no manual preparation is required."
        )
        self.dialogue_mapping_summary_label.setStyleSheet("color: #666666;")
        self.dialogue_mapping_summary_label.setWordWrap(True)
        dialogue_mapping_actions.addWidget(self.dialogue_mapping_summary_label, 1)
        dialogue_mapping_layout.addLayout(dialogue_mapping_actions)
        self.dialogue_mapping_progress = QProgressBar()
        self.dialogue_mapping_progress.setVisible(False)
        dialogue_mapping_layout.addWidget(self.dialogue_mapping_progress)
        # Older integrations can still access this widget, but it is intentionally not
        # placed in the visible layout. The guided review presents one decision at a time.
        self.mapping_review_table = QTableWidget()
        self.mapping_review_table.setVisible(False)

        self.mapping_review_actions = QGroupBox("One decision needed")
        mapping_review_actions_layout = QVBoxLayout(self.mapping_review_actions)
        review_header = QHBoxLayout()
        self.mapping_review_counter_label = QLabel()
        self.mapping_review_counter_label.setStyleSheet("font-weight: bold; color: #0f6cbd;")
        review_header.addWidget(self.mapping_review_counter_label)
        review_header.addStretch()
        self.mapping_review_previous_btn = QPushButton("← Previous")
        self.mapping_review_previous_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.mapping_review_previous_btn.clicked.connect(self._show_previous_dialogue_review)
        review_header.addWidget(self.mapping_review_previous_btn)
        self.mapping_review_next_btn = QPushButton("Next →")
        self.mapping_review_next_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.mapping_review_next_btn.clicked.connect(self._show_next_dialogue_review)
        review_header.addWidget(self.mapping_review_next_btn)
        mapping_review_actions_layout.addLayout(review_header)

        self.mapping_review_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.mapping_review_splitter.setChildrenCollapsible(False)
        self.mapping_review_splitter.setHandleWidth(8)
        self.mapping_review_splitter.setStyleSheet(
            "QSplitter::handle { background: #d6d6d6; margin: 0 2px; } "
            "QSplitter::handle:hover { background: #0f6cbd; }"
        )

        game_review_panel = QGroupBox("Game project")
        game_review_layout = QVBoxLayout(game_review_panel)
        game_review_layout.addWidget(QLabel("Text that needs a decision:"))
        self.mapping_review_source_label = QLabel()
        self.mapping_review_source_label.setWordWrap(True)
        self.mapping_review_source_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.mapping_review_source_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.mapping_review_source_label.setStyleSheet(
            "background: white; border: 1px solid #cccccc; border-radius: 3px; "
            "padding: 10px; font-size: 12pt;"
        )
        self.mapping_review_source_label.setMinimumHeight(90)
        game_review_layout.addWidget(self.mapping_review_source_label)
        self.mapping_review_explanation_label = QLabel(
            "This looks like a possible match, but the program is not certain."
        )
        self.mapping_review_explanation_label.setWordWrap(True)
        game_review_layout.addWidget(self.mapping_review_explanation_label)
        game_review_layout.addStretch()

        script_review_panel = QGroupBox("Marked script")
        script_review_layout = QVBoxLayout(script_review_panel)
        script_review_layout.addWidget(QLabel("Selected place:"))
        self.mapping_review_candidate_label = QLabel()
        self.mapping_review_candidate_label.setWordWrap(True)
        self.mapping_review_candidate_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.mapping_review_candidate_label.setStyleSheet(
            "background: #f3f8fc; border: 1px solid #9ccbee; border-radius: 3px; "
            "padding: 10px; font-size: 12pt;"
        )
        self.mapping_review_candidate_label.setMinimumHeight(44)
        script_review_layout.addWidget(self.mapping_review_candidate_label)
        self.mapping_review_location_label = QLabel()
        self.mapping_review_location_label.setWordWrap(True)
        self.mapping_review_location_label.setStyleSheet("color: #666666;")
        script_review_layout.addWidget(self.mapping_review_location_label)
        script_review_layout.addWidget(QLabel("Nearby marked dialogue:"))
        self.mapping_context_preview = QTextEdit()
        self.mapping_context_preview.setReadOnly(True)
        self.mapping_context_preview.setMinimumHeight(100)
        self.mapping_context_preview.setStyleSheet(
            "QTextEdit { background: white; border: 1px solid #cccccc; "
            "border-radius: 3px; padding: 6px; font-size: 11pt; }"
        )
        script_review_layout.addWidget(self.mapping_context_preview, 1)

        self.mapping_dialogue_choice_widget = QWidget()
        mapping_dialogue_choice_layout = QVBoxLayout(self.mapping_dialogue_choice_widget)
        mapping_dialogue_choice_layout.setContentsMargins(0, 0, 0, 0)
        candidate_picker_help = QLabel(
            "Type part of a line, speaker, or scene. Select a result to preview its nearby dialogue."
        )
        candidate_picker_help.setWordWrap(True)
        mapping_dialogue_choice_layout.addWidget(candidate_picker_help)
        self.mapping_dialogue_combo = QComboBox()
        self.mapping_dialogue_combo.setEditable(True)
        self.mapping_dialogue_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.mapping_dialogue_combo.setPlaceholderText("Select a marked script line…")
        self.mapping_dialogue_combo.setMaxVisibleItems(18)
        self.mapping_dialogue_combo.view().setMinimumWidth(760)
        self.mapping_dialogue_combo.completer().setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self.mapping_dialogue_combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.mapping_dialogue_combo.currentIndexChanged.connect(
            self._on_dialogue_choice_changed
        )
        mapping_dialogue_choice_layout.addWidget(self.mapping_dialogue_combo, 1)
        self.mapping_dialogue_choice_widget.setVisible(False)
        script_review_layout.insertWidget(1, self.mapping_dialogue_choice_widget)

        self.mapping_review_splitter.addWidget(game_review_panel)
        self.mapping_review_splitter.addWidget(script_review_panel)
        self.mapping_review_splitter.setStretchFactor(0, 2)
        self.mapping_review_splitter.setStretchFactor(1, 5)
        self.mapping_review_splitter.setSizes([300, 600])
        self.mapping_review_splitter.setMinimumHeight(320)
        mapping_review_actions_layout.addWidget(self.mapping_review_splitter, 1)

        review_decision_actions = QHBoxLayout()
        self.approve_mapping_btn = QPushButton("Use Context")
        self.approve_mapping_btn.setToolTip("Save the selected marked-script location for this game text.")
        self.approve_mapping_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.approve_mapping_btn.setEnabled(False)
        self.approve_mapping_btn.clicked.connect(self._approve_selected_dialogue_mapping)
        review_decision_actions.addWidget(self.approve_mapping_btn)
        self.choose_other_mapping_btn = QPushButton("Compare Places…")
        self.choose_other_mapping_btn.setToolTip("Search and preview another marked script location.")
        self.choose_other_mapping_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.choose_other_mapping_btn.clicked.connect(self._show_dialogue_candidate_picker)
        review_decision_actions.addWidget(self.choose_other_mapping_btn)
        self.open_mapping_in_studio_btn = QPushButton("Open Studio")
        self.open_mapping_in_studio_btn.setToolTip(
            "Open this exact source line in Script Markup Studio to inspect or re-mark it."
        )
        self.open_mapping_in_studio_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.open_mapping_in_studio_btn.setEnabled(False)
        self.open_mapping_in_studio_btn.clicked.connect(
            self._open_current_dialogue_in_markup_studio
        )
        review_decision_actions.addWidget(self.open_mapping_in_studio_btn)
        self.reject_mapping_btn = QPushButton("Not Story")
        self.reject_mapping_btn.setToolTip(
            "Keep this game text out of story context and remove it from the review queue."
        )
        self.reject_mapping_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.reject_mapping_btn.clicked.connect(self._reject_selected_dialogue_mapping)
        review_decision_actions.addWidget(self.reject_mapping_btn)
        review_decision_actions.addStretch()
        mapping_review_actions_layout.addLayout(review_decision_actions)
        self.mapping_review_actions.setVisible(False)
        dialogue_mapping_layout.addWidget(self.mapping_review_actions, 1)
        self.chapters_splitter = QSplitter(Qt.Orientation.Vertical)
        self.chapters_splitter.setChildrenCollapsible(False)
        self.chapters_splitter.setHandleWidth(8)
        self.chapters_splitter.setStyleSheet(
            "QSplitter::handle { background: #d6d6d6; margin: 2px 0; } "
            "QSplitter::handle:hover { background: #0f6cbd; }"
        )
        self.chapters_splitter.addWidget(self.story_group)
        self.chapters_splitter.addWidget(self.dialogue_mapping_group)
        self.chapters_splitter.setStretchFactor(0, 3)
        self.chapters_splitter.setStretchFactor(1, 2)
        self.chapters_splitter.setSizes([390, 260])
        chapters_layout.addWidget(self.chapters_splitter, 1)
        self.story_group.setVisible(False)
        # Compatibility widgets for the removed chapter-mapping pipeline. They stay
        # out of the visible layout until the new dialogue-node mapping is implemented.
        self.map_chapters_btn = QPushButton("Map BMG to Script Chapters")
        self.map_chapters_btn.setToolTip(
            "Segment the script and map project dialogue lines to its chapters."
        )
        self.map_chapters_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.map_chapters_btn.clicked.connect(self._start_chapters_mapping)
        self.map_chapters_btn.setVisible(False)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Chapter", "Title", "Lines range", "Mapped lines", "AI Status"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setVisible(False)
        chapters_nav = QHBoxLayout()
        self.story_context_completion_label = QLabel(
            "After the automatic search, only the decision cards shown above need attention. "
            "If there are no cards, this step is complete."
        )
        self.story_context_completion_label.setWordWrap(True)
        self.story_context_completion_label.setStyleSheet("color: #666666;")
        chapters_nav.addWidget(self.story_context_completion_label, 1)
        chapters_nav.addStretch()
        self.story_context_done_btn = QPushButton("Done — Close Builder")
        self.story_context_done_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.story_context_done_btn.setVisible(False)
        self.story_context_done_btn.clicked.connect(self._handle_close_or_cancel)
        chapters_nav.addWidget(self.story_context_done_btn)
        self.mapping_next_btn = QPushButton("Analysis will unlock in the next stage")
        self.mapping_next_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.mapping_next_btn.setEnabled(False)
        self.mapping_next_btn.setVisible(False)
        self.mapping_next_btn.clicked.connect(lambda: self._go_to_wizard_step(2))
        chapters_nav.addWidget(self.mapping_next_btn)
        chapters_layout.addLayout(chapters_nav)
        self.workflow_tabs.addTab(chapters_tab, "2. Story Context")

        # Step 3: future analysis and activity
        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
        analysis_layout.setContentsMargins(14, 14, 14, 14)
        analysis_layout.setSpacing(10)
        analysis_intro = QLabel(
            "Analyze mapped chapters and finish character speech profiling. Progress and logs "
            "for long-running operations stay on this step."
        )
        analysis_intro.setWordWrap(True)
        analysis_layout.addWidget(analysis_intro)

        analysis_actions = QGroupBox("Analysis actions")
        analysis_actions_layout = QVBoxLayout(analysis_actions)
        chapter_actions = QHBoxLayout()
        self.analyze_chapter_btn = QPushButton("Analyze Selected Chapters")
        self.analyze_chapter_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.analyze_chapter_btn.clicked.connect(self._analyze_selected_chapter)
        chapter_actions.addWidget(self.analyze_chapter_btn)
        self.analyze_all_chapters_btn = QPushButton("Analyze All Chapters")
        self.analyze_all_chapters_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.analyze_all_chapters_btn.clicked.connect(self._analyze_all_chapters)
        chapter_actions.addWidget(self.analyze_all_chapters_btn)
        chapter_actions.addStretch()
        analysis_actions_layout.addLayout(chapter_actions)
        self.ai_profile_speech_btn = QPushButton("Profile Character Speech via AI")
        self.ai_profile_speech_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.ai_profile_speech_btn.clicked.connect(self._profile_characters_speech_via_ai)
        analysis_actions_layout.addWidget(self.ai_profile_speech_btn, 0, Qt.AlignmentFlag.AlignLeft)
        analysis_layout.addWidget(analysis_actions)

        automation_group = QGroupBox("Automation")
        automation_layout = QVBoxLayout(automation_group)
        self.pipeline_btn = QPushButton("Run Complete Automated Workflow")
        self.pipeline_btn.setToolTip("Run all MemePalace processing steps sequentially.")
        self.pipeline_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.pipeline_btn.clicked.connect(self._start_complete_pipeline)
        automation_layout.addWidget(self.pipeline_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.prevent_sleep_checkbox = QCheckBox("Prevent computer sleep during analysis")
        self.prevent_sleep_checkbox.setChecked(True)
        self.prevent_sleep_checkbox.toggled.connect(self._handle_prevent_sleep_toggled)
        self.sleep_after_checkbox = QCheckBox("Put computer to sleep when finished")
        self.sleep_after_checkbox.setChecked(False)
        self.sleep_after_checkbox.toggled.connect(self._handle_sleep_after_toggled)
        sleep_layout = QHBoxLayout()
        sleep_layout.addWidget(self.prevent_sleep_checkbox)
        sleep_layout.addWidget(self.sleep_after_checkbox)
        sleep_layout.addStretch()
        automation_layout.addLayout(sleep_layout)
        analysis_layout.addWidget(automation_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        analysis_layout.addWidget(self.progress_bar)
        analysis_layout.addWidget(QLabel("Activity log"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(100)
        analysis_layout.addWidget(self.log_text, 1)
        danger_row = QHBoxLayout()
        danger_row.addStretch()
        self.clear_btn = QPushButton("Clear MemePalace Database…")
        self.clear_btn.setToolTip("Permanently clear all mapped MemPalace data.")
        self.clear_btn.setStyleSheet(DANGER_BUTTON_STYLE)
        self.clear_btn.clicked.connect(self._clear_database)
        danger_row.addWidget(self.clear_btn)
        analysis_layout.addLayout(danger_row)
        self.workflow_tabs.addTab(analysis_tab, "3. Analysis")

        self.workflow_tabs.setTabEnabled(1, False)
        self.workflow_tabs.setTabEnabled(2, False)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton("Close")
        self.cancel_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.cancel_btn.clicked.connect(self._handle_close_or_cancel)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

    def _set_ui_enabled(self, enabled: bool):
        """Internal helper to set the ui enabled."""
        self.ai_profile_speech_btn.setEnabled(enabled)
        self.map_chapters_btn.setEnabled(enabled)
        self.match_dialogue_btn.setEnabled(
            enabled and self.story_document_id is not None and bool(self.mw.data_store.data)
        )
        self.analyze_chapter_btn.setEnabled(enabled)
        self.analyze_all_chapters_btn.setEnabled(enabled)
        self.pipeline_btn.setEnabled(enabled)
        self.table.setEnabled(enabled)
        self.file_path_edit.setEnabled(enabled)
        self.hierarchy_project_browse_btn.setEnabled(enabled)
        self.hierarchy_project_import_btn.setEnabled(enabled and self.hierarchy_project is not None)
        self.wing_edit.setEnabled(enabled)
        self.clear_btn.setEnabled(enabled)
        self.browse_btn.setEnabled(False)
        self.file_path_edit.setEnabled(False)
        if enabled:
            self.cancel_btn.setText("Close")
            self.cancel_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        else:
            self.cancel_btn.setText("Stop")
            self.cancel_btn.setStyleSheet(DANGER_BUTTON_STYLE)

    def _update_pipeline_btn_text(self):
        """Update Complete Pipeline button label based on saved session state."""
        has_saved = getattr(self, "saved_pipeline_running", False) and getattr(self, "saved_pipeline_step", 0) > 0
        if has_saved:
            step = self.saved_pipeline_step
            self.pipeline_btn.setText(f"Continue Pipeline (Step {step}/4)")
            self.pipeline_btn.setToolTip(f"Continue incomplete pipeline session from Step {step} or start a new one.")
        else:
            self.pipeline_btn.setText("Run Complete Automated Workflow")
            self.pipeline_btn.setToolTip("Sequentially execute all MemePalace steps step-by-step automatically.")
