# --- START OF FILE handlers/translation/translation_ui_handler.py ---
# handlers/translation/translation_ui_handler.py ---
import json
import re
from typing import Dict, List, Optional, Tuple

from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor

from .base_translation_handler import BaseTranslationHandler
from components.translation_variations_dialog import TranslationVariationsDialog
from components.session_bootstrap_dialog import SessionBootstrapDialog
from components.ai_status_dialog import AIStatusDialog
from utils.utils import convert_spaces_to_dots_for_display

class TranslationUIHandler(BaseTranslationHandler):
    def __init__(self, main_handler):
        self.main_handler = main_handler
        super().__init__(main_handler)
        self._status_dialog: Optional[AIStatusDialog] = None

    def _set_ai_controls_enabled(self, enabled: bool) -> None:
        for attr in ('ai_translate_button', 'ai_variation_button'):
            control = getattr(self.mw, attr, None)
            if control is not None:
                control.setEnabled(enabled)


    @property
    def status_dialog(self) -> AIStatusDialog:
        if self._status_dialog is None:
            self._status_dialog = AIStatusDialog(self.mw)
        return self._status_dialog

    def show_variations_dialog(self, variations: List[str]) -> Optional[str]:
        self.update_status_message("AI: choose one of the suggested options", persistent=False)
        dialog = TranslationVariationsDialog(self.mw, variations)
        if dialog.exec_() == dialog.Accepted:
            return dialog.selected_translation
        return None

    def prompt_session_bootstrap(self, system_prompt: str) -> Optional[str]:
        dialog = SessionBootstrapDialog(self.mw, system_prompt)
        if dialog.exec_() != dialog.Accepted:
            return None
        return dialog.get_instructions()

    def confirm_line_count(self, expected: int, translation: str, *, strict: bool, mode_label: str) -> bool:
        actual = len(translation.split('\n')) if translation else 0
        if actual == expected:
            return True
        
        message = f"Expected {expected} lines, received {actual}. The translation for {mode_label} may break formatting. Apply?"
        if strict:
            QMessageBox.warning(self.mw, "AI Translation", message)
            return False
        
        reply = QMessageBox.question(self.mw, "AI Translation", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return reply == QMessageBox.Yes

    def apply_full_translation(self, new_text: str):
        edited_widget = getattr(self.mw, 'edited_text_edit', None)
        if not edited_widget: return

        visual_text = new_text
        if self.mw.current_game_rules:
            visual_text = self.mw.current_game_rules.get_text_representation_for_editor(str(new_text))
        
        display_text = convert_spaces_to_dots_for_display(visual_text, self.mw.show_multiple_spaces_as_dots)

        cursor = edited_widget.textCursor()
        self.mw.is_programmatically_changing_text = True
        cursor.beginEditBlock()
        cursor.select(QTextCursor.Document)
        cursor.insertText(display_text)
        cursor.endEditBlock()
        self.mw.is_programmatically_changing_text = False
        
        restored = edited_widget.textCursor()
        restored.movePosition(QTextCursor.End)
        edited_widget.setTextCursor(restored)
        
        self.mw.editor_operation_handler.text_edited()

    def apply_inline_variation(self, variation: str):
        edited_widget = getattr(self.mw, 'edited_text_edit', None)
        if not edited_widget: return
        
        cursor = edited_widget.textCursor()
        if not cursor.hasSelection():
            QMessageBox.warning(self.mw, "Apply Variation", "No text selected to apply variation to.")
            return

        self.mw.is_programmatically_changing_text = True
        cursor.beginEditBlock()
        cursor.insertText(variation)
        cursor.endEditBlock()
        self.mw.is_programmatically_changing_text = False
        
        self.mw.editor_operation_handler.text_edited()

    def apply_partial_translation(self, translated_segment: str, start_line: int, end_line: int):
        current_text, _ = self.data_processor.get_current_string_text(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
        current_lines = str(current_text).split('\n')
        translated_lines = translated_segment.split('\n') if translated_segment else []
        
        for offset, new_line in enumerate(translated_lines):
            target_idx = start_line + offset
            if len(current_lines) <= target_idx: current_lines.append('')
            current_lines[target_idx] = new_line
        
        self.apply_full_translation('\n'.join(current_lines))

    def normalize_line_count(self, translation: str, expected_lines: int, mode_label: str) -> str:
        text = translation or ''
        lines = text.split('\n')
        if len(lines) < expected_lines:
            lines.extend([''] * (expected_lines - len(lines)))
        return '\n'.join(lines[:expected_lines])

    def parse_variation_payload(self, raw_text: str) -> List[str]:
        text = (raw_text or '').strip()
        if not text: return []
        
        # Strategy 1: Look for JSON code blocks
        import re
        code_block_pattern = re.compile(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", re.IGNORECASE)
        matches = code_block_pattern.findall(text)
        if matches:
            # Try parsing the LAST code block found, as reasoning often comes first
            try:
                parsed = json.loads(matches[-1])
                if isinstance(parsed, list):
                    return [str(item) for item in parsed if isinstance(item, str)]
            except json.JSONDecodeError:
                pass

        # Strategy 2: Scan for the last valid JSON array in the text
        # (Handles cases where reasoning precedes the JSON without code blocks)
        try:
            # Find the last closing bracket
            end_idx = text.rfind(']')
            if end_idx != -1:
                # Iterate backwards to find the matching opening bracket
                cursor = end_idx
                while cursor >= 0:
                    start_idx = text.rfind('[', 0, cursor)
                    if start_idx == -1:
                        break
                    
                    candidate = text[start_idx : end_idx+1]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, list):
                            return [str(item) for item in parsed if isinstance(item, str)]
                    except json.JSONDecodeError:
                        # If parse fails, keep searching backwards for an earlier '['
                        cursor = start_idx
                    else:
                        cursor = -1 # Should not happen if successful, but to prevent infinite loop
        except Exception:
            pass

        # Strategy 3: Fallback to simple line parsing if JSON fails
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if isinstance(item, str)]
        except json.JSONDecodeError:
            pass

        numbered_pattern = re.compile(r'^\s*\d+[\).:-]\s*', re.MULTILINE)
        if numbered_pattern.search(text):
            return [numbered_pattern.sub('', line).strip() for line in text.splitlines() if line.strip()]
        
        return [chunk.strip() for chunk in text.split('\n\n') if chunk.strip()]

    def update_status_message(self, message: str, *, persistent: bool = True) -> None:
        if self.mw.statusBar: self.mw.statusBar.showMessage(message, 0 if persistent else 4000)

    def clear_status_message(self) -> None:
        if self.mw.statusBar: self.mw.statusBar.clearMessage()
    
    def start_ai_operation(self, title: str, is_chunked: bool = False, model_name: Optional[str] = None):
        self._set_ai_controls_enabled(False)
        self.status_dialog.start(title, is_chunked, model_name=model_name)
        self.status_dialog.cancelled.connect(self._handle_dialog_rejection)

    def _handle_dialog_rejection(self):
        if self.main_handler.worker:
            self.main_handler.worker.cancel()
        self.main_handler.prompt_for_revert_after_cancel()

    def update_ai_operation_step(self, step_index: int, text: str, status: int):
        self.status_dialog.update_step(step_index, text, status)

    def finish_ai_operation(self):
        self.status_dialog.finish()
        self._set_ai_controls_enabled(True)

    def merge_session_instructions(self, instructions: str, message: str) -> str:
        instructions_clean = (instructions or '').strip()
        return f"{instructions_clean}\n\n{message}" if instructions_clean and message else instructions_clean or message

    def _activate_entry(self, entry: Dict[str, object]) -> None:
        block = entry.get('block_idx')
        string = entry.get('string_idx')
        line_idx = entry.get('line_idx')
        if block is None or string is None: return

        block_idx, string_idx = int(block), int(string)
        line_number = int(line_idx) if line_idx is not None else None

        block_widget = getattr(self.mw, 'block_list_widget', None)
        if block_widget and hasattr(block_widget, 'select_block_by_index'):
            block_widget.select_block_by_index(block_idx)

        self.mw.list_selection_handler.string_selected_from_preview(string_idx)

        editor = getattr(self.mw, 'original_text_edit', None)
        if editor and line_number is not None:
            block_obj = editor.document().findBlockByNumber(line_number)
            if block_obj.isValid():
                cursor = editor.textCursor()
                cursor.setPosition(block_obj.position())
                editor.setTextCursor(cursor)
                editor.ensureCursorVisible()
