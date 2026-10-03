"""Strict source/translation line-layout contracts for AI text operations."""

from __future__ import annotations

import re
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
    allow_reflow: bool = False,
) -> str:
    """The translation, if its line layout is one the game can show; raises TranslationLayoutError otherwise.

    ``allow_reflow``: the model may break the text into more or fewer lines than the source (a translation is
    longer or shorter); blank lines (page breaks) and the trailing newline must stay. Lines wider than the window
    are re-wrapped when the translation is applied (``TextFormatter.fit_translation_to_window``).
    """
    source = normalize_newlines(source_text)
    translated = normalize_newlines(translation)
    expected = layout_signature(source, lines_per_window)
    actual = layout_signature(translated, lines_per_window)
    reflowed = actual["line_count"] != expected["line_count"]
    if reflowed and not allow_reflow:
        raise TranslationLayoutError(
            f"line layout mismatch: expected {expected['line_count']} lines, "
            f"received {actual['line_count']}; do not remove or merge source lines"
        )
    blank_layout_changed = (
        len(actual["blank_line_indices"]) < len(expected["blank_line_indices"])
        if reflowed
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
        not reflowed
        and actual.get("window_count") != expected.get("window_count")
    ):
        raise TranslationLayoutError(
            f"dialogue-window count mismatch: expected {expected['window_count']}, "
            f"received {actual['window_count']}"
        )
    return translated


_WORD = re.compile(r"[^\W\d_]{3,}")
_TAG = re.compile(r"\{[^}]*\}|\[[^\]]*\]")


def check_translated(source_text: Any, translation: Any, *, item_id: Any = None) -> None:
    """Raise when a reply leaves a line in the source language (live run 2026-10-03: "You bought a шматочок
    пирога! One bite, and you're in heaven!" -- only the glossary term was translated).

    Untranslated = the line has at least four source words of 3+ letters and more than half of them are still
    there word for word. Tags are left out; a line of names or codes is too short to count.
    """
    source_words = [w.casefold() for w in _WORD.findall(_TAG.sub(" ", str(source_text or "")))]
    if len(source_words) < 4:
        return
    kept = set(w.casefold() for w in _WORD.findall(_TAG.sub(" ", str(translation or ""))))
    left = sum(1 for word in source_words if word in kept)
    if left * 2 > len(source_words):
        label = f"item {item_id}" if item_id is not None else "a line"
        raise TranslationLayoutError(
            f"{label} is not translated: {left} of {len(source_words)} source words are still in it")
