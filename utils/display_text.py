import re

from core.tag_utils import ALL_TAGS_PATTERN
from plugins.common.markers import P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER

SPACE_DOT_SYMBOL = "·"

def clean_spaces(text: str) -> str:
    """Clean spaces."""
    if text is None:
        return ""

    # Normalize non-breaking spaces
    text = text.replace("\u00a0", " ")

    # Get active tag mappings and build lookahead prefix
    from utils.utils import get_active_tag_mappings, get_active_font_map, get_active_icon_sequences, is_visible_tag
    mappings = get_active_tag_mappings()
    font_map = get_active_font_map()
    icon_sequences = get_active_icon_sequences()

    curly_forced = ["f:", "F:"]
    bracket_forced = ["f:", "F:"]

    if mappings:
        for alias, original in mappings.items():
            if alias.lower().startswith("{f:") and original.startswith("{") and original.endswith("}"):
                curly_forced.append(re.escape(original[1:-1]))
            if alias.lower().startswith("{f:") and original.startswith("[") and original.endswith("]"):
                bracket_forced.append(re.escape(original[1:-1]))

    # Scan text for other tags that have non-zero width or are button tags
    tags_found = ALL_TAGS_PATTERN.findall(text)
    for tag in tags_found:
        if tag.startswith("{") and tag.endswith("}"):
            inner = tag[1:-1]
            if inner.lower().startswith("f:"):
                continue
            if is_visible_tag(tag, mappings, font_map, icon_sequences=icon_sequences):
                curly_forced.append(re.escape(inner))
        elif tag.startswith("[") and tag.endswith("]"):
            inner = tag[1:-1]
            if inner.lower().startswith("f:"):
                continue
            if is_visible_tag(tag, mappings, font_map, icon_sequences=icon_sequences):
                bracket_forced.append(re.escape(inner))

    curly_lookahead = "|".join(curly_forced)
    bracket_lookahead = "|".join(bracket_forced)

    lines = text.split('\n')
    cleaned_lines = []

    # Регулярний вираз для порожніх початкових/кінцевих тегів (фігурні теги або колірні квадратні теги)
    empty_tags_subpattern = rf"(?:\{{(?!(?:{curly_lookahead}))[^}}]*\}}|\[(?!(?:{bracket_lookahead}))(?:Red|Green|Blue|Yellow|l_Blue|Purple|Silver|Orange|White)\])*"
    leading_space_pat = re.compile(rf"^{empty_tags_subpattern}[ ·]")
    trailing_space_pat = re.compile(rf"[ ·]{empty_tags_subpattern}$")

    non_forced_tags_pattern = re.compile(
        rf'\[(?!(?:{bracket_lookahead}))[^\]]*\]|'
        rf'\{{(?!(?:{curly_lookahead}))[^}}]*\}}|' +
        re.escape(P_VISUAL_EDITOR_MARKER) + r'|' +
        re.escape(L_VISUAL_EDITOR_MARKER)
    )

    for line in lines:
        parts = re.split(f"({non_forced_tags_pattern.pattern})", line)

        # 1. Strip leading spaces: if line starts with leading space (optionally after empty tags), strip across tags.
        starts_with_space = bool(leading_space_pat.match(line))
        if starts_with_space:
            for i in range(0, len(parts), 2):
                stripped = parts[i].lstrip(" ")
                if stripped:
                    parts[i] = stripped
                    break
                else:
                    parts[i] = ""
        elif parts:
            parts[0] = parts[0].lstrip(" ")

        # 2. Strip trailing spaces: if line ends with trailing space (optionally before empty tags), strip across tags.
        ends_with_space = bool(trailing_space_pat.search(line))
        if ends_with_space:
            start_idx = len(parts) - 1 if len(parts) % 2 != 0 else len(parts) - 2
            for i in range(start_idx, -1, -2):
                stripped = parts[i].rstrip(" ")
                if stripped:
                    parts[i] = stripped
                    break
                else:
                    parts[i] = ""
        elif len(parts) % 2 != 0 and parts:
            parts[-1] = parts[-1].rstrip(" ")

        # 3. Collapse consecutive spaces inside each text part
        for i in range(len(parts)):
            if i % 2 == 0:
                parts[i] = re.sub(r' {2,}', ' ', parts[i])

        # 4. Collapse consecutive spaces across tags (skipping empty parts)
        last_ended_with_space = False
        if parts:
            if parts[0]:
                last_ended_with_space = parts[0].endswith(" ")

            for i in range(2, len(parts), 2):
                if parts[i].startswith(" "):
                    if last_ended_with_space:
                        parts[i] = parts[i].lstrip(" ")

                if parts[i]:
                    last_ended_with_space = parts[i].endswith(" ")

        cleaned_lines.append("".join(parts))

    return "\n".join(cleaned_lines)

_SPACE_DOT_RE = re.compile(f'[ {re.escape(SPACE_DOT_SYMBOL)}]+')

def _make_replacer(line_len: int):
    """Internal helper to create replacer."""
    def _replace(match: re.Match) -> str:
        """Internal helper to replace."""
        cluster = match.group(0)
        if match.start() == 0 or match.end() == line_len or len(cluster) > 1:
            return SPACE_DOT_SYMBOL * len(cluster)
        return cluster
    return _replace

def convert_spaces_to_dots_for_display(text: str, enable_conversion: bool) -> str:
    """Convert spaces to dots for display."""
    if not enable_conversion or text is None:
        return text if text is not None else ""

    lines = text.splitlines(keepends=True)
    processed_lines = []

    for line in lines:
        line_content = line.rstrip('\r\n')
        line_endings = line[len(line_content):]

        replacer = _make_replacer(len(line_content))
        new_content = _SPACE_DOT_RE.sub(replacer, line_content)
        processed_lines.append(new_content + line_endings)

    return "".join(processed_lines)

def convert_dots_to_spaces_from_editor(text: str) -> str:
    """Convert dots to spaces from editor."""
    if text is None:
        return ""
    return text.replace(SPACE_DOT_SYMBOL, " ").replace("\u00a0", " ")

def convert_raw_to_display_text(raw_text: str, show_dots: bool, newline_char_for_preview: str = "") -> str:
    """Convert raw to display text."""
    if raw_text is None:
        return ""

    text_with_dots = convert_spaces_to_dots_for_display(str(raw_text), show_dots)

    if newline_char_for_preview:
        text_with_dots = text_with_dots.replace('\n', newline_char_for_preview)

    return text_with_dots
