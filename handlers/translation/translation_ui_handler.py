# handlers/translation/translation_ui_handler.py ---
import json
import re
from typing import Dict, List, Optional, Tuple, Any

from PyQt6.QtWidgets import QDialog, QMessageBox, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor

from .base_translation_handler import BaseTranslationHandler
from components.translation_variations_dialog import TranslationVariationsDialog
from components.session_bootstrap_dialog import SessionBootstrapDialog
from components.ai_status_dialog import AIStatusDialog
from utils.utils import convert_spaces_to_dots_for_display
from core.state_manager import AppState

class TranslationUIHandler(BaseTranslationHandler):
    """Handler for translation u i operations."""
    def __init__(self, main_handler):
        """Initialize a new instance."""
        self.main_handler = main_handler
        super().__init__(main_handler)
        self._status_dialog: Optional[AIStatusDialog] = None

    def _set_ai_controls_enabled(self, enabled: bool) -> None:
        """Internal helper to set the ai controls enabled."""
        for attr in ('ai_translate_button', 'ai_variation_button'):
            control = getattr(self.mw, attr, None)
            if control is not None:
                control.setEnabled(enabled)


    @property
    def status_dialog(self) -> AIStatusDialog:
        """Status dialog."""
        if self._status_dialog is None:
            self._status_dialog = AIStatusDialog(self.mw)
        return self._status_dialog

    def show_variations_dialog(self, variations: List[str], show_refresh: bool = False, parent: Optional[Any] = None) -> Optional[str]:
        """Show variations dialog."""
        self.update_status_message("AI: choose one of the suggested options", persistent=False)
        parent_widget = parent if parent is not None else self.mw
        dialog = TranslationVariationsDialog(parent_widget, variations, show_refresh=show_refresh)
        dialog.setModal(True)
        self._set_ai_controls_enabled(False)

        dialog.exec()

        self._set_ai_controls_enabled(True)

        res = dialog.result()
        if res == QDialog.DialogCode.Accepted:
            return dialog.selected_translation
        elif res == 2:
            return "__REFRESH__"
        return None

    def prompt_session_bootstrap(self, system_prompt: str) -> Optional[str]:
        """Prompt session bootstrap."""
        dialog = SessionBootstrapDialog(self.mw, system_prompt)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.get_instructions()

    def confirm_line_count(self, expected: int, translation: str, *, strict: bool, mode_label: str) -> bool:
        """Confirm line count."""
        actual = len(translation.split('\n')) if translation else 0
        if actual == expected:
            return True
        
        message = f"Expected {expected} lines, received {actual}. The translation for {mode_label} may break formatting. Apply?"
        if strict:
            QMessageBox.warning(self.mw, "AI Translation", message)
            return False
        
        reply = QMessageBox.question(self.mw, "AI Translation", message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes

    def apply_full_translation(self, new_text: str):
        """Apply full translation."""
        edited_widget = getattr(self.mw, 'edited_text_edit', None)
        if not edited_widget: return

        visual_text = new_text
        if self.mw.current_game_rules:
            visual_text = self.mw.current_game_rules.get_text_representation_for_editor(str(new_text))
        
        display_text = convert_spaces_to_dots_for_display(visual_text, self.mw.show_multiple_spaces_as_dots)

        cursor = edited_widget.textCursor()
        with self.mw.state.enter(AppState.PROGRAMMATIC_TEXT_CHANGE):
            cursor.beginEditBlock()
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.insertText(display_text)
            cursor.endEditBlock()
        
        restored = edited_widget.textCursor()
        restored.movePosition(QTextCursor.MoveOperation.End)
        edited_widget.setTextCursor(restored)
        
        self.mw.editor_operation_handler.text_edited()

    def apply_inline_variation(self, variation: str):
        """Apply inline variation."""
        edited_widget = getattr(self.mw, 'edited_text_edit', None)
        if not edited_widget: return
        
        cursor = edited_widget.textCursor()
        if not cursor.hasSelection():
            QMessageBox.warning(self.mw, "Apply Variation", "No text selected to apply variation to.")
            return

        with self.mw.state.enter(AppState.PROGRAMMATIC_TEXT_CHANGE):
            cursor.beginEditBlock()
            cursor.insertText(variation)
            cursor.endEditBlock()
        
        self.mw.editor_operation_handler.text_edited()

    def apply_partial_translation(self, translated_segment: str, start_line: int, end_line: int):
        """Apply partial translation."""
        current_text, _ = self.data_processor.get_current_string_text(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
        current_lines = str(current_text).split('\n')
        translated_lines = translated_segment.split('\n') if translated_segment else []
        
        for offset, new_line in enumerate(translated_lines):
            target_idx = start_line + offset
            if len(current_lines) <= target_idx: current_lines.append('')
            current_lines[target_idx] = new_line
        
        self.apply_full_translation('\n'.join(current_lines))

    def normalize_line_count(self, translation: str, expected_lines: int, mode_label: str) -> str:
        """Normalize line count."""
        text = translation or ''
        lines = text.split('\n')
        if len(lines) < expected_lines:
            lines.extend([''] * (expected_lines - len(lines)))
        return '\n'.join(lines[:expected_lines])

    def parse_variation_payload(self, raw_text: str) -> List[str]:
        """Parse variation payload."""
        text = (raw_text or '').strip()
        if not text: return []

        def extract_list(obj) -> Optional[List[str]]:
            """Extract list."""
            if isinstance(obj, list):
                return [str(item) for item in obj]
            if isinstance(obj, dict):
                # Search for lists by known keys
                for key in ["variations", "variants", "options", "translations", "results"]:
                    if key in obj and isinstance(obj[key], list):
                        return [str(item) for item in obj[key]]
                # Search for any value that is a list
                for val in obj.values():
                    if isinstance(val, list) and val:
                        return [str(item) for item in val]
            return None

        # Strategy 1: Look for JSON code blocks (either array or object)
        import re
        code_block_pattern = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", re.IGNORECASE)
        matches = code_block_pattern.findall(text)
        if matches:
            try:
                parsed = json.loads(matches[-1])
                res = extract_list(parsed)
                if res is not None:
                    return res
            except json.JSONDecodeError:
                pass

        # Strategy 2: Scan for the last valid JSON array or object in the text
        # (Handles cases where reasoning precedes the JSON without code blocks)
        for start_char, end_char in [('[', ']'), ('{', '}')]:
            try:
                end_idx = text.rfind(end_char)
                if end_idx != -1:
                    cursor = end_idx
                    while cursor >= 0:
                        start_idx = text.rfind(start_char, 0, cursor)
                        if start_idx == -1:
                            break
                        
                        candidate = text[start_idx : end_idx+1]
                        try:
                            parsed = json.loads(candidate)
                            res = extract_list(parsed)
                            if res is not None:
                                return res
                        except json.JSONDecodeError:
                            cursor = start_idx
            except Exception:
                pass

        # Strategy 3: Try parsing the entire text as JSON
        try:
            parsed = json.loads(text)
            res = extract_list(parsed)
            if res is not None:
                return res
        except json.JSONDecodeError:
            pass

        # Strategy 4: Fallback to simple line parsing if JSON fails
        numbered_pattern = re.compile(r'^\s*\d+[\).:-]\s*', re.MULTILINE)
        if numbered_pattern.search(text):
            return [numbered_pattern.sub('', line).strip() for line in text.splitlines() if line.strip()]
        
        return [chunk.strip() for chunk in text.split('\n\n') if chunk.strip()]

    def update_status_message(self, message: str, *, persistent: bool = True) -> None:
        """Update the status message."""
        if self.mw.statusBar: self.mw.statusBar.showMessage(message, 0 if persistent else 4000)

    def clear_status_message(self) -> None:
        """Remove status message."""
        if self.mw.statusBar: self.mw.statusBar.clearMessage()
    
    def start_ai_operation(self, title: str, is_chunked: bool = False, model_name: Optional[str] = None, parent: Optional[Any] = None):
        """Start ai operation."""
        self.main_handler.current_session_translations = {}
        self.main_handler.current_session_previous_translations = {}
        self._set_ai_controls_enabled(False)
        
        parent_widget = parent if parent is not None else self.mw
        if self._status_dialog is not None and self._status_dialog.parentWidget() != parent_widget:
            self._status_dialog.deleteLater()
            self._status_dialog = None
            
        if self._status_dialog is None:
            self._status_dialog = AIStatusDialog(parent_widget)
            
        self._status_dialog.start(title, is_chunked, model_name=model_name)
        try:
            self._status_dialog.cancelled.disconnect(self._handle_dialog_rejection)
        except TypeError:
            pass # Signal was not connected yet
        self._status_dialog.cancelled.connect(self._handle_dialog_rejection)

    def _handle_dialog_rejection(self):
        """Internal helper to handle dialog rejection."""
        if self.main_handler.worker:
            self.main_handler.worker.cancel()
        self.main_handler.prompt_for_revert_after_cancel()

    def update_ai_operation_step(self, step_index: int, text: str, status: int):
        """Update the ai operation step."""
        self.status_dialog.update_step(step_index, text, status)

    def finish_ai_operation(self, success: bool = True, show_popup: bool = True, translation_details: Optional[Dict[int, List[Tuple[int, str]]]] = None, previous_translations: Optional[Dict[int, List[Tuple[int, str]]]] = None):
        """Finish ai operation."""
        self.status_dialog.finish(success, show_popup=show_popup, translation_details=translation_details, previous_translations=previous_translations)
        self._set_ai_controls_enabled(True)

    def merge_session_instructions(self, instructions: str, message: str) -> str:
        """Merge session instructions."""
        instructions_clean = (instructions or '').strip()
        return f"{instructions_clean}\n\n{message}" if instructions_clean and message else instructions_clean or message

    def _activate_entry(self, entry: Dict[str, object]) -> None:
        """Internal helper to activate entry."""
        block = entry.get('block_idx')
        string = entry.get('string_idx')
        line_idx = entry.get('line_idx')
        if block is None or string is None: return

        block_idx, string_idx = int(block), int(string)
        line_number = int(line_idx) if line_idx is not None else None

        block_widget = getattr(self.mw, 'block_list_widget', None)
        current_block_idx = getattr(self.mw.data_store, 'current_block_idx', -1)
        block_changed = (block_idx != current_block_idx)

        if block_widget and hasattr(block_widget, 'select_block_by_index'):
            block_widget.select_block_by_index(block_idx)

        def select_string_and_scroll():
            """Select string and scroll."""
            if hasattr(self.mw, 'list_selection_handler'):
                self.mw.list_selection_handler.select_string_by_absolute_index(string_idx)
            else:
                self.mw.data_store.current_block_idx = block_idx
                self.mw.data_store.current_string_idx = string_idx
                self.ui_updater.populate_strings_for_block(block_idx)
                self.mw.ui_updater.update_text_views()

            editor = getattr(self.mw, 'original_text_edit', None)
            if editor and line_number is not None:
                block_obj = editor.document().findBlockByNumber(line_number)
                if block_obj.isValid():
                    cursor = editor.textCursor()
                    cursor.setPosition(block_obj.position())
                    editor.setTextCursor(cursor)
                    editor.ensureCursorVisible()

            def apply_focus():
                """Apply focus."""
                if hasattr(self.mw, 'edited_text_edit') and self.mw.edited_text_edit:
                    self.mw.edited_text_edit.setFocus(Qt.FocusReason.OtherFocusReason)
                elif editor:
                    editor.setFocus(Qt.FocusReason.OtherFocusReason)
                self.mw.raise_()
                self.mw.activateWindow()

            QTimer.singleShot(100, apply_focus)

        if block_changed:
            QTimer.singleShot(200, select_string_and_scroll)
        else:
            select_string_and_scroll()
