import pytest
import re
from core.tag_utils import (
    ANY_TAG_PATTERN,
    CURLY_TAG_PATTERN,
    BRACKET_TAG_PATTERN,
    strip_tags,
    mask_tags,
    split_keeping_tags,
    mask_all_tags_including_visual_markers,
)
from plugins.default_plugin.tag_manager import TagManager

def test_tag_patterns():
    # Test curly tag pattern
    assert CURLY_TAG_PATTERN.match("{Color:Red}")
    assert not CURLY_TAG_PATTERN.match("[PLAYER]")

    # Test bracket tag pattern
    assert BRACKET_TAG_PATTERN.match("[PLAYER]")
    assert not BRACKET_TAG_PATTERN.match("{Color:Red}")

    # Test any tag pattern
    assert ANY_TAG_PATTERN.match("{Color:Red}")
    assert ANY_TAG_PATTERN.match("[PLAYER]")
    assert not ANY_TAG_PATTERN.match("Hello")

def test_strip_tags():
    assert strip_tags("Hello {Color:Red}World [PLAYER]!") == "Hello World !"
    assert strip_tags("") == ""
    assert strip_tags(None) == ""

def test_mask_tags():
    assert mask_tags("Hello {Color:Red}World [PLAYER]!") == "Hello  World  !"
    assert mask_tags("") == ""
    assert mask_tags(None) == ""

def test_mask_all_tags_including_visual_markers():
    # Visual editor markers should be masked too
    assert mask_all_tags_including_visual_markers("Hello ▶ World ▷ {Color:Red} [PLAYER]") == "Hello   World      "
    assert mask_all_tags_including_visual_markers("") == ""
    assert mask_all_tags_including_visual_markers(None) == ""

def test_split_keeping_tags():
    text = "Hello {Color:Red}World [PLAYER]!"
    parts = split_keeping_tags(text)
    assert parts == ["Hello ", "{Color:Red}", "World ", "[PLAYER]", "!"]
    assert split_keeping_tags("") == []
    assert split_keeping_tags(None) == []

def test_default_plugin_empty_tags_rejected():
    tm = TagManager()
    # Legitimate non-empty tags
    assert tm.is_tag_legitimate("{Color:Red}")
    assert tm.is_tag_legitimate("[PLAYER]")
    # Empty tags must be rejected
    assert not tm.is_tag_legitimate("{}")
    assert not tm.is_tag_legitimate("[]")
    # Invalid values
    assert not tm.is_tag_legitimate(None)
    assert not tm.is_tag_legitimate(123)

