# handlers/width_calculation_worker.py
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from typing import List, Dict, Any, Optional
from utils.utils import calculate_string_width, remove_all_tags

class WidthCalculationWorker(QThread):
    progress_updated = pyqtSignal(int)
    calculation_finished = pyqtSignal(dict)
    cancelled = pyqtSignal()
    
    def __init__(self, block_idx: int, block_data: List[Any], block_name: str, 
                 font_map_helper: Any, data_processor: Any, 
                 game_rules_plugin: Any, mw_settings: Dict[str, Any], 
                 all_font_maps: Optional[Dict[str, dict]] = None,
                 target_indices: Optional[set] = None, parent=None):
        # Handle mocking in tests: MagicMock doesn't pass isinstance(QObject) but causes TypeError in super().__init__
        if parent is not None and (not isinstance(parent, QObject) or "Mock" in str(type(parent))):
            parent = None
        super().__init__(parent)
        self.block_idx = block_idx
        self.block_data = block_data
        self.block_name = block_name
        self.font_map_helper = font_map_helper
        self.data_processor = data_processor
        self.game_rules_plugin = game_rules_plugin
        self.mw_settings = mw_settings
        self.all_font_maps = all_font_maps or {}
        self.target_indices = target_indices
        self.is_cancelled = False
        
    def cancel(self):
        self.is_cancelled = True
        
    def run(self):
        # We use num_strings for progress bar scale. 
        num_strings = len(self.block_data)
        
        # Determine actual indices to process
        indices_to_process = list(range(num_strings))
        if self.target_indices is not None:
            indices_to_process = sorted([i for i in indices_to_process if i in self.target_indices])
            
        report_parts: List[str] = []
        chart_entries: List[Dict[str, Any]] = []
        problem_definitions = self.game_rules_plugin.get_problem_definitions()
        analyzer = getattr(self.game_rules_plugin, 'problem_analyzer', self.game_rules_plugin)
        
        # Optimization: cache for text processing (remove_all_tags is expensive in a loop)
        text_processing_cache: Dict[str, Any] = {}
        
        for i, data_str_idx in enumerate(indices_to_process):
            if self.is_cancelled:
                self.cancelled.emit()
                return
            
            # Emit progress based on index in THE LIST of processed items
            self.progress_updated.emit(i)
            
            current_text_data_line, source = self.data_processor.get_current_string_text(self.block_idx, data_str_idx)
            original_text_data_line = self.data_processor._get_string_from_source(
                self.block_idx, data_str_idx, self.block_data, "width_calc_worker_original_data"
            )
            
            font_map_for_string = self.font_map_helper.get_font_map_for_string(self.block_idx, data_str_idx)
            string_meta = self.mw_settings.get('string_metadata', {}).get((self.block_idx, data_str_idx), {})
            editor_warning_threshold = string_meta.get("width", self.mw_settings.get('line_width_warning_threshold_pixels', 200))

            line_report_parts = [f"Data Line {data_str_idx + 1}:"]
            
            sources_to_check = [
                ("Current", str(current_text_data_line), source),
                ("Original", str(original_text_data_line), "original_data")
            ]

            for title_prefix, text_to_analyze, text_source_info in sources_to_check:
                line_report_parts.append(f"  {title_prefix} (src:{text_source_info}):")
                
                # Check cache for this text
                cache_key = text_to_analyze
                if cache_key not in text_processing_cache:
                    logical_sublines: List[str] = []
                    if hasattr(analyzer, '_get_sublines_from_data_string'):
                        logical_sublines = analyzer._get_sublines_from_data_string(text_to_analyze)
                    else:
                        logical_sublines = text_to_analyze.split('\n')
                    
                    game_like_text_no_newlines_rstripped = remove_all_tags(
                        text_to_analyze.replace('\\n','').replace('\\p','').replace('\\l','')
                    ).rstrip()
                    
                    text_processing_cache[cache_key] = {
                        'logical_sublines': logical_sublines,
                        'game_like_text': game_like_text_no_newlines_rstripped
                    }
                
                cached_data = text_processing_cache[cache_key]
                logical_sublines = cached_data['logical_sublines']
                game_like_text = cached_data['game_like_text']
                
                total_game_width = calculate_string_width(game_like_text, font_map_for_string)
                game_status = "OK"
                if total_game_width > self.mw_settings.get('game_dialog_max_width_pixels', 400):
                    game_status = f"EXCEEDS GAME DIALOG LIMIT ({total_game_width - self.mw_settings.get('game_dialog_max_width_pixels', 400)}px)"
                line_report_parts.append(f"    Total (game dialog, rstripped): {total_game_width}px ({game_status})")

                for subline_idx, sub_line_text in enumerate(logical_sublines):
                    sub_line_no_tags_rstripped = remove_all_tags(sub_line_text).rstrip()
                    width_px = calculate_string_width(sub_line_no_tags_rstripped, font_map_for_string)
                    
                    # Add to chart entries ONLY for current text 
                    if title_prefix == "Current":
                        # CRITICAL: Calculate widths for ALL fonts now for "smooth switching"
                        all_widths = {}
                        for f_name, f_map in self.all_font_maps.items():
                            all_widths[f_name] = float(calculate_string_width(sub_line_no_tags_rstripped, f_map))
                        
                        chart_entries.append({
                            'text': sub_line_no_tags_rstripped,
                            'block_idx': self.block_idx,
                            'string_idx': data_str_idx,
                            'line_idx': subline_idx,
                            'width_pixels': float(width_px), # Default width (current/specified font)
                            'widths': all_widths           # Multi-font widths
                        })

                    # Problem Analysis logic (stays the same as it depends on the specified/active font)
                    current_subline_problems: set = set()
                    if hasattr(analyzer, 'analyze_data_string'):
                        problems_per_subline_list = analyzer.analyze_data_string(text_to_analyze, font_map_for_string, editor_warning_threshold)
                        current_subline_problems = problems_per_subline_list[subline_idx] if subline_idx < len(problems_per_subline_list) else set()
                    elif hasattr(analyzer, 'analyze_subline'):
                        next_subline = logical_sublines[subline_idx+1] if subline_idx + 1 < len(logical_sublines) else None
                        current_subline_problems = analyzer.analyze_subline(
                            text=sub_line_text, next_text=next_subline, 
                            subline_number_in_data_string=subline_idx, qtextblock_number_in_editor=subline_idx,
                            is_last_subline_in_data_string=(subline_idx == len(logical_sublines) - 1), 
                            editor_font_map=font_map_for_string,
                            editor_line_width_threshold=editor_warning_threshold,
                            full_data_string_text_for_logical_check=text_to_analyze
                        )
                    
                    statuses: List[str] = []
                    for prob_id in current_subline_problems:
                        if prob_id in problem_definitions:
                            statuses.append(problem_definitions[prob_id]['name'])
                    
                    status_str = ", ".join(statuses) if statuses else "OK"
                    line_report_parts.append(f"    Sub {subline_idx+1} (rstripped): {width_px}px ({status_str}) '{sub_line_no_tags_rstripped[:30]}...'")
                
                if title_prefix == "Current":
                    line_report_parts.append("")

            report_parts.append("\n".join(line_report_parts))
            
        # After processing all strings, we need to find the top 100 entries FOR EACH FONT
        # to ensure instant/smooth switching in the UI without re-sorting thousands of entries.
        all_fonts_top_entries: Dict[str, List[dict]] = {}
        for font_name in self.all_font_maps.keys():
            # Get only entries that have this font width
            font_entries = [e for e in chart_entries if 'widths' in e and font_name in e['widths']]
            if not font_entries:
                continue
            # Sort by width for this particular font
            sorted_entries = sorted(font_entries, key=lambda x: x['widths'][font_name], reverse=True)
            # Store top 100 for this font
            all_fonts_top_entries[font_name] = sorted_entries[:100]

        self.calculation_finished.emit({
            'report_text': "\n\n".join(report_parts),
            'entries': chart_entries,
            'all_fonts_top_entries': all_fonts_top_entries
        })
