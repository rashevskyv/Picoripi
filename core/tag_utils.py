import re
from utils.logging_utils import log_debug

from plugins.common.markers import P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER

ANY_TAG_PATTERN_STR = r'\[[^\]]*\]|\{[^}]*\}'
ANY_TAG_PATTERN = re.compile(ANY_TAG_PATTERN_STR)
ANY_TAG_CAPTURE_PATTERN = re.compile(rf'({ANY_TAG_PATTERN_STR})')

ANY_NON_EMPTY_TAG_PATTERN_STR = r'\[[^\]]+\]|\{[^}]+\}'
ANY_NON_EMPTY_TAG_PATTERN = re.compile(ANY_NON_EMPTY_TAG_PATTERN_STR)
ANY_NON_EMPTY_TAG_CAPTURE_PATTERN = re.compile(rf'({ANY_NON_EMPTY_TAG_PATTERN_STR})')

CURLY_TAG_PATTERN = re.compile(r'\{[^}]*\}')
BRACKET_TAG_PATTERN = re.compile(r'\[[^\]]*\]')

ALL_TAGS_PATTERN = re.compile(
    ANY_TAG_PATTERN_STR + r'|' + re.escape(P_VISUAL_EDITOR_MARKER) + r'|' + re.escape(L_VISUAL_EDITOR_MARKER)
)

def strip_tags(text: str) -> str:
    """Remove all tag patterns from text."""
    if not text:
        return ""
    return ANY_TAG_PATTERN.sub("", text)

def mask_tags(text: str) -> str:
    """Mask tags by replacing them with space."""
    if not text:
        return ""
    return ANY_TAG_PATTERN.sub(" ", text)

def mask_all_tags_including_visual_markers(text: str) -> str:
    """Mask all tags and visual markers (▶, ▷) by replacing them with space."""
    if not text:
        return ""
    return ALL_TAGS_PATTERN.sub(" ", text)

def split_keeping_tags(text: str) -> list[str]:
    """Split text, keeping tags as separate elements."""
    if not text:
        return []
    return ANY_TAG_CAPTURE_PATTERN.split(text)

TAG_STATUS_OK = "OK"
TAG_STATUS_CRITICAL = "CRITICAL"
TAG_STATUS_MISMATCHED_CURLY = "MISMATCHED_CURLY"
TAG_STATUS_UNRESOLVED_BRACKETS = "UNRESOLVED_BRACKETS"

def apply_default_mappings_only(text_segment: str, default_mappings: dict) -> tuple[str, bool]:
    """Apply default mappings only."""
    if not default_mappings or not text_segment: return text_segment, False
    modified_segment = str(text_segment); changed = False
    sorted_keys = sorted(default_mappings.keys(), key=len, reverse=True)
    for short_tag in sorted_keys:
        full_tag = default_mappings[short_tag]
        if short_tag in modified_segment:
            modified_segment = modified_segment.replace(short_tag, full_tag); changed = True
    return modified_segment, changed