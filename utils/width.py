from collections import OrderedDict
from typing import Optional, List, Tuple

DEFAULT_CHAR_WIDTH_FALLBACK = 6


def get_active_font_map() -> dict:
    """Get the active font map."""
    from utils import utils as uu
    if uu._ACTIVE_FONT_MAP is not None:
        return uu._ACTIVE_FONT_MAP
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                if widget.objectName() == "MainWindow" or widget.__class__.__name__ == "MainWindow":
                    return getattr(widget, "font_map", {})
    except Exception:
        pass
    return {}


def get_active_icon_sequences() -> list:
    """Get the active icon sequences."""
    from utils import utils as uu
    if uu._ACTIVE_ICON_SEQUENCES is not None:
        return uu._ACTIVE_ICON_SEQUENCES
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                if widget.objectName() == "MainWindow" or widget.__class__.__name__ == "MainWindow":
                    return getattr(widget, "icon_sequences", [])
    except Exception:
        pass
    return []


def get_active_tag_mappings() -> dict:
    """Get the active tag mappings."""
    from utils import utils as uu
    if uu._ACTIVE_TAG_MAPPINGS is not None:
        return uu._ACTIVE_TAG_MAPPINGS
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                if widget.objectName() == "MainWindow" or widget.__class__.__name__ == "MainWindow":
                    return getattr(widget, "default_tag_mappings", {})
    except Exception:
        pass
    return {}

class TrieNode:
    """Trie node implementation."""
    __slots__ = ('children', 'width', 'length')
    def __init__(self):
        """Initialize a new instance."""
        self.children: dict = {}
        self.width = None
        self.length: int = 0

_WIDTH_CACHE = {}

_STRING_WIDTH_CACHE = OrderedDict()

def clear_width_caches():
    """Clear all width calculation caches."""
    global _WIDTH_CACHE, _STRING_WIDTH_CACHE
    _WIDTH_CACHE.clear()
    _STRING_WIDTH_CACHE.clear()

def _get_trie_and_flat_map(font_map: dict, default_char_width: int, icon_sequences: Optional[List[str]], strict: bool = False):
    """Internal helper to get the trie and flat map."""
    cache_key = (id(font_map), default_char_width, tuple(icon_sequences) if icon_sequences else None, strict)
    if cache_key in _WIDTH_CACHE:
        return _WIDTH_CACHE[cache_key]

    root = TrieNode()

    font_map_icons = [str(k) for k in font_map.keys() if len(str(k)) > 1]
    if not icon_sequences:
        seqs_to_use = font_map_icons
    else:
        seqs_to_use = list(set(icon_sequences + font_map_icons))

    for seq in seqs_to_use:
        if not seq:
            continue
        node = root
        for ch in seq:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]

        info = font_map.get(seq)
        if strict:
            if info is None or (isinstance(info, dict) and 'width' not in info):
                width = None
            else:
                width = info['width'] if isinstance(info, dict) else None
        else:
            info_dict = info if isinstance(info, dict) else {}
            width = info_dict.get('width', default_char_width * len(seq))

        node.width = width
        node.length = len(seq)

    flat_widths = {}
    for k, v in font_map.items():
        if len(str(k)) == 1:
            if strict:
                w = v.get('width') if isinstance(v, dict) else None
            else:
                w = v.get('width', default_char_width) if isinstance(v, dict) else default_char_width
            flat_widths[str(k)] = w

    _WIDTH_CACHE[cache_key] = (root, flat_widths)
    return root, flat_widths

def get_tag_width(tag: str, default_tag_mappings: Optional[dict], font_map: dict, default_char_width: int = 8, icon_sequences: Optional[List[str]] = None, strict: bool = False) -> int:
    """Get the tag width."""
    if tag.startswith('{') and tag.endswith('}'):
        inner = tag[1:-1]
        if inner.lower().startswith('f:'):
            forced_text = inner[2:]
            return _calculate_string_width_impl(forced_text, font_map, default_char_width, icon_sequences, strict, default_tag_mappings) or 0

    if default_tag_mappings is None:
        from utils.utils import get_active_tag_mappings
        default_tag_mappings = get_active_tag_mappings()

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
        alias = None
        if default_tag_mappings:
            if t in default_tag_mappings:
                alias = t
            else:
                for a, orig in default_tag_mappings.items():
                    if orig == t:
                        alias = a
                        break

        if alias:
            if font_map and alias in font_map:
                alias_info = font_map.get(alias)
                if alias_info is not None:
                    if isinstance(alias_info, dict):
                        return alias_info.get("width", 0)
                    elif isinstance(alias_info, (int, float)):
                        return int(alias_info)
            if alias.startswith('{') and alias.endswith('}'):
                alias_inner = alias[1:-1]
                if alias_inner.lower().startswith('f:'):
                    forced_text = alias_inner[2:]
                    return _calculate_string_width_impl(forced_text, font_map, default_char_width, icon_sequences, strict, default_tag_mappings) or 0

    return 0

def _calculate_string_width_impl(text: str, font_map: dict, default_char_width: int = 8, icon_sequences: Optional[List[str]] = None, strict: bool = False, default_tag_mappings: Optional[dict] = None) -> Optional[int]:
    """Internal helper to calculate string width impl."""
    if not text:
        return 0

    cache_key = (
        text,
        id(font_map),
        default_char_width,
        tuple(icon_sequences) if icon_sequences else None,
        strict,
        id(default_tag_mappings) if default_tag_mappings is not None else None
    )

    global _STRING_WIDTH_CACHE
    if cache_key in _STRING_WIDTH_CACHE:
        _STRING_WIDTH_CACHE.move_to_end(cache_key)
        return _STRING_WIDTH_CACHE[cache_key]

    from utils.display_text import SPACE_DOT_SYMBOL
    if SPACE_DOT_SYMBOL in text or "\u00a0" in text:
        text = text.replace(SPACE_DOT_SYMBOL, " ").replace("\u00a0", " ")

    trie, char_widths = _get_trie_and_flat_map(font_map, default_char_width, icon_sequences, strict=strict)

    total_width = 0
    i = 0
    text_len = len(text)

    while i < text_len:
        ch = text[i]

        node = trie.children.get(ch)
        if node is not None:
            best_width = None
            best_len = 0
            is_match = False
            j = i + 1
            while node is not None and j <= text_len:
                if node.length > 0:
                    best_width = node.width
                    best_len = node.length
                    is_match = True
                if j < text_len:
                    node = node.children.get(text[j])
                else:
                    break
                j += 1

            if is_match:
                if strict and best_width is None:
                    return None
                total_width += best_width
                i += best_len
                continue

        if ch == '[':
            end_index = text.find(']', i)
            if end_index != -1:
                tag = text[i:end_index + 1]
                total_width += get_tag_width(tag, default_tag_mappings, font_map, default_char_width, icon_sequences, strict)
                i = end_index + 1
                continue
            else:
                break
        if ch == '{':
            end_index = text.find('}', i)
            if end_index != -1:
                tag = text[i:end_index + 1]
                total_width += get_tag_width(tag, default_tag_mappings, font_map, default_char_width, icon_sequences, strict)
                i = end_index + 1
                continue
            else:
                break

        if strict:
            width = char_widths.get(ch)
            if width is None:
                return None
            total_width += width
        else:
            total_width += char_widths.get(ch, default_char_width)
        i += 1

    if len(_STRING_WIDTH_CACHE) >= 10000:
        _STRING_WIDTH_CACHE.popitem(last=False)
    _STRING_WIDTH_CACHE[cache_key] = total_width
    return total_width

def calculate_string_width(text: str, font_map: dict, default_char_width: int = 8, icon_sequences: Optional[List[str]] = None, default_tag_mappings: Optional[dict] = None) -> int:
    """Calculate string width."""
    return _calculate_string_width_impl(text, font_map, default_char_width, icon_sequences, strict=False, default_tag_mappings=default_tag_mappings)

def calculate_strict_string_width(text: str, font_map: dict, icon_sequences: Optional[List[str]] = None, default_tag_mappings: Optional[dict] = None) -> Optional[int]:
    """Calculate strict string width."""
    return _calculate_string_width_impl(text, font_map, 8, icon_sequences, strict=True, default_tag_mappings=default_tag_mappings)

def _positive_int(value) -> Optional[int]:
    """Return value as a positive int, or None if it isn't one."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    return None

def resolve_string_layout(game_rules, block_idx, string_idx) -> dict:
    """Plugin-provided per-string layout (window-kind widths/font/pagination).

    Safe against missing hooks, exceptions and non-dict results (e.g. mocks).
    """
    if game_rules is None or not hasattr(game_rules, 'get_string_layout'):
        return {}
    try:
        layout = game_rules.get_string_layout(block_idx, string_idx)
    except Exception:
        return {}
    return layout if isinstance(layout, dict) else {}

def resolve_width_limits(string_meta, game_rules, block_idx, string_idx,
                         default_warn, default_max) -> Tuple[int, int]:
    """Resolve (warn_width, max_width) for one string.

    Priority: explicit per-string metadata override ("width") >
    plugin layout hook (window-kind defaults) > global settings.
    """
    meta = string_meta or {}
    override = _positive_int(meta.get("width"))
    if override is not None:
        return override, override

    layout = resolve_string_layout(game_rules, block_idx, string_idx)
    warn = _positive_int(layout.get("warn_width"))
    max_w = _positive_int(layout.get("max_width"))
    warn_default = _positive_int(default_warn) or 280
    max_default = _positive_int(default_max) or 300
    return (warn if warn is not None else warn_default,
            max_w if max_w is not None else max_default)
