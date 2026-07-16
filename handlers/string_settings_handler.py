# handlers/string_settings_handler.py
from typing import Any, List, Optional, Tuple, Dict
from .base_handler import BaseHandler
from utils.utils import log_debug, calculate_string_width

class StringSettingsHandler(BaseHandler):
    """Handler for string settings operations."""
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor, ui_updater)

    def get_default_width_for_string(self, block_idx: int, string_idx: int) -> int:
        """Return the effective plugin default for this specific string.

        Plugins such as zelda_bmg derive this from the message's window kind;
        plugins without per-string layouts continue to use the global limit.
        """
        from utils.utils import resolve_width_limits

        _, max_width = resolve_width_limits(
            {}, getattr(self.mw, "current_game_rules", getattr(self.mw, "game_rules", None)),
            block_idx, string_idx,
            getattr(self.mw, "line_width_warning_threshold_pixels", 280),
            getattr(self.mw, "game_dialog_max_width_pixels", 300),
        )
        return max_width

    def _is_default_width(self, width: int, block_idx: int, string_idx: int) -> bool:
        return width == 0 or width == self.get_default_width_for_string(block_idx, string_idx)

    def copy_original_width_to_editor(self) -> None:
        """Copy the selected original row's measured max width into the editor control."""
        block_idx = getattr(self.mw.data_store, "physical_block_idx", -1)
        string_idx = getattr(self.mw.data_store, "current_string_idx", -1)
        if block_idx < 0 or string_idx < 0:
            return
        original_text = self.data_processor._get_string_from_source(
            block_idx, string_idx, self.mw.data_store.data, "original_data"
        )
        if original_text is None:
            return
        font_map = self.mw.helper.get_font_map_for_string(block_idx, string_idx)
        icon_sequences = getattr(self.mw, "icon_sequences", [])
        default_tag_mappings = getattr(self.mw, "default_tag_mappings", None)
        max_width = max(
            (
                calculate_string_width(
                    line,
                    font_map,
                    icon_sequences=icon_sequences,
                    default_tag_mappings=default_tag_mappings,
                )
                for line in str(original_text).split("\n")
            ),
            default=0,
        )
        if max_width > 0:
            self.mw.width_spinbox.setValue(max_width)
        
    def _apply_and_rescan(self) -> None:
        """Internal helper to apply and rescan."""
        log_debug("--- Applying string settings and performing full block refresh ---")
        
        current_block_idx: int = self.mw.data_store.current_block_idx
        physical_block_idx: int = self.mw.data_store.physical_block_idx
 
        if physical_block_idx != -1:
            log_debug(f"Refreshing UI for block {physical_block_idx}")
            if hasattr(self.mw, 'issue_scan_handler'):
                self.mw.issue_scan_handler.rescan_issues_for_single_block(physical_block_idx, show_message_on_completion=False)
            if current_block_idx != -1:
                self.mw.ui_updater.update_block_item_text_with_problem_count(current_block_idx)
            self.mw.ui_updater.update_block_item_text_with_problem_count(physical_block_idx)
            self.mw.ui_updater.update_text_views()
            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_string_settings_panel()
        else:
            log_debug("No block selected, only updating settings panel.")
            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_string_settings_panel()

    def on_font_changed(self, index: int) -> None:
        """Handle the font changed event."""
        block_idx = self.mw.data_store.physical_block_idx
        if block_idx == -1 or self.mw.data_store.current_string_idx == -1:
            return
 
        key: Tuple[int, int] = (block_idx, self.mw.data_store.current_string_idx)
        current_meta: Dict[str, Any] = self.mw.string_metadata.get(key, {})
        current_font: Optional[str] = current_meta.get("font_file")

        selected_data: Any = self.mw.font_combobox.itemData(index)
        new_font: Optional[str] = None
        if selected_data != "default":
            new_font = str(selected_data)
            
        if current_font != new_font:
            self.mw.apply_width_button.setEnabled(True)
        else:
            # If reverted to the same value as before, the button becomes inactive
            current_width: Optional[int] = current_meta.get("width")
            spinbox_width: int = self.mw.width_spinbox.value()
            default_width = self.get_default_width_for_string(block_idx, key[1])
            if (not current_width and spinbox_width == default_width) or \
               (current_width and spinbox_width == current_width):
                self.mw.apply_width_button.setEnabled(False)

    def on_width_changed(self, value: int) -> None:
        """Handle the width changed event."""
        block_idx = self.mw.data_store.physical_block_idx
        if block_idx == -1 or self.mw.data_store.current_string_idx == -1:
            return
 
        key: Tuple[int, int] = (block_idx, self.mw.data_store.current_string_idx)
        current_meta: Dict[str, Any] = self.mw.string_metadata.get(key, {})
        current_width: Optional[int] = current_meta.get("width")

        new_width: int = value
        
        is_width_changed: bool = False
        if current_width is None: # Was default value
            if not self._is_default_width(new_width, block_idx, key[1]):
                is_width_changed = True
        else: # Was custom value
            if new_width != current_width:
                is_width_changed = True

        if is_width_changed:
            self.mw.apply_width_button.setEnabled(True)
        else:
            # If width reverted to initial state, check font state
            current_font: Optional[str] = current_meta.get("font_file")
            selected_font_data: Any = self.mw.font_combobox.currentData()
            new_font: Optional[str] = selected_font_data if selected_font_data != "default" else None
            if current_font == new_font:
                 self.mw.apply_width_button.setEnabled(False)


    def apply_settings_change(self) -> None:
        """Apply settings change."""
        block_idx = self.mw.data_store.physical_block_idx
        if block_idx == -1 or self.mw.data_store.current_string_idx == -1:
            return
 
        key: Tuple[int, int] = (block_idx, self.mw.data_store.current_string_idx)
        
        # Apply font
        selected_font_data: Any = self.mw.font_combobox.currentData()
        if key not in self.mw.string_metadata:
            self.mw.string_metadata[key] = {}
        
        if selected_font_data == "default":
            if "font_file" in self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]["font_file"]
        else:
            self.mw.string_metadata[key]["font_file"] = selected_font_data

        # Apply width
        new_width: int = self.mw.width_spinbox.value()
        if self._is_default_width(new_width, block_idx, key[1]):
            if "width" in self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]["width"]
        else:
            self.mw.string_metadata[key]["width"] = new_width
            
        # Clear empty metadata
        if not self.mw.string_metadata[key]:
            del self.mw.string_metadata[key]
            
        log_debug(f"Applied and updated string_metadata for {key}: {self.mw.string_metadata.get(key)}")
        
        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.save_settings()
            
        current_string_idx_before_rescan: int = self.mw.data_store.current_string_idx
        self._apply_and_rescan()
        if hasattr(self.mw, 'list_selection_handler'):
            self.mw.list_selection_handler.select_string_by_absolute_index(current_string_idx_before_rescan)


    def apply_font_to_range(self, start_line: int, end_line: int, font_file: str) -> None:
        """Apply font to range."""
        block_idx: int = self.mw.data_store.physical_block_idx
        if block_idx == -1:
            return
            
        log_debug(f"Applying font '{font_file}' to lines {start_line}-{end_line} in block {block_idx}")
        for line_idx in range(start_line, end_line + 1):
            key: Tuple[int, int] = (block_idx, line_idx)
            if key not in self.mw.string_metadata:
                if font_file == "default": continue
                self.mw.string_metadata[key] = {}
            
            if font_file == "default":
                if "font_file" in self.mw.string_metadata[key]:
                    del self.mw.string_metadata[key]["font_file"]
            else:
                self.mw.string_metadata[key]["font_file"] = font_file
            
            if not self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]
        
        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.save_settings()
        
        self._apply_and_rescan()

    def apply_font_to_lines(self, line_indices: List[int], font_file: str) -> None:
        """Apply font to lines."""
        block_idx: int = self.mw.data_store.physical_block_idx
        if block_idx == -1:
            return
            
        log_debug(f"Applying font '{font_file}' to lines {line_indices} in block {block_idx}")
        for line_idx in line_indices:
            key: Tuple[int, int] = (block_idx, line_idx)
            if key not in self.mw.string_metadata:
                if font_file == "default": continue
                self.mw.string_metadata[key] = {}
            
            if font_file == "default":
                if "font_file" in self.mw.string_metadata[key]:
                    del self.mw.string_metadata[key]["font_file"]
            else:
                self.mw.string_metadata[key]["font_file"] = font_file
            
            if not self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]
        
        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.save_settings()
        
        self._apply_and_rescan()

    def apply_font_to_block(self, block_idx: int, font_file: str) -> None:
        """Apply font to block."""
        if block_idx == -1:
            return

        if not self.mw.data_store.data or block_idx >= len(self.mw.data_store.data):
            return

        total_lines = len(self.mw.data_store.data[block_idx])
        log_debug(f"Applying font '{font_file}' to all {total_lines} lines in block {block_idx}")
        for line_idx in range(total_lines):
            key: Tuple[int, int] = (block_idx, line_idx)
            if key not in self.mw.string_metadata:
                if font_file == "default":
                    continue
                self.mw.string_metadata[key] = {}

            if font_file == "default":
                if "font_file" in self.mw.string_metadata[key]:
                    del self.mw.string_metadata[key]["font_file"]
            else:
                self.mw.string_metadata[key]["font_file"] = font_file

            if not self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]

        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.save_settings()

        self._apply_and_rescan()

    def apply_width_to_lines(self, line_indices: List[int], width: int) -> None:
        """Apply width to lines."""
        block_idx: int = self.mw.data_store.physical_block_idx
        if block_idx == -1:
            return

        log_debug(f"Applying width '{width}' to lines {line_indices} in block {block_idx}")
        for line_idx in line_indices:
            key: Tuple[int, int] = (block_idx, line_idx)
            is_default_width = self._is_default_width(width, block_idx, line_idx)
            if key not in self.mw.string_metadata:
                if is_default_width: continue
                self.mw.string_metadata[key] = {}

            if is_default_width:
                if "width" in self.mw.string_metadata[key]:
                    del self.mw.string_metadata[key]["width"]
            else:
                self.mw.string_metadata[key]["width"] = width

            if not self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]

        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.save_settings()

        self._apply_and_rescan()

    def apply_width_to_range(self, start_line: int, end_line: int, width: int) -> None:
        """Apply width to range."""
        block_idx: int = self.mw.data_store.physical_block_idx
        if block_idx == -1:
            return

        log_debug(f"Applying width '{width}' to lines {start_line}-{end_line} in block {block_idx}")
        for line_idx in range(start_line, end_line + 1):
            key: Tuple[int, int] = (block_idx, line_idx)
            is_default_width = self._is_default_width(width, block_idx, line_idx)
            if key not in self.mw.string_metadata:
                if is_default_width: continue
                self.mw.string_metadata[key] = {}

            if is_default_width:
                if "width" in self.mw.string_metadata[key]:
                    del self.mw.string_metadata[key]["width"]
            else:
                self.mw.string_metadata[key]["width"] = width

            if not self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]
        
        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.save_settings()
        
        self._apply_and_rescan()

    def apply_auto_width_from_original_to_lines(self, line_indices: List[int]) -> None:
        """Apply auto width from original to lines."""
        block_idx: int = self.mw.data_store.physical_block_idx
        if block_idx == -1:
            return

        log_debug(f"Applying auto-width from original to lines {line_indices} in block {block_idx}")
        
        icon_sequences = getattr(self.mw, 'icon_sequences', [])
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', None)

        for line_idx in line_indices:
            original_text = self.data_processor._get_string_from_source(
                block_idx, line_idx, self.mw.data_store.data, "original_data"
            )
            if original_text is None:
                continue

            font_map = self.mw.helper.get_font_map_for_string(block_idx, line_idx)
            
            lines = str(original_text).split('\n')
            max_w = 0
            for line in lines:
                w = calculate_string_width(line, font_map, icon_sequences=icon_sequences, default_tag_mappings=default_tag_mappings)
                if w > max_w:
                    max_w = w

            key: Tuple[int, int] = (block_idx, line_idx)
            is_default_width = self._is_default_width(max_w, block_idx, line_idx)

            if key not in self.mw.string_metadata:
                if is_default_width:
                    continue
                self.mw.string_metadata[key] = {}

            if is_default_width:
                if "width" in self.mw.string_metadata[key]:
                    del self.mw.string_metadata[key]["width"]
            else:
                self.mw.string_metadata[key]["width"] = max_w

            if not self.mw.string_metadata[key]:
                del self.mw.string_metadata[key]

        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.save_settings()

        self._apply_and_rescan()
