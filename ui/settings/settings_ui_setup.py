from pathlib import Path
import pycountry
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from utils.logging_utils import log_debug
from components.labeled_spinbox import LabeledSpinBox
from components.dictionary_manager_dialog import DictionaryManagerDialog
from core.translation.config import build_default_translation_config, merge_translation_config
from .settings_widgets import ColorPickerButton, TagDisplayWidget

class SettingsDialogUiMixin:
    def setup_general_tab(self):
        layout = QFormLayout(self.general_tab)
        
        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(["Auto", "Light", "Dark"])
        layout.addRow(QLabel("Theme (requires restart):"), self.theme_combo)
        
        self.plugin_combo = QComboBox(self)
        self.populate_plugin_list()
        layout.addRow(QLabel("Active Game Plugin:"), self.plugin_combo)
        
        self.font_size_spinbox = LabeledSpinBox("Application Font Size:", 6, 24, 10, parent=self)
        layout.addRow(self.font_size_spinbox)
        
        self.show_spaces_checkbox = QCheckBox("Show special spaces as dots", self)
        layout.addRow(self.show_spaces_checkbox)
        
        self.space_dot_color_picker = ColorPickerButton(parent=self)
        layout.addRow("Space Dot Color:", self.space_dot_color_picker)
        
        self.restore_session_checkbox = QCheckBox("Restore unsaved session on startup", self)
        self.restore_session_checkbox.setToolTip("If unchecked, any unsaved changes will be discarded on close.")
        layout.addRow(self.restore_session_checkbox)

        self.prompt_editor_checkbox = QCheckBox("Show prompt editor before AI requests", self)
        layout.addRow(self.prompt_editor_checkbox)

        self.plugin_combo.activated.connect(self.on_plugin_changed)
        self.theme_combo.activated.connect(self.on_theme_changed)


    def setup_plugin_tab(self):
        plugin_layout = QVBoxLayout(self.plugin_tab)
        self.plugin_tabs = QTabWidget(self.plugin_tab)
        plugin_layout.addWidget(self.plugin_tabs)
        self.rebuild_plugin_tabs()

    def rebuild_plugin_tabs(self):
        while self.plugin_tabs.count():
            self.plugin_tabs.removeTab(0)

        paths_tab = QWidget()
        display_tab = QWidget()
        rules_tab = QWidget()
        detection_tab = QWidget()
        autofix_tab = QWidget()
        context_tags_tab = QWidget()

        self.plugin_tabs.addTab(paths_tab, "File Paths")
        self.plugin_tabs.addTab(display_tab, "Display")
        self.plugin_tabs.addTab(rules_tab, "Rules")
        self.plugin_tabs.addTab(context_tags_tab, "Context Tags")
        self.plugin_tabs.addTab(detection_tab, "Detection")
        self.plugin_tabs.addTab(autofix_tab, "Auto-fix")

        self._setup_paths_subtab(paths_tab)
        self._setup_display_subtab(display_tab)
        self._setup_rules_subtab(rules_tab)
        self._setup_context_tags_subtab(context_tags_tab)
        
        self.detection_checkboxes.clear()
        self.autofix_checkboxes.clear()
        self._setup_detection_subtab(detection_tab)
        self._setup_autofix_subtab(autofix_tab)

    def setup_spelling_tab(self):
        layout = QFormLayout(self.spelling_tab)
        
        self.spellcheck_enabled_checkbox = QCheckBox("Enable spell checking", self)
        layout.addRow(self.spellcheck_enabled_checkbox)
        
        self.spellcheck_language_combo = QComboBox(self)
        layout.addRow("Dictionary Language:", self.spellcheck_language_combo)
        
        manage_button = QPushButton("Manage Dictionaries...", self)
        manage_button.clicked.connect(self._open_dictionary_manager)
        layout.addRow(manage_button)
        
        self.populate_spellchecker_languages()

    def _open_dictionary_manager(self):
        dialog = DictionaryManagerDialog(self)
        dialog.exec_()
        self.populate_spellchecker_languages()

    def populate_spellchecker_languages(self):
        current_lang_data = self.spellcheck_language_combo.currentData()
        self.spellcheck_language_combo.clear()
        if self.mw and self.mw.spellchecker_manager:
            available_dicts = self.mw.spellchecker_manager.scan_local_dictionaries()
            for lang_code in sorted(available_dicts.keys()):
                display_name = self._get_lang_name(lang_code)
                self.spellcheck_language_combo.addItem(f"{display_name} ({lang_code})", lang_code)
        
        if current_lang_data:
            index = self.spellcheck_language_combo.findData(current_lang_data)
            if index != -1:
                self.spellcheck_language_combo.setCurrentIndex(index)

    def _populate_font_list(self, plugin_dir_name: str):
        self.font_file_combo.clear()
        self.font_file_combo.addItem("None", "")

        if not plugin_dir_name:
            return
            
        fonts_dir = Path("plugins") / plugin_dir_name / "fonts"
        if fonts_dir.is_dir():
            for font_path in sorted(fonts_dir.iterdir()):
                if font_path.suffix.lower() == ".json":
                    self.font_file_combo.addItem(font_path.name, font_path.name)

    def _setup_display_subtab(self, tab):
        layout = QFormLayout(tab)
        self.font_file_combo = QComboBox(self)
        layout.addRow("Default Font for Plugin:", self.font_file_combo)
        
        self.preview_wrap_checkbox = QCheckBox("Wrap lines in preview panel", self)
        layout.addRow(self.preview_wrap_checkbox)
        self.editors_wrap_checkbox = QCheckBox("Wrap lines in editor panels", self)
        layout.addRow(self.editors_wrap_checkbox)
        self.newline_symbol_edit = QLineEdit(self)
        layout.addRow("Newline Symbol:", self.newline_symbol_edit)

        newline_style_row = QWidget(self)
        nlr = QHBoxLayout(newline_style_row); nlr.setContentsMargins(0,0,0,0)
        self.newline_color_picker = ColorPickerButton(parent=self)
        self.newline_bold_chk = QCheckBox("Bold", self)
        self.newline_italic_chk = QCheckBox("Italic", self)
        self.newline_underline_chk = QCheckBox("Underline", self)
        nlr.addWidget(self.newline_color_picker)
        nlr.addWidget(self.newline_bold_chk)
        nlr.addWidget(self.newline_italic_chk)
        nlr.addWidget(self.newline_underline_chk)
        nlr.addStretch(1)
        layout.addRow("Newline Symbol Style:", newline_style_row)

        tag_style_row = QWidget(self)
        tsr = QHBoxLayout(tag_style_row); tsr.setContentsMargins(0,0,0,0)
        self.tag_color_picker = ColorPickerButton(parent=self)
        self.tag_bold_chk = QCheckBox("Bold", self)
        self.tag_italic_chk = QCheckBox("Italic", self)
        self.tag_underline_chk = QCheckBox("Underline", self)
        tsr.addWidget(self.tag_color_picker)
        tsr.addWidget(self.tag_bold_chk)
        tsr.addWidget(self.tag_italic_chk)
        tsr.addWidget(self.tag_underline_chk)
        tsr.addStretch(1)
        layout.addRow("Tag Style:", tag_style_row)

    def on_rules_changed(self):
        self.rules_changed_requires_rescan = True
        log_debug("SettingsDialog: Rules changed, marked for rescan.")

    def _setup_rules_subtab(self, tab):
        layout = QFormLayout(tab)
        self.game_dialog_width_spinbox = LabeledSpinBox("Game Dialog Max Width (px):", 100, 10000, 240, parent=self)
        self.game_dialog_width_spinbox.spin_box.valueChanged.connect(self.on_rules_changed)
        layout.addRow(self.game_dialog_width_spinbox)
        
        self.width_warning_spinbox = LabeledSpinBox("Editor Line Width Warning (px):", 100, 10000, 208, parent=self)
        self.width_warning_spinbox.spin_box.valueChanged.connect(self.on_rules_changed)
        layout.addRow(self.width_warning_spinbox)

        self.lines_per_page_spinbox = LabeledSpinBox("Lines Per Page:", 1, 20, 4, parent=self)
        self.lines_per_page_spinbox.spin_box.valueChanged.connect(self.on_rules_changed)
        layout.addRow(self.lines_per_page_spinbox)

    def _setup_context_tags_subtab(self, tab):
        layout = QVBoxLayout(tab)
        
        # Search Filter
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Filter Tags:"))
        self.tags_search_edit = QLineEdit(self)
        self.tags_search_edit.setPlaceholderText("Search by hex, emoji, or tag name...")
        self.tags_search_edit.setClearButtonEnabled(True)
        self.tags_search_edit.textChanged.connect(self._filter_tags_tables)
        search_layout.addWidget(self.tags_search_edit)
        layout.addLayout(search_layout)
        
        # Single Tags
        single_group = QGroupBox("Single Tags (RMB without selection)", self)
        single_layout = QVBoxLayout(single_group)
        self.single_tags_table = QTableWidget(0, 2, self)
        self.single_tags_table.setHorizontalHeaderLabels(["Display (Emoji/Hex)", "Tag"])
        
        header = self.single_tags_table.horizontalHeader()
        try:
            from PyQt5.QtWidgets import QHeaderView
            header.setSectionResizeMode(QHeaderView.Stretch)
        except ImportError:
            header.setStretchLastSection(True)
            
        self.single_tags_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.single_tags_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(pos, self.single_tags_table))
        self.single_tags_table.mouseDoubleClickEvent = lambda e: self._handle_table_double_click(e, self.single_tags_table)
        single_layout.addWidget(self.single_tags_table)
        
        single_btn_row = QHBoxLayout()
        add_single_btn = QPushButton("Add Row", self)
        add_single_btn.clicked.connect(lambda: self._add_table_row(self.single_tags_table))
        remove_single_btn = QPushButton("Remove Row", self)
        remove_single_btn.clicked.connect(lambda: self._remove_table_row(self.single_tags_table))
        single_btn_row.addWidget(add_single_btn); single_btn_row.addWidget(remove_single_btn)
        single_layout.addLayout(single_btn_row)
        layout.addWidget(single_group)
        
        # Wrap Tags
        wrap_group = QGroupBox("Wrap Tags (RMB with selection)", self)
        wrap_layout = QVBoxLayout(wrap_group)
        self.wrap_tags_table = QTableWidget(0, 3, self)
        self.wrap_tags_table.setHorizontalHeaderLabels(["Display (Emoji/Hex)", "Opening Tag", "Closing Tag"])
        
        header_wrap = self.wrap_tags_table.horizontalHeader()
        try:
            from PyQt5.QtWidgets import QHeaderView
            header_wrap.setSectionResizeMode(QHeaderView.Stretch)
        except ImportError:
            header_wrap.setStretchLastSection(True)
            
        self.wrap_tags_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.wrap_tags_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(pos, self.wrap_tags_table))
        self.wrap_tags_table.mouseDoubleClickEvent = lambda e: self._handle_table_double_click(e, self.wrap_tags_table)
        wrap_layout.addWidget(self.wrap_tags_table)
        
        wrap_btn_row = QHBoxLayout()
        add_wrap_btn = QPushButton("Add Row", self)
        add_wrap_btn.clicked.connect(lambda: self._add_table_row(self.wrap_tags_table))
        remove_wrap_btn = QPushButton("Remove Row", self)
        remove_wrap_btn.clicked.connect(lambda: self._remove_table_row(self.wrap_tags_table))
        wrap_btn_row.addWidget(add_wrap_btn); wrap_btn_row.addWidget(remove_wrap_btn)
        wrap_layout.addLayout(wrap_btn_row)
        layout.addWidget(wrap_group)

    def _handle_table_double_click(self, event, table):
        item = table.itemAt(event.pos())
        if item is None:
            row = table.rowAt(event.pos().y())
            if row == -1:
                self._add_table_row(table)
            else:
                self._add_table_row(table, insert_at_row=row + 1)
        else:
            QTableWidget.mouseDoubleClickEvent(table, event)

    def _show_table_context_menu(self, pos, table):
        menu = QMenu(self)
        
        item = table.itemAt(pos)
        clicked_row = item.row() if item else -1
        
        if clicked_row == -1:
            clicked_row = table.rowAt(pos.y())
            
        selected_rows = sorted(list(set([i.row() for i in table.selectedItems()])))
        if clicked_row != -1 and clicked_row not in selected_rows:
            selected_rows = [clicked_row]
            
        add_action = menu.addAction("Add Row")
        clone_action = menu.addAction(f"Clone Row{'s' if len(selected_rows) > 1 else ''}")
        delete_action = menu.addAction(f"Delete Row{'s' if len(selected_rows) > 1 else ''}")
        
        if not selected_rows:
            clone_action.setEnabled(False)
            delete_action.setEnabled(False)
            
        action = menu.exec_(table.viewport().mapToGlobal(pos))
        
        if action == add_action:
            if clicked_row != -1:
                self._add_table_row(table, insert_at_row=clicked_row + 1)
            else:
                self._add_table_row(table)
        elif action == clone_action:
            for row in reversed(selected_rows):
                widget = table.cellWidget(row, 0)
                disp = widget.text() if widget else ""
                
                item1 = table.item(row, 1)
                col1 = item1.text() if item1 else ""
                
                col2 = ""
                if table.columnCount() > 2:
                    item2 = table.item(row, 2)
                    col2 = item2.text() if item2 else ""
                    
                self._add_table_row(table, display_text=disp, col1=col1, col2=col2, insert_at_row=row + 1)
        elif action == delete_action:
            for row in reversed(selected_rows):
                table.removeRow(row)

    def _add_table_row(self, table, display_text="", col1="", col2="", insert_at_row=None):
        sorting_was_enabled = table.isSortingEnabled()
        if sorting_was_enabled:
            table.setSortingEnabled(False)
            
        if insert_at_row is not None:
            row = insert_at_row
        else:
            row = table.rowCount()
        table.insertRow(row)
        
        disp_item = QTableWidgetItem()
        disp_item.setData(Qt.DisplayRole, display_text)
        table.setItem(row, 0, disp_item)
        
        widget = TagDisplayWidget(display_text, table)
        widget.textChanged.connect(lambda txt, i=disp_item: i.setData(Qt.DisplayRole, txt))
        table.setCellWidget(row, 0, widget)
        
        table.setItem(row, 1, QTableWidgetItem(col1))
        
        if table.columnCount() > 2:
            table.setItem(row, 2, QTableWidgetItem(col2))
            
        if sorting_was_enabled:
            table.setSortingEnabled(True)

    def _filter_tags_tables(self, text):
        search_text = text.lower()
        for table in (self.single_tags_table, self.wrap_tags_table):
            for r in range(table.rowCount()):
                row_matches = False
                for c in range(table.columnCount()):
                    widget = table.cellWidget(r, c)
                    if widget and isinstance(widget, TagDisplayWidget):
                        cell_text = widget.text().lower()
                    else:
                        item = table.item(r, c)
                        cell_text = item.text().lower() if item else ""
                    if search_text in cell_text:
                        row_matches = True
                        break
                table.setRowHidden(r, not row_matches)

    def _remove_table_row(self, table):
        curr = table.currentRow()
        if curr != -1: table.removeRow(curr)
        elif table.rowCount() > 0: table.removeRow(table.rowCount() - 1)

    def _setup_paths_subtab(self, tab):
        layout = QFormLayout(tab)
        self.original_path_edit = QLineEdit(self)
        self.original_path_edit.setObjectName("PathLineEdit")
        self.edited_path_edit = QLineEdit(self)
        self.edited_path_edit.setObjectName("PathLineEdit")
        layout.addRow("Original File Path:", self._create_path_selector(self.original_path_edit))
        layout.addRow("Changes File Path:", self._create_path_selector(self.edited_path_edit))

    def _populate_checkbox_subtab(self, tab, checkbox_dict, title):
        layout = QFormLayout(tab)
        layout.addRow(QLabel(title))

        if not self.mw.current_game_rules:
            layout.addRow(QLabel("No game rules loaded."))
            return

        problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        if not problem_definitions:
            layout.addRow(QLabel("No problem definitions found in current plugin."))
            # Add a hint about potential fallback
            if self.mw.current_game_rules.get_display_name() == "Base Game (No Plugin)":
                layout.addRow(QLabel("<i>(Running in fallback mode due to plugin load error)</i>"))
            return

        sorted_problem_ids = sorted(
            problem_definitions.keys(),
            key=lambda pid: problem_definitions[pid].get("priority", 99)
        )

        for problem_id in sorted_problem_ids:
            definition = problem_definitions[problem_id]

            # Create a widget with color indicator and checkbox
            row_widget = QWidget(self)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            # Color indicator
            color_label = QLabel(self)
            color_label.setFixedSize(20, 20)
            problem_color = definition.get("color", QColor(200, 200, 200, 100))
            if isinstance(problem_color, QColor):
                # Use rgba() format to preserve alpha channel
                r, g, b, a = problem_color.red(), problem_color.green(), problem_color.blue(), problem_color.alpha()
                color_label.setStyleSheet(f"background-color: rgba({r}, {g}, {b}, {a}); border: 1px solid #888;")
                color_label.setToolTip(f"Problem color: rgba({r}, {g}, {b}, {a})")
            else:
                color_label.setStyleSheet(f"background-color: {problem_color}; border: 1px solid #888;")
                color_label.setToolTip(f"Problem color: {problem_color}")
            row_layout.addWidget(color_label)

            # Checkbox
            checkbox = QCheckBox(definition.get("name", problem_id), self)
            checkbox.setToolTip(definition.get("description", "No description available."))
            checkbox_dict[problem_id] = checkbox
            checkbox.stateChanged.connect(self.on_rules_changed)
            row_layout.addWidget(checkbox)
            row_layout.addStretch(1)

            layout.addRow(row_widget)

    def _setup_detection_subtab(self, tab):
        self._populate_checkbox_subtab(tab, self.detection_checkboxes, "Enable/disable problem detection:")

    def _setup_autofix_subtab(self, tab):
        self._populate_checkbox_subtab(tab, self.autofix_checkboxes, "Enable/disable auto-fix for specific problems:")

    def on_provider_changed(self, index):
        provider_key = self.translation_provider_combo.itemData(index)
        page_index = self.provider_page_map.get(provider_key, 0)
        self.ai_provider_pages.setCurrentIndex(page_index)

    def setup_ai_translation_tab(self):
        layout = QVBoxLayout(self.ai_translation_tab)
        provider_form = QFormLayout()
        self.translation_provider_combo = QComboBox(self)
        self.translation_provider_combo.addItem("Disabled", "disabled")
        self.translation_provider_combo.addItem("OpenAI", "openai_chat")

        self.translation_provider_combo.addItem("Ollama Chat", "ollama_chat")
        self.translation_provider_combo.addItem("DeepL", "deepl")
        self.translation_provider_combo.addItem("Gemini", "gemini")
        self.translation_provider_combo.addItem("Perplexity", "perplexity")
        provider_form.addRow("Active Provider:", self.translation_provider_combo)
        layout.addLayout(provider_form)

        self.ai_provider_pages = QStackedWidget(self)
        layout.addWidget(self.ai_provider_pages)

        disabled_page = QWidget()
        self.ai_provider_pages.addWidget(disabled_page)

        openai_group = QGroupBox("OpenAI", self.ai_translation_tab)
        openai_layout = QFormLayout(openai_group)
        self.openai_api_key_edit = QLineEdit(self)
        self.openai_api_key_edit.setEchoMode(QLineEdit.Password)
        self.openai_api_key_edit.setPlaceholderText("Bearer token")
        openai_layout.addRow("API Key:", self.openai_api_key_edit)
        self.openai_api_key_env_edit = QLineEdit(self)
        self.openai_api_key_env_edit.setPlaceholderText("OPENAI_API_KEY")
        openai_layout.addRow("API Key Env Var:", self.openai_api_key_env_edit)
        self.openai_base_url_edit = QLineEdit(self)
        self.openai_base_url_edit.setPlaceholderText("https://api.openai.com/v1 or http://127.0.0.1:8000")
        openai_layout.addRow("Base URL:", self.openai_base_url_edit)
        self.openai_model_edit = QLineEdit(self)
        self.openai_model_edit.setPlaceholderText("gpt-4o-mini")
        openai_layout.addRow("Model:", self.openai_model_edit)
        self.openai_temperature_spin = QDoubleSpinBox(self)
        self.openai_temperature_spin.setRange(0.0, 2.0); self.openai_temperature_spin.setDecimals(2); self.openai_temperature_spin.setSingleStep(0.05); self.openai_temperature_spin.setValue(0.0)
        openai_layout.addRow("Temperature:", self.openai_temperature_spin)
        self.openai_max_tokens_spin = QSpinBox(self)
        self.openai_max_tokens_spin.setRange(0, 200000); self.openai_max_tokens_spin.setSingleStep(100); self.openai_max_tokens_spin.setSpecialValueText("Provider default"); self.openai_max_tokens_spin.setValue(0)
        openai_layout.addRow("Max Output Tokens:", self.openai_max_tokens_spin)
        self.openai_timeout_spin = QSpinBox(self)
        self.openai_timeout_spin.setRange(1, 600); self.openai_timeout_spin.setSuffix(" s"); self.openai_timeout_spin.setValue(60)
        openai_layout.addRow("Request Timeout:", self.openai_timeout_spin)
        self.ai_provider_pages.addWidget(openai_group)



        ollama_group = QGroupBox("Ollama Chat API", self.ai_translation_tab)
        ollama_layout = QFormLayout(ollama_group)
        self.ollama_base_url_edit = QLineEdit(self); self.ollama_base_url_edit.setPlaceholderText("http://localhost:11434"); ollama_layout.addRow("Base URL:", self.ollama_base_url_edit)
        self.ollama_model_edit = QLineEdit(self); self.ollama_model_edit.setPlaceholderText("llama3"); ollama_layout.addRow("Model:", self.ollama_model_edit)
        self.ollama_temperature_spin = QDoubleSpinBox(self); self.ollama_temperature_spin.setRange(0.0, 2.0); self.ollama_temperature_spin.setDecimals(2); self.ollama_temperature_spin.setSingleStep(0.05); self.ollama_temperature_spin.setValue(0.0); ollama_layout.addRow("Temperature:", self.ollama_temperature_spin)
        self.ollama_timeout_spin = QSpinBox(self); self.ollama_timeout_spin.setRange(1, 600); self.ollama_timeout_spin.setSuffix(" s"); self.ollama_timeout_spin.setValue(120); ollama_layout.addRow("Request Timeout:", self.ollama_timeout_spin)
        self.ollama_keep_alive_edit = QLineEdit(self); self.ollama_keep_alive_edit.setPlaceholderText("e.g. 5m or leave blank"); ollama_layout.addRow("Keep Alive:", self.ollama_keep_alive_edit)
        self.ai_provider_pages.addWidget(ollama_group)

        deepl_group = QGroupBox("DeepL API", self.ai_translation_tab)
        deepl_layout = QFormLayout(deepl_group)
        self.deepl_api_key_edit = QLineEdit(self); self.deepl_api_key_edit.setEchoMode(QLineEdit.Password); self.deepl_api_key_edit.setPlaceholderText("DeepL API Key"); deepl_layout.addRow("API Key:", self.deepl_api_key_edit)
        self.deepl_server_url_edit = QLineEdit(self); self.deepl_server_url_edit.setPlaceholderText("e.g. https://api.deepl.com (Pro)"); deepl_layout.addRow("Server URL (Pro):", self.deepl_server_url_edit)
        self.ai_provider_pages.addWidget(deepl_group)

        gemini_group = QGroupBox("Google Gemini API", self.ai_translation_tab)
        gemini_layout = QFormLayout(gemini_group)
        self.gemini_base_url_edit = QLineEdit(self)
        self.gemini_base_url_edit.setPlaceholderText("Leave empty for native API")
        gemini_layout.addRow("Base URL (optional):", self.gemini_base_url_edit)
        self.gemini_api_key_edit = QLineEdit(self); self.gemini_api_key_edit.setEchoMode(QLineEdit.Password); self.gemini_api_key_edit.setPlaceholderText("Gemini API Key"); gemini_layout.addRow("API Key:", self.gemini_api_key_edit)
        self.gemini_model_edit = QLineEdit(self); self.gemini_model_edit.setPlaceholderText("gemini-1.5-flash-latest"); gemini_layout.addRow("Model:", self.gemini_model_edit)
        self.ai_provider_pages.addWidget(gemini_group)

        perplexity_group = QGroupBox("Perplexity API", self.ai_translation_tab)
        perplexity_layout = QFormLayout(perplexity_group)
        self.perplexity_api_key_edit = QLineEdit(self)
        self.perplexity_api_key_edit.setEchoMode(QLineEdit.Password)
        self.perplexity_api_key_edit.setPlaceholderText("Bearer token")
        perplexity_layout.addRow("API Key:", self.perplexity_api_key_edit)
        self.perplexity_base_url_edit = QLineEdit(self)
        self.perplexity_base_url_edit.setPlaceholderText("https://api.perplexity.ai")
        perplexity_layout.addRow("Base URL:", self.perplexity_base_url_edit)
        self.perplexity_model_edit = QLineEdit(self)
        self.perplexity_model_edit.setPlaceholderText("sonar-medium-8x7b-chat")
        perplexity_layout.addRow("Model:", self.perplexity_model_edit)
        self.perplexity_temperature_spin = QDoubleSpinBox(self)
        self.perplexity_temperature_spin.setRange(0.0, 2.0); self.perplexity_temperature_spin.setDecimals(2); self.perplexity_temperature_spin.setSingleStep(0.05); self.perplexity_temperature_spin.setValue(0.0)
        perplexity_layout.addRow("Temperature:", self.perplexity_temperature_spin)
        self.perplexity_max_tokens_spin = QSpinBox(self)
        self.perplexity_max_tokens_spin.setRange(0, 200000); self.perplexity_max_tokens_spin.setSingleStep(100); self.perplexity_max_tokens_spin.setSpecialValueText("Provider default"); self.perplexity_max_tokens_spin.setValue(0)
        perplexity_layout.addRow("Max Output Tokens:", self.perplexity_max_tokens_spin)
        self.perplexity_timeout_spin = QSpinBox(self)
        self.perplexity_timeout_spin.setRange(1, 600); self.perplexity_timeout_spin.setSuffix(" s"); self.perplexity_timeout_spin.setValue(60)
        perplexity_layout.addRow("Request Timeout:", self.perplexity_timeout_spin)
        self.ai_provider_pages.addWidget(perplexity_group)

        self.translation_provider_combo.currentIndexChanged.connect(self.on_provider_changed)
        self.openai_api_key_edit.textChanged.connect(self._refresh_glossary_api_key_from_translation)
        self.openai_api_key_env_edit.textChanged.connect(self._refresh_glossary_api_key_from_translation)

        self.gemini_api_key_edit.textChanged.connect(self._refresh_glossary_api_key_from_translation)
        layout.addStretch(1)

    def setup_ai_glossary_tab(self):
        layout = QFormLayout(self.ai_glossary_tab)

        self.glossary_provider_combo = QComboBox(self)
        # For now, let's keep it simple. We can expand this later.
        self.glossary_provider_combo.addItems(["OpenAI", "Ollama", "Gemini"])
        layout.addRow("Provider:", self.glossary_provider_combo)

        self.glossary_api_key_edit = QLineEdit(self)
        self.glossary_api_key_edit.setEchoMode(QLineEdit.Password)
        self.glossary_api_key_edit.setPlaceholderText("Provider API Key")
        layout.addRow("API Key:", self.glossary_api_key_edit)

        self.glossary_use_translation_key_checkbox = QCheckBox("Use API key from AI Translation", self)
        layout.addRow("", self.glossary_use_translation_key_checkbox)

        self.glossary_model_edit = QLineEdit(self)
        self.glossary_model_edit.setPlaceholderText("e.g., gpt-4o-mini")
        layout.addRow("Model:", self.glossary_model_edit)

        self.glossary_chunk_size_spin = QSpinBox(self)
        self.glossary_chunk_size_spin.setRange(1000, 32000)
        self.glossary_chunk_size_spin.setSingleStep(100)
        self.glossary_chunk_size_spin.setSuffix(" chars")
        layout.addRow("Text Chunk Size:", self.glossary_chunk_size_spin)

        self.glossary_use_translation_key_checkbox.stateChanged.connect(self._on_glossary_use_translation_key_changed)
        self.glossary_provider_combo.currentIndexChanged.connect(self._on_glossary_provider_changed)
        self.glossary_api_key_edit.textChanged.connect(self._on_glossary_api_key_changed)


    def _set_glossary_api_key_text(self, value: str) -> None:
        self._glossary_updating_api_key = True
        try:
            self.glossary_api_key_edit.setText(value or "")
        finally:
            self._glossary_updating_api_key = False

    def _get_translation_credentials_for_glossary(self, provider_name: str) -> dict:
        providers_cfg = {}
        if isinstance(self.translation_config_snapshot, dict):
            providers_cfg = self.translation_config_snapshot.get('providers', {}) or {}

        if provider_name == 'OpenAI':
            api_key = self.openai_api_key_edit.text().strip()
            if not api_key:
                api_key = providers_cfg.get('openai_chat', {}).get('api_key', '')

            api_key_env = self.openai_api_key_env_edit.text().strip()
            if not api_key_env:
                api_key_env = providers_cfg.get('openai_chat', {}).get('api_key_env', '')

            return {
                'api_key': api_key,
                'api_key_env': api_key_env
            }

        if provider_name == 'Gemini':
            api_key = self.gemini_api_key_edit.text().strip()
            api_key_env = ''
            gemini_cfg = providers_cfg.get('gemini', {}) or {}
            if not api_key:
                api_key = gemini_cfg.get('api_key', '')
            api_key_env = gemini_cfg.get('api_key_env', '')
            return {
                'api_key': api_key,
                'api_key_env': api_key_env
            }

        return {}

    def _update_glossary_api_key_controls(self, provider_name: str = None) -> None:
        provider = provider_name or self.glossary_provider_combo.currentText()
        use_translation = self.glossary_use_translation_key_checkbox.isChecked()
        self.glossary_api_key_edit.setEnabled(not use_translation)

        if use_translation:
            credentials = self._get_translation_credentials_for_glossary(provider)
            self._set_glossary_api_key_text(credentials.get('api_key') or '')
        else:
            manual_value = self._glossary_manual_api_keys.get(provider, '')
            self._set_glossary_api_key_text(manual_value)

    def _refresh_glossary_api_key_from_translation(self, *args):
        if not self.glossary_use_translation_key_checkbox.isChecked():
            return
        provider = self.glossary_provider_combo.currentText()
        if provider in ("OpenAI", "Gemini"):
            self._update_glossary_api_key_controls(provider)

    def _on_glossary_use_translation_key_changed(self, state):
        provider = self.glossary_provider_combo.currentText()
        if state == Qt.Checked:
            self._glossary_manual_api_keys[provider] = self.glossary_api_key_edit.text().strip()
        self._update_glossary_api_key_controls(provider)

    def _on_glossary_provider_changed(self, index):
        provider = self.glossary_provider_combo.itemText(index)
        if not provider:
            provider = self.glossary_provider_combo.currentText()
        self._update_glossary_api_key_controls(provider)

    def _on_glossary_api_key_changed(self, text):
        if self._glossary_updating_api_key:
            return
        if self.glossary_use_translation_key_checkbox.isChecked():
            return
        provider = self.glossary_provider_combo.currentText()
        self._glossary_manual_api_keys[provider] = text.strip()


    def find_plugins(self):
        plugins_dir = Path("plugins")
        found_plugins = {}
        if not plugins_dir.is_dir():
            return found_plugins
        
        for item_path in plugins_dir.iterdir():
            config_path = item_path / "config.json"
            if item_path.is_dir() and config_path.exists() and item_path.name != "import_plugins":
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    display_name = config_data.get("display_name", item_path.name)
                    found_plugins[display_name] = item_path.name
                except Exception as e:
                    log_debug(f"Could not read config for plugin '{item_path.name}': {e}")
                    found_plugins[item_path.name] = item_path.name
        return found_plugins

    def populate_plugin_list(self):
        self.plugin_map = self.find_plugins()
        self.plugin_combo.addItems(self.plugin_map.keys())

    def setup_logging_tab(self):
        layout = QVBoxLayout(self.logging_tab)
        
        handler_group = QGroupBox("Log Destinations", self.logging_tab)
        handler_layout = QFormLayout(handler_group)
        self.enable_console_logging_checkbox = QCheckBox("Enable Console Logging", self)
        handler_layout.addRow(self.enable_console_logging_checkbox)
        self.enable_file_logging_checkbox = QCheckBox("Enable File Logging", self)
        handler_layout.addRow(self.enable_file_logging_checkbox)
        
        self.log_file_path_edit = QLineEdit(self)
        self.log_file_path_edit.setPlaceholderText("Leave empty for default app_debug.txt")
        handler_layout.addRow("Log File Path:", self._create_path_selector(self.log_file_path_edit))
        layout.addWidget(handler_group)
        
        cat_group = QGroupBox("Log Event Categories", self.logging_tab)
        cat_layout = QVBoxLayout(cat_group)
        
        self.log_categories_checkboxes = {}
        categories_def = {
            "general": "General / Other system messages",
            "lifecycle": "Application lifecycle (startup/shutdown, configs)",
            "file_ops": "File operations (load/save files, load font maps)",
            "settings": "Settings changes",
            "ui_action": "User interactions (button clicks, menu selects)",
            "ai": "AI & Translation actions",
            "scanner": "Issue scanner logic",
            "plugins": "Plugin systems"
        }
        
        for cat_id, cat_name in categories_def.items():
            chk = QCheckBox(cat_name, self)
            chk.setObjectName(cat_id)
            self.log_categories_checkboxes[cat_id] = chk
            cat_layout.addWidget(chk)
            
        layout.addWidget(cat_group)
        layout.addStretch(1)

    def on_theme_changed(self, index):
        log_debug("SettingsDialog: Theme changed in dropdown.")
        selected_theme = self.theme_combo.currentText().lower()
        if selected_theme != self.initial_theme:
            self.theme_changed_requires_restart = True
            QMessageBox.information(self, "Theme Change", "A restart is required to apply the new theme.", QMessageBox.Ok)
        else:
            self.theme_changed_requires_restart = False

    def on_plugin_changed(self, index):
        log_debug("SettingsDialog: Plugin changed in dropdown.")
        selected_dir_name = self.plugin_map.get(self.plugin_combo.currentText())
        
        self._populate_font_list(selected_dir_name)
        
        if selected_dir_name == self.initial_plugin_name:
            self.plugin_changed_requires_restart = False
            return

        self.plugin_changed_requires_restart = True
        QMessageBox.information(self, "Plugin Change", "A restart is required to switch the game plugin.", QMessageBox.Ok)


