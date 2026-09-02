"""Width guideline calculation and related width properties."""
from __future__ import annotations

from PyQt6.QtWidgets import QMainWindow

from utils.constants import (
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
)


class GuidelinesMixin:
    """Width guideline calculation and related width properties."""

    def calculate_block_guidelines(self, block, font_map, sequences, limit_px, default_tag_mappings=None) -> None:
        """Calculate block guidelines."""
        from utils.utils import calculate_string_width, convert_dots_to_spaces_from_editor
        from PyQt6.QtGui import QTextCursor

        if not hasattr(self, 'guideline_positions'):
            self.guideline_positions = {}

        layout = block.layout()
        if not layout:
            return

        block_text_raw = convert_dots_to_spaces_from_editor(block.text())
        block_num = block.blockNumber()

        # Initialize all visual lines of this block to False (default: no guideline)
        for i in range(layout.lineCount()):
            self.guideline_positions[(block_num, i)] = False

        main_win = self.window()
        rules = getattr(main_win, 'current_game_rules', None)

        def get_width(txt):
            """Get the width."""
            if rules and hasattr(rules, 'calculate_string_width_override'):
                override_val = rules.calculate_string_width_override(txt, font_map)
                if isinstance(override_val, (int, float)):
                    return override_val
            return calculate_string_width(txt, font_map, icon_sequences=sequences, default_tag_mappings=default_tag_mappings)

        block_width_px = get_width(block_text_raw.rstrip())
        is_exceeded = (block_width_px > limit_px)

        cursor = QTextCursor(self.document())

        if is_exceeded:
            # Width is monotonic, so locate the crossing in O(log n) measurements.
            # The previous linear prefix scan repeatedly parsed all BMG aliases and
            # made long strings quadratic during every row change.
            found = False
            low, high = 1, len(block_text_raw)
            while low < high:
                middle = (low + high) // 2
                if get_width(block_text_raw[:middle]) >= limit_px:
                    high = middle
                else:
                    low = middle + 1
            if block_text_raw:
                k = low
                prefix_w = get_width(block_text_raw[:k])
                if prefix_w >= limit_px:
                    prev_w = get_width(block_text_raw[:k - 1])

                    # Find which visual line contains character index k - 1.
                    found_line = -1
                    for i in range(layout.lineCount()):
                        line = layout.lineAt(i)
                        if not line.isValid():
                            continue
                        line_start = line.textStart()
                        line_len = line.textLength()
                        is_last = (i == layout.lineCount() - 1)
                        if line_start <= k - 1 < line_start + line_len or (is_last and k - 1 == line_start + line_len):
                            found_line = i
                            break

                    if found_line != -1:
                        line = layout.lineAt(found_line)

                        cursor.setPosition(block.position() + k - 1)
                        x_prev = self.cursorRect(cursor).left()

                        cursor.setPosition(block.position() + k)
                        x_curr = self.cursorRect(cursor).left()

                        if prefix_w > prev_w:
                            fraction = (limit_px - prev_w) / (prefix_w - prev_w)
                        else:
                            fraction = 0
                        limit_x = x_prev + fraction * (x_curr - x_prev)
                        self.guideline_positions[(block_num, found_line)] = (limit_x, True)
                        found = True
            # Fallback if somehow not found (should not happen if block_width_px > limit_px)
            if not found and layout.lineCount() > 0:
                last_idx = layout.lineCount() - 1
                line = layout.lineAt(last_idx)
                cursor.setPosition(block.position() + line.textStart() + line.textLength())
                self.guideline_positions[(block_num, last_idx)] = (self.cursorRect(cursor).left(), True)
        else:
            # Not exceeded: green dashed line on the last visual line
            if layout.lineCount() > 0:
                last_idx = layout.lineCount() - 1
                line = layout.lineAt(last_idx)
                if line.isValid():
                    line_start = line.textStart()
                    line_len = line.textLength()
                    line_text = block_text_raw[line_start:line_start + line_len]
                    line_text_stripped = line_text.rstrip()

                    cumulative_width_before_last_line = get_width(block_text_raw[:line_start])
                    last_line_game_width = get_width(line_text_stripped)

                    cursor.setPosition(block.position() + line_start)
                    x_start = self.cursorRect(cursor).left()

                    remaining_px = limit_px - cumulative_width_before_last_line

                    if last_line_game_width > 0:
                        cursor.setPosition(block.position() + line_start + len(line_text_stripped))
                        x_end = self.cursorRect(cursor).left()
                        viewport_text_w = x_end - x_start

                        limit_x = x_start + viewport_text_w * (remaining_px / last_line_game_width)
                    else:
                        fm = self.fontMetrics()
                        char_w = fm.horizontalAdvance('A')
                        limit_x = x_start + remaining_px * (char_w / 7.5)

                    self.guideline_positions[(block_num, last_idx)] = (limit_x, False)

    def recalculate_guidelines(self) -> None:
        """Recalculate guidelines."""
        self.guideline_positions = {}
        if not self.show_width_guideline or self.line_width_warning_threshold_pixels <= 0:
            return

        main_window = self.window()
        font_map = getattr(self, 'font_map', {})
        if not font_map and hasattr(main_window, 'font_map'):
            font_map = main_window.font_map

        limit_px = self.line_width_warning_threshold_pixels

        if hasattr(main_window, 'data_store') and hasattr(main_window, 'helper'):
            block_idx = getattr(
                main_window.data_store,
                'physical_block_idx',
                main_window.data_store.current_block_idx,
            )
            string_idx = main_window.data_store.current_string_idx
            if block_idx != -1 and string_idx != -1:
                font_map = main_window.helper.get_font_map_for_string(block_idx, string_idx)
                
                string_meta = getattr(main_window, 'string_metadata', {}).get((block_idx, string_idx), {})
                if "width" in string_meta:
                    custom_w = string_meta["width"]
                    global_max = getattr(main_window, 'game_dialog_max_width_pixels', limit_px)
                    standard_threshold = getattr(main_window, 'line_width_warning_threshold_pixels', limit_px)
                    if global_max > 0:
                        limit_px = int(custom_w * (standard_threshold / global_max))
                    else:
                        limit_px = custom_w

        sequences = getattr(main_window, 'icon_sequences', []) if main_window else []
        default_tag_mappings = getattr(main_window, 'default_tag_mappings', {}) if main_window else {}

        block = self.firstVisibleBlock()

        while block.isValid():
            self.calculate_block_guidelines(block, font_map, sequences, limit_px, default_tag_mappings=default_tag_mappings)
            block = block.next()
        self.viewport().update()

    @property
    def game_dialog_max_width_pixels(self):
        """Game dialog max width pixels."""
        main_window = self.window()
        if main_window is not self and isinstance(main_window, QMainWindow) and hasattr(main_window, 'game_dialog_max_width_pixels'):
            return main_window.game_dialog_max_width_pixels
        return getattr(self, '_game_dialog_max_width_pixels', DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS)

    @game_dialog_max_width_pixels.setter
    def game_dialog_max_width_pixels(self, val):
        """Game dialog max width pixels."""
        self._game_dialog_max_width_pixels = val

    @property
    def line_width_warning_threshold_pixels(self):
        """Line width warning threshold pixels."""
        main_window = self.window()
        if main_window is not self and isinstance(main_window, QMainWindow) and hasattr(main_window, 'line_width_warning_threshold_pixels'):
            return main_window.line_width_warning_threshold_pixels
        return getattr(self, '_line_width_warning_threshold_pixels', DEFAULT_LINE_WIDTH_WARNING_THRESHOLD)

    @line_width_warning_threshold_pixels.setter
    def line_width_warning_threshold_pixels(self, val):
        """Line width warning threshold pixels."""
        self._line_width_warning_threshold_pixels = val

    @property
    def show_width_guideline(self):
        """Show width guideline."""
        main_window = self.window()
        if main_window is not self and isinstance(main_window, QMainWindow) and hasattr(main_window, 'show_width_guideline'):
            return main_window.show_width_guideline
        return getattr(self, '_show_width_guideline', True)

    @show_width_guideline.setter
    def show_width_guideline(self, val):
        """Show width guideline."""
        self._show_width_guideline = val
