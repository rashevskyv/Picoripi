# --- START OF FILE tests/test_utils.py ---
"""
Tests for utils/utils.py — string width calculation, tag removal, fuzzy match, space/dot conversion.
Safety net for refactoring: Issue #5 (plugin markers), Issue #11 (pathlib migration).
"""
import pytest

from utils.utils import (
    calculate_string_width,
    calculate_strict_string_width,
    remove_all_tags,
    is_fuzzy_match,
    convert_spaces_to_dots_for_display,
    convert_dots_to_spaces_from_editor,
    remove_curly_tags,
    convert_raw_to_display_text,
    prepare_text_for_tagless_search,
    SPACE_DOT_SYMBOL,
)


# ── calculate_string_width ──────────────────────────────────────────

@pytest.fixture
def sample_font_map():
    return {
        'a': {'width': 6}, 
        'b': {'width': 6}, 
        'c': {'width': 5}, 
        ' ': {'width': 4},
        '[L]': {'width': 8}, 
        '[L-Stick]': {'width': 12}, 
        '{PLAYER}': {'width': 48}
    }

@pytest.fixture
def empty_font_map():
    return {}

class TestCalculateStringWidth:
    def test_simple_ascii(self, sample_font_map):
        """Simple ASCII characters use their widths from font_map."""
        width = calculate_string_width("abc", sample_font_map)
        assert width == 6 + 6 + 5  # a=6, b=6, c=5

    def test_space(self, sample_font_map):
        """Space character has its own width."""
        width = calculate_string_width("a b", sample_font_map)
        assert width == 6 + 4 + 6  # a=6, space=4, b=6

    def test_empty_string(self, sample_font_map):
        """Empty string has width 0."""
        assert calculate_string_width("", sample_font_map) == 0

    def test_curly_tags_have_zero_width(self, sample_font_map):
        """Tags like {Color:Red} should have width 0 (skipped)."""
        width_with_tag = calculate_string_width("{Color:Red}abc", sample_font_map)
        width_without_tag = calculate_string_width("abc", sample_font_map)
        assert width_with_tag == width_without_tag

    def test_square_tags_have_zero_width(self, sample_font_map):
        """Tags like [tag] should have width 0 (skipped), unless in font_map."""
        width = calculate_string_width("[unknown_tag]abc", sample_font_map)
        width_plain = calculate_string_width("abc", sample_font_map)
        assert width == width_plain

    def test_icon_from_font_map(self, sample_font_map):
        """Icon sequences defined in font_map use their specific width."""
        width = calculate_string_width("{PLAYER}", sample_font_map)
        assert width == 48

    def test_icon_sequence_priority(self, sample_font_map):
        """Longer icon sequences take priority over shorter ones: [L-Stick] vs [L]."""
        width = calculate_string_width("[L-Stick]", sample_font_map)
        assert width == 12  # [L-Stick]=12, not [L]=8

    def test_short_icon(self, sample_font_map):
        """Short icon [L] uses its specific width."""
        width = calculate_string_width("[L]", sample_font_map)
        assert width == 8

    def test_mixed_text_tags_icons(self, sample_font_map):
        """Mix of text, tags, and icons should compute correctly."""
        text = "a{Color:Red}b[L]c"
        width = calculate_string_width(text, sample_font_map)
        # a=6, {Color:Red}=0, b=6, [L]=8, c=5
        assert width == 6 + 6 + 8 + 5

    def test_unknown_char_uses_default(self, sample_font_map):
        """Characters not in font_map use default_char_width."""
        width = calculate_string_width("Ω", sample_font_map, default_char_width=10)
        assert width == 10

    def test_empty_font_map(self, empty_font_map):
        """With empty font_map, all chars use default_char_width."""
        width = calculate_string_width("abc", empty_font_map, default_char_width=7)
    def test_with_icon_sequences(self, sample_font_map):
        """Testing icon_sequences being passed."""
        width = calculate_string_width("abc", sample_font_map, icon_sequences=["[Custom]"])
        assert width == 17

class TestCalculateStrictStringWidth:
    def test_strict_all_known(self, sample_font_map):
        width = calculate_strict_string_width("abc[L]", sample_font_map)
        assert width == 6 + 6 + 5 + 8
        
    def test_strict_missing_char(self, sample_font_map):
        assert calculate_strict_string_width("abXc", sample_font_map) is None
        
    def test_strict_missing_sequence(self, sample_font_map):
        assert calculate_strict_string_width("[UNKNOWN]", sample_font_map, icon_sequences=["[UNKNOWN]"]) is None
        
    def test_strict_tags_ignored(self, sample_font_map):
        assert calculate_strict_string_width("{Color}a", sample_font_map) == 6
        assert calculate_strict_string_width("[Tag]a", sample_font_map) == 6


# ── remove_all_tags ─────────────────────────────────────────────────

class TestRemoveAllTags:
    def test_remove_curly_tags(self):
        """Curly tags like {PLAYER} are removed."""
        assert remove_all_tags("Hello {PLAYER}!") == "Hello !"

    def test_remove_square_tags(self):
        """Square tags like [A] are removed."""
        assert remove_all_tags("Press [A] button") == "Press  button"

    def test_no_tags(self):
        """Text without tags remains unchanged."""
        assert remove_all_tags("Hello world") == "Hello world"

    def test_none_input(self):
        """None input returns empty string."""
        assert remove_all_tags(None) == ""

    def test_only_tags(self):
        """String of only tags becomes empty."""
        assert remove_all_tags("{A}{B}[C]") == ""

    def test_nested_like_tags(self):
        """Tags cannot be nested, inner braces are just consumed."""
        result = remove_all_tags("{outer}")
        assert result == ""


# ── is_fuzzy_match ──────────────────────────────────────────────────

class TestIsFuzzyMatch:
    def test_identical_words(self):
        """Identical words should match."""
        assert is_fuzzy_match("hello", "hello") is True

    def test_case_insensitive(self):
        """Match should be case-insensitive."""
        assert is_fuzzy_match("Hello", "hello") is True

    def test_very_similar(self):
        """Very similar words should match (e.g., typo)."""
        assert is_fuzzy_match("hello", "helo") is True  # ratio ~0.89

    def test_different_words(self):
        """Completely different words should not match."""
        assert is_fuzzy_match("hello", "world") is False

    def test_empty_strings(self):
        """Empty strings should not match."""
        assert is_fuzzy_match("", "hello") is False
        assert is_fuzzy_match("hello", "") is False
        assert is_fuzzy_match("", "") is False

    def test_length_diff_optimization(self):
        """Words differing by more than 3 chars should not match (optimization)."""
        assert is_fuzzy_match("hi", "hello!") is False

    def test_custom_threshold(self):
        """Custom threshold changes sensitivity."""
        assert is_fuzzy_match("abc", "abd", threshold=0.5) is True
        assert is_fuzzy_match("abc", "xyz", threshold=0.5) is False


# ── convert_spaces_to_dots / convert_dots_to_spaces ─────────────────

class TestSpaceDotConversion:
    def test_multiple_spaces_to_dots(self):
        """Two or more consecutive spaces become dots."""
        result = convert_spaces_to_dots_for_display("a  b", True)
        assert result == f"a{SPACE_DOT_SYMBOL}{SPACE_DOT_SYMBOL}b"

    def test_single_space_unchanged(self):
        """A single space between words stays as space."""
        result = convert_spaces_to_dots_for_display("a b c", True)
        assert result == "a b c"

    def test_leading_space(self):
        """A single leading space becomes a dot."""
        result = convert_spaces_to_dots_for_display(" hello", True)
        assert result == f"{SPACE_DOT_SYMBOL}hello"

    def test_trailing_space(self):
        """A single trailing space becomes a dot."""
        result = convert_spaces_to_dots_for_display("hello ", True)
        assert result == f"hello{SPACE_DOT_SYMBOL}"

    def test_disabled(self):
        """When disabled, text is returned unchanged."""
        result = convert_spaces_to_dots_for_display("a  b", False)
        assert result == "a  b"

    def test_none_input(self):
        """None input returns empty string."""
        assert convert_spaces_to_dots_for_display(None, True) == ""
        assert convert_spaces_to_dots_for_display(None, False) == ""

    def test_dots_to_spaces_roundtrip(self):
        """Converting to dots then back to spaces restores multi-space sequences."""
        original = "a  b"
        dotted = convert_spaces_to_dots_for_display(original, True)
        restored = convert_dots_to_spaces_from_editor(dotted)
        assert restored == original

    def test_convert_dots_to_spaces_none(self):
        assert convert_dots_to_spaces_from_editor(None) == ""


# ── remove_curly_tags ───────────────────────────────────────────────

class TestRemoveCurlyTags:
    def test_basic(self):
        assert remove_curly_tags("{Color:Red}text{Color:White}") == "text"

    def test_none(self):
        assert remove_curly_tags(None) == ""

    def test_no_tags(self):
        assert remove_curly_tags("plain text") == "plain text"

    def test_square_tags_preserved(self):
        """Square tags are NOT removed by this function."""
        assert remove_curly_tags("[A] test") == "[A] test"


# ── convert_raw_to_display_text ─────────────────────────────────────

class TestConvertRawToDisplayText:
    def test_none(self):
        assert convert_raw_to_display_text(None, False) == ""

    def test_newline_replacement(self):
        result = convert_raw_to_display_text("line1\nline2", False, "↵")
        assert result == "line1↵line2"

    def test_with_dots(self):
        result = convert_raw_to_display_text("a  b", True)
        assert SPACE_DOT_SYMBOL in result


# ── prepare_text_for_tagless_search ─────────────────────────────────

class TestPrepareTextForTaglessSearch:
    def test_removes_tags(self):
        result = prepare_text_for_tagless_search("{PLAYER} hello [A]")
        assert result == "hello"

    def test_replaces_newlines_with_spaces(self):
        result = prepare_text_for_tagless_search("line1\nline2")
        assert result == "line1 line2"

    def test_normalizes_spaces(self):
        result = prepare_text_for_tagless_search("a   b")
        assert result == "a b"

    def test_strips(self):
        result = prepare_text_for_tagless_search("  hello  ")
        assert result == "hello"

    def test_none(self):
        assert prepare_text_for_tagless_search(None) == ""
