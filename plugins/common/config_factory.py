from PyQt6.QtGui import QColor

def generate_base_config(prefix: str, overrides: dict = None, custom_problems: dict = None):
    """
    Generate unified base problem configuration definitions for a plugin prefix.
    """
    prob_tag_warning = f"{prefix}_TAG_WARNING"
    prob_width_exceeded = f"{prefix}_WIDTH_EXCEEDED"
    prob_short_line = f"{prefix}_SHORT_LINE"
    prob_empty_odd_subline = f"{prefix}_EMPTY_ODD_SUBLINE_DISPLAY"
    prob_single_word_subline = f"{prefix}_SINGLE_WORD_SUBLINE"
    prob_single_word_non_start = f"{prefix}_SINGLE_WORD_SUBLINE_NON_START"
    prob_bad_spacing = f"{prefix}_BAD_SPACING"
    prob_missing_icon_spacing = f"{prefix}_MISSING_ICON_SPACING"
    prob_broken_icon_hyphen = f"{prefix}_BROKEN_ICON_HYPHEN"

    prob_empty_first_line = f"{prefix}_EMPTY_FIRST_LINE_OF_PAGE"

    # Default Priorities
    priorities = {
        "TAG_WARNING": 2,
        "WIDTH_EXCEEDED": 3,
        "EMPTY_ODD_SUBLINE_DISPLAY": 4,
        "EMPTY_FIRST_LINE_OF_PAGE": 5,
        "SINGLE_WORD_SUBLINE": 6,
        "SINGLE_WORD_SUBLINE_NON_START": 5,
        "SHORT_LINE": 7,
        "BAD_SPACING": 2,
        "MISSING_ICON_SPACING": 8,
        "BROKEN_ICON_HYPHEN": 8,
    }
    if overrides and "priorities" in overrides:
        priorities.update(overrides["priorities"])

    # Default Colors
    colors = {
        "TAG_WARNING": QColor(200, 200, 200, 150),
        "WIDTH_EXCEEDED": QColor(255, 0, 0, 100),
        "EMPTY_ODD_SUBLINE_DISPLAY": QColor(255, 165, 0, 180),
        "EMPTY_FIRST_LINE_OF_PAGE": QColor(255, 105, 180, 100),
        "SHORT_LINE": QColor(0, 200, 0, 100),
        "SINGLE_WORD_SUBLINE": QColor(0, 0, 255, 120),
        "SINGLE_WORD_SUBLINE_NON_START": QColor(139, 69, 19, 120),
        "BAD_SPACING": QColor(255, 255, 0, 80),
        "MISSING_ICON_SPACING": QColor(173, 216, 230, 150),
        "BROKEN_ICON_HYPHEN": QColor(221, 160, 221, 150),  # Plum/Purple-like
    }
    if overrides and "colors" in overrides:
        colors.update(overrides["colors"])

    # Base Definitions
    problem_definitions = {
        prob_tag_warning: {
            "name": "Tag Warning",
            "color": colors["TAG_WARNING"],
            "priority": priorities["TAG_WARNING"],
            "description": "Tag count mismatch for {...} or an illegitimate tag."
        },
        prob_width_exceeded: {
            "name": "Subline Width Exceeded",
            "color": colors["WIDTH_EXCEEDED"],
            "priority": priorities["WIDTH_EXCEEDED"],
            "description": "The subline is longer than the set width limit."
        },
        prob_empty_odd_subline: {
            "name": "Empty Odd Display Subline",
            "color": colors["EMPTY_ODD_SUBLINE_DISPLAY"],
            "priority": priorities["EMPTY_ODD_SUBLINE_DISPLAY"],
            "description": "A displayed odd-numbered subline (QTextBlock) is empty or contains '0' (if not the only subline)."
        },
        prob_empty_first_line: {
            "name": "Empty First Line of Page",
            "color": colors["EMPTY_FIRST_LINE_OF_PAGE"],
            "priority": priorities["EMPTY_FIRST_LINE_OF_PAGE"],
            "description": "The first line of a page is empty, but subsequent lines on the page are not."
        },
        prob_short_line: {
            "name": "Short Subline",
            "color": colors["SHORT_LINE"],
            "priority": priorities["SHORT_LINE"],
            "description": "The subline does not end with a punctuation mark and has enough space for the first word of the next subline."
        },
        prob_single_word_subline: {
            "name": "Single Word Subline",
            "color": colors["SINGLE_WORD_SUBLINE"],
            "priority": priorities["SINGLE_WORD_SUBLINE"],
            "description": "The subline consists of only one word (and possible punctuation)."
        },
        prob_single_word_non_start: {
            "name": "Single Word Subline (Non-Start)",
            "color": colors["SINGLE_WORD_SUBLINE_NON_START"],
            "priority": priorities["SINGLE_WORD_SUBLINE_NON_START"],
            "description": "The subline consists of only one word, but not at the start of a page/dialogue window."
        },
        prob_bad_spacing: {
            "name": "Bad Spacing",
            "color": colors["BAD_SPACING"],
            "priority": priorities["TAG_WARNING"],
            "description": "Double spaces or line starting with a space (ignoring tags)."
        },
        prob_missing_icon_spacing: {
            "name": "Missing Tag Spacing",
            "color": colors["MISSING_ICON_SPACING"],
            "priority": priorities["MISSING_ICON_SPACING"],
            "description": "Missing space around visible tags, or between words separated by zero-width tags."
        },
        prob_broken_icon_hyphen: {
            "name": "Broken Icon-Hyphen Wrap",
            "color": colors["BROKEN_ICON_HYPHEN"],
            "priority": priorities["BROKEN_ICON_HYPHEN"],
            "description": "A tag-hyphen-word construct is broken across a line break."
        }
    }

    # Inject overrides for base problem definitions if provided
    if overrides and "problem_definitions" in overrides:
        for k, v in overrides["problem_definitions"].items():
            # Support both short key (e.g. "EMPTY_ODD_SUBLINE_DISPLAY") and full key (e.g. "ZWW_EMPTY_ODD_SUBLINE_DISPLAY")
            mapped_k = f"{prefix}_{k}" if not k.startswith(prefix) else k
            if mapped_k in problem_definitions:
                problem_definitions[mapped_k].update(v)

    # Custom problems unique to a plugin
    if custom_problems:
        for k, v in custom_problems.items():
            mapped_k = f"{prefix}_{k}" if not k.startswith(prefix) else k
            problem_definitions[mapped_k] = v

    # Build detection settings
    default_detection = {k: True for k in problem_definitions.keys()}
    if overrides and "detection_settings" in overrides:
        for k, v in overrides["detection_settings"].items():
            mapped_k = f"{prefix}_{k}" if not k.startswith(prefix) else k
            if mapped_k in default_detection:
                default_detection[mapped_k] = v

    # Build autofix settings
    default_autofix = {k: True for k in problem_definitions.keys()}
    # Standard overrides (some autofixes are False by default)
    default_autofix[prob_tag_warning] = False
    default_autofix[prob_single_word_subline] = False
    default_autofix[prob_single_word_non_start] = False

    if overrides and "autofix_settings" in overrides:
        for k, v in overrides["autofix_settings"].items():
            mapped_k = f"{prefix}_{k}" if not k.startswith(prefix) else k
            if mapped_k in default_autofix:
                default_autofix[mapped_k] = v

    return problem_definitions, default_detection, default_autofix
