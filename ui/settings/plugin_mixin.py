from pathlib import Path
import json
from PyQt6.QtWidgets import (
    QVBoxLayout, QTabWidget, QWidget, QFormLayout, QComboBox, QCheckBox, 
    QLineEdit, QHBoxLayout, QLabel, QGroupBox, QTableWidget, QTableWidgetItem, 
    QHeaderView, QMenu, QAbstractItemView, QPushButton, QSpinBox, QStackedWidget,
    QGridLayout, QRadioButton, QButtonGroup, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from utils.logging_utils import log_debug
from components.labeled_spinbox import LabeledSpinBox
from .settings_widgets import ColorPickerButton, TagDisplayWidget

class SettingsPluginMixin:
    """Mixin class for project/plugin settings tab and subtabs."""

    _ZELDA_BMG_WINDOW_GROUPS = (
        ("dialog", "Dialogue (all talk variants)", None),
        ("signs", "Wood / stone signs", ("2", "15", "6")),
        ("item", "Item window", ("9",)),
        ("explain", "Descriptions / save", ("16",)),
        ("subtitles", "Subtitles", ("1", "5")),
        ("titles", "Location / boss name", ("12", "19")),
        ("howling", "Howling", ("17",)),
        ("credits", "Staff credits", ("7",)),
    )

    def setup_plugin_tab(self):
        """Setup plugin tab."""
        plugin_layout = QVBoxLayout(self.plugin_tab)
        self.plugin_tabs = QTabWidget(self.plugin_tab)
        plugin_layout.addWidget(self.plugin_tabs)
        self.rebuild_plugin_tabs()

    def rebuild_plugin_tabs(self):
        """Rebuild plugin tabs."""
        while self.plugin_tabs.count():
            self.plugin_tabs.removeTab(0)

        paths_tab = QWidget()
        display_tab = QWidget()
        rules_tab = QWidget()
        detection_tab = QWidget()
        autofix_tab = QWidget()
        context_tags_tab = QWidget()
        aliases_tab = QWidget()
        font_map_tab = QWidget()

        self.plugin_tabs.addTab(paths_tab, "File Paths")
        self.plugin_tabs.addTab(display_tab, "Display")
        self.plugin_tabs.addTab(rules_tab, "Rules")
        self.plugin_tabs.addTab(context_tags_tab, "Context Tags")
        self.plugin_tabs.addTab(aliases_tab, "Tag Aliases")
        self.plugin_tabs.addTab(font_map_tab, "Font Map")
        self.plugin_tabs.addTab(detection_tab, "Detection")
        self.plugin_tabs.addTab(autofix_tab, "Auto-fix")

        self._setup_paths_subtab(paths_tab)
        self._setup_display_subtab(display_tab)
        self._setup_rules_subtab(rules_tab)
        self._setup_context_tags_subtab(context_tags_tab)
        self._setup_aliases_subtab(aliases_tab)
        self._setup_font_map_subtab(font_map_tab)
        
        self.detection_checkboxes.clear()
        self.autofix_checkboxes.clear()
        self._setup_detection_subtab(detection_tab)
        self._setup_autofix_subtab(autofix_tab)

    def _populate_font_list(self, plugin_dir_name: str):
        """Internal helper to populate font list."""
        self.font_file_combo.clear()
        self.font_file_combo.addItem("None", "")

        if not plugin_dir_name:
            return
            
        fonts_dirs = [Path("plugins") / plugin_dir_name / "fonts"]
        custom_fonts_path = getattr(self.mw, 'fonts_dir_path', None)
        if custom_fonts_path:
            custom_dir = Path(custom_fonts_path)
            if custom_dir.is_dir():
                fonts_dirs.append(custom_dir)

        seen_fonts = set()
        for fonts_dir in fonts_dirs:
            if fonts_dir.is_dir():
                for font_path in sorted(fonts_dir.iterdir()):
                    suffix = font_path.suffix.lower()
                    if suffix in (".arc", ".rarc", ".u8"):
                        try:
                            from core.containers import ContainerManager
                            archive_data = font_path.read_bytes()
                            if ContainerManager.is_supported(archive_data):
                                container = ContainerManager.open(archive_data)
                                if container:
                                    for inner_path in sorted(container.list_files()):
                                        inner_suffix = Path(inner_path).suffix.lower()
                                        if inner_suffix in (".json", ".bfn"):
                                            font_key = f"{font_path.name}/{Path(inner_path).name}"
                                            if font_key not in seen_fonts:
                                                seen_fonts.add(font_key)
                                                self.font_file_combo.addItem(font_key, font_key)
                        except Exception:
                            pass
                    elif suffix in (".json", ".bfn"):
                        if font_path.name not in seen_fonts:
                            seen_fonts.add(font_path.name)
                            self.font_file_combo.addItem(font_path.name, font_path.name)

    def _setup_display_subtab(self, tab):
        """Internal helper to setup display subtab."""
        layout = QFormLayout(tab)
        self.font_file_combo = QComboBox(self)
        layout.addRow("Default Font for Project:", self.font_file_combo)
        
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
        """Handle the rules changed event."""
        self.rules_changed_requires_rescan = True
        log_debug("SettingsDialog: Rules changed, marked for rescan.")

    def _setup_rules_subtab(self, tab):
        """Internal helper to setup rules subtab."""
        layout = QFormLayout(tab)
        self.game_dialog_width_spinbox = LabeledSpinBox("Game Dialog Max Width (px):", 100, 10000, 240, parent=self)
        self.game_dialog_width_spinbox.spin_box.valueChanged.connect(self.on_rules_changed)

        self.width_warning_spinbox = LabeledSpinBox("Editor Line Width Warning (px):", 100, 10000, 208, parent=self)
        self.width_warning_spinbox.spin_box.valueChanged.connect(self.on_rules_changed)

        self.show_width_guideline_checkbox = QCheckBox("Show guideline", self)
        self.show_width_guideline_checkbox.stateChanged.connect(self.on_rules_changed)

        self.lines_per_page_spinbox = LabeledSpinBox("Lines Per Page:", 1, 20, 4, parent=self)
        self.lines_per_page_spinbox.spin_box.valueChanged.connect(self.on_rules_changed)

        if getattr(self.mw, "active_game_plugin", None) == "zelda_bmg":
            self._setup_zelda_bmg_window_rules(layout)
        else:
            layout.addRow(self.game_dialog_width_spinbox)
            spinbox_layout = self.width_warning_spinbox.layout()
            if spinbox_layout:
                spinbox_layout.insertSpacing(2, 20)
                spinbox_layout.insertWidget(3, self.show_width_guideline_checkbox)
            layout.addRow(self.width_warning_spinbox)
            layout.addRow(self.lines_per_page_spinbox)

    def _setup_zelda_bmg_window_rules(self, layout):
        """Build the global/per-window rule mode switch for TP BMG."""
        self._zelda_window_layouts_path = Path("plugins") / "zelda_bmg" / "window_layouts.json"
        try:
            with self._zelda_window_layouts_path.open("r", encoding="utf-8") as stream:
                document = json.load(stream)
        except Exception as exc:
            log_debug(f"SettingsDialog: Failed to load window_layouts.json: {exc}")
            document = {"default": {}, "kinds": {}}

        self._zelda_window_layouts_document = document
        self._zelda_window_layout_controls = {}

        use_per_type = getattr(self.mw, "use_per_window_layouts", True)

        mode_group = QGroupBox("Window limit mode", self)
        mode_layout = QHBoxLayout(mode_group)
        mode_layout.setContentsMargins(12, 8, 12, 8)
        self.shared_window_mode_radio = QRadioButton("Shared for all windows", mode_group)
        self.per_window_mode_radio = QRadioButton("Separate by window type", mode_group)
        self.window_mode_button_group = QButtonGroup(self)
        self.window_mode_button_group.addButton(self.shared_window_mode_radio, 0)
        self.window_mode_button_group.addButton(self.per_window_mode_radio, 1)
        self.shared_window_mode_radio.setChecked(not use_per_type)
        self.per_window_mode_radio.setChecked(use_per_type)
        # Compatibility alias used by settings loading/saving.
        self.use_per_window_layouts_checkbox = self.per_window_mode_radio
        mode_layout.addWidget(self.shared_window_mode_radio)
        mode_layout.addSpacing(24)
        mode_layout.addWidget(self.per_window_mode_radio)
        mode_layout.addStretch(1)
        layout.addRow(mode_group)

        self.window_rules_mode_stack = QStackedWidget(self)
        self.window_rules_mode_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        global_page = QWidget(self.window_rules_mode_stack)
        global_group = QGroupBox("Shared defaults", global_page)
        global_layout = QFormLayout(global_group)
        global_layout.setContentsMargins(12, 10, 12, 10)
        global_layout.addRow(self.game_dialog_width_spinbox)
        global_layout.addRow(self.width_warning_spinbox)
        global_layout.addRow(self.lines_per_page_spinbox)
        global_page_layout = QVBoxLayout(global_page)
        global_page_layout.setContentsMargins(0, 4, 0, 0)
        global_page_layout.addWidget(global_group)
        self.window_rules_mode_stack.addWidget(global_page)

        per_type_page = QWidget(self.window_rules_mode_stack)
        per_type_layout = QVBoxLayout(per_type_page)
        per_type_layout.setContentsMargins(0, 4, 0, 0)
        defaults_group = QGroupBox("Defaults by window type", per_type_page)
        defaults_layout = QVBoxLayout(defaults_group)
        defaults_layout.setContentsMargins(12, 10, 12, 12)
        description = QLabel(
            "The message's fuki_kind selects one of these default layouts automatically."
        )
        description.setWordWrap(True)
        defaults_layout.addWidget(description)

        grid = QGridLayout()
        self.zelda_window_layouts_grid = grid
        grid.setContentsMargins(0, 6, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        headers = ("Window type", "Warning", "Maximum", "Lines")
        for column, text in enumerate(headers):
            header = QLabel(text, defaults_group)
            header.setStyleSheet("font-weight: bold;")
            grid.addWidget(header, 0, column)
        grid.setColumnStretch(0, 1)

        defaults = document.get("default") if isinstance(document.get("default"), dict) else {}
        kinds = document.get("kinds") if isinstance(document.get("kinds"), dict) else {}
        for row, (key, label, target_kinds) in enumerate(self._ZELDA_BMG_WINDOW_GROUPS):
            source = defaults
            if target_kinds:
                candidate = kinds.get(target_kinds[0])
                if isinstance(candidate, dict):
                    source = {**defaults, **candidate}

            name_label = QLabel(label, defaults_group)
            controls = {
                "warn_width": self._make_window_layout_spinbox(1, 10000, source.get("warn_width", 280), " px", 105),
                "max_width": self._make_window_layout_spinbox(1, 10000, source.get("max_width", 300), " px", 105),
                "lines_per_page": self._make_window_layout_spinbox(1, 20, source.get("lines_per_page", 4), "", 72),
            }
            grid_row = row + 1
            grid.addWidget(name_label, grid_row, 0)
            grid.addWidget(controls["warn_width"], grid_row, 1)
            grid.addWidget(controls["max_width"], grid_row, 2)
            grid.addWidget(controls["lines_per_page"], grid_row, 3)
            self._zelda_window_layout_controls[key] = controls

        defaults_layout.addLayout(grid)
        per_type_layout.addWidget(defaults_group)
        self.window_rules_mode_stack.addWidget(per_type_page)

        self.window_rules_mode_stack.setCurrentIndex(1 if use_per_type else 0)
        self.per_window_mode_radio.toggled.connect(
            lambda checked: self.window_rules_mode_stack.setCurrentIndex(1 if checked else 0)
        )
        self.per_window_mode_radio.toggled.connect(self.on_rules_changed)
        layout.addRow(self.window_rules_mode_stack)
        layout.addRow(self.show_width_guideline_checkbox)

    def _make_window_layout_spinbox(self, minimum, maximum, value, suffix="", width=95):
        spinbox = QSpinBox(self)
        spinbox.setRange(minimum, maximum)
        spinbox.setSuffix(suffix)
        spinbox.setFixedWidth(width)
        spinbox.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        try:
            spinbox.setValue(int(value))
        except (TypeError, ValueError):
            spinbox.setValue(minimum)
        spinbox.valueChanged.connect(self.on_rules_changed)
        return spinbox

    def persist_zelda_bmg_window_rules(self):
        """Persist TP per-window defaults after OK. Returns (success, error)."""
        controls_by_group = getattr(self, "_zelda_window_layout_controls", None)
        if not controls_by_group:
            return True, ""

        document = json.loads(json.dumps(self._zelda_window_layouts_document))
        defaults = document.setdefault("default", {})
        kinds = document.setdefault("kinds", {})

        for key, _label, target_kinds in self._ZELDA_BMG_WINDOW_GROUPS:
            controls = controls_by_group[key]
            values = {
                "warn_width": controls["warn_width"].value(),
                "max_width": controls["max_width"].value(),
                "lines_per_page": controls["lines_per_page"].value(),
            }
            if values["warn_width"] > values["max_width"]:
                return False, f"{_label}: warning width cannot exceed maximum width."

            targets = [defaults] if target_kinds is None else [kinds.setdefault(kind, {}) for kind in target_kinds]
            for target in targets:
                target.update(values)

        if document == self._zelda_window_layouts_document:
            return True, ""

        try:
            path = self._zelda_window_layouts_path
            temporary_path = path.with_suffix(path.suffix + ".tmp")
            temporary_path.write_text(
                json.dumps(document, indent=4, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(path)
        except Exception as exc:
            log_debug(f"SettingsDialog: Failed to save window_layouts.json: {exc}")
            return False, str(exc)

        self._zelda_window_layouts_document = document
        rules = getattr(self.mw, "current_game_rules", None)
        if rules is not None and hasattr(rules, "_window_layouts"):
            rules._window_layouts = None
        self.rules_changed_requires_rescan = True
        return True, ""

    def _setup_context_tags_subtab(self, tab):
        """Internal helper to setup context tags subtab."""
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
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            
        self.single_tags_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.single_tags_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(pos, self.single_tags_table))
        self.single_tags_table.mouseDoubleClickEvent = lambda e: self._handle_table_double_click(e, self.single_tags_table)
        single_layout.addWidget(self.single_tags_table)
        
        single_btn_row = QHBoxLayout()
        add_single_btn = QPushButton("Add Row", self)
        add_single_btn.setToolTip(
            "<b>Add row</b><br>"
            "Click — append an empty single-tag row, then type the tag and its "
            "display text.<br>"
            "Changes take effect after you press OK in Settings."
        )
        add_single_btn.clicked.connect(lambda: self._add_table_row(self.single_tags_table))
        remove_single_btn = QPushButton("Remove Row", self)
        remove_single_btn.setToolTip(
            "<b>Remove row</b><br>"
            "Click — delete the row selected in the table; with nothing selected it "
            "removes the last row. One row per click."
        )
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
        header_wrap.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            
        self.wrap_tags_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.wrap_tags_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(pos, self.wrap_tags_table))
        self.wrap_tags_table.mouseDoubleClickEvent = lambda e: self._handle_table_double_click(e, self.wrap_tags_table)
        wrap_layout.addWidget(self.wrap_tags_table)
        
        wrap_btn_row = QHBoxLayout()
        add_wrap_btn = QPushButton("Add Row", self)
        add_wrap_btn.setToolTip(
            "<b>Add row</b><br>"
            "Click — append an empty wrapping-tag row (a tag with an opening and a "
            "closing part).<br>"
            "Changes take effect after you press OK in Settings."
        )
        add_wrap_btn.clicked.connect(lambda: self._add_table_row(self.wrap_tags_table))
        remove_wrap_btn = QPushButton("Remove Row", self)
        remove_wrap_btn.setToolTip(
            "<b>Remove row</b><br>"
            "Click — delete the row selected in the table; with nothing selected it "
            "removes the last row. One row per click."
        )
        remove_wrap_btn.clicked.connect(lambda: self._remove_table_row(self.wrap_tags_table))
        wrap_btn_row.addWidget(add_wrap_btn); wrap_btn_row.addWidget(remove_wrap_btn)
        wrap_layout.addLayout(wrap_btn_row)
        layout.addWidget(wrap_group)

    def _handle_table_double_click(self, event, table):
        """Internal helper to handle table double click."""
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
        """Internal helper to show table context menu."""
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
            
        action = menu.exec(table.viewport().mapToGlobal(pos))
        
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
        """Internal helper to add table row."""
        sorting_was_enabled = table.isSortingEnabled()
        if sorting_was_enabled:
            table.setSortingEnabled(False)
            
        if insert_at_row is not None:
            row = insert_at_row
        else:
            row = table.rowCount()
        table.insertRow(row)
        
        disp_item = QTableWidgetItem()
        disp_item.setData(Qt.ItemDataRole.DisplayRole, display_text)
        table.setItem(row, 0, disp_item)
        
        widget = TagDisplayWidget(display_text, table)
        widget.textChanged.connect(lambda txt, i=disp_item: i.setData(Qt.ItemDataRole.DisplayRole, txt))
        table.setCellWidget(row, 0, widget)
        
        table.setItem(row, 1, QTableWidgetItem(col1))
        
        if table.columnCount() > 2:
            table.setItem(row, 2, QTableWidgetItem(col2))
            
        if sorting_was_enabled:
            table.setSortingEnabled(True)

    def _filter_tags_tables(self, text):
        """Internal helper to filter tags tables."""
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
        """Internal helper to remove table row."""
        curr = table.currentRow()
        if curr != -1: table.removeRow(curr)
        elif table.rowCount() > 0: table.removeRow(table.rowCount() - 1)

    def _setup_paths_subtab(self, tab):
        """Internal helper to setup paths subtab."""
        layout = QFormLayout(tab)
        
        self.dir_mode_checkbox = QCheckBox("Directory Mode (Load from folder)", tab)
        self.auto_generate_checkbox = QCheckBox("Auto-generate translation path", tab)
        
        layout.addRow(self.dir_mode_checkbox)
        layout.addRow(self.auto_generate_checkbox)
        
        self.original_path_edit = QLineEdit(tab)
        self.original_path_edit.setObjectName("PathLineEdit")
        self.edited_path_edit = QLineEdit(tab)
        self.edited_path_edit.setObjectName("PathLineEdit")

        self.orig_label_widget = QLabel("Original File Path:")
        self.changes_label_widget = QLabel("Changes File Path:")

        self.original_path_selector = self._create_path_selector(self.original_path_edit)
        self.edited_path_selector = self._create_path_selector(self.edited_path_edit)
        layout.addRow(self.orig_label_widget, self.original_path_selector)
        layout.addRow(self.changes_label_widget, self.edited_path_selector)

        # Original Fonts Directory Path Selection
        self.orig_fonts_path_edit = QLineEdit(tab)
        self.orig_fonts_path_edit.setObjectName("PathLineEdit")
        self.orig_fonts_path_edit.setPlaceholderText("Optional path to original fonts folder")
        self.orig_fonts_path_selector = self._create_dir_selector(self.orig_fonts_path_edit)
        layout.addRow(QLabel("Original Fonts Directory Path (original font):"), self.orig_fonts_path_selector)

        # Fonts Directory Path Selection
        self.fonts_path_edit = QLineEdit(tab)
        self.fonts_path_edit.setObjectName("PathLineEdit")
        self.fonts_path_edit.setPlaceholderText("Optional path to fonts folder")
        self.fonts_path_selector = self._create_dir_selector(self.fonts_path_edit)
        layout.addRow(QLabel("Fonts Directory Path (translated font):"), self.fonts_path_selector)

        # Signals
        self.dir_mode_checkbox.stateChanged.connect(self._on_dir_mode_changed)
        self.auto_generate_checkbox.stateChanged.connect(self._on_auto_generate_changed)
        self.original_path_edit.textChanged.connect(self._update_auto_changes_path)
        self.fonts_path_edit.textChanged.connect(self._on_fonts_dir_changed)
        self.orig_fonts_path_edit.textChanged.connect(self._on_orig_fonts_dir_changed)

    def _on_dir_mode_changed(self, state):
        """Internal helper to handle the dir mode changed event."""
        is_dir = (state == Qt.CheckState.Checked)
        if is_dir:
            self.orig_label_widget.setText("Original Directory Path:")
            self.changes_label_widget.setText("Changes Directory Path:")
        else:
            self.orig_label_widget.setText("Original File Path:")
            self.changes_label_widget.setText("Changes File Path:")
        self._update_auto_changes_path()

    def _on_auto_generate_changed(self, state):
        """Internal helper to handle the auto generate changed event."""
        is_auto = (state == Qt.CheckState.Checked)
        if hasattr(self, 'edited_path_selector'):
            self.edited_path_selector.setEnabled(not is_auto)
        else:
            self.edited_path_edit.setEnabled(not is_auto)
        self._update_auto_changes_path()

    def _update_auto_changes_path(self):
        """Internal helper to update the auto changes path."""
        if not hasattr(self, 'auto_generate_checkbox') or not self.auto_generate_checkbox.isChecked():
            return
        
        orig_path = self.original_path_edit.text().strip()
        if not orig_path:
            self.edited_path_edit.setText("")
            return

        is_dir = self.dir_mode_checkbox.isChecked()
        try:
            path_obj = Path(orig_path)
            if is_dir:
                parent = path_obj.parent
                name = path_obj.name
                if name:
                    new_path = (parent / f"{name}_translation").as_posix()
                else:
                    new_path = f"{orig_path}_translation"
            else:
                parent = path_obj.parent
                stem = path_obj.stem
                suffix = path_obj.suffix
                new_path = (parent / f"{stem}_translation{suffix}").as_posix()
                
            self.edited_path_edit.setText(new_path)
        except Exception:
            self.edited_path_edit.setText(f"{orig_path}_translation")

    def _populate_checkbox_subtab(self, tab, checkbox_dict, title):
        """Internal helper to populate checkbox subtab."""
        layout = QFormLayout(tab)
        layout.addRow(QLabel(title))

        if not self.mw.current_game_rules:
            layout.addRow(QLabel("No game rules loaded."))
            return

        problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        if not problem_definitions:
            layout.addRow(QLabel("No problem definitions found in current plugin."))
            if self.mw.current_game_rules.get_display_name() == "Base Game (No Plugin)":
                layout.addRow(QLabel("<i>(Running in fallback mode due to plugin load error)</i>"))
            return

        sorted_problem_ids = sorted(
            problem_definitions.keys(),
            key=lambda pid: problem_definitions[pid].get("priority", 99)
        )

        for problem_id in sorted_problem_ids:
            definition = problem_definitions[problem_id]

            row_widget = QWidget(self)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            color_label = QLabel(self)
            color_label.setFixedSize(20, 20)
            problem_color = definition.get("color", QColor(200, 200, 200, 100))
            if isinstance(problem_color, QColor):
                r, g, b, a = problem_color.red(), problem_color.green(), problem_color.blue(), problem_color.alpha()
                color_label.setStyleSheet(f"background-color: rgba({r}, {g}, {b}, {a}); border: 1px solid #888;")
                color_label.setToolTip(f"Problem color: rgba({r}, {g}, {b}, {a})")
            else:
                color_label.setStyleSheet(f"background-color: {problem_color}; border: 1px solid #888;")
                color_label.setToolTip(f"Problem color: {problem_color}")
            row_layout.addWidget(color_label)

            checkbox = QCheckBox(definition.get("name", problem_id), self)
            checkbox.setToolTip(definition.get("description", "No description available."))
            checkbox_dict[problem_id] = checkbox
            checkbox.stateChanged.connect(self.on_rules_changed)
            row_layout.addWidget(checkbox)
            row_layout.addStretch(1)

            layout.addRow(row_widget)

    def _setup_detection_subtab(self, tab):
        """Internal helper to setup detection subtab."""
        self._populate_checkbox_subtab(tab, self.detection_checkboxes, "Enable/disable problem detection:")

    def _setup_autofix_subtab(self, tab):
        """Internal helper to setup autofix subtab."""
        layout = QVBoxLayout(tab)
        
        general_group = QGroupBox("General Auto-fix Settings", tab)
        general_layout = QVBoxLayout(general_group)
        self.align_sentences_checkbox = QCheckBox("Align sentences to original page layout", general_group)
        self.align_sentences_checkbox.setToolTip("Align translation sentences structure and pages matching original layout.")
        self.align_sentences_checkbox.stateChanged.connect(self.on_rules_changed)
        general_layout.addWidget(self.align_sentences_checkbox)
        
        self.prevent_empty_lines_checkbox = QCheckBox("Prevent adding empty padding lines during pagination", general_group)
        self.prevent_empty_lines_checkbox.setToolTip("Do not add empty padding lines at the end of pages to fill remaining space.")
        self.prevent_empty_lines_checkbox.stateChanged.connect(self.on_rules_changed)
        general_layout.addWidget(self.prevent_empty_lines_checkbox)
        
        layout.addWidget(general_group)
        
        sub_widget = QWidget(tab)
        self._populate_checkbox_subtab(sub_widget, self.autofix_checkboxes, "Enable/disable auto-fix for specific problems:")
        layout.addWidget(sub_widget)
        layout.addStretch(1)

    def _setup_aliases_subtab(self, tab):
        """Internal helper to setup aliases subtab."""
        layout = QVBoxLayout(tab)
        
        # Search Filter
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Filter Aliases:"))
        self.aliases_search_edit = QLineEdit(tab)
        self.aliases_search_edit.setPlaceholderText("Search by alias or original tag...")
        self.aliases_search_edit.setClearButtonEnabled(True)
        self.aliases_search_edit.textChanged.connect(self._filter_aliases_table)
        search_layout.addWidget(self.aliases_search_edit)
        layout.addLayout(search_layout)
        
        # Table
        self.aliases_table = QTableWidget(0, 2, tab)
        self.aliases_table.setHorizontalHeaderLabels(["Alias (e.g. {F:Link})", "Original Tag (e.g. {escape:0:0000})"])
        self.aliases_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.aliases_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.aliases_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        # Context Menu & double click
        self.aliases_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.aliases_table.customContextMenuRequested.connect(self._show_aliases_context_menu)
        self.aliases_table.mouseDoubleClickEvent = lambda e: self._handle_aliases_double_click(e)
        layout.addWidget(self.aliases_table)
        
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Alias", tab)
        add_btn.setToolTip(
            "<b>Add alias</b><br>"
            "Click — append an empty alias row mapping a raw game tag to a readable "
            "name.<br>"
            "Use the search field above to find an existing alias before adding a "
            "duplicate."
        )
        add_btn.clicked.connect(lambda: self._add_alias_row())
        remove_btn = QPushButton("Remove Alias", tab)
        remove_btn.setToolTip(
            "<b>Remove alias</b><br>"
            "Click — delete the selected alias row; with nothing selected it removes "
            "the last row. One row per click."
        )
        remove_btn.clicked.connect(self._remove_alias_row)
        btn_row.addWidget(add_btn); btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        # Populate
        self._populate_aliases_table()

    def _populate_aliases_table(self):
        """Internal helper to populate aliases table."""
        self.aliases_table.setRowCount(0)
        default_tag_mappings = getattr(self.mw, "default_tag_mappings", {})
        for idx, (alias, orig_tag) in enumerate(default_tag_mappings.items()):
            self.aliases_table.insertRow(idx)
            self.aliases_table.setItem(idx, 0, QTableWidgetItem(alias))
            self.aliases_table.setItem(idx, 1, QTableWidgetItem(orig_tag))
        self.aliases_table.resizeColumnsToContents()

    def _add_alias_row(self, alias="", orig_tag="", insert_at_row=None):
        """Internal helper to add alias row."""
        if insert_at_row is not None:
            row = insert_at_row
        else:
            row = self.aliases_table.rowCount()
        self.aliases_table.insertRow(row)
        self.aliases_table.setItem(row, 0, QTableWidgetItem(alias))
        self.aliases_table.setItem(row, 1, QTableWidgetItem(orig_tag))

    def _remove_alias_row(self):
        """Internal helper to remove alias row."""
        curr = self.aliases_table.currentRow()
        if curr != -1:
            self.aliases_table.removeRow(curr)
        elif self.aliases_table.rowCount() > 0:
            self.aliases_table.removeRow(self.aliases_table.rowCount() - 1)

    def _filter_aliases_table(self, text):
        """Internal helper to filter aliases table."""
        search_text = text.lower()
        for r in range(self.aliases_table.rowCount()):
            row_matches = False
            for c in range(self.aliases_table.columnCount()):
                item = self.aliases_table.item(r, c)
                cell_text = item.text().lower() if item else ""
                if search_text in cell_text:
                    row_matches = True
                    break
            self.aliases_table.setRowHidden(r, not row_matches)

    def _handle_aliases_double_click(self, event):
        """Internal helper to handle aliases double click."""
        item = self.aliases_table.itemAt(event.pos())
        if item is None:
            row = self.aliases_table.rowAt(event.pos().y())
            if row == -1:
                self._add_alias_row()
            else:
                self._add_alias_row(insert_at_row=row + 1)
        else:
            QTableWidget.mouseDoubleClickEvent(self.aliases_table, event)

    def _show_aliases_context_menu(self, pos):
        """Internal helper to show aliases context menu."""
        menu = QMenu(self)
        item = self.aliases_table.itemAt(pos)
        clicked_row = item.row() if item else -1
        if clicked_row == -1:
            clicked_row = self.aliases_table.rowAt(pos.y())
            
        selected_rows = sorted(list(set([i.row() for i in self.aliases_table.selectedItems()])))
        if clicked_row != -1 and clicked_row not in selected_rows:
            selected_rows = [clicked_row]
            
        add_action = menu.addAction("Add Alias")
        clone_action = menu.addAction(f"Clone Alias{'es' if len(selected_rows) > 1 else ''}")
        delete_action = menu.addAction(f"Delete Alias{'es' if len(selected_rows) > 1 else ''}")
        
        if not selected_rows:
            clone_action.setEnabled(False)
            delete_action.setEnabled(False)
            
        action = menu.exec(self.aliases_table.viewport().mapToGlobal(pos))
        
        if action == add_action:
            if clicked_row != -1:
                self._add_alias_row(insert_at_row=clicked_row + 1)
            else:
                self._add_alias_row()
        elif action == clone_action:
            for row in reversed(selected_rows):
                item0 = self.aliases_table.item(row, 0)
                item1 = self.aliases_table.item(row, 1)
                alias = item0.text() if item0 else ""
                orig = item1.text() if item1 else ""
                self._add_alias_row(alias=alias, orig_tag=orig, insert_at_row=row + 1)
        elif action == delete_action:
            for row in reversed(selected_rows):
                self.aliases_table.removeRow(row)

    def _setup_font_map_subtab(self, tab):
        """Internal helper to setup font map subtab."""
        layout = QVBoxLayout(tab)
        
        # Search Filter
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Filter Characters:"))
        self.font_map_search_edit = QLineEdit(tab)
        self.font_map_search_edit.setPlaceholderText("Search by character or sequence...")
        self.font_map_search_edit.setClearButtonEnabled(True)
        self.font_map_search_edit.textChanged.connect(self._filter_font_map_table)
        search_layout.addWidget(self.font_map_search_edit)
        layout.addLayout(search_layout)
        
        # Table
        self.font_map_table = QTableWidget(0, 2, tab)
        self.font_map_table.setHorizontalHeaderLabels(["Character / Sequence", "Width (pixels)"])
        self.font_map_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.font_map_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.font_map_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        # Context Menu & double click
        self.font_map_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.font_map_table.customContextMenuRequested.connect(self._show_font_map_context_menu)
        self.font_map_table.mouseDoubleClickEvent = lambda e: self._handle_font_map_double_click(e)
        layout.addWidget(self.font_map_table)
        
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Character", tab)
        add_btn.setToolTip(
            "<b>Add character</b><br>"
            "Click — append an empty row for a character and its pixel width.<br>"
            "Widths feed the line-width warnings, so recalculate widths after "
            "changing them."
        )
        add_btn.clicked.connect(lambda: self._add_font_map_row())
        remove_btn = QPushButton("Remove Character", tab)
        remove_btn.setToolTip(
            "<b>Remove character</b><br>"
            "Click — delete the selected character row; with nothing selected it "
            "removes the last row. One row per click."
        )
        remove_btn.clicked.connect(self._remove_font_map_row)
        btn_row.addWidget(add_btn); btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        # Populate
        self._populate_font_map_table()

    def _populate_font_map_table(self):
        """Internal helper to populate font map table."""
        self.font_map_table.setRowCount(0)
        
        plugin_dir_name = self.plugin_combo.currentData() or getattr(self.mw, 'active_game_plugin', 'zelda_bmg')
        if not plugin_dir_name:
            return
            
        font_map_path = Path("plugins") / plugin_dir_name / "font_map.json"
        if not font_map_path.exists():
            font_map_path = Path("plugins") / "common" / "defaults" / "font_map.json"
            
        font_map = {}
        if font_map_path.exists():
            try:
                with open(font_map_path, 'r', encoding='utf-8') as f:
                    font_map = json.load(f)
            except Exception as e:
                log_debug(f"Failed to read font_map.json inside settings setup: {e}")
                
        if not font_map and hasattr(self.mw, 'current_font_map'):
            font_map = self.mw.current_font_map or {}
            
        for idx, (char, info) in enumerate(font_map.items()):
            self.font_map_table.insertRow(idx)
            self.font_map_table.setItem(idx, 0, QTableWidgetItem(char))
            
            width_val = ""
            if isinstance(info, dict):
                width_val = str(info.get("width", ""))
            elif isinstance(info, (int, float)):
                width_val = str(int(info))
                
            self.font_map_table.setItem(idx, 1, QTableWidgetItem(width_val))
            
        self.font_map_table.resizeColumnsToContents()

    def _add_font_map_row(self, char="", width_val="", insert_at_row=None):
        """Internal helper to add font map row."""
        if insert_at_row is not None:
            row = insert_at_row
        else:
            row = self.font_map_table.rowCount()
        self.font_map_table.insertRow(row)
        self.font_map_table.setItem(row, 0, QTableWidgetItem(char))
        self.font_map_table.setItem(row, 1, QTableWidgetItem(width_val))

    def _remove_font_map_row(self):
        """Internal helper to remove font map row."""
        curr = self.font_map_table.currentRow()
        if curr != -1:
            self.font_map_table.removeRow(curr)
        elif self.font_map_table.rowCount() > 0:
            self.font_map_table.removeRow(self.font_map_table.rowCount() - 1)

    def _filter_font_map_table(self, text):
        """Internal helper to filter font map table."""
        search_text = text.lower()
        for r in range(self.font_map_table.rowCount()):
            row_matches = False
            for c in range(self.font_map_table.columnCount()):
                item = self.font_map_table.item(r, c)
                cell_text = item.text().lower() if item else ""
                if search_text in cell_text:
                    row_matches = True
                    break
            self.font_map_table.setRowHidden(r, not row_matches)

    def _handle_font_map_double_click(self, event):
        """Internal helper to handle font map double click."""
        item = self.font_map_table.itemAt(event.pos())
        if item is None:
            row = self.font_map_table.rowAt(event.pos().y())
            if row == -1:
                self._add_font_map_row()
            else:
                self._add_font_map_row(insert_at_row=row + 1)
        else:
            QTableWidget.mouseDoubleClickEvent(self.font_map_table, event)

    def _show_font_map_context_menu(self, pos):
        """Internal helper to show font map context menu."""
        menu = QMenu(self)
        item = self.font_map_table.itemAt(pos)
        clicked_row = item.row() if item else -1
        if clicked_row == -1:
            clicked_row = self.font_map_table.rowAt(pos.y())
            
        selected_rows = sorted(list(set([i.row() for i in self.font_map_table.selectedItems()])))
        if clicked_row != -1 and clicked_row not in selected_rows:
            selected_rows = [clicked_row]
            
        add_action = menu.addAction("Add Character")
        clone_action = menu.addAction(f"Clone Character{'s' if len(selected_rows) > 1 else ''}")
        delete_action = menu.addAction(f"Delete Character{'s' if len(selected_rows) > 1 else ''}")
        
        if not selected_rows:
            clone_action.setEnabled(False)
            delete_action.setEnabled(False)
            
        action = menu.exec(self.font_map_table.viewport().mapToGlobal(pos))
        
        if action == add_action:
            if clicked_row != -1:
                self._add_font_map_row(insert_at_row=clicked_row + 1)
            else:
                self._add_font_map_row()
        elif action == clone_action:
            for row in reversed(selected_rows):
                item0 = self.font_map_table.item(row, 0)
                item1 = self.font_map_table.item(row, 1)
                char = item0.text() if item0 else ""
                width_val = item1.text() if item1 else ""
                self._add_font_map_row(char=char, width_val=width_val, insert_at_row=row + 1)
        elif action == delete_action:
            for row in reversed(selected_rows):
                self.font_map_table.removeRow(row)
