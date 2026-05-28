from typing import List, Tuple, Dict, Optional
from plugins.base_game_rules import BaseGameRules 
# from utils.logging_utils import log_debug # Якщо буде логування в apply_mappings_to_text

# plugins/import_plugins/base_game_rules.py

# Константи статусів обробки тегів
TAG_STATUS_OK = "OK"
TAG_STATUS_CRITICAL = "CRITICAL_ERROR" 
TAG_STATUS_UNRESOLVED_BRACKETS = "UNRESOLVED_BRACKETS" 
TAG_STATUS_MISMATCHED_CURLY = "MISMATCHED_CURLY"     
TAG_STATUS_WARNING = "WARNING" 

class BaseImportRules:
    def __init__(self, main_window_ref=None):
        self.mw = main_window_ref

    def parse_clipboard_text(self, clipboard_text: str) -> List[str]:
        raise NotImplementedError("Subclasses must implement parse_clipboard_text")

    def process_segment_for_insertion(self, 
                                      segment_to_insert: str, 
                                      original_data_string_for_context: str, 
                                      game_rules: Optional[BaseGameRules], 
                                      default_tag_mappings: Dict[str, str],
                                      editor_player_tag: str
                                      ) -> Tuple[str, str, str]:
        raise NotImplementedError("Subclasses must implement process_segment_for_insertion")

    def apply_mappings_to_text(self, text_segment: str, mappings: Dict[str, str]) -> Tuple[str, bool]:
        """
        Застосовує надані мапінги до текстового сегмента.
        Повертає оброблений текст та прапорець, чи були зроблені зміни.
        """
        if not mappings or not text_segment: 
            return text_segment, False
        
        modified_segment = str(text_segment)
        changed = False
        
        sorted_keys = sorted(mappings.keys(), key=len, reverse=True)
        
        for short_tag in sorted_keys:
            full_tag = mappings[short_tag]
            if short_tag in modified_segment:
                # Змінюємо перевірку, щоб вона була більш надійною
                temp_modified_segment = modified_segment.replace(short_tag, full_tag)
                if temp_modified_segment != modified_segment:
                    modified_segment = temp_modified_segment
                    changed = True
                    # log_debug(f"ImportRule: Applied mapping: '{short_tag}' -> '{full_tag}'") 
        
        return modified_segment, changed