import re
from typing import Optional, List

from core.tag_utils import ALL_TAGS_PATTERN

FORCED_ALIAS_PATTERN = re.compile(r'\{[Ff]:([^}]*)\}')

def remove_all_tags(text: str, tag_mappings: Optional[dict] = None) -> str:
    """Remove all tags."""
    if text is None:
        return ""
    if tag_mappings is None:
        from utils.utils import get_active_tag_mappings
        tag_mappings = get_active_tag_mappings()
    if tag_mappings:
        sorted_mappings = sorted(tag_mappings.items(), key=lambda item: len(item[1]), reverse=True)
        for alias, original_tag in sorted_mappings:
            if original_tag:
                text = text.replace(original_tag, alias)
    text = FORCED_ALIAS_PATTERN.sub(r"\1", text)
    return ALL_TAGS_PATTERN.sub("", text)

def is_visible_tag(tag: str, mappings: Optional[dict] = None, font_map: Optional[dict] = None, icon_sequences: Optional[List[str]] = None) -> bool:
    """Check if is visible tag."""
    if tag is None:
        return False
    tag_lower = tag.lower()
    if tag_lower in ('{*}', '{tab}', '{escape:6:000a}', '{escape:6:000b}'):
        return False
    if '(' in tag and ')' in tag:
        return True

    if mappings is None:
        from utils.utils import get_active_tag_mappings
        mappings = get_active_tag_mappings()
    if font_map is None:
        from utils.utils import get_active_font_map
        font_map = get_active_font_map()
    if icon_sequences is None:
        from utils.utils import get_active_icon_sequences
        icon_sequences = get_active_icon_sequences()

    from utils.width import get_tag_width

    # Generate normalized variants to support tags with or without parentheses (e.g. {btn5} vs {(btn5)})
    normalized_tags = [tag]
    if tag.startswith('{') and tag.endswith('}'):
        inner = tag[1:-1]
        if not (inner.startswith('(') and inner.endswith(')')):
            normalized_tags.append(f"{{({inner})}}")
        else:
            normalized_tags.append(f"{{{inner[1:-1]}}}")
    elif tag.startswith('[') and tag.endswith(']'):
        inner = tag[1:-1]
        if not (inner.startswith('(') and inner.endswith(')')):
            normalized_tags.append(f"[({inner})]")
        else:
            normalized_tags.append(f"[{inner[1:-1]}]")

    for t in normalized_tags:
        is_known = False

        if font_map and t in font_map:
            val = font_map.get(t)
            if val is not None:
                w = val.get("width", 0) if isinstance(val, dict) else int(val)
                if w > 0:
                    return True
                is_known = True

        # Font maps are authoritative: a known zero-width control tag must not
        # become a visible icon merely because the icon-sequence cache contains
        # every multi-character font-map key.
        if not is_known and icon_sequences and t in icon_sequences:
            return True

        width = get_tag_width(t, mappings, font_map, icon_sequences=icon_sequences)
        if width > 0:
            return True

        if mappings:
            if t in mappings:
                orig = mappings[t]
                if orig and '(' in orig and ')' in orig:
                    return True
                is_known = True
            else:
                for alias, orig in mappings.items():
                    if orig == t:
                        if alias and '(' in alias and ')' in alias:
                            return True
                        is_known = True
                        break

        # If the variant contains parentheses and is a known tag in the system, treat it as visible
        if '(' in t and ')' in t and is_known:
            return True

    return False

def remove_curly_tags(text: str, tag_mappings: Optional[dict] = None) -> str:
    """Remove curly tags."""
    if text is None:
        return ""
    if tag_mappings is None:
        from utils.utils import get_active_tag_mappings
        tag_mappings = get_active_tag_mappings()
    if tag_mappings:
        sorted_mappings = sorted(tag_mappings.items(), key=lambda item: len(item[1]), reverse=True)
        for alias, original_tag in sorted_mappings:
            if original_tag:
                text = text.replace(original_tag, alias)
    text = FORCED_ALIAS_PATTERN.sub(r"\1", text)
    return re.sub(r"\{[^}]*\}", "", text)

def has_visible_content(text: str, mappings: Optional[dict] = None, font_map: Optional[dict] = None, icon_sequences: Optional[List[str]] = None) -> bool:
    """Check if has visible content."""
    if not text:
        return False
    text_no_tags = remove_all_tags(text, mappings)
    if text_no_tags.strip():
        return True
    for tag_match in ALL_TAGS_PATTERN.finditer(text):
        tag = tag_match.group(0)
        if is_visible_tag(tag, mappings, font_map, icon_sequences):
            return True
    return False
