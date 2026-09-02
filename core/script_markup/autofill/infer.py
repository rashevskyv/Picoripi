"""Infer hierarchy marks from approved local examples."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from core.script_markup.hierarchy_markup import HierarchyMark, HierarchyType, sorted_marks

from .patterns import (
    _GENERIC_PATTERN_EXCLUDED_TYPES,
    _generic_pattern_match,
    _generic_surface_patterns,
    _infer_structure_patterns,
    _inline_speaker_parts,
    _is_speaker_line,
    _next_structure_boundary,
    _structure_depth_for_line,
)
from .scenes import _infer_scene_structures
from .text import (
    _DEFAULT_CONTEXT_SHAPES,
    _clean,
    _context_shapes_from_marks,
    _context_span,
    _covered_lines,
    _ignored_lines,
    _is_action_line,
    _is_breaker_line,
    _line_is_available,
    _mode,
    _source_text,
    _speaker_line_is_upper,
)


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
    contexts: int = 0
    items: int = 0
    item_descriptions: int = 0
    other_types: int = 0


_STANDARD_RESULT_TYPES = {
    *_GENERIC_PATTERN_EXCLUDED_TYPES,
    HierarchyType.ACTION,
    HierarchyType.CONTEXT,
    HierarchyType.BREAKER,
    HierarchyType.ITEM,
    HierarchyType.ITEM_DESCRIPTION,
}


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
    ignored_lines = _ignored_lines(marks)
    approved_marks = [
        mark for mark in marks
        if mark.approved and mark.origin == "manual"
        and (
            mark.type_id == HierarchyType.IGNORE
            or not any(
                line in ignored_lines
                for line in range(mark.start_line, mark.end_line + 1)
            )
        )
    ]
    covered = _covered_lines(marks, raw_lines)
    existing_keys = {
        (mark.start_line, mark.end_line, mark.depth, mark.type_id, mark.start_col, mark.end_col)
        for mark in marks
    }
    next_order = max((mark.order for mark in marks), default=0) + 1

    inferred: list[HierarchyMark] = []
    used_non_container_lines: set[int] = set()
    counters = Counter()

    def add_mark(
        start: int,
        end: int,
        depth: int,
        type_id: str,
        text: str = "",
        *,
        start_col: int | None = None,
        end_col: int | None = None,
    ):
        nonlocal next_order
        if start < 0 or end < start or start >= len(raw_lines):
            return None
        end = min(end, len(raw_lines) - 1)
        if any(line in ignored_lines for line in range(start, end + 1)):
            return None
        key = (start, end, depth, type_id, start_col, end_col)
        if key in existing_keys:
            return None
        existing_keys.add(key)
        mark = HierarchyMark(
            start,
            end,
            depth,
            type_id,
            text=text,
            order=next_order,
            start_col=start_col,
            end_col=end_col,
            origin="local_autofill",
            approved=False,
        )
        next_order += 1
        inferred.append(mark)
        counters[type_id] += 1
        return mark

    keyword_depths, delimiter_depths = _infer_structure_patterns(approved_marks, raw_lines)
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
            end = _next_structure_boundary(
                idx,
                depth,
                raw_lines,
                existing_structures,
                structure_starts,
                ignored_lines,
            )
            add_mark(idx, end, depth, HierarchyType.STRUCTURE, text=_clean(raw_lines[idx]))

    ignore_samples = {
        _source_text(mark, raw_lines).casefold()
        for mark in approved_marks
        if mark.type_id == HierarchyType.IGNORE and _source_text(mark, raw_lines)
    }
    if ignore_samples:
        for idx, raw in enumerate(raw_lines):
            text = _clean(raw)
            if _line_is_available(idx, raw_lines, covered) and text.casefold() in ignore_samples:
                add_mark(idx, idx, 0, HierarchyType.IGNORE)
                used_non_container_lines.add(idx)

    breaker_depth = _mode(
        (mark.depth for mark in approved_marks if mark.type_id == HierarchyType.BREAKER),
        default=0,
    )
    if any(mark.type_id == HierarchyType.BREAKER for mark in approved_marks):
        breaker_samples = {
            raw_lines[mark.start_line]
            for mark in approved_marks
            if mark.type_id == HierarchyType.BREAKER
            and 0 <= mark.start_line < len(raw_lines)
            and raw_lines[mark.start_line].strip()
        }
        for idx, raw in enumerate(raw_lines):
            if (
                _line_is_available(idx, raw_lines, covered)
                and idx not in used_non_container_lines
                and raw in breaker_samples
            ):
                add_mark(idx, idx, breaker_depth, HierarchyType.BREAKER)
                used_non_container_lines.add(idx)

    available_structures = [
        *existing_structures,
        *[mark for mark in inferred if mark.type_id == HierarchyType.STRUCTURE],
    ]
    _infer_scene_structures(
        raw_lines,
        approved_marks,
        available_structures,
        add_mark,
        ignored_lines,
    )

    item_marks = [
        mark for mark in approved_marks if mark.type_id == HierarchyType.ITEM
    ]
    item_description_marks = [
        mark
        for mark in approved_marks
        if mark.type_id == HierarchyType.ITEM_DESCRIPTION
    ]
    item_pairs = [
        (item, description)
        for item in item_marks
        for description in item_description_marks
        if description.depth == item.depth + 1
        and description.start_line == item.end_line + 1
    ]
    if item_pairs:
        item_depth = _mode((item.depth for item, _description in item_pairs), default=0)
        description_depth = _mode(
            (description.depth for _item, description in item_pairs),
            default=item_depth + 1,
        )
        learned_scopes = {}
        for item, _description in item_pairs:
            containing = [
                structure
                for structure in existing_structures
                if structure.depth < item.depth
                and structure.start_line <= item.start_line <= structure.end_line
            ]
            if containing:
                scope = max(
                    containing,
                    key=lambda mark: (mark.depth, mark.start_line, -mark.end_line, mark.order),
                )
                learned_scopes[(scope.start_line, scope.end_line, scope.depth, scope.order)] = scope

        for scope in learned_scopes.values():
            cursor = scope.start_line
            while cursor <= scope.end_line:
                while cursor <= scope.end_line and not raw_lines[cursor].strip():
                    cursor += 1
                block_start = cursor
                while cursor <= scope.end_line and raw_lines[cursor].strip():
                    cursor += 1
                block_end = cursor - 1
                if block_end <= block_start:
                    continue
                title = _clean(raw_lines[block_start])
                title_words = title.split()
                candidate_lines = range(block_start, block_end + 1)
                if (
                    not title
                    or len(title) > 80
                    or len(title_words) > 10
                    or title.endswith((".", "!", "?", ":", ";"))
                    or any(
                        not _line_is_available(line, raw_lines, covered)
                        or line in used_non_container_lines
                        for line in candidate_lines
                    )
                ):
                    continue
                item = add_mark(
                    block_start,
                    block_start,
                    item_depth,
                    HierarchyType.ITEM,
                )
                description = add_mark(
                    block_start + 1,
                    block_end,
                    description_depth,
                    HierarchyType.ITEM_DESCRIPTION,
                )
                if item is not None and description is not None:
                    used_non_container_lines.update(candidate_lines)

    action_depth = _mode(
        (mark.depth for mark in approved_marks if mark.type_id == HierarchyType.ACTION),
        default=0,
    )
    if any(
        mark.type_id == HierarchyType.ACTION and _is_action_line(_source_text(mark, raw_lines))
        for mark in approved_marks
    ):
        for idx, raw in enumerate(raw_lines):
            if _line_is_available(idx, raw_lines, covered) and idx not in used_non_container_lines and _is_action_line(raw):
                add_mark(idx, idx, action_depth, HierarchyType.ACTION)
                used_non_container_lines.add(idx)

    speaker_marks = [mark for mark in approved_marks if mark.type_id == HierarchyType.SPEAKER]
    text_marks = [mark for mark in approved_marks if mark.type_id == HierarchyType.TEXT]
    context_marks = [mark for mark in approved_marks if mark.type_id == HierarchyType.CONTEXT]
    if speaker_marks and text_marks:
        speaker_depth = _mode((mark.depth for mark in speaker_marks), default=0)
        first_speaker_line_by_depth: dict[int, int] = {}
        for speaker_mark in speaker_marks:
            first_speaker_line_by_depth[speaker_mark.depth] = min(
                speaker_mark.start_line,
                first_speaker_line_by_depth.get(
                    speaker_mark.depth,
                    speaker_mark.start_line,
                ),
            )
        text_depth = _mode(
            (
                text_mark.depth
                for text_mark in text_marks
                if text_mark.depth - 1 in first_speaker_line_by_depth
                and text_mark.start_line
                > first_speaker_line_by_depth[text_mark.depth - 1]
            ),
            default=speaker_depth + 1,
        )
        require_upper = any(_speaker_line_is_upper(_source_text(mark, raw_lines)) for mark in speaker_marks)
        speaker_lines_with_context = {speaker.start_line for speaker in speaker_marks}
        inline_context_shapes = _context_shapes_from_marks(
            (
                context
                for context in context_marks
                if context.start_line in speaker_lines_with_context
            ),
            raw_lines,
        )
        standalone_context_shapes = _context_shapes_from_marks(
            (
                context
                for context in context_marks
                if context.start_line not in speaker_lines_with_context
            ),
            raw_lines,
        )
        learn_inline_context = bool(inline_context_shapes)
        learn_standalone_context = bool(standalone_context_shapes)

        existing_speakers_by_line = {mark.start_line: mark for mark in speaker_marks}
        candidate_speaker_lines = {
            idx for idx, raw in enumerate(raw_lines)
            if _line_is_available(idx, raw_lines, covered)
            and idx not in used_non_container_lines
            and _structure_depth_for_line(raw, keyword_depths, delimiter_depths) is None
            and _is_speaker_line(
                raw,
                require_upper=require_upper,
                allow_inline_context=learn_inline_context,
                context_shapes=inline_context_shapes or _DEFAULT_CONTEXT_SHAPES,
            )
        }
        speaker_lines = sorted(set(existing_speakers_by_line) | candidate_speaker_lines)

        for anchor_idx, speaker_line in enumerate(speaker_lines):
            existing_speaker = existing_speakers_by_line.get(speaker_line)
            active_speaker_depth = existing_speaker.depth if existing_speaker is not None else speaker_depth
            active_text_depth = max(text_depth, active_speaker_depth + 1)
            speaker_name, inline_context = _inline_speaker_parts(
                raw_lines[speaker_line],
                inline_context_shapes or _DEFAULT_CONTEXT_SHAPES,
            )
            if not learn_inline_context:
                inline_context = None
            active_context_depth: int | None = None
            if existing_speaker is None:
                leading = len(raw_lines[speaker_line]) - len(raw_lines[speaker_line].lstrip())
                speaker = add_mark(
                    speaker_line,
                    speaker_line,
                    active_speaker_depth,
                    HierarchyType.SPEAKER,
                    text=speaker_name,
                    start_col=leading if inline_context is not None else None,
                    end_col=(leading + len(speaker_name)) if inline_context is not None else None,
                )
                if speaker is not None:
                    used_non_container_lines.add(speaker_line)
            if inline_context is not None:
                context_start, context_end, context_text = inline_context
                context = add_mark(
                    speaker_line,
                    speaker_line,
                    active_speaker_depth + 1,
                    HierarchyType.CONTEXT,
                    text=context_text,
                    start_col=context_start,
                    end_col=context_end,
                )
                if context is not None:
                    used_non_container_lines.add(speaker_line)
                active_context_depth = active_speaker_depth + 1

            limit = speaker_lines[anchor_idx + 1] if anchor_idx + 1 < len(speaker_lines) else len(raw_lines)
            text_start: int | None = None

            def flush_text(end_line: int):
                nonlocal text_start
                if text_start is None or end_line < text_start:
                    text_start = None
                    return
                depth = (
                    active_context_depth + 1
                    if active_context_depth is not None
                    else active_text_depth
                )
                text = add_mark(text_start, end_line, depth, HierarchyType.TEXT)
                if text is not None:
                    used_non_container_lines.update(range(text_start, end_line + 1))
                text_start = None

            for cursor in range(speaker_line + 1, limit):
                raw = raw_lines[cursor]
                if cursor in ignored_lines:
                    flush_text(cursor - 1)
                    break
                is_boundary = (
                    _is_breaker_line(raw)
                    or _structure_depth_for_line(raw, keyword_depths, delimiter_depths) is not None
                )
                if is_boundary:
                    flush_text(cursor - 1)
                    break
                context_span = (
                    _context_span(raw, standalone_context_shapes)
                    if learn_standalone_context
                    else None
                )
                if context_span is not None:
                    flush_text(cursor - 1)
                    context_start, context_end, context_text = context_span
                    context = add_mark(
                        cursor,
                        cursor,
                        active_speaker_depth + 1,
                        HierarchyType.CONTEXT,
                        text=context_text,
                        start_col=context_start,
                        end_col=context_end,
                    )
                    if context is not None:
                        used_non_container_lines.add(cursor)
                    active_context_depth = active_speaker_depth + 1
                    continue
                available = _line_is_available(cursor, raw_lines, covered)
                is_text = (
                    available
                    and cursor not in used_non_container_lines
                    and not _is_action_line(raw)
                )
                if is_text:
                    if text_start is None:
                        text_start = cursor
                else:
                    flush_text(cursor - 1)
            else:
                flush_text(limit - 1)

    exact_patterns, wrapper_patterns = _generic_surface_patterns(
        approved_marks,
        raw_lines,
    )
    if exact_patterns or wrapper_patterns:
        occupied = [
            mark
            for mark in (*marks, *inferred)
            if mark.type_id not in {
                HierarchyType.STRUCTURE,
                HierarchyType.GLOSSARY,
                HierarchyType.TEXT,
                HierarchyType.IGNORE,
                HierarchyType.UNMARKED,
            }
        ]
        for idx, raw in enumerate(raw_lines):
            if idx in ignored_lines or not raw.strip():
                continue
            match = _generic_pattern_match(raw, exact_patterns, wrapper_patterns)
            if match is None:
                continue
            type_id, depth, start_col, end_col, text = match
            line_length = len(raw)
            candidate_start = start_col or 0
            candidate_end = line_length if end_col is None else end_col
            collision = any(
                node.start_line <= idx <= node.end_line
                and (
                    node.start_line != node.end_line
                    or max(candidate_start, node.start_col or 0)
                    < min(
                        candidate_end,
                        line_length if node.end_col is None else node.end_col,
                    )
                )
                for node in occupied
            )
            if collision:
                continue
            created = add_mark(
                idx,
                idx,
                depth,
                type_id,
                text=text,
                start_col=start_col,
                end_col=end_col,
            )
            if created is not None:
                occupied.append(created)

    return LocalAutofillResult(
        marks=inferred,
        structures=counters[HierarchyType.STRUCTURE],
        speakers=counters[HierarchyType.SPEAKER],
        texts=counters[HierarchyType.TEXT],
        actions=counters[HierarchyType.ACTION],
        breakers=counters[HierarchyType.BREAKER],
        ignored=counters[HierarchyType.IGNORE],
        contexts=counters[HierarchyType.CONTEXT],
        items=counters[HierarchyType.ITEM],
        item_descriptions=counters[HierarchyType.ITEM_DESCRIPTION],
        other_types=sum(
            count
            for type_id, count in counters.items()
            if type_id not in _STANDARD_RESULT_TYPES
        ),
    )
