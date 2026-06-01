# handlers/issue_scan_handler.py
import json
from pathlib import Path
from PyQt5.QtWidgets import QMessageBox, QProgressDialog
from PyQt5.QtCore import QTimer, Qt
from .base_handler import BaseHandler
from utils.logging_utils import log_info, log_debug, log_error
from utils.constants import APP_VERSION

class IssueScanHandler(BaseHandler):
    def __init__(self, main_window, data_processor, ui_updater):
        super().__init__(main_window, data_processor, ui_updater)
        self._progress_dialog = None
        self._scan_total_count = 0

    def _get_block_file_for_mtime(self, block_idx: int) -> Optional[str]:
        if not hasattr(self.mw, 'project_manager') or not self.mw.project_manager or not self.mw.project_manager.project:
            return None
        
        project_blocks = self.mw.project_manager.project.blocks
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)
        if proj_b_idx >= len(project_blocks):
            return None
            
        block = project_blocks[proj_b_idx]
        if block.metadata.get('is_archive_member'):
            archive_rel_path = block.metadata.get('archive_rel_path')
            if archive_rel_path:
                return self.mw.project_manager.get_absolute_path(archive_rel_path, is_translation=True)
                
        return self.mw.project_manager.get_absolute_path(block.translation_file, is_translation=True)

    def _get_cache_path(self) -> Optional[Path]:
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project_dir:
            return Path(self.mw.project_manager.project_dir) / "issues_cache.json"
        return None

    def _save_issues_cache(self):
        cache_path = self._get_cache_path()
        if not cache_path:
            return
            
        try:
            blocks_mtimes = {}
            for block_idx in range(len(self.mw.data_store.data)):
                filepath = self._get_block_file_for_mtime(block_idx)
                if filepath and Path(filepath).exists():
                    blocks_mtimes[str(block_idx)] = Path(filepath).stat().st_mtime
                    
            problems_by_block = {}
            for key, problem_set in self.mw.data_store.problems_per_subline.items():
                b_idx, s_idx, sub_idx = key
                problems_by_block.setdefault(str(b_idx), []).append([s_idx, sub_idx, list(problem_set)])
                
            cache_data = {
                "app_version": APP_VERSION,
                "project_id": self.mw.project_manager.project.id if self.mw.project_manager.project else None,
                "settings": {
                    "cache_format_version": 2,
                    "game_dialog_max_width_pixels": getattr(self.mw, 'game_dialog_max_width_pixels', 300),
                    "line_width_warning_threshold_pixels": getattr(self.mw, 'line_width_warning_threshold_pixels', 280),
                    "default_font_file": getattr(self.mw, 'default_font_file', None),
                    "fonts_dir_path": getattr(self.mw, 'fonts_dir_path', None),
                    "detection_enabled": getattr(self.mw, 'detection_enabled', {})
                },
                "blocks_mtimes": blocks_mtimes,
                "problems": problems_by_block
            }
            
            with cache_path.open('w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=4, ensure_ascii=False)
                
            log_debug(f"Saved issues cache to {cache_path}")
        except Exception as e:
            log_error(f"Failed to save issues cache: {e}", exc_info=True)

    def _load_issues_cache(self) -> Optional[dict]:
        cache_path = self._get_cache_path()
        if not cache_path or not cache_path.exists():
            return None
            
        try:
            with cache_path.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_error(f"Failed to load issues cache: {e}", exc_info=True)
            return None

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
            width_threshold_for_string = string_meta.get("width", getattr(self.mw, 'line_width_warning_threshold_pixels', 280))
            logical_hard_limit_for_string = string_meta.get("width", getattr(self.mw, 'game_dialog_max_width_pixels', 300))
            
            all_problems_for_string = [] # List of sets, one per subline
            
            if hasattr(analyzer, 'analyze_data_string'):
                all_problems_for_string = analyzer.analyze_data_string(text, font_map_for_string, width_threshold_for_string, logical_hard_limit_for_string)
            elif hasattr(analyzer, 'analyze_subline'):
                sublines = text.split('\n')
                for i, subline in enumerate(sublines):
                    next_subline = sublines[i+1] if i + 1 < len(sublines) else None
                    problems = analyzer.analyze_subline(
                        text=subline, next_text=next_subline, subline_number_in_data_string=i, qtextblock_number_in_editor=i,
                        is_last_subline_in_data_string=(i == len(sublines) - 1), editor_font_map=font_map_for_string,
                        editor_line_width_threshold=width_threshold_for_string,
                        full_data_string_text_for_logical_check=text,
                        logical_hard_limit=logical_hard_limit_for_string
                    )
                    all_problems_for_string.append(problems)
            
            for i, problem_set in enumerate(all_problems_for_string):
                if problem_set:
                    self.mw.data_store.problems_per_subline[(block_idx, string_idx, i)] = problem_set
                    log_debug(f"  Found problems in block {block_idx}, string {string_idx}, subline {i}: {problem_set}")

    # -----------------------------------------------------------------------
    # Async batched initial scan – runs in chunks so the UI never freezes
    # -----------------------------------------------------------------------
    _SCAN_BATCH_SIZE = 5   # blocks per timer tick

    def _show_scan_progress_dialog(self, pending_scan_indices: list):
        from PyQt5.QtWidgets import QWidget
        parent_widget = self.mw if isinstance(self.mw, QWidget) else None
        self._progress_dialog = QProgressDialog("Please wait, calculating issues...", "Cancel", 0, len(pending_scan_indices), parent_widget)
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setValue(0)
        
        # Save indices to scan
        self._scan_pending_indices = list(pending_scan_indices)
        self._scan_total_count = len(pending_scan_indices)
        
        # Set up timer for chunked scanning
        self._scan_timer = QTimer()
        self._scan_timer.setSingleShot(True)
        self._scan_timer.timeout.connect(self._scan_next_batch)
        
        from PyQt5.QtWidgets import QApplication
        is_test = "Mock" in str(type(self.mw)) or not isinstance(QApplication.instance(), QApplication)
        delay = 0 if is_test else 30
        self._scan_timer.start(delay)

    def _perform_initial_silent_scan_all_issues(self):
        """Start (or restart) an scan of all blocks, loading from cache if valid."""
        if not self.mw.data_store.data:
            self.mw.data_store.problems_per_subline.clear()
            return

        # Cancel any in-progress scan
        if hasattr(self, '_scan_timer') and self._scan_timer is not None:
            self._scan_timer.stop()
            self._scan_timer = None

        cache = self._load_issues_cache()
        
        # Check if cache is valid globally
        cache_valid = False
        if cache:
            settings = cache.get("settings", {})
            cache_valid = (
                cache.get("app_version") == APP_VERSION
                and settings.get("cache_format_version") == 2
                and settings.get("game_dialog_max_width_pixels") == getattr(self.mw, 'game_dialog_max_width_pixels', 300)
                and settings.get("line_width_warning_threshold_pixels") == getattr(self.mw, 'line_width_warning_threshold_pixels', 280)
                and settings.get("default_font_file") == getattr(self.mw, 'default_font_file', None)
                and settings.get("fonts_dir_path") == getattr(self.mw, 'fonts_dir_path', None)
                and settings.get("detection_enabled") == getattr(self.mw, 'detection_enabled', {})
            )
            
        pending_scan_indices = []
        self.mw.data_store.problems_per_subline.clear()
        
        if cache_valid:
            cache_mtimes = cache.get("blocks_mtimes", {})
            cache_problems = cache.get("problems", {})
            
            for block_idx in range(len(self.mw.data_store.data)):
                filepath = self._get_block_file_for_mtime(block_idx)
                current_mtime = None
                if filepath and Path(filepath).exists():
                    current_mtime = Path(filepath).stat().st_mtime
                
                cached_mtime = cache_mtimes.get(str(block_idx))
                
                # If mtime matches, load problems from cache
                if current_mtime is not None and cached_mtime is not None and abs(current_mtime - cached_mtime) < 0.01:
                    block_problems = cache_problems.get(str(block_idx), [])
                    for s_idx, sub_idx, problem_list in block_problems:
                        self.mw.data_store.problems_per_subline[(block_idx, s_idx, sub_idx)] = set(problem_list)
                else:
                    pending_scan_indices.append(block_idx)
        else:
            pending_scan_indices = list(range(len(self.mw.data_store.data)))

        if not pending_scan_indices:
            log_info("Loaded all block issues from cache.")
            if hasattr(self.mw, 'ui_updater'):
                self.ui_updater.populate_blocks()
            return

        log_info(f"Scanning {len(pending_scan_indices)} blocks for issues (not found or outdated in cache).")
        self._show_scan_progress_dialog(pending_scan_indices)

    def _scan_next_batch(self):
        """Process one batch of blocks and schedule the next batch."""
        if not hasattr(self, '_scan_pending_indices') or not self._scan_pending_indices:
            self._scan_timer = None
            if hasattr(self, '_progress_dialog') and self._progress_dialog:
                self._progress_dialog.close()
                self._progress_dialog = None
            return

        # Check if progress dialog was canceled
        if hasattr(self, '_progress_dialog') and self._progress_dialog and self._progress_dialog.wasCanceled():
            self._scan_pending_indices = []
            self._scan_timer = None
            self._progress_dialog = None
            log_info("Initial issue scan canceled by user.")
            return

        batch = self._scan_pending_indices[:self._SCAN_BATCH_SIZE]
        self._scan_pending_indices = self._scan_pending_indices[self._SCAN_BATCH_SIZE:]

        for block_idx in batch:
            if block_idx < len(self.mw.data_store.data):
                self._perform_issues_scan_for_block(block_idx)

        # Refresh problem counts in the tree for processed blocks
        if hasattr(self.mw, 'ui_updater'):
            for block_idx in batch:
                self.mw.ui_updater.update_block_item_text_with_problem_count(block_idx)

        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            completed = self._scan_total_count - len(self._scan_pending_indices)
            self._progress_dialog.setValue(completed)

        if self._scan_pending_indices:
            # Schedule next batch
            self._scan_timer = QTimer()
            self._scan_timer.setSingleShot(True)
            self._scan_timer.timeout.connect(self._scan_next_batch)
            
            from PyQt5.QtWidgets import QApplication
            is_test = "Mock" in str(type(self.mw)) or not isinstance(QApplication.instance(), QApplication)
            delay = 0 if is_test else 30
            self._scan_timer.start(delay)
        else:
            self._scan_timer = None
            if hasattr(self, '_progress_dialog') and self._progress_dialog:
                self._progress_dialog.close()
                self._progress_dialog = None
            log_debug("Initial issue scan complete.")
            self._save_issues_cache()

    def rescan_issues_for_single_block(self, block_idx: int = -1, show_message_on_completion: bool = True, use_default_mappings: bool = True):
        target_block_idx = block_idx if block_idx != -1 else self.mw.data_store.current_block_idx
        if target_block_idx == -1: return
        
        self._perform_issues_scan_for_block(target_block_idx)
        self.ui_updater.update_block_item_text_with_problem_count(target_block_idx)
        
        if show_message_on_completion:
            QMessageBox.information(self.mw, "Scan Complete", f"Issue scan for block {target_block_idx} complete.")
        
        # Save the updated issues cache
        self._save_issues_cache()

    def rescan_all_tags(self):
        # Invalidate cache to force a full scan
        cache_path = self._get_cache_path()
        if cache_path and cache_path.exists():
            try:
                cache_path.unlink()
            except Exception:
                pass
        self._perform_initial_silent_scan_all_issues()
        self.ui_updater.populate_blocks()
        QMessageBox.information(self.mw, "Scan Complete", "Full issue scan complete.")

