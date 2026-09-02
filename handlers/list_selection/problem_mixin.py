"""Problem-string detection and navigation."""
from __future__ import annotations

from utils.logging_utils import log_debug


class ProblemMixin:
    """Problem-string detection and navigation."""

    def _data_string_has_any_problem(self, block_idx: int, string_idx: int) -> bool:
        """Internal helper to data string has any problem."""
        if not self.mw.current_game_rules:
            return False

        data_string_text, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        if data_string_text is None:
            return False

        num_sublines = str(data_string_text).count('\n') + 1

        detection_config = getattr(self.mw, 'detection_enabled', {})

        for i in range(num_sublines):
            key = (block_idx, string_idx, i)
            if key in self.mw.data_store.problems_per_subline:
                problems = self.mw.data_store.problems_per_subline[key]
                if any(detection_config.get(p_id, True) for p_id in problems):
                    return True

        return False

    def navigate_to_problem_string(self, direction_down: bool):
        """Navigate to problem string."""
        if self.mw.data_store.current_block_idx == -1 or not self.mw.data_store.data or \
           not (0 <= self.mw.data_store.current_block_idx < len(self.mw.data_store.data)):
            return

        current_block_data = self.mw.data_store.data[self.mw.data_store.current_block_idx]
        if not isinstance(current_block_data, list) or not current_block_data:
            return

        num_strings_in_block = len(current_block_data)
        start_scan_idx = self.mw.data_store.current_string_idx
        log_debug(f"[NAV] Start navigation. Direction down: {direction_down}, current_string_idx: {start_scan_idx}")

        current_check_idx = -1
        if start_scan_idx == -1:
            current_check_idx = 0 if direction_down else num_strings_in_block - 1
        else:
             current_check_idx = (start_scan_idx + 1) if direction_down else (start_scan_idx - 1)

        original_programmatic_state = self.mw.is_programmatically_changing_text

        found_target_s_idx = -1

        if direction_down:
            for s_idx in range(current_check_idx, num_strings_in_block):
                if self._data_string_has_any_problem(self.mw.data_store.current_block_idx, s_idx):
                    found_target_s_idx = s_idx
                    break
            if found_target_s_idx == -1:
                for s_idx in range(0, current_check_idx if start_scan_idx != -1 else num_strings_in_block):
                    if self._data_string_has_any_problem(self.mw.data_store.current_block_idx, s_idx):
                        found_target_s_idx = s_idx
                        break
        else:
            for s_idx in range(current_check_idx, -1, -1):
                if self._data_string_has_any_problem(self.mw.data_store.current_block_idx, s_idx):
                    found_target_s_idx = s_idx
                    break
            if found_target_s_idx == -1:
                for s_idx in range(num_strings_in_block - 1, current_check_idx if start_scan_idx != -1 else -1, -1):
                    if self._data_string_has_any_problem(self.mw.data_store.current_block_idx, s_idx):
                        found_target_s_idx = s_idx
                        break

        if found_target_s_idx != -1:
            log_debug(f"[NAV] Found target string at index: {found_target_s_idx}")
            self.mw.is_programmatically_changing_text = True # Set programmatic state before calling string_selected_from_preview
            self.string_selected_from_preview(found_target_s_idx)
            self.mw.is_programmatically_changing_text = original_programmatic_state # Restore after selection
        else:
            log_debug("[NAV] No problem string found in current search.")
            if start_scan_idx != -1 and self._data_string_has_any_problem(self.mw.data_store.current_block_idx, start_scan_idx):
                 self.mw.is_programmatically_changing_text = True # Set programmatic state before calling string_selected_from_preview
                 self.string_selected_from_preview(start_scan_idx)
                 self.mw.is_programmatically_changing_text = original_programmatic_state # Restore after selection
            else:
                self.mw.is_programmatically_changing_text = original_programmatic_state
