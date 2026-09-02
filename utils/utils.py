"""Compatibility barrel for utils helpers.

Implementation lives in cohesive sibling modules; this module re-exports
every previously public name with identity-preserving bindings so existing
`from utils.utils import X` and `utils.utils._ACTIVE_*` mutations keep working.
"""
from core.tag_utils import ALL_TAGS_PATTERN

# Active-map overrides must live on this module: callers assign
# `utils.utils._ACTIVE_FONT_MAP = ...` (and siblings) directly.
_ACTIVE_FONT_MAP = None
_ACTIVE_TAG_MAPPINGS = None
_ACTIVE_ICON_SEQUENCES = None

from utils.width import (
    DEFAULT_CHAR_WIDTH_FALLBACK,
    TrieNode,
    clear_width_caches,
    get_active_font_map,
    get_active_icon_sequences,
    get_active_tag_mappings,
    get_tag_width,
    calculate_string_width,
    calculate_strict_string_width,
    resolve_string_layout,
    resolve_width_limits,
    _calculate_string_width_impl,
    _get_trie_and_flat_map,
    _positive_int,
    _WIDTH_CACHE,
    _STRING_WIDTH_CACHE,
)
from utils.text_tags import (
    FORCED_ALIAS_PATTERN,
    remove_all_tags,
    remove_curly_tags,
    is_visible_tag,
    has_visible_content,
)
from utils.spacing import (
    analyze_missing_icon_spacing,
    find_missing_icon_spacing_spans,
    fix_missing_icon_spacing_for_line,
    fix_missing_icon_spacing,
    tokenize_string_for_spacing,
    check_broken_icon_hyphen_boundary,
)
from utils.display_text import (
    SPACE_DOT_SYMBOL,
    clean_spaces,
    convert_spaces_to_dots_for_display,
    convert_dots_to_spaces_from_editor,
    convert_raw_to_display_text,
    _SPACE_DOT_RE,
    _make_replacer,
)
from utils.search_text import (
    is_fuzzy_match,
    prepare_text_for_tagless_search,
    suggest_smart_translation,
    extract_first_word_with_tags,
    PUNCTUATION_CHARS,
    clean_and_map_punctuation,
    find_smart_matches,
)
from utils.sentence_shift import (
    shift_split_sentences,
    shift_split_sentences_aligned,
    get_line_words_and_visible_tags,
)
from utils.text_misc import (
    is_control_modifier_pressed,
    resolve_target_language_prompt,
    natural_sort_key,
    _NATURAL_CHUNK_RE,
)

__all__ = [
    "ALL_TAGS_PATTERN",
    "_ACTIVE_FONT_MAP",
    "_ACTIVE_TAG_MAPPINGS",
    "_ACTIVE_ICON_SEQUENCES",
    "DEFAULT_CHAR_WIDTH_FALLBACK",
    "TrieNode",
    "clear_width_caches",
    "get_active_font_map",
    "get_active_icon_sequences",
    "get_active_tag_mappings",
    "get_tag_width",
    "calculate_string_width",
    "calculate_strict_string_width",
    "resolve_string_layout",
    "resolve_width_limits",
    "_calculate_string_width_impl",
    "_get_trie_and_flat_map",
    "_positive_int",
    "_WIDTH_CACHE",
    "_STRING_WIDTH_CACHE",
    "FORCED_ALIAS_PATTERN",
    "remove_all_tags",
    "remove_curly_tags",
    "is_visible_tag",
    "has_visible_content",
    "analyze_missing_icon_spacing",
    "find_missing_icon_spacing_spans",
    "fix_missing_icon_spacing_for_line",
    "fix_missing_icon_spacing",
    "tokenize_string_for_spacing",
    "check_broken_icon_hyphen_boundary",
    "SPACE_DOT_SYMBOL",
    "clean_spaces",
    "convert_spaces_to_dots_for_display",
    "convert_dots_to_spaces_from_editor",
    "convert_raw_to_display_text",
    "_SPACE_DOT_RE",
    "_make_replacer",
    "is_fuzzy_match",
    "prepare_text_for_tagless_search",
    "suggest_smart_translation",
    "extract_first_word_with_tags",
    "PUNCTUATION_CHARS",
    "clean_and_map_punctuation",
    "find_smart_matches",
    "shift_split_sentences",
    "shift_split_sentences_aligned",
    "get_line_words_and_visible_tags",
    "is_control_modifier_pressed",
    "resolve_target_language_prompt",
    "natural_sort_key",
    "_NATURAL_CHUNK_RE",
]
