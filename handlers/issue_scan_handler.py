# --- START OF FILE handlers/issue_scan_handler.py ---
# handlers/issue_scan_handler.py
from PyQt5.QtWidgets import QMessageBox
from .base_handler import BaseHandler
from utils.logging_utils import log_info, log_debug

class IssueScanHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)

    def _perform_issues_scan_for_block(self, block_idx: int, is_single_block_scan: bool = False, use_default_mappings_in_scan: bool = False):
        if not self.mw.current_game_rules or not (0 <= block_idx < len(self.mw.data_store.data)):
            return

        log_debug(f"Scanning block {block_idx} for issues...")
        
        # Clear existing problems for this block
        keys_to_remove = [k for k in self.mw.data_store.problems_per_subline if k[0] == block_idx]
        for key in keys_to_remove:
            del self.mw.data_store.problems_per_subline[key]
        
        block_data = self.mw.data_store.data[block_idx]
        if not isinstance(block_data, list):
            return

        # Use problem_analyzer if it exists, otherwise use the game rules object itself
        analyzer = getattr(self.mw.current_game_rules, 'problem_analyzer', self.mw.current_game_rules)
        
        for string_idx, _ in enumerate(block_data):
            text, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
            if text is None: continue
            
            text = str(text)
            
            font_map_for_string = self.mw.helper.get_font_map_for_string(block_idx, string_idx)
            
            string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
            width_threshold_for_string = string_meta.get("width", self.mw.line_width_warning_threshold_pixels)
            
            all_problems_for_string = [] # List of sets, one per subline
            
            if hasattr(analyzer, 'analyze_data_string'):
                all_problems_for_string = analyzer.analyze_data_string(text, font_map_for_string, width_threshold_for_string)
            elif hasattr(analyzer, 'analyze_subline'):
                sublines = text.split('\n')
                for i, subline in enumerate(sublines):
                    next_subline = sublines[i+1] if i + 1 < len(sublines) else None
                    problems = analyzer.analyze_subline(
                        text=subline, next_text=next_subline, subline_number_in_data_string=i, qtextblock_number_in_editor=i,
                        is_last_subline_in_data_string=(i == len(sublines) - 1), editor_font_map=font_map_for_string,
                        editor_line_width_threshold=width_threshold_for_string,
                        full_data_string_text_for_logical_check=text
                    )
                    all_problems_for_string.append(problems)
            
            for i, problem_set in enumerate(all_problems_for_string):
                if problem_set:
                    self.mw.data_store.problems_per_subline[(block_idx, string_idx, i)] = problem_set
                    log_debug(f"  Found problems in block {block_idx}, string {string_idx}, subline {i}: {problem_set}")

    def _perform_initial_silent_scan_all_issues(self):
        self.mw.data_store.problems_per_subline.clear()
        if not self.mw.data_store.data:
            return
        
        for block_idx in range(len(self.mw.data_store.data)):
            self._perform_issues_scan_for_block(block_idx)

    def rescan_issues_for_single_block(self, block_idx: int = -1, show_message_on_completion: bool = True, use_default_mappings: bool = True):
        target_block_idx = block_idx if block_idx != -1 else self.mw.data_store.current_block_idx
        if target_block_idx == -1: return
        
        self._perform_issues_scan_for_block(target_block_idx)
        self.ui_updater.update_block_item_text_with_problem_count(target_block_idx)
        
        if show_message_on_completion:
            QMessageBox.information(self.mw, "Scan Complete", f"Issue scan for block {target_block_idx} complete.")

    def rescan_all_tags(self):
        self._perform_initial_silent_scan_all_issues()
        self.ui_updater.populate_blocks()
        QMessageBox.information(self.mw, "Scan Complete", "Full issue scan complete.")
