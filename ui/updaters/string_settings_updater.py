# --- START OF FILE ui/updaters/string_settings_updater.py ---
from pathlib import Path
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtGui import QColor, QPalette
from .base_ui_updater import BaseUIUpdater
from utils.utils import log_debug

class StringSettingsUpdater(BaseUIUpdater):
    def __init__(self, main_window, data_processor):
        super().__init__(main_window, data_processor)
        self.highlight_style = "border: 1px solid #9370DB;" # MediumPurple

    def update_font_combobox(self):
        self.mw.font_combobox.blockSignals(True)
        self.mw.font_combobox.clear()

        plugin_dir_name = self.mw.active_game_plugin
        
        default_font_display_text = f"Default ({self.mw.default_font_file or 'None'})"
        self.mw.font_combobox.addItem(default_font_display_text, "default")

        if not plugin_dir_name:
            self.mw.font_combobox.blockSignals(False)
            return
        
        fonts_dir = Path("plugins") / plugin_dir_name / "fonts"
        if fonts_dir.is_dir():
            for font_file in sorted(fonts_dir.iterdir()):
                if font_file.is_file() and font_file.suffix.lower() == ".json":
                    filename = font_file.name
                    if filename != self.mw.default_font_file:
                        self.mw.font_combobox.addItem(filename, filename)
        
        self.mw.font_combobox.blockSignals(False)

    def update_string_settings_panel(self):
        default_style_sheet = self.mw.styleSheet() 

        block_idx = self.mw.data_store.current_block_idx
        string_idx = self.mw.data_store.current_string_idx

        if block_idx == -1 or string_idx == -1:
            self.mw.font_combobox.setEnabled(False)
            self.mw.width_spinbox.setEnabled(False)
            self.mw.apply_width_button.setEnabled(False)
            self.mw.font_combobox.setCurrentIndex(0)
            self.mw.width_spinbox.setValue(0)
            self.mw.width_spinbox.setStyleSheet("")
            self.mw.font_combobox.setStyleSheet("")
            return

        self.mw.font_combobox.setEnabled(True)
        self.mw.width_spinbox.setEnabled(True)

        metadata_key = (block_idx, string_idx)
        string_meta = self.mw.string_metadata.get(metadata_key, {})

        # Оновлення шрифту
        font_file = string_meta.get("font_file")
        if font_file and font_file != self.mw.default_font_file:
            index = self.mw.font_combobox.findData(font_file)
            if index != -1:
                self.mw.font_combobox.setCurrentIndex(index)
                self.mw.font_combobox.setStyleSheet(self.highlight_style)
            else:
                self.mw.font_combobox.setCurrentIndex(0)
                self.mw.font_combobox.setStyleSheet("")
        else:
            self.mw.font_combobox.setCurrentIndex(0)
            self.mw.font_combobox.setStyleSheet("")

        # Оновлення ширини
        width = string_meta.get("width")
        self.mw.width_spinbox.blockSignals(True)
        if width and width != self.mw.line_width_warning_threshold_pixels:
            self.mw.width_spinbox.setValue(width)
            self.mw.width_spinbox.setStyleSheet(self.highlight_style)
        else:
            self.mw.width_spinbox.setValue(self.mw.line_width_warning_threshold_pixels)
            self.mw.width_spinbox.setStyleSheet("")
        self.mw.width_spinbox.blockSignals(False)
        self.mw.apply_width_button.setEnabled(False)