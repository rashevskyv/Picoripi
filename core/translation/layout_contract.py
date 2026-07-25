"""Strict source/translation line-layout contracts for AI text operations."""

from __future__ import annotations

from math import ceil
from typing import Any, Optional


class TranslationLayoutError(ValueError):
    pass


def normalize_newlines(text: Any) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n")


def editor_text_for_layout(text: Any, game_rules=None) -> str:
    value = normalize_newlines(text)
    if game_rules and hasattr(game_rules, "get_text_representation_for_editor"):
        converted = game_rules.get_text_representation_for_editor(value)
        if isinstance(converted, str):
            value = normalize_newlines(converted)
    return value


def resolve_lines_per_window(
    main_window: Any,
    block_idx: Optional[int] = None,
    string_idx: Optional[int] = None,
) -> Optional[int]:
    """Resolve the actual dialogue-window capacity for one string."""
    rules = getattr(main_window, "current_game_rules", None)
    if rules:
        for method_name in ("get_string_layout", "get_preview_window_style"):
            method = getattr(rules, method_name, None)
            if not callable(method):
                continue
            try:
                layout = method(block_idx, string_idx)
            except (TypeError, ValueError):
                continue
            if isinstance(layout, dict):
                value = layout.get("lines_per_page")
                if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                    return value
    value = getattr(main_window, "lines_per_page", None)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def layout_signature(text: Any, lines_per_window: Optional[int] = None) -> dict:
    value = normalize_newlines(text)
    lines = value.split("\n")
    signature = {
        "line_count": len(lines),
        "blank_line_indices": [
            index for index, line in enumerate(lines) if not line.strip()
        ],
        "ends_with_newline": value.endswith("\n"),
    }
    if isinstance(lines_per_window, int) and lines_per_window > 0:
        visible_line_count = len(value.splitlines()) if value else 0
        signature.update({
            "visible_line_count": visible_line_count,
            "lines_per_window": lines_per_window,
            "window_count": ceil(max(1, visible_line_count) / lines_per_window),
        })
    return signature


def validate_translation_layout(
    source_text: Any,
    translation: Any,
    lines_per_window: Optional[int] = None,
    *,
    allow_line_expansion: bool = False,
) -> str:
    source = normalize_newlines(source_text)
    translated = normalize_newlines(translation)
    expected = layout_signature(source, lines_per_window)
    actual = layout_signature(translated, lines_per_window)
    expanded = actual["line_count"] > expected["line_count"]
    if actual["line_count"] != expected["line_count"] and not (
        allow_line_expansion and expanded
    ):
        raise TranslationLayoutError(
            f"line layout mismatch: expected {expected['line_count']} lines, "
            f"received {actual['line_count']}; do not remove or merge source lines"
        )
    blank_layout_changed = (
        len(actual["blank_line_indices"]) < len(expected["blank_line_indices"])
        if expanded
        else actual["blank_line_indices"] != expected["blank_line_indices"]
    )
    if blank_layout_changed:
        raise TranslationLayoutError(
            "blank-line layout mismatch: expected blank lines at indices "
            f"{expected['blank_line_indices']}, received {actual['blank_line_indices']}"
        )
    if actual["ends_with_newline"] != expected["ends_with_newline"]:
        raise TranslationLayoutError(
            "trailing-newline layout mismatch"
        )
    if (
        not expanded
        and actual.get("window_count") != expected.get("window_count")
    ):
        raise TranslationLayoutError(
            f"dialogue-window count mismatch: expected {expected['window_count']}, "
            f"received {actual['window_count']}"
        )
    return translated
