"""Local hierarchy auto-fill for Script Markup Studio.

This module intentionally does not call AI. It uses conservative patterns from
already approved marks and leaves uncertain text unmarked.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from .hierarchy_markup import HierarchyMark, HierarchyType, mark_text, sorted_marks


_STRUCTURE_KEYWORDS = {
    "act",
    "chapter",
    "scene",
    "part",
    "section",
    "prologue",
    "epilogue",
}


@dataclass(frozen=True)
class LocalAutofillResult:
    """Marks inferred locally plus lightweight counters for user feedback."""

    marks: list[HierarchyMark]
    structures: int = 0
    speakers: int = 0
    texts: int = 0
    actions: int = 0
    breakers: int = 0
    ignored: int = 0


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _mode(values: Iterable[int], default: int = 0) -> int:
    counts = Counter(values)
    if not counts:
        return default
    return counts.most_common(1)[0][0]


def _covered_lines(marks: Iterable[HierarchyMark]) -> set[int]:
    covered: set[int] = set()
    for mark in marks:
        if mark.type_id in (HierarchyType.STRUCTURE, HierarchyType.SPEAKER):
            covered.add(mark.start_line)
        else:
            covered.update(range(mark.start_line, mark.end_line + 1))
    return covered


def _line_is_available(idx: int, raw_lines: list[str], covered: set[int]) -> bool:
    return 0 <= idx < len(raw_lines) and idx not in covered and bool(raw_lines[idx].strip())


def _source_text(mark: HierarchyMark, raw_lines: list[str]) -> str:
    return _clean(mark_text(mark, raw_lines))


def _keyword(text: str) -> str:
    match = re.match(r"^\s*([A-Za-z]+)\b", text or "")
    return match.group(1).casefold() if match else ""


def _delimiter_shape(text: str) -> tuple[str, str] | None:
    stripped = text.strip()
    match = re.match(r"^(?P<lead>[^A-Za-z0-9]+).+?(?P<trail>[^A-Za-z0-9]+)$", stripped)
    if not match:
        return None
    lead = match.group("lead").strip()
    trail = match.group("trail").strip()
    if not lead and not trail:
        return None
    return lead, trail


def _matches_delimiter_shape(text: str, shape: tuple[str, str]) -> bool:
    lead, trail = shape
    stripped = text.strip()
    return bool(stripped) and stripped.startswith(lead) and stripped.endswith(trail)


def _is_action_line(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if re.fullmatch(r"\[\s*\*?.+?\*?\s*\]", stripped):
        return True
    if re.fullmatch(r"\{\s*(?:Action|Context)\s*:.+?\}", stripped, re.IGNORECASE):
        return True
    return False


def _is_breaker_line(text: str) -> bool:
    stripped = text.strip()
    return bool(re.fullmatch(r"[~=_*\-#]{4,}", stripped))


def _speaker_line_is_upper(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    return bool(letters) and all(char.upper() == char for char in letters)


def _is_speaker_line(text: str, *, require_upper: bool) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > 48:
        return False
    if ":" in stripped or _is_action_line(stripped) or _is_breaker_line(stripped):
        return False
    if _keyword(stripped) in _STRUCTURE_KEYWORDS:
        return False
    if len(stripped.split()) > 5:
        return False
    if require_upper and not _speaker_line_is_upper(stripped):
        return False
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 .'#\-]*", stripped))


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
) -> int:
    boundary = len(raw_lines) - 1
    for mark in existing_structures:
        if mark.start_line > start_line and mark.depth <= depth:
            boundary = min(boundary, mark.start_line - 1)
    for line_idx, candidate_depth in candidate_starts:
        if line_idx > start_line and candidate_depth <= depth:
            boundary = min(boundary, line_idx - 1)
    return max(start_line, boundary)


def infer_hierarchy_marks_from_examples(
    raw_text: str,
    hierarchy_marks: Iterable[HierarchyMark],
) -> LocalAutofillResult:
    """Infer safe local hierarchy marks from existing examples.

    The function is intentionally conservative. It adds marks only for repeated
    surface patterns already represented in the approved marks.
    """

    raw_lines = (raw_text or "").splitlines()
    marks = sorted_marks(hierarchy_marks)
    covered = _covered_lines(marks)
    existing_keys = {
        (mark.start_line, mark.end_line, mark.depth, mark.type_id)
        for mark in marks
    }
    next_order = max((mark.order for mark in marks), default=0) + 1

    inferred: list[HierarchyMark] = []
    used_non_container_lines: set[int] = set()
    counters = Counter()

    def add_mark(start: int, end: int, depth: int, type_id: str, text: str = ""):
        nonlocal next_order
        if start < 0 or end < start or start >= len(raw_lines):
            return None
        end = min(end, len(raw_lines) - 1)
        key = (start, end, depth, type_id)
        if key in existing_keys:
            return None
        existing_keys.add(key)
        mark = HierarchyMark(start, end, depth, type_id, text=text, order=next_order)
        next_order += 1
        inferred.append(mark)
        counters[type_id] += 1
        return mark

    keyword_depths, delimiter_depths = _infer_structure_patterns(marks, raw_lines)
    existing_structures = [mark for mark in marks if mark.type_id == HierarchyType.STRUCTURE]
    structure_starts: list[tuple[int, int]] = []
    if keyword_depths or delimiter_depths:
        for idx, raw in enumerate(raw_lines):
            if not _line_is_available(idx, raw_lines, covered):
                continue
            depth = _structure_depth_for_line(raw, keyword_depths, delimiter_depths)
            if depth is not None:
                structure_starts.append((idx, depth))
        for idx, depth in structure_starts:
            end = _next_structure_boundary(idx, depth, raw_lines, existing_structures, structure_starts)
            add_mark(idx, end, depth, HierarchyType.STRUCTURE, text=_clean(raw_lines[idx]))

    ignore_samples = {
        _source_text(mark, raw_lines).casefold()
        for mark in marks
        if mark.type_id == HierarchyType.IGNORE and _source_text(mark, raw_lines)
    }
    if ignore_samples:
        for idx, raw in enumerate(raw_lines):
            text = _clean(raw)
            if _line_is_available(idx, raw_lines, covered) and text.casefold() in ignore_samples:
                add_mark(idx, idx, 0, HierarchyType.IGNORE)
                used_non_container_lines.add(idx)

    breaker_depth = _mode(
        (mark.depth for mark in marks if mark.type_id == HierarchyType.BREAKER),
        default=0,
    )
    if any(mark.type_id == HierarchyType.BREAKER for mark in marks):
        for idx, raw in enumerate(raw_lines):
            if _line_is_available(idx, raw_lines, covered) and idx not in used_non_container_lines and _is_breaker_line(raw):
                add_mark(idx, idx, breaker_depth, HierarchyType.BREAKER)
                used_non_container_lines.add(idx)

    action_depth = _mode(
        (mark.depth for mark in marks if mark.type_id == HierarchyType.ACTION),
        default=0,
    )
    if any(mark.type_id == HierarchyType.ACTION and _is_action_line(_source_text(mark, raw_lines)) for mark in marks):
        for idx, raw in enumerate(raw_lines):
            if _line_is_available(idx, raw_lines, covered) and idx not in used_non_container_lines and _is_action_line(raw):
                add_mark(idx, idx, action_depth, HierarchyType.ACTION)
                used_non_container_lines.add(idx)

    speaker_marks = [mark for mark in marks if mark.type_id == HierarchyType.SPEAKER]
    text_marks = [mark for mark in marks if mark.type_id == HierarchyType.TEXT]
    if speaker_marks and text_marks:
        speaker_depth = _mode((mark.depth for mark in speaker_marks), default=0)
        text_depth = _mode(
            (
                text_mark.depth
                for text_mark in text_marks
                for speaker_mark in speaker_marks
                if text_mark.start_line > speaker_mark.start_line
                and text_mark.depth > speaker_mark.depth
            ),
            default=speaker_depth + 1,
        )
        require_upper = any(_speaker_line_is_upper(_source_text(mark, raw_lines)) for mark in speaker_marks)

        idx = 0
        while idx < len(raw_lines):
            if (
                not _line_is_available(idx, raw_lines, covered)
                or idx in used_non_container_lines
                or _structure_depth_for_line(raw_lines[idx], keyword_depths, delimiter_depths) is not None
                or not _is_speaker_line(raw_lines[idx], require_upper=require_upper)
            ):
                idx += 1
                continue

            speaker_line = idx
            body_start = speaker_line + 1
            body_end = body_start - 1
            cursor = body_start
            while cursor < len(raw_lines):
                if (
                    not _line_is_available(cursor, raw_lines, covered)
                    or cursor in used_non_container_lines
                    or _is_speaker_line(raw_lines[cursor], require_upper=require_upper)
                    or _is_action_line(raw_lines[cursor])
                    or _is_breaker_line(raw_lines[cursor])
                    or _structure_depth_for_line(raw_lines[cursor], keyword_depths, delimiter_depths) is not None
                ):
                    break
                body_end = cursor
                cursor += 1

            speaker = add_mark(
                speaker_line,
                speaker_line,
                speaker_depth,
                HierarchyType.SPEAKER,
                text=_clean(raw_lines[speaker_line]),
            )
            if speaker is not None:
                used_non_container_lines.add(speaker_line)
            if body_end >= body_start:
                text = add_mark(body_start, body_end, text_depth, HierarchyType.TEXT)
                if text is not None:
                    used_non_container_lines.update(range(body_start, body_end + 1))
            idx = max(cursor, idx + 1)

    return LocalAutofillResult(
        marks=inferred,
        structures=counters[HierarchyType.STRUCTURE],
        speakers=counters[HierarchyType.SPEAKER],
        texts=counters[HierarchyType.TEXT],
        actions=counters[HierarchyType.ACTION],
        breakers=counters[HierarchyType.BREAKER],
        ignored=counters[HierarchyType.IGNORE],
    )
