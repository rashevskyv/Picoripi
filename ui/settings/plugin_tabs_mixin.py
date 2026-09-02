from pathlib import Path
import json
from PyQt6.QtWidgets import (
    QVBoxLayout, QTabWidget, QWidget, QFormLayout, QComboBox, QCheckBox,
    QLineEdit, QHBoxLayout, QLabel, QGroupBox, QSpinBox, QStackedWidget,
    QGridLayout, QRadioButton, QButtonGroup, QSizePolicy
)
from utils.logging_utils import log_debug
from components.labeled_spinbox import LabeledSpinBox
from .settings_widgets import ColorPickerButton
from core.i18n import tr


class PluginTabsMixin:
    """Plugin tab setup, display, and rules (including Zelda BMG window rules)."""

    _ZELDA_BMG_WINDOW_GROUPS = (
        ("dialog", "Dialogue (all talk variants)", None),
        ("signs", "Wood / stone signs", ("2", "6")),
        ("kanban_talk", "Dialogue (kanban)", ("15",)),
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

        self.plugin_tabs.addTab(paths_tab, tr('File Paths'))
        self.plugin_tabs.addTab(display_tab, tr('Display'))
        self.plugin_tabs.addTab(rules_tab, tr('Rules'))
        self.plugin_tabs.addTab(context_tags_tab, tr('Context Tags'))
        self.plugin_tabs.addTab(aliases_tab, tr('Tag Aliases'))
        self.plugin_tabs.addTab(font_map_tab, tr('Font Map'))
        self.plugin_tabs.addTab(detection_tab, tr('Detection'))
        self.plugin_tabs.addTab(autofix_tab, tr('Auto-fix'))

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
        self.font_file_combo.addItem(tr('None'), tr(''))

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
        layout.addRow(tr('Default Font for Project:'), self.font_file_combo)
        
        self.preview_wrap_checkbox = QCheckBox(tr('Wrap lines in preview panel'), self)
        layout.addRow(self.preview_wrap_checkbox)
        self.editors_wrap_checkbox = QCheckBox(tr('Wrap lines in editor panels'), self)
        layout.addRow(self.editors_wrap_checkbox)
        self.newline_symbol_edit = QLineEdit(self)
        layout.addRow(tr('Newline Symbol:'), self.newline_symbol_edit)

        newline_style_row = QWidget(self)
        nlr = QHBoxLayout(newline_style_row); nlr.setContentsMargins(0,0,0,0)
        self.newline_color_picker = ColorPickerButton(parent=self)
        self.newline_bold_chk = QCheckBox(tr('Bold'), self)
        self.newline_italic_chk = QCheckBox(tr('Italic'), self)
        self.newline_underline_chk = QCheckBox(tr('Underline'), self)
        nlr.addWidget(self.newline_color_picker)
        nlr.addWidget(self.newline_bold_chk)
        nlr.addWidget(self.newline_italic_chk)
        nlr.addWidget(self.newline_underline_chk)
        nlr.addStretch(1)
        layout.addRow(tr('Newline Symbol Style:'), newline_style_row)

        tag_style_row = QWidget(self)
        tsr = QHBoxLayout(tag_style_row); tsr.setContentsMargins(0,0,0,0)
        self.tag_color_picker = ColorPickerButton(parent=self)
        self.tag_bold_chk = QCheckBox(tr('Bold'), self)
        self.tag_italic_chk = QCheckBox(tr('Italic'), self)
        self.tag_underline_chk = QCheckBox(tr('Underline'), self)
        tsr.addWidget(self.tag_color_picker)
        tsr.addWidget(self.tag_bold_chk)
        tsr.addWidget(self.tag_italic_chk)
        tsr.addWidget(self.tag_underline_chk)
        tsr.addStretch(1)
        layout.addRow(tr('Tag Style:'), tag_style_row)

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

        self.show_width_guideline_checkbox = QCheckBox(tr('Show guideline'), self)
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

        mode_group = QGroupBox(tr('Window limit mode'), self)
        mode_layout = QHBoxLayout(mode_group)
        mode_layout.setContentsMargins(12, 8, 12, 8)
        self.shared_window_mode_radio = QRadioButton(tr('Shared for all windows'), mode_group)
        self.per_window_mode_radio = QRadioButton(tr('Separate by window type'), mode_group)
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
        global_group = QGroupBox(tr('Shared defaults'), global_page)
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
        defaults_group = QGroupBox(tr('Defaults by window type'), per_type_page)
        defaults_layout = QVBoxLayout(defaults_group)
        defaults_layout.setContentsMargins(12, 10, 12, 12)
        description = QLabel(
            tr("The message's fuki_kind selects one of these default layouts automatically.")
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
