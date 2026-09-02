"""UI construction, menus, styling, legend, and minimap for Script Markup Studio."""
from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QCheckBox, QGroupBox, QComboBox,
    QLineEdit, QSpinBox, QSplitter, QWidget, QMenu,
    QAbstractItemView, QSizePolicy,
)
from PyQt6.QtGui import (
    QFont, QShortcut, QKeySequence,
)
from PyQt6.QtCore import Qt
from core.script_markup import (
    HierarchyType,
)
from core.i18n import tr

from ui.script_markup.widgets import (
    _ClassificationHighlighter,
    _SearchLineEdit,
    _ScriptMarkupRawEdit,
    _ScriptTreeWidget,
    CompactStatsLabel,
    CompactLegendLabel,
)


class UiMixin:
    """UI construction, menus, styling, legend, and minimap for Script Markup Studio."""

    # ------------------------------------------------------------------ UI
    def _add_menu_action(self, menu: QMenu, text: str, callback, tooltip: str = ""):
        action = menu.addAction(text)
        if tooltip:
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
        action.triggered.connect(lambda _checked=False, cb=callback: cb())
        return action

    def _create_menu_button(self, text: str, tooltip: str) -> tuple[QPushButton, QMenu]:
        button = QPushButton(text, self)
        button.setAutoDefault(False)
        button.setToolTip(tooltip)
        menu = QMenu(button)
        button.setMenu(menu)
        return button, menu

    def _disable_default_buttons(self):
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        self._apply_studio_style()

        # Legacy compat widgets (initialized but not added to layout)
        self.script_menu_btn, self.script_menu = self._create_menu_button("Script", "Open script...")
        self.script_menu_btn.setGeometry(-2000, -2000, 0, 0)
        self.load_btn = self._add_menu_action(self.script_menu, "Open script...", self._load_file)

        self.project_menu_btn, self.project_menu = self._create_menu_button("Project", "Project menu")
        self.project_menu_btn.setGeometry(-2000, -2000, 0, 0)
        self.load_markup_btn = self._add_menu_action(self.project_menu, "Open project...", self._load_hierarchy_project)
        self.save_markup_btn = self._add_menu_action(self.project_menu, "Save project...", self._save_hierarchy_project)
        self.reset_markup_btn = self._add_menu_action(self.project_menu, "Reset marks...", self._reset_current_markup)

        self.save_project_primary_btn = QPushButton(tr('Save Project…'), self)
        self.save_project_primary_btn.setGeometry(-2000, -2000, 0, 0)
        self.save_project_primary_btn.setToolTip(tr('Save the markup project.'))
        self.save_project_primary_btn.clicked.connect(self._save_hierarchy_project)

        self.finish_mempalace_btn = QPushButton(tr('Finish for MemPalace…'), self)
        self.finish_mempalace_btn.setGeometry(-2000, -2000, 0, 0)
        self.finish_mempalace_btn.setToolTip(tr('Finish the markup and go to MemPalace.'))
        self.finish_mempalace_btn.clicked.connect(self._finish_markup_for_mempalace)

        self.template_menu_btn, self.template_menu = self._create_menu_button("Template", "Template menu")
        self.template_menu_btn.setGeometry(-2000, -2000, 0, 0)
        self.load_template_btn = self._add_menu_action(self.template_menu, "Open template...", self._load_hierarchy_template)
        self.save_template_btn = self._add_menu_action(self.template_menu, "Save template...", self._save_hierarchy_template)

        self.auto_markup_menu_btn, self.auto_markup_menu = self._create_menu_button("Auto-fill", "Auto-fill menu")
        self.join_structures_btn = self._add_menu_action(self.auto_markup_menu, "Join selected structures", self._join_selected_structures)
        self.continue_examples_btn = self._add_menu_action(self.auto_markup_menu, "Continue from marked examples...", self._continue_hierarchy_from_examples)
        self.ai_markup_btn = self._add_menu_action(self.auto_markup_menu, "AI mark missing...", self._run_hierarchy_ai_markup)

        self.recipe_menu_btn, self.recipe_menu = self._create_menu_button("Recipe", "Recipe menu")
        self.recipe_menu_btn.setGeometry(-2000, -2000, 0, 0)
        self.load_recipe_btn = self._add_menu_action(self.recipe_menu, "Open recipe...", self._load_recipe)
        self.save_recipe_btn = self._add_menu_action(self.recipe_menu, "Save recipe...", self._save_recipe)

        self.mode_combo = QComboBox(self)
        self.mode_combo.setGeometry(-2000, -2000, 0, 0)
        self.mode_combo.addItem(tr('Hierarchy markup'), tr('hierarchy'))
        self.mode_combo.addItem(tr('Picoripi rules'), tr('picoripi'))
        self.mode_combo.addItem(tr('Custom recipe'), tr('custom'))
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.mode_combo.setVisible(False)

        # Top row: Progress stages (Breadcrumbs) + Save status (On the same level)
        top_header = QHBoxLayout()
        top_header.setContentsMargins(0, 2, 0, 2)

        # Progress stages bar (Breadcrumbs)
        self.progress_layout = QHBoxLayout()
        self.progress_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_layout.setSpacing(6)

        self.stage_source_label = QLabel(tr('1. Source'))
        self.stage_line1_label = QLabel(tr(' ── '))
        self.stage_markup_label = QLabel(tr('2. Markup'))
        self.stage_line2_label = QLabel(tr(' ── '))
        self.stage_review_label = QLabel(tr('3. Review'))
        self.stage_line3_label = QLabel(tr(' ── '))
        self.stage_mempalace_label = QLabel(tr('4. MemPalace'))

        stage_font = QFont()
        stage_font.setPointSize(9)
        stage_font.setBold(True)
        for label in (self.stage_source_label, self.stage_markup_label, self.stage_review_label, self.stage_mempalace_label):
            label.setFont(stage_font)
            label.setStyleSheet("color:#8a8a8a;")

        line_font = QFont()
        line_font.setPointSize(9)
        for label in (self.stage_line1_label, self.stage_line2_label, self.stage_line3_label):
            label.setFont(line_font)
            label.setStyleSheet("color:#ccc;")

        self.progress_layout.addWidget(self.stage_source_label)
        self.progress_layout.addWidget(self.stage_line1_label)
        self.progress_layout.addWidget(self.stage_markup_label)
        self.progress_layout.addWidget(self.stage_line2_label)
        self.progress_layout.addWidget(self.stage_review_label)
        self.progress_layout.addWidget(self.stage_line3_label)
        self.progress_layout.addWidget(self.stage_mempalace_label)

        top_header.addLayout(self.progress_layout)
        top_header.addStretch(1)

        self.save_status_label = QLabel(tr('Project saved ✓'))
        self.save_status_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #107c41;")
        top_header.addWidget(self.save_status_label)
        root.addLayout(top_header)

        # Next Action Panel (initialized, will be added to outline_layout later)
        self.next_action_box = QWidget(self)
        self.next_action_box.setStyleSheet(
            "QWidget { background: #fdfdfd; border: 1px solid #e0e0e0; border-radius: 4px; }"
        )
        next_layout = QVBoxLayout(self.next_action_box)
        next_layout.setContentsMargins(8, 8, 8, 8)
        next_layout.setSpacing(6)

        self.next_action_desc_label = QLabel(tr('No script or project loaded yet.'))
        self.next_action_desc_label.setStyleSheet("font-size: 11px; color: #444; border: none; background: transparent;")
        self.next_action_desc_label.setWordWrap(True)
        next_layout.addWidget(self.next_action_desc_label)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)

        self.next_action_btn = QPushButton(tr('Open Script or Project…'))
        self.next_action_btn.setToolTip(tr('Execute the recommended next action.'))
        self.next_action_btn.setAutoDefault(False)
        self.next_action_btn.setStyleSheet(
            "QPushButton { background: #0f6cbd; color: white; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 4px 10px; min-height: 22px; border: none; }"
            "QPushButton:hover { background: #115ea3; }"
            "QPushButton:pressed { background: #0c5289; }"
        )
        self.next_action_btn.clicked.connect(self._on_next_action_clicked)
        btn_layout.addWidget(self.next_action_btn)

        self.next_action_secondary_btn = QPushButton(tr('AI Fill Remaining…'))
        self.next_action_secondary_btn.setToolTip(tr('Fill the remaining unmarked lines using AI.'))
        self.next_action_secondary_btn.setAutoDefault(False)
        self.next_action_secondary_btn.setStyleSheet(
            "QPushButton { background: #f7f7f7; border: 1px solid #b8b8b8; color: #333; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 4px 10px; min-height: 22px; }"
            "QPushButton:hover { background: #ffffff; border-color: #8a8a8a; }"
            "QPushButton:pressed { background: #e9e9e9; }"
        )
        self.next_action_secondary_btn.clicked.connect(self._run_hierarchy_ai_markup)
        self.next_action_secondary_btn.setVisible(False)
        btn_layout.addWidget(self.next_action_secondary_btn)
        btn_layout.addStretch(1)
        next_layout.addLayout(btn_layout)

        # Control Row buttons
        control_row = QHBoxLayout()
        control_row.setSpacing(6)

        # File menu button
        self.file_btn = QPushButton(tr('File ▾'))
        self.file_btn.setToolTip(tr('Open script, open/save projects, or close Markup Studio.'))
        self.file_menu = QMenu(self.file_btn)
        self.file_btn.setMenu(self.file_menu)

        self.load_btn = self._add_menu_action(
            self.file_menu,
            "Open script...",
            self._load_file,
            "Open a raw walkthrough/script file.",
        )
        self.load_markup_btn = self._add_menu_action(
            self.file_menu,
            "Open project...",
            self._load_hierarchy_project,
            "Open a saved markup project.",
        )
        self.file_menu.addSeparator()
        self.save_btn_menu = self._add_menu_action(
            self.file_menu,
            "Save",
            self._quick_save_project,
            "Save the current project to the open file.",
        )
        self.save_markup_btn = self._add_menu_action(
            self.file_menu,
            "Save As...",
            self._save_hierarchy_project,
            "Save the current project to a new JSON file.",
        )
        self.file_menu.addSeparator()
        self._add_menu_action(
            self.file_menu,
            "Close",
            self.close,
            "Close Script Markup Studio.",
        )
        control_row.addWidget(self.file_btn)

        # Quick Save button
        self.quick_save_btn = QPushButton(tr('Save'))
        self.quick_save_btn.setToolTip(tr('Quick save changes (Ctrl+S).'))
        self.quick_save_btn.clicked.connect(self._quick_save_project)
        control_row.addWidget(self.quick_save_btn)

        # Undo / Redo
        self.undo_btn = QPushButton(tr('Undo'))
        self.undo_btn.setToolTip(tr('Undo the last action.'))
        self.undo_btn.clicked.connect(self._undo_history)
        control_row.addWidget(self.undo_btn)

        self.redo_btn = QPushButton(tr('Redo'))
        self.redo_btn.setToolTip(tr('Redo the undone action.'))
        self.redo_btn.clicked.connect(self._redo_history)
        control_row.addWidget(self.redo_btn)

        control_row.addStretch(1)

        # Add Auto-fill to control row
        self.auto_markup_menu_btn.setText(tr('Auto-fill ▾'))
        control_row.addWidget(self.auto_markup_menu_btn)

        # Advanced menu button
        self.advanced_btn = QPushButton(tr('Advanced ▾'), self)
        self.advanced_btn.setToolTip(tr('Advanced and legacy features menu.'))
        self.advanced_menu = QMenu(self.advanced_btn)
        self.advanced_btn.setMenu(self.advanced_menu)

        # Submenu: Template
        self.template_menu = QMenu(tr('Template'), self.advanced_menu)
        self.load_template_btn = self._add_menu_action(
            self.template_menu,
            "Open template...",
            self._load_hierarchy_template,
            "Open hierarchy type definitions from a template.",
        )
        self.save_template_btn = self._add_menu_action(
            self.template_menu,
            "Save template...",
            self._save_hierarchy_template,
            "Save current type definitions as a template.",
        )
        self.advanced_menu.addMenu(self.template_menu)

        # Submenu: Export
        self.export_menu = QMenu(tr('Export'), self.advanced_menu)
        self.preview_btn = self._add_menu_action(
            self.export_menu,
            "Preview result…",
            self._open_preview,
            "Show the standardized script markdown.",
        )
        self.export_btn = self._add_menu_action(
            self.export_menu,
            "Export game_script.md…",
            self._export,
            "Export current script to a Markdown file.",
        )
        self.advanced_menu.addMenu(self.export_menu)

        self._add_menu_action(
            self.advanced_menu,
            "Change Type Color...",
            self._choose_hierarchy_type_color,
            "Choose a color for the selected hierarchy type.",
        )

        # Submenu: Legacy tools
        self.legacy_menu = QMenu(tr('Legacy tools'), self.advanced_menu)
        self.action_mode_hierarchy = self.legacy_menu.addAction(tr('Rules mode: Hierarchy markup'))
        self.action_mode_hierarchy.setCheckable(True)
        self.action_mode_hierarchy.setChecked(self.mode == "hierarchy")
        self.action_mode_hierarchy.triggered.connect(lambda: self._set_rules_mode("hierarchy"))

        self.action_mode_picoripi = self.legacy_menu.addAction(tr('Rules mode: Picoripi rules'))
        self.action_mode_picoripi.setCheckable(True)
        self.action_mode_picoripi.setChecked(self.mode == "picoripi")
        self.action_mode_picoripi.triggered.connect(lambda: self._set_rules_mode("picoripi"))

        self.action_mode_custom = self.legacy_menu.addAction(tr('Rules mode: Custom recipe'))
        self.action_mode_custom.setCheckable(True)
        self.action_mode_custom.setChecked(self.mode == "custom")
        self.action_mode_custom.triggered.connect(lambda: self._set_rules_mode("custom"))

        self.legacy_menu.addSeparator()
        self.show_legacy_controls_action = self.legacy_menu.addAction(tr('Show legacy parser controls'))
        self.show_legacy_controls_action.setCheckable(True)
        self.show_legacy_controls_action.setChecked(False)
        self.show_legacy_controls_action.triggered.connect(self._toggle_legacy_controls)

        self.advanced_menu.addMenu(self.legacy_menu)
        control_row.addWidget(self.advanced_btn)

        # Hide other unparented / unmapped legacy widgets so they don't render at (0, 0)
        self.script_menu_btn.setVisible(False)
        self.project_menu_btn.setVisible(False)
        self.save_project_primary_btn.setVisible(False)
        self.finish_mempalace_btn.setVisible(False)
        self.template_menu_btn.setVisible(False)
        self.recipe_menu_btn.setVisible(False)

        # Help button
        self.help_btn = QPushButton(tr('? Help'))
        self.help_btn.setToolTip(tr('Open guide.'))
        self.help_btn.clicked.connect(self._show_help)
        control_row.addWidget(self.help_btn)

        root.addLayout(control_row)

        self.path_label = QLabel(tr('No file loaded'))
        self.path_label.setVisible(False)  # We hide it, but keep it for compatibility

        self.project_state_label = QLabel(tr('Markup project: Not saved'))
        self.project_state_label.setVisible(False)

        # Recipe flags + teach (custom engine only)
        controls = QHBoxLayout()
        self.recipe_box = QGroupBox(tr('Recipe'))
        flags_layout = QHBoxLayout(self.recipe_box)
        self.cb_gutter = QCheckBox(tr('Gutter speakers (Format B)'))
        self.cb_gutter.setToolTip(
            tr('Treat a standalone speaker name line as the speaker for the dialogue lines below it.')
        )
        self.cb_gutter.setChecked(self.recipe.gutter_speakers)
        self.cb_gutter.toggled.connect(self._on_flag_changed)
        flags_layout.addWidget(self.cb_gutter)
        self.cb_continuation = QCheckBox(tr('Join wrapped lines'))
        self.cb_continuation.setToolTip(
            tr('Join wrapped dialogue lines before previewing or exporting the standardized script.')
        )
        self.cb_continuation.setChecked(self.recipe.continuation)
        self.cb_continuation.toggled.connect(self._on_flag_changed)
        flags_layout.addWidget(self.cb_continuation)
        controls.addWidget(self.recipe_box)

        self.teach_box = QGroupBox(tr('Mark current line as…'))
        teach_layout = QHBoxLayout(self.teach_box)
        tooltips = {
            "speaker": "Open the speaker teacher: mark the NAME and the spoken TEXT separately — works for any separator.",
            "chapter": "Cursor on a chapter header with delimiters (=== Act One ===).",
            "location": "Cursor on a location header with delimiters (--- Ordon ---).",
            "ignore": "Cursor on a recurring noise line to drop every identical line (Ctrl+I).",
        }
        for label, kind in (("Speaker", "speaker"), ("Chapter", "chapter"),
                            ("Location", "location"), ("Ignore", "ignore")):
            btn = QPushButton(label)
            btn.setToolTip(tooltips[kind])
            if kind == "speaker":
                btn.clicked.connect(self._open_speaker_teacher)
            else:
                btn.clicked.connect(lambda _c, k=kind: self._teach_current_line(k))
            teach_layout.addWidget(btn)
        controls.addWidget(self.teach_box, 1)

        self.hierarchy_box = QGroupBox(tr('Mark selected text'))
        hierarchy_layout = QHBoxLayout(self.hierarchy_box)
        hierarchy_layout.addWidget(QLabel(tr('Depth:')))
        self.hierarchy_depth_spin = QSpinBox()
        self.hierarchy_depth_spin.setRange(0, 12)
        self.hierarchy_depth_spin.setToolTip(tr('0 is the top level; higher numbers are nested deeper.'))
        hierarchy_layout.addWidget(self.hierarchy_depth_spin)

        hierarchy_layout.addWidget(QLabel(tr('Type:')))
        self.hierarchy_type_combo = QComboBox()
        self.hierarchy_type_combo.setEditable(True)
        self.hierarchy_type_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.hierarchy_type_combo.setMinimumWidth(170)
        self.hierarchy_type_combo.setMinimumContentsLength(14)
        self.hierarchy_type_combo.setToolTip(
            tr('Choose the hierarchy mark type. Shortcuts: Ctrl+S Structure, Ctrl+P Speaker, Ctrl+T Text, Ctrl+B Breaker, Ctrl+I Ignore.')
        )
        for type_def in self.hierarchy_type_definitions.values():
            self._add_hierarchy_type_item(type_def)
        self.hierarchy_type_combo.lineEdit().setPlaceholderText(tr('Type or choose'))
        self.hierarchy_type_combo.lineEdit().setToolTip(self.hierarchy_type_combo.toolTip())
        self.hierarchy_type_combo.lineEdit().editingFinished.connect(
            self._finalize_hierarchy_type_text
        )
        self.hierarchy_type_combo.currentIndexChanged.connect(self._on_hierarchy_type_changed)
        hierarchy_layout.addWidget(self.hierarchy_type_combo)

        self.hierarchy_role_label = QLabel(tr('Role:'))
        hierarchy_layout.addWidget(self.hierarchy_role_label)
        self.hierarchy_role_combo = QComboBox()
        self.hierarchy_role_combo.addItem(tr('Speaker'), tr('speaker'))
        self.hierarchy_role_combo.addItem(tr('Item'), tr('item'))
        self.hierarchy_role_combo.setToolTip(
            tr('Speaker creates dialogue. Item creates a non-dialogue reference entry. For Text, Item automatically means Item Description.')
        )
        self.hierarchy_role_combo.currentIndexChanged.connect(
            self._on_hierarchy_role_changed
        )
        hierarchy_layout.addWidget(self.hierarchy_role_combo)

        self.hierarchy_label_edit = QLineEdit()
        self.hierarchy_label_edit.setPlaceholderText(tr('Label/text (optional)'))
        hierarchy_layout.addWidget(self.hierarchy_label_edit, 1)

        self.hierarchy_split_text_cb = QCheckBox(tr('Split paragraphs'))
        self.hierarchy_split_text_cb.setToolTip(
            tr('<b>Split paragraphs</b><br>Only has an effect when Type is <b>Text</b>; disabled otherwise.<br><br><b>Checked</b> — Apply mark makes one Text block per paragraph in the selection, splitting at blank lines and skipping empty ones. Use this for a run of dialogue where each paragraph is its own line of speech; assign the speakers afterwards from the tree.<br><b>Unchecked</b> — the whole selection becomes a single Text block.')
        )
        hierarchy_layout.addWidget(self.hierarchy_split_text_cb)

        self.hierarchy_color_btn = QPushButton(tr('Color'))
        self.hierarchy_color_btn.setMinimumWidth(82)
        self.hierarchy_color_btn.clicked.connect(self._choose_hierarchy_type_color)
        hierarchy_layout.addWidget(self.hierarchy_color_btn)

        self.hierarchy_mark_btn = QPushButton(tr('Apply mark'))
        self.hierarchy_mark_btn.setMinimumWidth(118)
        self.hierarchy_mark_btn.setToolTip(
            tr('Mark the current selection with the chosen Type (Ctrl+M). Quick types: Ctrl+S Structure, Ctrl+P Speaker, Ctrl+T Text, Ctrl+B Breaker, Ctrl+I Ignore.')
        )
        self.hierarchy_mark_btn.clicked.connect(self._mark_selection_as_hierarchy)
        hierarchy_layout.addWidget(self.hierarchy_mark_btn)

        self.hierarchy_clear_btn = QPushButton(tr('Remove mark'))
        self.hierarchy_clear_btn.setMinimumWidth(98)
        self.hierarchy_clear_btn.clicked.connect(self._clear_selected_hierarchy_marks)
        hierarchy_layout.addWidget(self.hierarchy_clear_btn)
        controls.addWidget(self.hierarchy_box, 2)
        self._on_hierarchy_type_changed()
        self._update_hierarchy_edit_controls()
        root.addLayout(controls)

        # Timeline range (legacy parser modes only).
        self.range_panel = QWidget()
        range_row = QHBoxLayout(self.range_panel)
        range_row.setContentsMargins(0, 0, 0, 0)
        self.range_label = QLabel(tr('Timeline range: full file'))
        self.range_label.setStyleSheet("color:#666;")
        range_row.addWidget(self.range_label, 1)
        self.start_range_btn = QPushButton(tr('Start from cursor'))
        self.start_range_btn.setToolTip(
            tr('Legacy parser helper: skip everything before the current line (table of contents, cast list, legal text).')
        )
        self.start_range_btn.clicked.connect(self._set_timeline_start)
        range_row.addWidget(self.start_range_btn)
        self.end_range_btn = QPushButton(tr('End at cursor'))
        self.end_range_btn.setToolTip(
            tr('Legacy parser helper: skip everything after the current line (appendices, credits, non-story notes).')
        )
        self.end_range_btn.clicked.connect(self._set_timeline_end)
        range_row.addWidget(self.end_range_btn)
        self.clear_range_btn = QPushButton(tr('Use full file'))
        self.clear_range_btn.setToolTip(tr('Legacy parser helper: remove the start/end crop.'))
        self.clear_range_btn.clicked.connect(self._clear_timeline_range)
        range_row.addWidget(self.clear_range_btn)
        root.addWidget(self.range_panel)

        # Main workspace: raw script on the left, outline tree on the right.
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.raw_panel = QWidget()
        raw_layout = QVBoxLayout(self.raw_panel)
        raw_layout.setContentsMargins(0, 0, 0, 0)
        raw_header = QHBoxLayout()
        raw_header.setContentsMargins(0, 0, 0, 0)
        # Search line and status indicator layout
        raw_header.addWidget(QLabel(tr('Find:')))
        self.search_edit = _SearchLineEdit()
        self.search_edit.setPlaceholderText(tr('Search raw script'))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(220)
        self.search_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_edit.setToolTip(
            tr('Search raw script (Ctrl+F). Press Enter for the next match or Shift+Enter for the previous match.')
        )
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.search_edit.findNextRequested.connect(self._find_next_search_match)
        self.search_edit.findPreviousRequested.connect(self._find_previous_search_match)
        raw_header.addWidget(self.search_edit, 1)

        self.search_prev_btn = QPushButton(tr('Prev'))
        self.search_prev_btn.setToolTip(
            tr('Jump to the previous search match in the raw script (Shift+Enter in Find).')
        )
        self.search_prev_btn.clicked.connect(self._find_previous_search_match)
        raw_header.addWidget(self.search_prev_btn)

        self.search_next_btn = QPushButton(tr('Next'))
        self.search_next_btn.setToolTip(
            tr('Jump to the next search match in the raw script (Enter in Find).')
        )
        self.search_next_btn.clicked.connect(self._find_next_search_match)
        raw_header.addWidget(self.search_next_btn)

        self.search_case_cb = QCheckBox(tr('Aa'))
        self.search_case_cb.setToolTip(tr('Only match text with the same uppercase/lowercase letters.'))
        self.search_case_cb.toggled.connect(self._on_search_options_changed)
        raw_header.addWidget(self.search_case_cb)

        self.search_word_cb = QCheckBox(tr('Word'))
        self.search_word_cb.setToolTip(tr('Only match complete words, not text inside longer words.'))
        self.search_word_cb.toggled.connect(self._on_search_options_changed)
        raw_header.addWidget(self.search_word_cb)

        self.search_regex_cb = QCheckBox(tr('.*'))
        self.search_regex_cb.setToolTip(tr('Interpret the search text as a regular expression pattern.'))
        self.search_regex_cb.toggled.connect(self._on_search_options_changed)
        raw_header.addWidget(self.search_regex_cb)

        self.search_status_label = QLabel(tr(''))
        self.search_status_label.setMinimumWidth(48)
        self.search_status_label.setStyleSheet("color:#666;")
        raw_header.addWidget(self.search_status_label)

        self.raw_label = QLabel(tr(''))
        raw_header.addWidget(self.raw_label)
        raw_layout.addLayout(raw_header)

        self.raw_edit = _ScriptMarkupRawEdit(self)
        self.raw_edit.setFont(QFont("Consolas", 10))
        self.raw_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.raw_edit.document().contentsChange.connect(self._on_raw_contents_change)
        self.raw_edit.textChanged.connect(self._on_raw_text_changed)
        self.highlighter = _ClassificationHighlighter(self.raw_edit.document())
        raw_layout.addWidget(self.raw_edit, 1)
        self.main_splitter.addWidget(self.raw_panel)

        self.outline_panel = QWidget()
        self.outline_panel.setMinimumWidth(260)
        outline_layout = QVBoxLayout(self.outline_panel)
        outline_layout.setContentsMargins(0, 0, 0, 0)
        outline_layout.setSpacing(4)
        outline_header = QHBoxLayout()
        outline_header.setContentsMargins(0, 0, 0, 0)
        self.outline_label = QLabel(tr('Script tree (double-click to jump):'))
        self.outline_label.setToolTip(
            tr('Double-click a node to jump to source. Press F2, use Rename node, or click an already selected node to rename.')
        )
        outline_header.addWidget(self.outline_label)
        outline_header.addStretch(1)
        self.expand_tree_btn = QPushButton(tr('Expand all'))
        self.expand_tree_btn.setToolTip(tr('Expand every node in the script tree.'))
        self.expand_tree_btn.clicked.connect(self._expand_outline_all)
        outline_header.addWidget(self.expand_tree_btn)
        self.collapse_tree_btn = QPushButton(tr('Collapse all'))
        self.collapse_tree_btn.setToolTip(tr('Collapse every node in the script tree.'))
        self.collapse_tree_btn.clicked.connect(self._collapse_outline_all)
        outline_header.addWidget(self.collapse_tree_btn)
        outline_layout.addLayout(outline_header)
        self.outline_search_edit = QLineEdit()
        self.outline_search_edit.setPlaceholderText(tr('Search tree…'))
        self.outline_search_edit.setClearButtonEnabled(True)
        self.outline_search_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.outline_search_edit.setToolTip(
            tr('Filter the script tree or review queue. Matching branches are expanded automatically.')
        )
        self.outline_search_edit.textChanged.connect(self._on_outline_search_changed)
        outline_layout.addWidget(self.outline_search_edit)
        self.flags_list = _ScriptTreeWidget(self)
        self.flags_list.setToolTip(
            tr('Double-click a node to jump to source. Press F2, use Rename node, or click an already selected node to rename.')
        )
        self.flags_list.setHeaderHidden(True)
        self.flags_list.setAlternatingRowColors(True)
        self.flags_list.setUniformRowHeights(True)
        self.flags_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.flags_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.flags_list.setDragEnabled(True)
        self.flags_list.setAcceptDrops(True)
        self.flags_list.setDropIndicatorShown(True)
        self.flags_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.flags_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.flags_list.itemDoubleClicked.connect(self._jump_to_flag)
        self.flags_list.itemExpanded.connect(self._on_outline_item_expanded)
        self.flags_list.itemCollapsed.connect(self._on_outline_item_collapsed)
        self.flags_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.flags_list.customContextMenuRequested.connect(self._show_outline_context_menu)
        outline_layout.addWidget(self.flags_list, 1)

        # Next Action Box under tree
        outline_layout.addWidget(self.next_action_box)

        # Bottom status bar at the very bottom of the dialog
        bottom_status_layout = QHBoxLayout()
        bottom_status_layout.setContentsMargins(4, 2, 4, 2)
        bottom_status_layout.setSpacing(10)

        self.legend_label = CompactLegendLabel(self)
        bottom_status_layout.addWidget(self.legend_label, 1)

        self.stats_label = CompactStatsLabel(self)
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bottom_status_layout.addWidget(self.stats_label)

        self.main_splitter.addWidget(self.outline_panel)
        self.main_splitter.setStretchFactor(0, 4)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([680, 280])
        root.addWidget(self.main_splitter, 1)
        root.addLayout(bottom_status_layout)



        self.find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.find_shortcut.activated.connect(self._focus_search)
        self.mark_shortcut = QShortcut(QKeySequence("Ctrl+M"), self)
        self.mark_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.mark_shortcut.activated.connect(self._activate_mark_shortcut)
        self.ignore_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        self.ignore_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.ignore_shortcut.activated.connect(self._activate_ignore_shortcut)
        self.structure_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.structure_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.structure_shortcut.activated.connect(
            lambda: self._activate_hierarchy_type_shortcut(HierarchyType.STRUCTURE)
        )
        self.speaker_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        self.speaker_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.speaker_shortcut.activated.connect(
            lambda: self._activate_hierarchy_type_shortcut(HierarchyType.SPEAKER)
        )
        self.text_shortcut = QShortcut(QKeySequence("Ctrl+T"), self)
        self.text_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.text_shortcut.activated.connect(
            lambda: self._activate_hierarchy_type_shortcut(HierarchyType.TEXT)
        )
        self.breaker_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self.breaker_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.breaker_shortcut.activated.connect(
            lambda: self._activate_hierarchy_type_shortcut(HierarchyType.BREAKER)
        )
        self.undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        self.undo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.undo_shortcut.activated.connect(self._undo_history)
        self.redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        self.redo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.redo_shortcut.activated.connect(self._redo_history)
        self._disable_default_buttons()

    def _apply_studio_style(self):
        arrow_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "resources", "icons", "chevron-down.svg")
        ).replace("\\", "/")
        style = """
            QPushButton {
                background: #f7f7f7;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                padding: 3px 10px;
                min-height: 24px;
            }
            QPushButton:hover {
                background: #ffffff;
                border-color: #8a8a8a;
            }
            QPushButton:pressed {
                background: #e9e9e9;
            }
            QComboBox {
                background: #ffffff;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                padding: 3px 26px 3px 8px;
                min-height: 24px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border-left: 1px solid #c9c9c9;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                background: #f1f1f1;
            }
            QComboBox::down-arrow {
                image: url("CHEVRON_DOWN_PATH");
                width: 12px;
                height: 12px;
            }
            QSpinBox {
                background: #ffffff;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                min-height: 24px;
                padding-left: 6px;
            }
            QLineEdit {
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                padding: 3px 7px;
                min-height: 24px;
            }
            QTreeWidget {
                border: 1px solid #b8b8b8;
                background: #ffffff;
                alternate-background-color: #f7f7f7;
            }
            QTreeWidget::item:selected {
                background: #0f6cbd;
                color: #ffffff;
            }
            QTreeWidget::item:selected:!active {
                background: #a8d0f0;
                color: #111111;
            }
        """
        self.setStyleSheet(style.replace("CHEVRON_DOWN_PATH", arrow_path))

    def _hierarchy_legend_html(self) -> str:
        if not self.hierarchy_marks and not self._has_unmarked_hierarchy_lines:
            return ""
        used_types = []
        for mark in self.hierarchy_marks:
            if mark.type_id not in used_types:
                used_types.append(mark.type_id)
        if self._has_unmarked_hierarchy_lines and HierarchyType.UNMARKED not in used_types:
            used_types.append(HierarchyType.UNMARKED)

        parts = []
        for type_id in used_types:
            type_def = self.hierarchy_type_definitions.get(type_id)
            if not type_def:
                continue
            parts.append(
                f'<span style="background:{type_def.color}; padding:1px 5px; '
                f'border:1px solid #ccc;">{type_def.label}</span>'
            )
        return " ".join(parts)

    def _update_legend(self):
        html = self._hierarchy_legend_html() if self.mode == "hierarchy" else ""
        self.legend_label.setText(html)
        self.legend_label.setVisible(bool(html))

    def _update_raw_minimap(self):
        if hasattr(self, "raw_edit") and hasattr(self.raw_edit, "_sync_viewport_margins"):
            if hasattr(self.raw_edit, "minimap"):
                self.raw_edit.minimap.invalidate()
            self.raw_edit._sync_viewport_margins()

