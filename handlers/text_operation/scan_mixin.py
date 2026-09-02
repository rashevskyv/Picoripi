from __future__ import annotations
from typing import Tuple
from PyQt6.QtGui import QTextCursor
from handlers.async_issue_scanner import AsyncIssueScanner, get_scanner_thread_pool


class ScanMixin:
    """Issue thresholds, rescans, async scanner launch/finish, asterisk sync."""

    def _get_string_thresholds(self, block_idx: int, string_idx: int) -> Tuple[int, int]:
        """Internal helper to get the string thresholds."""
        string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
        if "width" in string_meta:
            custom_w = string_meta["width"]
            logical_limit = custom_w
            global_max = getattr(self.mw, 'game_dialog_max_width_pixels', 300)
            standard_threshold = getattr(self.mw, 'line_width_warning_threshold_pixels', 280)
            if global_max > 0:
                threshold = int(custom_w * (standard_threshold / global_max))
            else:
                threshold = custom_w
        else:
            # No explicit override: plugin window-kind layout > global settings
            from utils.utils import resolve_width_limits
            threshold, logical_limit = resolve_width_limits(
                string_meta, getattr(self.mw, 'current_game_rules', None),
                block_idx, string_idx,
                getattr(self.mw, 'line_width_warning_threshold_pixels', 280),
                getattr(self.mw, 'game_dialog_max_width_pixels', 300))
        return threshold, logical_limit

    def _rescan_issues_for_current_string(self, block_idx: int, string_idx: int, new_text: str) -> None:
        """Internal helper to rescan issues for current string."""
        if not self.mw.current_game_rules:
            return

        keys_to_remove = [k for k in self.mw.data_store.problems_per_subline if k[0] == block_idx and k[1] == string_idx]
        for key in keys_to_remove:
            del self.mw.data_store.problems_per_subline[key]
            
        # Use problem_analyzer if it exists, otherwise use the game rules object itself
        analyzer = getattr(self.mw.current_game_rules, 'problem_analyzer', self.mw.current_game_rules)
        sublines = new_text.split('\n')
        
        font_map_for_string = self.mw.helper.get_font_map_for_string(block_idx, string_idx)
        width_threshold_for_string, logical_hard_limit_for_string = self._get_string_thresholds(block_idx, string_idx)
        
        problems_in_string = []
        if hasattr(analyzer, 'analyze_data_string'):
            problems_in_string = analyzer.analyze_data_string(new_text, font_map_for_string, width_threshold_for_string, logical_hard_limit_for_string)
        elif hasattr(analyzer, 'analyze_subline'):
            for i, subline in enumerate(sublines):
                next_subline = sublines[i+1] if i + 1 < len(sublines) else None
                problems = analyzer.analyze_subline(
                    text=subline, next_text=next_subline, subline_number_in_data_string=i, qtextblock_number_in_editor=i,
                    is_last_subline_in_data_string=(i == len(sublines) - 1), editor_font_map=font_map_for_string,
                    editor_line_width_threshold=width_threshold_for_string,
                    full_data_string_text_for_logical_check=new_text,
                    logical_hard_limit=logical_hard_limit_for_string
                )
                problems_in_string.append(problems)

        for i, problem_set in enumerate(problems_in_string):
             if problem_set:
                 self.mw.data_store.problems_per_subline[(block_idx, string_idx, i)] = problem_set

        self.data_processor.schedule_autosave()

    def _launch_async_scanner_for_fixed_text(
        self,
        block_idx: int,
        string_idx: int,
        fixed_data: str,
        font_map: dict,
        width_threshold: int,
        logical_hard_limit: int,
    ) -> None:
        """Launch a new AsyncIssueScanner for the given (fixed) text.

        Called after AutoFix completes (regardless of whether the text changed).
        The scanner updates glossary / spellcheck highlights in the background
        without blocking the UI. Because the sync rescan already populated
        problems_per_subline with the correct results, we keep the scanner output
        consistent by scanning the same fixed_data — the async result should match.
        """
        if not self.mw.current_game_rules:
            return

        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        analyzer = getattr(self.mw.current_game_rules, 'problem_analyzer', self.mw.current_game_rules)

        source_text = ""
        if hasattr(self.mw, 'original_text_edit') and self.mw.original_text_edit:
            source_text = self.mw.original_text_edit.toPlainText()

        editor_text = str(fixed_data)
        if hasattr(self.mw.current_game_rules, 'get_text_representation_for_editor'):
            editor_text = str(self.mw.current_game_rules.get_text_representation_for_editor(editor_text))

        if self.current_scanner_thread is not None:
            self.current_scanner_thread.cancel()
            self.current_scanner_thread = None

        self.current_scanner_thread = AsyncIssueScanner(
            block_idx=block_idx,
            string_idx=string_idx,
            text=fixed_data,
            font_map=dict(font_map),
            width_threshold=width_threshold,
            analyzer=analyzer,
            glossary_manager=getattr(getattr(edited_edit, 'highlighter', None), '_glossary_manager', None),
            spellchecker_manager=getattr(self.mw, 'spellchecker_manager', None),
            source_text=source_text,
            active_word="",
            warnings_enabled=getattr(self.mw, 'warnings_enabled', True),
            glossary_enabled=getattr(self.mw, 'glossary_enabled', True),
            editor_text=editor_text,
            logical_hard_limit=logical_hard_limit,
        )
        self.current_scanner_thread.finished_scan.connect(self._on_issue_scan_finished)
        if getattr(self.mw, '_is_sync_scan', False) is True:
            self.current_scanner_thread.run()
        else:
            get_scanner_thread_pool().start(self.current_scanner_thread)

    def launch_async_scanner_immediate(self, block_idx: int = -1, string_idx: int = -1) -> None:
        """Launch a new AsyncIssueScanner immediately without QTimer debounce."""
        if block_idx == -1 or string_idx == -1:
            block_idx = self.mw.data_store.physical_block_idx
            string_idx = self.mw.data_store.current_string_idx

        if block_idx == -1 or string_idx == -1:
            return

        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if not edited_edit or not self.mw.current_game_rules:
            return

        current_text_raw, _ = self.data_processor.get_current_string_text(block_idx, string_idx)
        if current_text_raw is None:
            return

        if self.current_scanner_thread is not None:
            self.current_scanner_thread.cancel()
            self.current_scanner_thread = None

        font_map_for_string = self.mw.helper.get_font_map_for_string(block_idx, string_idx)
        width_threshold_for_string, logical_hard_limit_for_string = self._get_string_thresholds(block_idx, string_idx)
        analyzer = getattr(self.mw.current_game_rules, 'problem_analyzer', self.mw.current_game_rules)

        source_text = ""
        if hasattr(self.mw, 'original_text_edit') and self.mw.original_text_edit:
            source_text = self.mw.original_text_edit.toPlainText()

        active_word = ""
        if edited_edit:
            try:
                cursor = edited_edit.textCursor()
                pos = cursor.position()
                if isinstance(pos, int) and pos > 0:
                    text = edited_edit.toPlainText()
                    if isinstance(text, str) and pos - 1 < len(text) and text[pos - 1] not in " \n\t.,!?;:·":
                        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
                        active_word = cursor.selectedText().strip("'·").lower()
            except BaseException:
                pass

        editor_text = str(current_text_raw)
        if self.mw.current_game_rules and hasattr(self.mw.current_game_rules, 'get_text_representation_for_editor'):
            editor_text = str(self.mw.current_game_rules.get_text_representation_for_editor(editor_text))

        self.current_scanner_thread = AsyncIssueScanner(
            block_idx=block_idx,
            string_idx=string_idx,
            text=str(current_text_raw),
            font_map=dict(font_map_for_string),
            width_threshold=width_threshold_for_string,
            analyzer=analyzer,
            glossary_manager=getattr(getattr(edited_edit, 'highlighter', None), '_glossary_manager', None),
            spellchecker_manager=getattr(self.mw, 'spellchecker_manager', None),
            source_text=source_text,
            active_word=active_word,
            warnings_enabled=getattr(self.mw, 'warnings_enabled', True),
            glossary_enabled=getattr(self.mw, 'glossary_enabled', True),
            editor_text=editor_text,
            logical_hard_limit=logical_hard_limit_for_string
        )
        self.current_scanner_thread.finished_scan.connect(self._on_issue_scan_finished)
        if getattr(self.mw, '_is_sync_scan', False) is True:
            self.current_scanner_thread.run()
        else:
            get_scanner_thread_pool().start(self.current_scanner_thread)

    def _log_undo_state(self, editor, context_message):
        """Internal helper to log undo state."""
        pass

    def _on_issue_scan_finished(self, block_idx: int, string_idx: int, text: str, problems_in_string: list,
                                 glossary_matches: list, translation_matches: list, spellcheck_matches: list) -> None:
        # Check if the block/string selection has changed while scanning
        """Internal helper to handle the issue scan finished event."""
        if block_idx != self.mw.data_store.physical_block_idx or string_idx != self.mw.data_store.current_string_idx:
            return

        # Clear existing problems for this string
        keys_to_remove = [k for k in self.mw.data_store.problems_per_subline if k[0] == block_idx and k[1] == string_idx]
        for key in keys_to_remove:
            del self.mw.data_store.problems_per_subline[key]

        # Apply newly found problems
        for i, problem_set in enumerate(problems_in_string):
            if problem_set:
                self.mw.data_store.problems_per_subline[(block_idx, string_idx, i)] = problem_set

        # Overlay only. update_text_views() would setPlainText the editors and
        # re-layout BFN, which steals the cursor and makes click-to-edit wait
        # on the scanner. The editors already show the current row.
        edited_edit = getattr(self.mw, 'edited_text_edit', None)
        if edited_edit:
            if hasattr(edited_edit, 'highlighter') and edited_edit.highlighter:
                edited_edit.highlighter._async_glossary_matches = glossary_matches
                edited_edit.highlighter._async_translation_matches = translation_matches
                edited_edit.highlighter._async_spellcheck_matches = spellcheck_matches
                edited_edit.highlighter.set_typing_mode(False, trigger_rehighlight=False)

        self.ui_updater.update_block_item_text_with_problem_count(block_idx)
        self.mw.ui_updater.update_status_bar()

        if edited_edit:
            self.mw.ui_updater.preview_updater._apply_highlights_to_editor(edited_edit, block_idx, string_idx)
            if hasattr(edited_edit, 'highlighter') and edited_edit.highlighter:
                edited_edit.highlighter.rehighlight()
            if hasattr(edited_edit, 'lineNumberArea'):
                edited_edit.lineNumberArea.update()
        
        self.data_processor.schedule_autosave()

    def sync_subline_asterisks(self, block_idx: int, string_idx: int, current_text: str) -> None:
        """
        Compares the current text of a string with its original version from the file 
        and updates mw.data_store.edited_sublines to show asterisks (*) on modified sublines in the editor.
        """
        if not hasattr(self.mw, 'data_store') or not hasattr(self.mw.data_store, 'edited_sublines'):
            return

        # Determine the baseline (original) text for comparison
        text_from_saved_file = self.data_processor._get_string_from_source(
            block_idx, string_idx, self.mw.data_store.edited_file_data, "edited_file_data"
        )
        if text_from_saved_file is None:
            text_from_saved_file = self.data_processor._get_string_from_source(
                block_idx, string_idx, self.mw.data_store.data, "original_data"
            )
        
        if text_from_saved_file is None:
            self.mw.data_store.edited_sublines.clear()
            return

        saved_lines = str(text_from_saved_file).split('\n')
        curr_lines = str(current_text).split('\n')
        
        self.mw.data_store.edited_sublines.clear()
        for i, curr_line in enumerate(curr_lines):
            # If current line differs OR it's a new line (beyond saved lines), mark as edited
            if i >= len(saved_lines) or curr_line != saved_lines[i]:
                self.mw.data_store.edited_sublines.add(i)
