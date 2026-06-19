from PyQt6.QtCore import QThread, pyqtSignal
from typing import List, Tuple, Dict, Set, Optional, Any

class AutofixWorker(QThread):
    """Background worker for executing autofix rules across multiple strings."""
    progress = pyqtSignal(int)
    completed = pyqtSignal(list)  # List of tuples: (block_idx, string_idx, original_text, fixed_text)
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, game_rules: Any, target_strings: Optional[List[Tuple[int, int]]],
                 data: List[List[str]], edited_data: Dict[Tuple[int, int], str],
                 edited_file_data: List[List[str]], string_metadata: Dict[Tuple[int, int], dict],
                 all_font_maps: Dict[str, dict], font_map: dict,
                 warning_threshold: int, logical_hard_limit: int,
                 allowed_problems: Optional[Set[str]], page_local: bool):
        super().__init__()
        self.game_rules = game_rules
        self.target_strings = target_strings
        self.data = data
        self.edited_data = edited_data
        self.edited_file_data = edited_file_data
        self.string_metadata = string_metadata
        self.all_font_maps = all_font_maps
        self.font_map = font_map
        self.warning_threshold = warning_threshold
        self.logical_hard_limit = logical_hard_limit
        self.allowed_problems = allowed_problems
        self.page_local = page_local
        self._is_cancelled = False

    def cancel(self):
        """Request cancellation."""
        self._is_cancelled = True

    def _get_string_from_source(self, block_idx: int, string_idx: int, source_data: List[Any]) -> Optional[str]:
        if not source_data or not (0 <= block_idx < len(source_data)):
            return None
        current_block = source_data[block_idx]
        if not isinstance(current_block, list) or not (0 <= string_idx < len(current_block)):
            return None
        return current_block[string_idx]

    def _get_current_string_text(self, block_idx: int, string_idx: int) -> str:
        key = (block_idx, string_idx)
        if key in self.edited_data:
            return self.edited_data[key]
        text_from_file = self._get_string_from_source(block_idx, string_idx, self.edited_file_data)
        if text_from_file is not None:
            return text_from_file
        text_from_original = self._get_string_from_source(block_idx, string_idx, self.data)
        if text_from_original is not None:
            return text_from_original
        return ""

    def _get_font_map_for_string(self, block_idx: int, string_idx: int) -> dict:
        metadata_key = (block_idx, string_idx)
        string_meta = self.string_metadata.get(metadata_key, {})
        custom_font_file = string_meta.get("font_file")
        if custom_font_file:
            if custom_font_file in self.all_font_maps:
                return self.all_font_maps[custom_font_file]
            for key, f_map in self.all_font_maps.items():
                if key.endswith("/" + custom_font_file):
                    return f_map
        return self.font_map

    def _get_string_thresholds(self, block_idx: int, string_idx: int) -> Tuple[int, int]:
        string_meta = self.string_metadata.get((block_idx, string_idx), {})
        logical_limit = string_meta.get("width", self.logical_hard_limit)
        if "width" in string_meta:
            custom_w = string_meta["width"]
            if self.logical_hard_limit > 0:
                threshold = int(custom_w * (self.warning_threshold / self.logical_hard_limit))
            else:
                threshold = custom_w
        else:
            threshold = self.warning_threshold
        return threshold, logical_limit

    def run(self):
        """Execute the worker."""
        try:
            strings_to_process = []
            if self.target_strings is not None:
                strings_to_process = self.target_strings
            else:
                for b_idx, block in enumerate(self.data):
                    if isinstance(block, list):
                        for s_idx in range(len(block)):
                            strings_to_process.append((b_idx, s_idx))

            total = len(strings_to_process)
            results = []

            for idx, (b_idx, s_idx) in enumerate(strings_to_process):
                if self._is_cancelled:
                    self.cancelled.emit()
                    return

                current_text = self._get_current_string_text(b_idx, s_idx)
                font_map_for_string = self._get_font_map_for_string(b_idx, s_idx)
                width_threshold_for_string, logical_hard_limit_for_string = self._get_string_thresholds(b_idx, s_idx)

                current_iter_text = current_text
                any_changed = False
                max_iterations = 5
                for _ in range(max_iterations):
                    if self._is_cancelled:
                        self.cancelled.emit()
                        return
                    fixed_text, changed = self.game_rules.autofix_data_string(
                        current_iter_text,
                        font_map_for_string,
                        width_threshold_for_string,
                        logical_hard_limit=logical_hard_limit_for_string,
                        allowed_problems=self.allowed_problems,
                        block_idx=b_idx,
                        string_idx=s_idx,
                        page_local=self.page_local
                    )
                    if not changed or fixed_text == current_iter_text:
                        break
                    current_iter_text = fixed_text
                    any_changed = True

                fixed_text = current_iter_text
                if any_changed and fixed_text != current_text:
                    results.append((b_idx, s_idx, current_text, fixed_text))

                if idx % 10 == 0 or idx == total - 1:
                    self.progress.emit(idx + 1)

            if not self._is_cancelled:
                self.completed.emit(results)
            else:
                self.cancelled.emit()

        except Exception as e:
            from utils.logging_utils import log_error
            log_error(f"AutofixWorker error: {e}", exc_info=True)
            self.error.emit(str(e))
