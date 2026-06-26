from pathlib import Path
import json
from PyQt6.QtWidgets import QVBoxLayout, QGroupBox, QFormLayout, QCheckBox, QLineEdit, QLabel
from utils.logging_utils import log_debug

class SettingsLoggingMixin:
    """Mixin class for Logging tab and plugin discovery in settings dialog."""

    def find_plugins(self):
        """Find plugins."""
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
        """Populate plugin list."""
        self.plugin_map = self.find_plugins()
        self.plugin_combo.clear()
        self.plugin_combo.addItem("None", "")
        for display_name, dir_name in self.plugin_map.items():
            self.plugin_combo.addItem(display_name, dir_name)

    def setup_logging_tab(self):
        """Setup logging tab."""
        layout = QVBoxLayout(self.logging_tab)
        
        handler_group = QGroupBox("Log Destinations", self.logging_tab)
        handler_layout = QFormLayout(handler_group)
        self.enable_console_logging_checkbox = QCheckBox("Enable Console Logging", self)
        handler_layout.addRow(self.enable_console_logging_checkbox)
        self.enable_file_logging_checkbox = QCheckBox("Enable File Logging", self)
        handler_layout.addRow(self.enable_file_logging_checkbox)
        
        self.log_ai_traffic_checkbox = QCheckBox("Log AI Traffic to File (ai_traffic.log)", self)
        handler_layout.addRow(self.log_ai_traffic_checkbox)
        
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
