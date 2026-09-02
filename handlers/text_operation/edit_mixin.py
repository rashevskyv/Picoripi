from __future__ import annotations
import re
from PyQt6.QtWidgets import QMessageBox, QApplication, QPlainTextEdit
from PyQt6.QtCore import Qt
from utils.logging_utils import log_debug
from utils.utils import calculate_string_width, remove_all_tags
from core.i18n import tr


class EditMixin:
    """Paste, revert, and width calculation actions."""

    def paste_block_text(self) -> None:
        """Paste block text."""
        log_debug("--> TextOperationHandler: paste_block_text triggered.")
        if self.mw.data_store.physical_block_idx == -1:
            QMessageBox.warning(self.mw, tr('Paste Error'), tr('Please select a block.'))
            return
        if not self.mw.current_game_rules:
            QMessageBox.warning(self.mw, tr('Paste Error'), tr('Game rules not loaded.'))
            return
            
        block_idx: int = self.mw.data_store.physical_block_idx
        
        self.mw.before_paste_edited_data_snapshot = {
            k: v for k,v in self.mw.data_store.edited_data.items() if k[0] == block_idx
        }
        self.mw.before_paste_block_idx_affected = block_idx
        
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if preview_edit and hasattr(preview_edit, 'highlightManager'):
            preview_edit.highlightManager.clearAllProblemHighlights() 
        
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if edited_edit and hasattr(edited_edit, 'highlightManager'):
            edited_edit.highlightManager.clearAllProblemHighlights()
        
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.begin_group()
            
        self.ui_updater.update_block_item_text_with_problem_count(block_idx)

            
        start_string_idx = self.mw.data_store.current_string_idx if self.mw.data_store.current_string_idx != -1 else 0
        pasted_text_raw = QApplication.clipboard().text()
        if not pasted_text_raw: QMessageBox.information(self.mw, tr('Paste'), tr('Clipboard empty.')); return
        
        segments_from_clipboard_raw = re.split(r'\{END\}\r?\n', pasted_text_raw)
        parsed_strings = []
        num_raw_segments = len(segments_from_clipboard_raw)
        for i, segment in enumerate(segments_from_clipboard_raw):
            cleaned_segment = segment
            if i > 0 and segment.startswith('\n'): cleaned_segment = segment[1:]
            if cleaned_segment or i < num_raw_segments - 1: parsed_strings.append(cleaned_segment)
        
        if parsed_strings and not parsed_strings[-1] and num_raw_segments > 1 and segments_from_clipboard_raw[-1] == '':
            parsed_strings.pop()
            
        if not parsed_strings: QMessageBox.information(self.mw, tr('Paste'), tr('No valid segments found.')); return
        
        original_block_len = len(self.mw.data_store.data[block_idx])
        successfully_processed_count = 0
        any_change_applied_to_data = False
        
        for i, segment_to_insert_raw in enumerate(parsed_strings):
            current_target_string_idx = start_string_idx + i
            if current_target_string_idx >= original_block_len:
                if i == 0:
                    QMessageBox.warning(self.mw, tr('Paste Error'), f"Cannot paste starting at line {start_string_idx + 1}. Block has {original_block_len} lines.")
                break
            
            original_text_for_tags = self.mw.data_store.data[block_idx][current_target_string_idx]
            
            processed_text, _, _ = self.mw.current_game_rules.process_pasted_segment(
                segment_to_insert_raw, original_text_for_tags, self.mw.EDITOR_PLAYER_TAG
            )
            final_text_to_apply = processed_text.rstrip('\n')
            
            if self.data_processor.update_edited_data(block_idx, current_target_string_idx, final_text_to_apply):
                if hasattr(self.mw, 'title_status_bar_updater'):
                    self.mw.title_status_bar_updater.update_title()
                elif hasattr(self.ui_updater, 'update_title'): 
                    self.ui_updater.update_title()
            
            # Rescan issues for this pasted string so warnings update immediately
            self._rescan_issues_for_current_string(block_idx, current_target_string_idx, final_text_to_apply)
            
            old_text_for_this_line = self.mw.before_paste_edited_data_snapshot.get((block_idx, current_target_string_idx), original_text_for_tags)
            if final_text_to_apply != old_text_for_this_line:
                 any_change_applied_to_data = True
            successfully_processed_count += 1
        
        # Smoothly update problem counts in block list instead of full rebuild
        self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)
        self.mw.ui_updater.populate_current_view(force=True)
        self.mw.ui_updater.update_text_views()
        

        if any_change_applied_to_data:
            self.mw.can_undo_paste = True
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(True)
        else:
            self.mw.can_undo_paste = False;
            if hasattr(self.mw, 'undo_paste_action'): self.mw.undo_paste_action.setEnabled(False)
            
        if hasattr(self.mw, 'undo_manager'):
            self.mw.undo_manager.end_group("PASTE")
            
        log_debug("<-- TextOperationHandler: paste_block_text finished.")

    def revert_single_line(self, line_index: int) -> None:
        """Revert single line."""
        block_idx = self.mw.data_store.physical_block_idx
        if block_idx == -1:
             return
             
        original_text = self.data_processor._get_string_from_source(block_idx, line_index, self.mw.data_store.data, "original_for_revert")
        
        if original_text is None:
            QMessageBox.warning(self.mw, tr('Revert Error'), f"Could not find original text for data line {line_index + 1}.")
            return

        current_text, _ = self.data_processor.get_current_string_text(block_idx, line_index)
        
        if current_text == original_text:
             return
        
        if self.data_processor.update_edited_data(block_idx, line_index, original_text, action_type="REVERT"):
            if hasattr(self.mw, 'title_status_bar_updater'):
                self.mw.title_status_bar_updater.update_title()
            elif hasattr(self.ui_updater, 'update_title'): 
                self.ui_updater.update_title()

        # Update problem analysis for this reverted string immediately
        self._rescan_issues_for_current_string(block_idx, line_index, original_text)

        # Update block list tree counts smoothly without rebuilding the tree or resetting focus/selection
        self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)
        
        # Update strings preview list with force=True to ensure it regenerates cached values
        self.mw.ui_updater.populate_current_view(force=True)
        self.mw.ui_updater.update_text_views()
        

        if hasattr(self.mw, 'statusBar'):
             self.mw.statusBar.showMessage(f"Data line {line_index + 1} reverted to original.", 2000)
        if self.mw.data_store.current_string_idx == line_index:
            original_edit = getattr(self.mw, 'original_text_edit', None)
            edited_edit = getattr(self.mw, 'edited_text_edit', None)
            if original_edit and hasattr(original_edit, 'lineNumberArea'): original_edit.lineNumberArea.update()
            if edited_edit and hasattr(edited_edit, 'lineNumberArea'): edited_edit.lineNumberArea.update()

    def calculate_width_for_data_line_action(self, data_line_idx: int) -> None:
        """Calculate width for data line action."""
        if self.mw.data_store.physical_block_idx == -1 or data_line_idx < 0:
            QMessageBox.warning(self.mw, tr('Calculate Width Error'), tr('No block or data line selected.'))
            return

        current_text_data_line, source = self.data_processor.get_current_string_text(self.mw.data_store.physical_block_idx, data_line_idx)
        original_text_data_line = self.data_processor._get_string_from_source(self.mw.data_store.physical_block_idx, data_line_idx, self.mw.data_store.data, "width_calc_original_data_line")

        if current_text_data_line is None and original_text_data_line is None:
            QMessageBox.warning(self.mw, tr('Calculate Width Error'), f"Could not retrieve text for data line {data_line_idx + 1}.")
            return
        
        if not self.mw.font_map:
             QMessageBox.warning(self.mw, tr('Calculate Width Error'), tr('Font map is not loaded. Cannot calculate width.'))
             return
        if not self.mw.current_game_rules:
            QMessageBox.warning(self.mw, tr('Calculate Width Error'), tr('Game rules plugin not loaded.'))
            return

        from utils.utils import resolve_width_limits
        string_meta = self.mw.string_metadata.get((self.mw.data_store.physical_block_idx, data_line_idx), {})
        warning_threshold, logical_hard_limit = resolve_width_limits(
            string_meta, getattr(self.mw, 'current_game_rules', None),
            self.mw.data_store.physical_block_idx, data_line_idx,
            self.mw.line_width_warning_threshold_pixels, self.mw.game_dialog_max_width_pixels)
        max_allowed_width = logical_hard_limit

        font_map_for_string = self.mw.helper.get_font_map_for_string(self.mw.data_store.physical_block_idx, data_line_idx)
        
        info_parts = [f"Data Line {data_line_idx + 1} (Block {self.mw.data_store.physical_block_idx}):\nMax Allowed Width (Game Dialog Limit): {logical_hard_limit}px\nWidth Guideline Threshold: {warning_threshold}px\n"]
        
        problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        
        # Use problem_analyzer if it exists, otherwise use the game rules object itself
        analyzer = getattr(self.mw.current_game_rules, 'problem_analyzer', self.mw.current_game_rules)

        sources_to_check = [
            ("Current", str(current_text_data_line), source),
            ("Original", str(original_text_data_line), "original_data")
        ]

        for title_prefix, text_to_analyze, text_source_info in sources_to_check:
            info_parts.append(f"--- {title_prefix} Text (Source: {text_source_info}) ---")
            
            game_like_text_no_newlines_rstripped = remove_all_tags(text_to_analyze.replace('\n','')).rstrip()
            total_game_width = calculate_string_width(game_like_text_no_newlines_rstripped, font_map_for_string)
            game_status = "OK"
            if total_game_width > logical_hard_limit:
                game_status = f"EXCEEDS GAME DIALOG LIMIT ({total_game_width - logical_hard_limit}px)"
            info_parts.append(f"Total (game-like, no newlines): {total_game_width}px ({game_status})")

            logical_sublines = []
            if hasattr(analyzer, '_get_sublines_from_data_string'):
                logical_sublines = analyzer._get_sublines_from_data_string(text_to_analyze)
            else:
                logical_sublines = text_to_analyze.split('\n')

            for subline_idx, sub_line_text in enumerate(logical_sublines):
                sub_line_no_tags_rstripped = remove_all_tags(sub_line_text).rstrip()
                width_px = calculate_string_width(sub_line_no_tags_rstripped, font_map_for_string)
                
                current_subline_problems = set()
                if hasattr(analyzer, 'analyze_data_string'):
                    problems_per_subline_list = analyzer.analyze_data_string(text_to_analyze, font_map_for_string, warning_threshold, logical_hard_limit)
                    current_subline_problems = problems_per_subline_list[subline_idx] if subline_idx < len(problems_per_subline_list) else set()
                elif hasattr(analyzer, 'analyze_subline'):
                    next_original_subline = logical_sublines[subline_idx + 1] if subline_idx + 1 < len(logical_sublines) else None
                    current_subline_problems = analyzer.analyze_subline(
                        text=sub_line_text,
                        next_text=next_original_subline,
                        subline_number_in_data_string=subline_idx,
                        qtextblock_number_in_editor=subline_idx, 
                        is_last_subline_in_data_string=(subline_idx == len(logical_sublines) - 1),
                        editor_font_map=font_map_for_string,
                        editor_line_width_threshold=warning_threshold,
                        full_data_string_text_for_logical_check=text_to_analyze,
                        logical_hard_limit=logical_hard_limit
                    )
                
                statuses = []
                for prob_id in current_subline_problems:
                    if prob_id in problem_definitions:
                        statuses.append(problem_definitions[prob_id]['name'])
                
                status_str = ", ".join(statuses) if statuses else "OK"
                info_parts.append(f"  Sub-line {subline_idx+1} (rstripped): {width_px}px ({status_str}) '{sub_line_no_tags_rstripped[:30]}...'")
            if title_prefix == "Current": info_parts.append("") 
        
        result_dialog = QMessageBox(self.mw)
        result_dialog.setWindowTitle(f"Width Analysis for Data Line {data_line_idx + 1}")
        result_dialog.setTextFormat(Qt.TextFormat.PlainText)
        result_dialog.setText("\n".join(info_parts))
        result_dialog.setIcon(QMessageBox.Icon.Information)
        result_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        text_edit_for_size = result_dialog.findChild(QPlainTextEdit)
        if text_edit_for_size:
            text_edit_for_size.setMinimumWidth(700)
            text_edit_for_size.setMinimumHeight(500)
        result_dialog.exec()
