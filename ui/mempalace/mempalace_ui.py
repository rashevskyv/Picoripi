from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QProgressBar, QTextEdit, QTableWidget, QHeaderView,
    QCheckBox, QWidget, QAbstractItemView, QTabWidget, QGroupBox, QFormLayout,
    QTreeWidget, QComboBox, QSplitter,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from core.i18n import tr


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

def set_workflow_enabled(button, enabled: bool) -> None:
    """Enable a workflow button and let its colour say so.

    Blue has to mean "this is the next thing you can do". Three blue buttons
    side by side say nothing about which comes first, so a step that is not
    reachable yet recedes to the secondary style instead of sitting there
    looking equally inviting.
    """
    button.setEnabled(enabled)
    button.setStyleSheet(WORKFLOW_BUTTON_STYLE if enabled else SECONDARY_BUTTON_STYLE)


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

        title_label = QLabel(tr('MemPalace Context Builder'))
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #0f6cbd;")
        layout.addWidget(title_label)

        desc_label = QLabel(
            tr('This is the story-context step of the localization pipeline — after the script is marked up and speakers are named, before the glossary is filled and the game text is translated.\n\nFirst import the Markup Studio project. Then link each game line to its place in that script. Then, if you want scene-aware translation, ask the AI to write what already happened (timeline) and how each character speaks (voices). Glossary and translation read those results; they do not replace them.')
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
            tr('<b>What this step is.</b> Markup Studio already decided which script lines are speakers, speech, chapters and scenes. This step copies that approved structure into MemePalace so later work can sit on the story instead of re-guessing it from a raw .txt file.<br><br><b>Do this after</b> the script is marked (and speakers named, if you use Merge Speakers). <b>Do this before</b> filling glossary descriptions or translating, if you want those prompts to know the scene.<br><br>Select <code>script_markup_project.json</code>, check the preview, then Import/Sync. Re-running Import after you re-mark the script updates the tree; it does not duplicate it.')
        )
        source_intro.setTextFormat(Qt.TextFormat.RichText)
        source_intro.setWordWrap(True)
        source_layout.addWidget(source_intro)

        markup_group = QGroupBox(tr('Markup Studio Project'))
        markup_layout = QVBoxLayout(markup_group)
        hierarchy_layout = QHBoxLayout()
        self.hierarchy_project_path_edit = QLineEdit()
        self.hierarchy_project_path_edit.setReadOnly(True)
        self.hierarchy_project_path_edit.setPlaceholderText(tr('Select script_markup_project.json...'))
        hierarchy_layout.addWidget(self.hierarchy_project_path_edit, 1)
        self.hierarchy_project_browse_btn = QPushButton(tr('Select project…'))
        self.hierarchy_project_browse_btn.setToolTip(
            tr('<b>Select Markup Studio project</b><br><br>Pick the <code>script_markup_project.json</code> that Script Markup Studio saved next to the walkthrough (or in the Picoripi project folder).<br><br>This file is the machine source of truth: who speaks, which lines are dialogue, and how chapters/scenes nest. MemePalace will not invent that structure from a raw script.<br><br>Choosing a file only fills the path. Nothing is imported until you press Import/Sync and see a green “Up to date” status.')
        )
        self.hierarchy_project_browse_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.hierarchy_project_browse_btn.clicked.connect(self._browse_hierarchy_project)
        hierarchy_layout.addWidget(self.hierarchy_project_browse_btn)
        self.hierarchy_project_import_btn = QPushButton(tr('Import/Sync'))
        self.hierarchy_project_import_btn.setToolTip(
            tr('<b>Import / sync the marked script</b><br><br>Reads the selected Markup Studio project into the MemePalace database: acts, chapters, scenes, speakers and dialogue nodes.<br><br>Only <b>approved</b> marks are imported. Unmarked or unapproved lines stay out until you finish them in Markup Studio and sync again.<br><br>Safe to run after you re-mark the script: existing links and analysis are updated in place, not copied. Enabled once a valid project file is selected and a wing name is set.')
        )
        self.hierarchy_project_import_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.hierarchy_project_import_btn.setEnabled(False)
        self.hierarchy_project_import_btn.clicked.connect(self._import_sync_hierarchy_project)
        hierarchy_layout.addWidget(self.hierarchy_project_import_btn)
        markup_layout.addLayout(hierarchy_layout)
        self.hierarchy_project_status_label = QLabel(tr('Status: Not imported'))
        self.hierarchy_project_status_label.setStyleSheet("color: #666666; font-weight: bold;")
        markup_layout.addWidget(self.hierarchy_project_status_label)
        self.hierarchy_project_preview_label = QLabel(
            tr('Select a Markup Studio project to preview its nodes.')
        )
        self.hierarchy_project_preview_label.setWordWrap(True)
        self.hierarchy_project_preview_label.setStyleSheet("color: #666666; font-size: 11px;")
        markup_layout.addWidget(self.hierarchy_project_preview_label)
        source_layout.addWidget(markup_group)

        project_group = QGroupBox(tr('Project'))
        project_form = QFormLayout(project_group)
        self.wing_edit = QLineEdit("Zelda_TP")
        if hasattr(self.mw, "active_game_rules") and self.mw.active_game_rules:
            game_name = self.mw.active_game_rules.get_display_name()
            if isinstance(game_name, str) and game_name.strip():
                clean_name = "".join(c if c.isalnum() else "_" for c in game_name).strip("_")
                if clean_name:
                    self.wing_edit.setText(clean_name)
        self.wing_edit.setToolTip(
            tr('<b>Wing name</b><br><br>A short label for this game inside MemePalace (for Twilight Princess it is usually filled from the plugin display name).<br><br>Chapters, mappings and character profiles are stored under this name. Changing it later looks like a different game unless you import again.')
        )
        self.wing_edit.textChanged.connect(self._refresh_wizard_state)
        project_form.addRow(tr('Wing name:'), self.wing_edit)
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
        self.browse_btn = QPushButton(tr('Browse…'))
        self.browse_btn.setToolTip(
            tr('<b>Browse for a raw script file</b><br>Legacy fallback source, kept hidden while the Markup Studio project is the supported input.')
        )
        self.browse_btn.setEnabled(False)
        self.browse_btn.setVisible(False)
        self.browse_btn.clicked.connect(self._browse_script_file)

        self.source_readiness_label = QLabel(tr('Complete the source selection to continue.'))
        self.source_readiness_label.setStyleSheet("color: #666666;")
        source_layout.addWidget(self.source_readiness_label)
        source_layout.addStretch()
        source_nav = QHBoxLayout()
        source_nav.addStretch()
        self.source_next_btn = QPushButton(tr('Continue to Story Context →'))
        self.source_next_btn.setToolTip(
            tr('<b>Continue to Story Context</b><br><br>Opens the next tab: link each in-game line to a marked script line, then optionally build the timeline and character voices.<br><br>Enabled when Import/Sync is up to date and a wing name is set. You can also click the tab header once it is unlocked.')
        )
        self.source_next_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.source_next_btn.setEnabled(False)
        self.source_next_btn.clicked.connect(lambda: self._go_to_wizard_step(1))
        source_nav.addWidget(self.source_next_btn)
        source_layout.addLayout(source_nav)
        self.workflow_tabs.addTab(source_tab, tr('1. Source'))

        # Step 2: connect game text to its story context
        chapters_tab = QWidget()
        chapters_layout = QVBoxLayout(chapters_tab)
        chapters_layout.setContentsMargins(14, 14, 14, 14)
        chapters_layout.setSpacing(10)
        chapters_intro = QLabel(
            tr('<b>What this tab is for.</b> The game file has lines; the marked script has story. Until they are linked, translation cannot know which scene a row belongs to.<br><br><b>Step 1</b> is automatic and does not use AI: it matches game text to marked dialogue. Clear matches are saved; only doubtful ones come back for a decision below. Menus and system messages are skipped.<br><br><b>Step 2 (timeline)</b> and <b>step 3 (voices)</b> are the analysis. They need step 1 first. Run them <b>before</b> you fill glossary descriptions if you want those notes and the translation prompt to know what already happened and how the speaker talks. They do not invent glossary terms and they do not overwrite names you confirmed in Merge Speakers.')
        )
        chapters_intro.setTextFormat(Qt.TextFormat.RichText)
        chapters_intro.setWordWrap(True)
        chapters_layout.addWidget(chapters_intro)
        self.toggle_story_btn = QPushButton(tr('Show imported structure'))
        self.toggle_story_btn.setToolTip(
            tr('<b>Show imported structure</b><br><br>Opens a read-only tree of what Import/Sync brought in: acts, chapters, scenes, speakers and dialogue with their source line numbers.<br><br>Use it to check that Markup Studio and MemePalace agree. Nothing in the tree is edited here — fix the script in Markup Studio, then Import/Sync again.')
        )
        self.toggle_story_btn.setCheckable(True)
        self.toggle_story_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.toggle_story_btn.toggled.connect(self._toggle_story_structure)
        self.story_group = QGroupBox(tr('Imported script structure'))
        story_layout = QVBoxLayout(self.story_group)
        self.story_tree_status_label = QLabel(tr('Import a Markup Studio project to build the tree.'))
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
        self.dialogue_mapping_group = QGroupBox(tr('Link lines, then analyse story and voices'))
        dialogue_mapping_layout = QVBoxLayout(self.dialogue_mapping_group)
        dialogue_mapping_help = QLabel(
            tr('The program will connect clear matches by itself. Menu text, system messages, and anything without a reliable place in the story will not be sent to you for review.')
        )
        dialogue_mapping_help.setWordWrap(True)
        dialogue_mapping_help.setVisible(False)
        dialogue_mapping_actions = QHBoxLayout()
        self.match_dialogue_btn = QPushButton(tr('Step 1 — Find Context Automatically'))
        self.match_dialogue_btn.setToolTip(
            tr('<b>Step 1 of 3 — Find context automatically (no AI)</b><br><br>Matches each non-empty game string to a marked script line by the text itself. Exact unique matches are saved at once. Repeated greetings and near-matches come back one by one below so you can Use Context, pick another place, or mark Not Story.<br><br>Menus, HUD and system lines are skipped — they are not story.<br><br>This has to finish before timeline or voices: those jobs only read <i>linked</i> lines. Re-run after you re-mark the script; already-decided links are kept unless the source text changed.')
        )
        self.match_dialogue_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.match_dialogue_btn.clicked.connect(self._start_dialogue_node_mapping)
        dialogue_mapping_actions.addWidget(self.match_dialogue_btn)
        dialogue_mapping_actions.addWidget(self.toggle_story_btn)
        self.dialogue_mapping_summary_label = QLabel(
            tr('Ready. Start the automatic search; no manual preparation is required.')
        )
        self.dialogue_mapping_summary_label.setStyleSheet("color: #666666;")
        self.dialogue_mapping_summary_label.setWordWrap(True)
        dialogue_mapping_actions.addWidget(self.dialogue_mapping_summary_label, 1)
        dialogue_mapping_layout.addLayout(dialogue_mapping_actions)
        self.dialogue_mapping_progress = QProgressBar()
        self.dialogue_mapping_progress.setVisible(False)
        dialogue_mapping_layout.addWidget(self.dialogue_mapping_progress)
        timeline_actions = QHBoxLayout()
        self.analyze_story_timeline_btn = QPushButton(tr('Step 2 — Build Timeline with AI'))
        self.analyze_story_timeline_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.analyze_story_timeline_btn.setEnabled(False)
        self.analyze_story_timeline_btn.setToolTip(
            tr('<b>Step 2 of 3 — Build the timeline (AI)</b><br><br>Reads linked dialogue in story order and writes a short event for each stretch: where we are, what just happened, what the scene is about.<br><br>That package is what the translation prompt uses instead of “translate this sentence in isolation”. Midna after the children are taken is not the same Midna as in Ordon.<br><br>Needs step 1. Does not fill the glossary. Run it <b>before</b> the glossary describe pass if you want scene notes available there. Long and billed per chunk; already-analysed stretches are reused.<br><br>Grey until step 1 has produced at least one link.')
        )
        self.analyze_story_timeline_btn.clicked.connect(self._start_story_timeline_analysis)
        timeline_actions.addWidget(self.analyze_story_timeline_btn)
        self.story_timeline_status_label = QLabel(
            tr('Build the timeline after the marked script has been imported.')
        )
        self.story_timeline_status_label.setWordWrap(True)
        self.story_timeline_status_label.setStyleSheet("color: #666666;")
        timeline_actions.addWidget(self.story_timeline_status_label, 1)
        dialogue_mapping_layout.addLayout(timeline_actions)
        self.story_timeline_progress = QProgressBar()
        self.story_timeline_progress.setVisible(False)
        dialogue_mapping_layout.addWidget(self.story_timeline_progress)
        character_actions = QHBoxLayout()
        self.analyze_character_voices_btn = QPushButton(tr('Step 3 — Analyze Character Voices with AI'))
        self.analyze_character_voices_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.analyze_character_voices_btn.setEnabled(False)
        self.analyze_character_voices_btn.setToolTip(
            tr('<b>Step 3 of 3 — Analyse character voices (AI)</b><br><br>Reads each named speaker’s linked lines and writes how they talk: register, tempo, habits, address (ти/ви), and translator guidance so Midna, Renado and a shop clerk do not share one voice.<br><br>Uses the names from Markup Studio / Merge Speakers. It does not invent or rename characters, and it does not dump a raw-script guess into the glossary.<br><br>Needs step 1. Best <b>before</b> glossary descriptions, so character notes can quote a real voice profile. Grey until step 1 has links.')
        )
        self.analyze_character_voices_btn.clicked.connect(
            self._start_normalized_character_profiling
        )
        character_actions.addWidget(self.analyze_character_voices_btn)
        self.character_profiles_status_label = QLabel(
            tr('Analyze marked speakers to give the translator consistent character voices.')
        )
        self.character_profiles_status_label.setWordWrap(True)
        self.character_profiles_status_label.setStyleSheet("color: #666666;")
        character_actions.addWidget(self.character_profiles_status_label, 1)
        dialogue_mapping_layout.addLayout(character_actions)
        self.character_profiles_progress = QProgressBar()
        self.character_profiles_progress.setVisible(False)
        dialogue_mapping_layout.addWidget(self.character_profiles_progress)
        # Older integrations can still access this widget, but it is intentionally not
        # placed in the visible layout. The guided review presents one decision at a time.
        self.mapping_review_table = QTableWidget()
        self.mapping_review_table.setVisible(False)

        self.mapping_review_actions = QGroupBox(tr('One decision needed'))
        mapping_review_actions_layout = QVBoxLayout(self.mapping_review_actions)
        review_header = QHBoxLayout()
        self.mapping_review_counter_label = QLabel()
        self.mapping_review_counter_label.setStyleSheet("font-weight: bold; color: #0f6cbd;")
        review_header.addWidget(self.mapping_review_counter_label)
        review_header.addStretch()
        self.mapping_review_previous_btn = QPushButton(tr('← Previous'))
        self.mapping_review_previous_btn.setToolTip(
            tr('<b>Previous case</b><br>Click — go back one case awaiting a decision. Skipping does not discard it; it stays in the queue until you decide.')
        )
        self.mapping_review_previous_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.mapping_review_previous_btn.clicked.connect(self._show_previous_dialogue_review)
        review_header.addWidget(self.mapping_review_previous_btn)
        self.mapping_review_next_btn = QPushButton(tr('Next →'))
        self.mapping_review_next_btn.setToolTip(
            tr('<b>Next case</b><br>Click — skip to the next case awaiting a decision. The skipped one stays in the queue until you decide.')
        )
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

        game_review_panel = QGroupBox(tr('Game project'))
        game_review_layout = QVBoxLayout(game_review_panel)
        game_review_layout.addWidget(QLabel(tr('Text that needs a decision:')))
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
            tr('This looks like a possible match, but the program is not certain.')
        )
        self.mapping_review_explanation_label.setWordWrap(True)
        game_review_layout.addWidget(self.mapping_review_explanation_label)
        game_review_layout.addStretch()

        script_review_panel = QGroupBox(tr('Marked script'))
        script_review_layout = QVBoxLayout(script_review_panel)
        script_review_layout.addWidget(QLabel(tr('Selected place:')))
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
        script_review_layout.addWidget(QLabel(tr('Nearby marked dialogue:')))
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
            tr('Type part of a line, speaker, or scene. Select a result to preview its nearby dialogue.')
        )
        candidate_picker_help.setWordWrap(True)
        mapping_dialogue_choice_layout.addWidget(candidate_picker_help)
        self.mapping_dialogue_combo = QComboBox()
        self.mapping_dialogue_combo.setEditable(True)
        self.mapping_dialogue_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.mapping_dialogue_combo.setPlaceholderText(tr('Select a marked script line…'))
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
        self.approve_mapping_btn = QPushButton(tr('Use Context'))
        self.approve_mapping_btn.setToolTip(
            tr('<b>Use this context</b><br><br>Saves the marked-script place on the right as the story location of the game line on the left. After this, timeline and voice analysis can include that line, and the editor’s Speaker / Story Timeline can show it.')
        )
        self.approve_mapping_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.approve_mapping_btn.setEnabled(False)
        self.approve_mapping_btn.clicked.connect(self._approve_selected_dialogue_mapping)
        review_decision_actions.addWidget(self.approve_mapping_btn)
        self.choose_other_mapping_btn = QPushButton(tr('Compare Places…'))
        self.choose_other_mapping_btn.setToolTip(
            tr('<b>Compare other places</b><br><br>Search marked dialogue by text, speaker or scene when the suggestion is wrong (the same “Yes.” is said by everyone). Preview nearby lines before you commit. Selecting a result updates the right-hand pane immediately.')
        )
        self.choose_other_mapping_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.choose_other_mapping_btn.clicked.connect(self._show_dialogue_candidate_picker)
        review_decision_actions.addWidget(self.choose_other_mapping_btn)
        self.open_mapping_in_studio_btn = QPushButton(tr('Open Studio'))
        self.open_mapping_in_studio_btn.setToolTip(
            tr('<b>Open in Markup Studio</b><br><br>Jumps to this exact source line in Script Markup Studio (the pipeline’s markup step, or a standalone Studio window). Fix the mark there, save, then Import/Sync and Find Context again if the link should change.')
        )
        self.open_mapping_in_studio_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.open_mapping_in_studio_btn.setEnabled(False)
        self.open_mapping_in_studio_btn.clicked.connect(
            self._open_current_dialogue_in_markup_studio
        )
        review_decision_actions.addWidget(self.open_mapping_in_studio_btn)
        self.reject_mapping_btn = QPushButton(tr('Not Story'))
        self.reject_mapping_btn.setToolTip(
            tr('<b>Not story</b><br><br>Leaves this game line out of the story map (HUD, shop bark, padding). It is removed from the review queue and will not get a timeline event or character-voice weight. Translations in the project are untouched.')
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
        self.map_chapters_btn = QPushButton(tr('Map BMG to Script Chapters'))
        self.map_chapters_btn.setToolTip(
            tr('Segment the script and map project dialogue lines to its chapters.')
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
            tr('Step 1 first: after the automatic search, only the cards above need a decision. When there are no cards, the links are done — then run timeline and voices if you want scene-aware translation, before filling the glossary.')
        )
        self.story_context_completion_label.setWordWrap(True)
        self.story_context_completion_label.setStyleSheet("color: #666666;")
        chapters_nav.addWidget(self.story_context_completion_label, 1)
        chapters_nav.addStretch()
        self.story_context_done_btn = QPushButton(tr('Done — Close Builder'))
        self.story_context_done_btn.setToolTip(
            tr('<b>Finish</b><br><br>Closes the builder. Links, timeline events and voice profiles already saved stay in MemePalace. Reopening resumes here. Glossary and translation are the next pipeline steps, not this window.')
        )
        self.story_context_done_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.story_context_done_btn.setVisible(False)
        self.story_context_done_btn.clicked.connect(self._handle_close_or_cancel)
        chapters_nav.addWidget(self.story_context_done_btn)
        chapters_layout.addLayout(chapters_nav)

        activity_group = QGroupBox(tr('Activity'))
        activity_layout = QVBoxLayout(activity_group)
        activity_help = QLabel(
            tr('Progress and the log belong to the jobs on this tab (Find Context, timeline, voices). Prevent sleep for long AI runs. Clearing the database wipes imported structure and analysis only — not your translations or glossary.')
        )
        activity_help.setWordWrap(True)
        activity_help.setStyleSheet("color: #666666;")
        activity_layout.addWidget(activity_help)
        self.prevent_sleep_checkbox = QCheckBox(tr('Prevent computer sleep during long jobs'))
        self.prevent_sleep_checkbox.setChecked(True)
        self.prevent_sleep_checkbox.setToolTip(
            tr('<b>Prevent sleep</b><br><br>Keeps the machine awake while Find Context, timeline or voice analysis is running. Uncheck if you are only reviewing cards.')
        )
        self.prevent_sleep_checkbox.toggled.connect(self._handle_prevent_sleep_toggled)
        self.sleep_after_checkbox = QCheckBox(tr('Sleep when the current job finishes'))
        self.sleep_after_checkbox.setChecked(False)
        self.sleep_after_checkbox.setToolTip(
            tr('<b>Sleep when finished</b><br><br>After the running job ends successfully, put the computer to sleep. Cancelled or failed jobs do not sleep. Useful overnight for timeline or voice analysis; not for a short Find Context pass.')
        )
        self.sleep_after_checkbox.toggled.connect(self._handle_sleep_after_toggled)
        sleep_layout = QHBoxLayout()
        sleep_layout.addWidget(self.prevent_sleep_checkbox)
        sleep_layout.addWidget(self.sleep_after_checkbox)
        sleep_layout.addStretch()
        activity_layout.addLayout(sleep_layout)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setToolTip(tr('Overall progress of the job currently running on this tab.'))
        activity_layout.addWidget(self.progress_bar)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(72)
        self.log_text.setMaximumHeight(140)
        self.log_text.setToolTip(tr('Timestamped log of import, matching and AI jobs.'))
        activity_layout.addWidget(self.log_text)
        danger_row = QHBoxLayout()
        danger_row.addStretch()
        self.clear_btn = QPushButton(tr('Clear MemePalace Database…'))
        self.clear_btn.setToolTip(
            tr('<b>Clear MemePalace database</b><br><br>Permanently deletes imported structure, line links, timeline events and voice profiles for this wing. Asks for confirmation; there is no undo.<br><br>Does not touch translations, glossary entries, or the Markup Studio project. Use after a bad import, not as a routine step.')
        )
        self.clear_btn.setStyleSheet(DANGER_BUTTON_STYLE)
        self.clear_btn.clicked.connect(self._clear_database)
        danger_row.addWidget(self.clear_btn)
        activity_layout.addLayout(danger_row)
        chapters_layout.addWidget(activity_group)

        self.workflow_tabs.addTab(chapters_tab, tr('2. Story Context'))
        self.workflow_tabs.setTabEnabled(1, False)

        # Hidden leftovers from the retired chapter-mining tab. Methods and
        # tests that still name these widgets keep working; they are not a step.
        self.mapping_next_btn = QPushButton(tr('Continue to Analysis →'))
        self.mapping_next_btn.setVisible(False)
        self.mapping_next_btn.setEnabled(False)
        self.analyze_chapter_btn = QPushButton(tr('Analyze Selected Chapters'))
        self.analyze_chapter_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.analyze_chapter_btn.setVisible(False)
        self.analyze_chapter_btn.clicked.connect(self._analyze_selected_chapter)
        self.analyze_all_chapters_btn = QPushButton(tr('Analyze All Chapters'))
        self.analyze_all_chapters_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.analyze_all_chapters_btn.setVisible(False)
        self.analyze_all_chapters_btn.clicked.connect(self._analyze_all_chapters)
        self.ai_profile_speech_btn = QPushButton(tr('Profile Character Speech via AI'))
        self.ai_profile_speech_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.ai_profile_speech_btn.setVisible(False)
        self.ai_profile_speech_btn.clicked.connect(self._profile_characters_speech_via_ai)
        self.pipeline_btn = QPushButton(tr('Run Complete Automated Workflow'))
        self.pipeline_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
        self.pipeline_btn.setVisible(False)
        self.pipeline_btn.clicked.connect(self._start_complete_pipeline)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton(tr('Close'))
        self.cancel_btn.setToolTip(
            tr('<b>Close</b><br><br>Closes the builder (Esc). A running job is asked to stop first; already saved links, timeline events and voice profiles stay. When this builder is inside Localization Pipeline, use the pipeline Close instead — this button is hidden there except as Stop.')
        )
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
            self.cancel_btn.setText(tr('Close'))
            self.cancel_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        else:
            self.cancel_btn.setText(tr('Stop'))
            self.cancel_btn.setStyleSheet(DANGER_BUTTON_STYLE)

    def _update_pipeline_btn_text(self):
        """Update Complete Pipeline button label based on saved session state."""
        has_saved = getattr(self, "saved_pipeline_running", False) and getattr(self, "saved_pipeline_step", 0) > 0
        if has_saved:
            step = self.saved_pipeline_step
            self.pipeline_btn.setText(f"Continue Pipeline (Step {step}/4)")
            self.pipeline_btn.setToolTip(f"Continue incomplete pipeline session from Step {step} or start a new one.")
        else:
            self.pipeline_btn.setText(tr('Run Complete Automated Workflow'))
            self.pipeline_btn.setToolTip(tr('Sequentially execute all MemePalace steps step-by-step automatically.'))
