import re
from typing import Tuple
from utils.logging_utils import log_debug

TAG_STATUS_OK = "OK"
TAG_STATUS_CRITICAL = "CRITICAL_ERROR"
TAG_STATUS_UNRESOLVED_BRACKETS = "UNRESOLVED_BRACKETS" 
TAG_STATUS_MISMATCHED_CURLY = "MISMATCHED_CURLY"     
TAG_STATUS_WARNING = "WARNING" 

ANY_TAG_PATTERN_WW = re.compile(r'\[[^\]]*\]')
PLAYER_TAG_WW = "[Name]"
CLOSING_COLOR_TAG_WW = "[/C]"
COLOR_TAG_PATTERN_WW = re.compile(r"\[Color:[^\]]+\]", re.IGNORECASE)


def _analyze_tags_for_issues_zww(processed_text: str, original_text: str) -> Tuple[str, str]:
    
    processed_tags = ANY_TAG_PATTERN_WW.findall(processed_text)
    original_tags = ANY_TAG_PATTERN_WW.findall(original_text)

    if len(processed_tags) != len(original_tags):
        error_msg = (f"Tag count mismatch. Processed: {len(processed_tags)} ({processed_tags}), "
                     f"Original: {len(original_tags)} ({original_tags}).")
        return TAG_STATUS_WARNING, error_msg

    original_player_count = original_tags.count(PLAYER_TAG_WW)
    processed_player_count = processed_tags.count(PLAYER_TAG_WW)
    if original_player_count != processed_player_count:
        error_msg = (f"Player tag '[Name]' count mismatch. Processed: {processed_player_count}, "
                     f"Original: {original_player_count}.")
        return TAG_STATUS_WARNING, error_msg
        
    original_color_tags = [tag for tag in original_tags if COLOR_TAG_PATTERN_WW.fullmatch(tag)]
    processed_color_tags = [tag for tag in processed_tags if COLOR_TAG_PATTERN_WW.fullmatch(tag)]
    if len(original_color_tags) != len(processed_color_tags):
         error_msg = (f"Color tag '[Color:...]' count mismatch. Processed: {len(processed_color_tags)}, "
                     f"Original: {len(original_color_tags)}.")
         return TAG_STATUS_WARNING, error_msg

    original_closing_color_count = original_tags.count(CLOSING_COLOR_TAG_WW)
    processed_closing_color_count = processed_tags.count(CLOSING_COLOR_TAG_WW)
    if original_closing_color_count != processed_closing_color_count:
        error_msg = (f"Closing color tag '[/C]' count mismatch. Processed: {processed_closing_color_count}, "
                     f"Original: {original_closing_color_count}.")
        return TAG_STATUS_WARNING, error_msg

    return TAG_STATUS_OK, ""


def process_segment_tags_aggressively_zww(
    segment_to_insert: str,
    original_text_for_tags: str,
    editor_player_tag_const: str
) -> Tuple[str, str, str]:
    log_debug(f"ZeldaWW Plugin Logic: Input Segment='{segment_to_insert[:80]}', Original='{original_text_for_tags[:80]}'")
    
    status, msg = _analyze_tags_for_issues_zww(segment_to_insert, original_text_for_tags)

    return segment_to_insert, status, msg