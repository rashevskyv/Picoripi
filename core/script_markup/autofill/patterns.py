"""Surface / structure / inline-speaker patterns for local hierarchy auto-fill."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from core.script_markup.hierarchy_markup import HierarchyMark, HierarchyType

from .text import (
    _STRUCTURE_KEYWORDS,
    _DEFAULT_CONTEXT_SHAPES,
    _clean,
    _delimiter_shape,
    _is_action_line,
    _is_breaker_line,
    _keyword,
    _matches_delimiter_shape,
    _mode,
    _source_text,
    _speaker_line_is_upper,
    _speaker_name_chars_are_valid,
)


_GENERIC_PATTERN_EXCLUDED_TYPES = {
    HierarchyType.STRUCTURE,
    HierarchyType.SPEAKER,
    HierarchyType.TEXT,
    HierarchyType.GLOSSARY,
    HierarchyType.ITEM,
    HierarchyType.ITEM_DESCRIPTION,
    HierarchyType.IGNORE,
    HierarchyType.UNMARKED,
}


def _generic_surface_patterns(
    marks: Iterable[HierarchyMark],
    raw_lines: list[str],
) -> tuple[
    dict[str, tuple[str, int]],
    dict[tuple[str, str, bool], tuple[str, int]],
]:
    """Learn unambiguous exact/wrapper patterns for unspecialized types."""

    exact_targets: dict[str, set[tuple[str, int]]] = defaultdict(set)
    wrapper_targets: dict[tuple[str, str, bool], set[tuple[str, int]]] = defaultdict(set)
    for mark in marks:
        if (
            mark.type_id in _GENERIC_PATTERN_EXCLUDED_TYPES
            or mark.start_line != mark.end_line
            or not (0 <= mark.start_line < len(raw_lines))
        ):
            continue
        source = raw_lines[mark.start_line]
        target = (mark.type_id, mark.depth)
        if mark.start_col is not None:
            start = max(0, min(mark.start_col, len(source)))
            end = len(source) if mark.end_col is None else max(
                start,
                min(mark.end_col, len(source)),
            )
            before = source[:start].rstrip()
            after = source[end:].lstrip()
            if before and after and not before[-1].isalnum() and not after[0].isalnum():
                wrapper_targets[(before[-1], after[0], True)].add(target)
            continue

        cleaned = _clean(source).casefold()
        if cleaned:
            exact_targets[cleaned].add(target)
        shape = _delimiter_shape(source)
        if shape is not None:
            wrapper_targets[(*shape, False)].add(target)

    exact = {
        sample: next(iter(targets))
        for sample, targets in exact_targets.items()
        if len(targets) == 1
    }
    wrappers = {
        shape: next(iter(targets))
        for shape, targets in wrapper_targets.items()
        if len(targets) == 1
    }
    return exact, wrappers


def _generic_pattern_match(
    raw: str,
    exact_patterns: dict[str, tuple[str, int]],
    wrapper_patterns: dict[tuple[str, str, bool], tuple[str, int]],
) -> tuple[str, int, int | None, int | None, str] | None:
    exact = exact_patterns.get(_clean(raw).casefold())
    if exact is not None:
        return (*exact, None, None, "")

    leading = len(raw) - len(raw.lstrip())
    trailing = len(raw.rstrip())
    stripped = raw[leading:trailing]
    for (opener, closer, partial), target in wrapper_patterns.items():
        if not stripped.startswith(opener) or not stripped.endswith(closer):
            continue
        if not partial:
            return (*target, None, None, "")
        start = leading + len(opener)
        end = trailing - len(closer)
        inner = raw[start:end]
        content = inner.strip()
        if not content:
            continue
        content_start = start + len(inner) - len(inner.lstrip())
        content_end = end - (len(inner) - len(inner.rstrip()))
        return (*target, content_start, content_end, content)
    return None


def _inline_speaker_parts(
    text: str,
    context_shapes: Iterable[tuple[str, str]] = _DEFAULT_CONTEXT_SHAPES,
) -> tuple[str, tuple[int, int, str] | None]:
    source = text or ""
    for opener, closer in context_shapes:
        pattern = re.fullmatch(
            rf"(?P<lead>\s*)(?P<speaker>.+?)\s+{re.escape(opener)}"
            rf"(?P<context>.*?){re.escape(closer)}\s*",
            source,
        )
        if not pattern:
            continue
        speaker = pattern.group("speaker").strip()
        context = pattern.group("context").strip()
        if _speaker_name_chars_are_valid(speaker) and context:
            return (
                speaker,
                (pattern.start("context"), pattern.end("context"), context),
            )
    return source.strip(), None


def _is_speaker_line(
    text: str,
    *,
    require_upper: bool,
    allow_inline_context: bool = False,
    context_shapes: Iterable[tuple[str, str]] = _DEFAULT_CONTEXT_SHAPES,
) -> bool:
    stripped, inline_context = _inline_speaker_parts(text, context_shapes)
    if inline_context is not None and not allow_inline_context:
        return False
    if not stripped or len(stripped) > 48:
        return False
    if ":" in stripped or _is_action_line(stripped) or _is_breaker_line(stripped):
        return False
    if _keyword(stripped) in _STRUCTURE_KEYWORDS:
        return False
    if len(stripped.split()) > 5:
        return False
    if sum(char.isalpha() for char in stripped) < 2:
        return False
    if require_upper and not _speaker_line_is_upper(stripped):
        return False
    return _speaker_name_chars_are_valid(stripped)


def _infer_structure_patterns(marks: list[HierarchyMark], raw_lines: list[str]):
    keyword_depths: dict[str, list[int]] = defaultdict(list)
    delimiter_depths: dict[tuple[str, str], list[int]] = defaultdict(list)
    for mark in marks:
        if mark.type_id != HierarchyType.STRUCTURE:
            continue
        text = _source_text(mark, raw_lines)
        word = _keyword(text)
        if word in _STRUCTURE_KEYWORDS:
            keyword_depths[word].append(mark.depth)
        shape = _delimiter_shape(text)
        if shape is not None:
            delimiter_depths[shape].append(mark.depth)
    return keyword_depths, delimiter_depths


def _structure_depth_for_line(
    text: str,
    keyword_depths: dict[str, list[int]],
    delimiter_depths: dict[tuple[str, str], list[int]],
) -> int | None:
    word = _keyword(text)
    if word in keyword_depths:
        return _mode(keyword_depths[word])
    for shape, depths in delimiter_depths.items():
        if _matches_delimiter_shape(text, shape):
            return _mode(depths)
    return None


def _next_structure_boundary(
    start_line: int,
    depth: int,
    raw_lines: list[str],
    existing_structures: list[HierarchyMark],
    candidate_starts: list[tuple[int, int]],
    ignored_lines: set[int],
) -> int:
    boundary = len(raw_lines) - 1
    for mark in existing_structures:
        if mark.start_line > start_line and mark.depth <= depth:
            boundary = min(boundary, mark.start_line - 1)
    for line_idx, candidate_depth in candidate_starts:
        if line_idx > start_line and candidate_depth <= depth:
            boundary = min(boundary, line_idx - 1)
    blocked_after_start = [line for line in ignored_lines if line > start_line]
    if blocked_after_start:
        boundary = min(boundary, min(blocked_after_start) - 1)
    return max(start_line, boundary)
