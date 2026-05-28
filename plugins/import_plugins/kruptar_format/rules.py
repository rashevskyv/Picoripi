from typing import List, Tuple, Dict, Optional
import re
from ..base_import_rules import BaseImportRules, TAG_STATUS_OK, TAG_STATUS_CRITICAL, TAG_STATUS_MISMATCHED_CURLY, TAG_STATUS_UNRESOLVED_BRACKETS, TAG_STATUS_WARNING
from plugins.base_game_rules import BaseGameRules 
from utils.logging_utils import log_debug 
from utils.constants import ORIGINAL_PLAYER_TAG 
from utils.utils import ALL_TAGS_PATTERN 


PLAYER_PSEUDO_TAG_FOR_COUNTING = "{PLAYER_CONSTRUCT_INTERNAL_KIF}" 

def _analyze_tags_for_issues_kruptar(processed_text: str, original_text: str, editor_player_tag:str) -> Tuple[str, str]:
    temp_processed_text = str(processed_text) 
    temp_original_text = str(original_text)   

    num_original_player_tags = temp_original_text.count(ORIGINAL_PLAYER_TAG)
    
    if num_original_player_tags > 0 or ORIGINAL_PLAYER_TAG in temp_processed_text:
        temp_processed_text = temp_processed_text.replace(ORIGINAL_PLAYER_TAG, PLAYER_PSEUDO_TAG_FOR_COUNTING)
        temp_original_text = temp_original_text.replace(ORIGINAL_PLAYER_TAG, PLAYER_PSEUDO_TAG_FOR_COUNTING)
        temp_processed_text = temp_processed_text.replace(editor_player_tag, PLAYER_PSEUDO_TAG_FOR_COUNTING)

    remaining_brackets = [
        tag for tag in ALL_TAGS_PATTERN.findall(temp_processed_text) 
        if tag.startswith('[') 
    ]
    if remaining_brackets: 
        error_msg = (f"Unresolved editor tags [...] found: {remaining_brackets}.")
        return TAG_STATUS_UNRESOLVED_BRACKETS, error_msg 

    final_pasted_curly_tags = re.findall(r'\{[^}]*\}', temp_processed_text)
    original_tags_curly_all = re.findall(r'\{[^}]*\}', temp_original_text)

    if len(final_pasted_curly_tags) != len(original_tags_curly_all):
        error_msg = (f"Tag count mismatch for {{...}} tags. Processed (adj.): {len(final_pasted_curly_tags)} "
                     f"(tags: {final_pasted_curly_tags}), Original (adj.): {len(original_tags_curly_all)} (tags: {original_tags_curly_all}).")
        return TAG_STATUS_MISMATCHED_CURLY, error_msg
        
    return TAG_STATUS_OK, ""


class ImportRules(BaseImportRules): 
    def parse_clipboard_text(self, clipboard_text: str) -> List[str]:
        segments_from_clipboard_raw = re.split(r'\{END\}\r?\n', clipboard_text)
        parsed_strings = []
        num_raw_segments = len(segments_from_clipboard_raw)
        for i, segment in enumerate(segments_from_clipboard_raw):
            cleaned_segment = segment
            if i > 0 and segment.startswith('\n'): 
                cleaned_segment = segment[1:]
            if cleaned_segment or i < num_raw_segments - 1:
                parsed_strings.append(cleaned_segment)
        
        if parsed_strings and not parsed_strings[-1] and clipboard_text.rstrip().endswith("{END}"):
            parsed_strings.pop()
            
        return parsed_strings

    def process_segment_for_insertion(self, 
                                      segment_to_insert: str, 
                                      original_data_string_for_context: str, 
                                      game_rules: Optional[BaseGameRules], 
                                      default_tag_mappings: Dict[str, str],
                                      editor_player_tag: str
                                      ) -> Tuple[str, str, str]:
        
        current_segment_state = str(segment_to_insert)

        segment_had_slash00 = "/00" in current_segment_state
        original_had_slash00 = "/00" in original_data_string_for_context
        if segment_had_slash00 and not original_had_slash00: 
            current_segment_state = current_segment_state.replace("/00", "")
        elif segment_had_slash00 and original_had_slash00: 
            return current_segment_state, TAG_STATUS_CRITICAL, "'/00' present in both original and pasted segment."
        
        current_segment_state, _ = self.apply_mappings_to_text(current_segment_state, default_tag_mappings)
        
        remaining_brackets_after_default_map = [
            tag for tag in ALL_TAGS_PATTERN.findall(current_segment_state) 
            if tag.startswith('[') 
        ]
        
        temp_original_for_curly_count = original_data_string_for_context.replace(ORIGINAL_PLAYER_TAG, PLAYER_PSEUDO_TAG_FOR_COUNTING)
        original_curly_tags_for_ordered_replace = re.findall(r'\{[^}]*\}', temp_original_for_curly_count)
        
        if remaining_brackets_after_default_map and \
           len(remaining_brackets_after_default_map) == len(original_curly_tags_for_ordered_replace):
            temp_segment_for_ordered_replace = current_segment_state
            curly_idx = 0
            def ordered_replace_func(match):
                nonlocal curly_idx
                tag = match.group(0)
                if tag.startswith('['): 
                    if curly_idx < len(original_curly_tags_for_ordered_replace):
                        replacement = original_curly_tags_for_ordered_replace[curly_idx]
                        if replacement == PLAYER_PSEUDO_TAG_FOR_COUNTING:
                            replacement = ORIGINAL_PLAYER_TAG
                        curly_idx += 1
                        return replacement
                return tag 

            current_segment_state = re.sub(r'\[[^\]]*\]', ordered_replace_func, temp_segment_for_ordered_replace)

        status, msg = _analyze_tags_for_issues_kruptar(current_segment_state, original_data_string_for_context, editor_player_tag)
        
        return current_segment_state, status, msg