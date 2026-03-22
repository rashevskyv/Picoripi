# --- START OF FILE core/tag_utils.py ---
import re
from utils.logging_utils import log_debug

ANY_TAG_PATTERN = re.compile(r'\[[^\]]*\]|\{[^}]*\}')

TAG_STATUS_OK = "OK"
TAG_STATUS_CRITICAL = "CRITICAL"
TAG_STATUS_MISMATCHED_CURLY = "MISMATCHED_CURLY"
TAG_STATUS_UNRESOLVED_BRACKETS = "UNRESOLVED_BRACKETS"

def apply_default_mappings_only(text_segment: str, default_mappings: dict) -> tuple[str, bool]:
    if not default_mappings or not text_segment: return text_segment, False
    modified_segment = str(text_segment); changed = False
    sorted_keys = sorted(default_mappings.keys(), key=len, reverse=True)
    for short_tag in sorted_keys:
        full_tag = default_mappings[short_tag]
        if short_tag in modified_segment:
            modified_segment = modified_segment.replace(short_tag, full_tag); changed = True
    return modified_segment, changed