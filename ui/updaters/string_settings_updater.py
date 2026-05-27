# --- START OF FILE ui/updaters/string_settings_updater.py ---
from pathlib import Path
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtGui import QColor, QPalette
from .base_ui_updater import BaseUIUpdater
from utils.utils import log_debug

class StringSettingsUpdater(BaseUIUpdater):
    def __init__(self, main_window, data_processor):
        super().__init__(main_window, data_processor)
        self.highlight_style = "QComboBox, QSpinBox QLineEdit { border: 1px solid rgba(147, 112, 219, 180); background-color: rgba(147, 112, 219, 30); }"

    def update_font_combobox(self):
        self.mw.font_combobox.blockSignals(True)
        self.mw.font_combobox.clear()

        default_font_display_text = f"Default ({self.mw.default_font_file or 'None'})"
        self.mw.font_combobox.addItem(default_font_display_text, "default")

        all_fonts = getattr(self.mw, 'all_font_maps', {})
        if all_fonts:
            for font_key in sorted(all_fonts.keys()):
                if font_key != self.mw.default_font_file:
                    self.mw.font_combobox.addItem(font_key, font_key)
        
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
            if hasattr(self.mw, 'speaker_label') and self.mw.speaker_label:
                self.mw.speaker_label.setText("")
            return

        self.mw.font_combobox.setEnabled(True)
        self.mw.width_spinbox.setEnabled(True)

        # Update Speaker Label instantly from MemePalace cache
        if hasattr(self.mw, 'speaker_label') and self.mw.speaker_label:
            speaker_text = ""
            import os
            
            block_label = ""
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and \
               self.mw.project_manager.project and block_idx < len(self.mw.project_manager.project.blocks):
                block_label = self.mw.project_manager.project.blocks[block_idx].name
            else:
                name_key = str(block_idx)
                if hasattr(self.mw, 'data_store') and self.mw.data_store and \
                   self.mw.data_store.block_names and name_key in self.mw.data_store.block_names:
                    b_desc = self.mw.data_store.block_names[name_key]
                    if "Message ID" in b_desc:
                        block_label = b_desc.partition("(")[0].strip()
                
                if not block_label and hasattr(self.mw, 'data_store') and self.mw.data_store:
                    json_path = getattr(self.mw.data_store, "json_path", None)
                    if json_path and isinstance(json_path, (str, bytes)):
                        block_label = os.path.splitext(os.path.basename(json_path))[0]
                        
                if not block_label:
                    block_label = f"Block_{block_idx}"
            
            bmg_id = f"{block_label}_Str_{string_idx}"
            
            raw_text = ""
            if hasattr(self.mw, 'data_processor') and self.mw.data_processor:
                raw_text, _ = self.mw.data_processor.get_current_string_text(block_idx, string_idx)
            
            composer = None
            if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                composer = getattr(self.mw.translation_handler, 'prompt_composer', None)
                
            client = None
            if composer and hasattr(composer, '_get_mempalace_client'):
                client = composer._get_mempalace_client()
            else:
                try:
                    from core.mempalace_client import MemePalaceClient
                    project_dir = None
                    if hasattr(self.mw, "project_manager") and self.mw.project_manager:
                        project_dir = getattr(self.mw.project_manager, "project_dir", None)
                    if not project_dir and hasattr(self.mw, "data_store") and self.mw.data_store:
                        project_file = getattr(self.mw.data_store, "project_file", None)
                        if project_file and isinstance(project_file, (str, bytes)):
                            project_dir = os.path.dirname(project_file)
                    if project_dir and isinstance(project_dir, (str, bytes)):
                        client = MemePalaceClient(project_dir=project_dir)
                except Exception:
                    pass
                
            if client:
                cached_ctx = client.get_cached_context(bmg_id, raw_text)
                if cached_ctx and cached_ctx.get("speaker"):
                    speaker_text = f"Speaker: {cached_ctx.get('speaker')}"
            
            self.mw.speaker_label.setText(speaker_text)

        metadata_key = (block_idx, string_idx)
        string_meta = self.mw.string_metadata.get(metadata_key, {})

        # Update font
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

        # Update width
        width = string_meta.get("width")
        self.mw.width_spinbox.blockSignals(True)
        
        line_edit_highlight = "border: 1px solid rgba(147, 112, 219, 180); background-color: rgba(147, 112, 219, 30);"
        
        if width and width != self.mw.game_dialog_max_width_pixels:
            self.mw.width_spinbox.setValue(width)
            if hasattr(self.mw.width_spinbox, 'lineEdit') and self.mw.width_spinbox.lineEdit():
                self.mw.width_spinbox.lineEdit().setStyleSheet(line_edit_highlight)
        else:
            self.mw.width_spinbox.setValue(self.mw.game_dialog_max_width_pixels)
            if hasattr(self.mw.width_spinbox, 'lineEdit') and self.mw.width_spinbox.lineEdit():
                self.mw.width_spinbox.lineEdit().setStyleSheet("")
        self.mw.width_spinbox.blockSignals(False)
        self.mw.apply_width_button.setEnabled(False)