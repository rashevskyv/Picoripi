from pathlib import Path
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtGui import QColor, QPalette
from .base_ui_updater import BaseUIUpdater
from utils.utils import log_debug

class StringSettingsUpdater(BaseUIUpdater):
    def __init__(self, main_window, data_processor):
        super().__init__(main_window, data_processor)
        self.highlight_style = (
            "QComboBox, QSpinBox { "
            "  border: 2px solid rgb(186, 85, 211); "
            "  background-color: rgba(186, 85, 211, 40); "
            "  border-radius: 3px; "
            "} "
            "QSpinBox QLineEdit { "
            "  background: transparent; "
            "  border: none; "
            "}"
        )

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
            try:
                if hasattr(self.mw, 'data_store') and self.mw.data_store.data:
                    if 0 <= block_idx < len(self.mw.data_store.data):
                        block_data = self.mw.data_store.data[block_idx]
                        if 0 <= string_idx < len(block_data):
                            raw_text = block_data[string_idx] or ""
            except Exception:
                pass
            
            composer = None
            if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                composer = getattr(self.mw.translation_handler, 'prompt_composer', None)
                
            if not composer:
                try:
                    from handlers.translation.ai_prompt_composer import AIPromptComposer
                    class DummyHandler:
                        def __init__(self, mw):
                            self.mw = mw
                            self.data_processor = mw.data_processor
                            self.ui_updater = mw.ui_updater
                            self._glossary_manager = getattr(mw, '_glossary_manager', None)
                        def __getattr__(self, name):
                            return getattr(self.mw, name)
                    if not hasattr(self.mw, '_temp_prompt_composer') or self.mw._temp_prompt_composer is None:
                        self.mw._temp_prompt_composer = AIPromptComposer(DummyHandler(self.mw))
                    composer = self.mw._temp_prompt_composer
                except Exception:
                    pass
                    
            if composer:
                result = composer._find_speaker_in_script(block_idx, string_idx, raw_text)
                if result and isinstance(result, (tuple, list)) and len(result) == 2:
                    raw_spk, matched_lines_str = result
                else:
                    raw_spk, matched_lines_str = "NONE", None

                if raw_spk == "NONE":
                    speaker_text = "Speaker: NONE"
                    self.mw.speaker_label.setToolTip("Speaker for the current line mapped from MemePalace")
                else:
                    trans_spk = composer._translate_speaker(raw_spk)
                    speaker_text = f"Speaker: {trans_spk} ({raw_spk})"
                    
                    tooltip_text = ""
                    font_size = getattr(self.mw, 'tooltip_font_size', 11)
                    if matched_lines_str:
                        tooltip_text = f"<div style='font-size: {font_size}px;'>Matching lines in script: <font color='#2e7d32'><b>{matched_lines_str}</b></font></div>"
                    else:
                        tooltip_text = f"<div style='font-size: {font_size}px;'>Speaker for the current line mapped from MemePalace</div>"
                        
                    # Fetch speaker details from glossary
                    glossary_manager = None
                    if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                        glossary_manager = getattr(self.mw.translation_handler, '_glossary_manager', None)
                    if glossary_manager and raw_spk and raw_spk != "NONE":
                        spk_parts = [s.strip() for s in raw_spk.split(",") if s.strip()]
                        glossary_infos = []
                        for spk in spk_parts:
                            entry = glossary_manager.get_entry(spk)
                            if entry:
                                info = f"• <b>{entry.original}</b>"
                                if entry.translation:
                                    info += f" —> <font color='#2e7d32'><b>{entry.translation}</b></font>"
                                if entry.notes:
                                    try:
                                        import markdown
                                        notes_html = markdown.markdown(entry.notes, extensions=['nl2br'])
                                        info += f"<br><div style='margin-left: 15px; font-weight: normal;'>{notes_html}</div>"
                                    except Exception:
                                        info += f"<br><div style='margin-left: 15px; font-style: italic; font-weight: normal;'>{entry.notes}</div>"
                                glossary_infos.append(info)
                        if glossary_infos:
                            tooltip_text += f"<br><div style='font-size: {font_size}px;'><b>Glossary Info:</b><br>" + "<br>".join(glossary_infos) + "</div>"
                            
                    self.mw.speaker_label.setToolTip(tooltip_text)
            else:
                self.mw.speaker_label.setToolTip("Speaker for the current line mapped from MemePalace")
            
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
        
        if width and width != self.mw.game_dialog_max_width_pixels:
            self.mw.width_spinbox.setValue(width)
            self.mw.width_spinbox.setStyleSheet(self.highlight_style)
        else:
            self.mw.width_spinbox.setValue(self.mw.game_dialog_max_width_pixels)
            self.mw.width_spinbox.setStyleSheet("")
        self.mw.width_spinbox.blockSignals(False)
        self.mw.apply_width_button.setEnabled(False)