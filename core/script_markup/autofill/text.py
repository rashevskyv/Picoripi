"""Text / line predicates for local hierarchy auto-fill."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Iterable

from core.script_markup.hierarchy_markup import HierarchyMark, HierarchyType, mark_text


_STRUCTURE_KEYWORDS = {
    "act",
    "chapter",
    "scene",
    "part",
    "section",
    "prologue",
    "epilogue",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _mode(values: Iterable[int], default: int = 0) -> int:
    counts = Counter(values)
    if not counts:
        return default
    return counts.most_common(1)[0][0]


def _structure_owns_source_line(
    mark: HierarchyMark,
    raw_lines: list[str] | None,
) -> bool:
    if raw_lines is None or not (0 <= mark.start_line < len(raw_lines)):
        return True
    explicit_label = _clean(mark.text or mark.label)
    if not explicit_label:
        return True
    source = _clean(raw_lines[mark.start_line])
    return explicit_label.casefold() == source.casefold()


def _covered_lines(
    marks: Iterable[HierarchyMark],
    raw_lines: list[str] | None = None,
) -> set[int]:
    covered: set[int] = set()
    for mark in marks:
        if mark.type_id == HierarchyType.STRUCTURE:
            if _structure_owns_source_line(mark, raw_lines):
                covered.add(mark.start_line)
        elif mark.type_id == HierarchyType.SPEAKER:
            covered.add(mark.start_line)
        else:
            covered.update(range(mark.start_line, mark.end_line + 1))
    return covered


def _ignored_lines(marks: Iterable[HierarchyMark]) -> set[int]:
    ignored: set[int] = set()
    for mark in marks:
        if mark.type_id == HierarchyType.IGNORE:
            ignored.update(range(mark.start_line, mark.end_line + 1))
    return ignored


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


_DEFAULT_CONTEXT_SHAPES = (("(", ")"),)


def _context_span(
    text: str,
    shapes: Iterable[tuple[str, str]] = _DEFAULT_CONTEXT_SHAPES,
) -> tuple[int, int, str] | None:
    source = text or ""
    leading = len(source) - len(source.lstrip())
    trailing = len(source.rstrip())
    stripped = source[leading:trailing]
    for opener, closer in shapes:
        if not opener or not closer or not stripped.startswith(opener) or not stripped.endswith(closer):
            continue
        start = leading + len(opener)
        end = trailing - len(closer)
        context = source[start:end].strip()
        if context:
            content_start = start + len(source[start:end]) - len(source[start:end].lstrip())
            content_end = end - (len(source[start:end]) - len(source[start:end].rstrip()))
            return content_start, content_end, context
    return None


def _context_shape_from_mark(
    mark: HierarchyMark,
    raw_lines: list[str],
) -> tuple[str, str] | None:
    if mark.start_line != mark.end_line or not (0 <= mark.start_line < len(raw_lines)):
        return None
    source = raw_lines[mark.start_line]
    if mark.start_col is not None:
        start = max(0, min(mark.start_col, len(source)))
        end = len(source) if mark.end_col is None else max(start, min(mark.end_col, len(source)))
        before = source[:start].rstrip()
        after = source[end:].lstrip()
        if before and after and before[-1] in "([{<" and after[0] in ")]}>":
            return before[-1], after[0]
    stripped = source.strip()
    if len(stripped) >= 2 and stripped[0] in "([{<" and stripped[-1] in ")]}>":
        return stripped[0], stripped[-1]
    return None


def _context_shapes_from_marks(
    marks: Iterable[HierarchyMark],
    raw_lines: list[str],
) -> tuple[tuple[str, str], ...]:
    return tuple(dict.fromkeys(
        shape
        for mark in marks
        if (shape := _context_shape_from_mark(mark, raw_lines)) is not None
    ))


def _speaker_name_chars_are_valid(text: str) -> bool:
    if not text or not text[0].isalpha():
        return False
    return all(
        char.isalnum()
        or char.isspace()
        or char in ".'’‘#-"
        or unicodedata.category(char).startswith("M")
        for char in text[1:]
    )


def _is_breaker_line(text: str) -> bool:
    stripped = text.strip()
    return bool(re.fullmatch(r"[~=_*\-#]{4,}", stripped))


def _speaker_line_is_upper(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    return bool(letters) and all(char.upper() == char for char in letters)
