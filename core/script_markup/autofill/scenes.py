"""Scene-structure inference for local hierarchy auto-fill."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from core.script_markup.hierarchy_markup import HierarchyMark, HierarchyType

from .patterns import _is_speaker_line
from .text import (
    _clean,
    _keyword,
    _mode,
    _source_text,
    _speaker_line_is_upper,
)


def _containing_structure_parent(
    child: HierarchyMark,
    structures: list[HierarchyMark],
) -> HierarchyMark | None:
    candidates = [
        mark for mark in structures
        if mark is not child
        and mark.depth < child.depth
        and mark.start_line <= child.start_line
        and child.end_line <= mark.end_line
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda mark: (mark.depth, mark.start_line, -mark.end_line))


def _scene_name_pattern(scene_marks: list[HierarchyMark]):
    """Return a numeric label formatter learned from existing scene siblings."""

    numbered = []
    for mark in sorted(scene_marks, key=lambda item: (item.start_line, item.order)):
        match = re.search(r"(?P<number>\d+)(?!.*\d)", _clean(mark.text))
        if match:
            numbered.append((mark, match))
    if not numbered:
        return None

    first_mark, first_match = numbered[0]
    prefix = first_mark.text[:first_match.start()]
    suffix = first_mark.text[first_match.end():]
    width = len(first_match.group("number"))
    initial = int(first_match.group("number"))

    def format_name(offset: int) -> str:
        number = str(initial + offset).zfill(width)
        return f"{prefix}{number}{suffix}"

    return format_name


def _infer_scene_structures(
    raw_lines: list[str],
    approved_marks: list[HierarchyMark],
    available_structures: list[HierarchyMark],
    add_mark,
    ignored_lines: set[int],
) -> None:
    """Fill child scene structures in peer chapters from marked tree examples."""

    approved_structures = [
        mark for mark in approved_marks if mark.type_id == HierarchyType.STRUCTURE
    ]
    approved_breakers = [
        mark for mark in approved_marks if mark.type_id == HierarchyType.BREAKER
    ]
    if not approved_structures or not approved_breakers:
        return

    require_upper = any(
        _speaker_line_is_upper(_source_text(mark, raw_lines))
        for mark in approved_marks
        if mark.type_id == HierarchyType.SPEAKER
    )
    allow_inline_context = any(
        context.start_line == speaker.start_line
        for context in approved_marks if context.type_id == HierarchyType.CONTEXT
        for speaker in approved_marks if speaker.type_id == HierarchyType.SPEAKER
    )

    scene_children_by_parent: dict[int, list[HierarchyMark]] = defaultdict(list)
    parents_by_id: dict[int, HierarchyMark] = {}
    breaker_texts_by_parent: dict[int, list[str]] = defaultdict(list)

    for scene in approved_structures:
        parent = _containing_structure_parent(scene, approved_structures)
        if parent is None:
            continue
        nested_breakers = [
            breaker for breaker in approved_breakers
            if breaker.depth == scene.depth + 1
            and scene.start_line <= breaker.start_line <= scene.end_line
        ]
        if not nested_breakers:
            continue
        parent_id = id(parent)
        parents_by_id[parent_id] = parent
        scene_children_by_parent[parent_id].append(scene)
        for breaker in nested_breakers:
            if 0 <= breaker.start_line < len(raw_lines):
                exact = raw_lines[breaker.start_line]
                if exact.strip():
                    breaker_texts_by_parent[parent_id].append(exact)

    completed_targets: set[tuple[int, int, int]] = set()
    for parent_id, example_scenes in scene_children_by_parent.items():
        example_parent = parents_by_id[parent_id]
        name_for = _scene_name_pattern(example_scenes)
        breaker_counts = Counter(breaker_texts_by_parent[parent_id])
        if name_for is None or not breaker_counts:
            continue
        breaker_text = breaker_counts.most_common(1)[0][0]
        scene_depth = _mode((scene.depth for scene in example_scenes))
        example_grandparent = _containing_structure_parent(
            example_parent,
            approved_structures,
        )

        for target in available_structures:
            if target.depth != example_parent.depth:
                continue
            example_kind = _keyword(_source_text(example_parent, raw_lines))
            target_kind = _keyword(_source_text(target, raw_lines))
            if example_kind and target_kind != example_kind:
                continue
            target_key = (target.start_line, target.end_line, scene_depth)
            if target_key in completed_targets:
                continue
            target_grandparent = _containing_structure_parent(target, available_structures)
            if example_grandparent is None:
                if target_grandparent is not None:
                    continue
            elif target_grandparent is None or target_grandparent.depth != example_grandparent.depth:
                continue

            existing_children = [
                mark for mark in available_structures
                if mark.depth == scene_depth
                and target.start_line <= mark.start_line
                and mark.end_line <= target.end_line
            ]
            if existing_children:
                continue

            breaker_lines = [
                idx for idx in range(target.start_line + 1, target.end_line + 1)
                if 0 <= idx < len(raw_lines)
                and idx not in ignored_lines
                and raw_lines[idx] == breaker_text
            ]
            boundaries = [*breaker_lines, target.end_line]
            cursor = target.start_line + 1
            scene_ranges: list[tuple[int, int]] = []
            for boundary in boundaries:
                if boundary < cursor:
                    continue
                speaker_line = next(
                    (
                        idx for idx in range(cursor, boundary + 1)
                        if idx not in ignored_lines
                        and _is_speaker_line(
                            raw_lines[idx],
                            require_upper=require_upper,
                            allow_inline_context=allow_inline_context,
                        )
                    ),
                    None,
                )
                if speaker_line is None:
                    cursor = boundary + 1
                    continue
                scene_ranges.append((speaker_line, boundary))
                cursor = boundary + 1

            # A single container would merely duplicate the chapter range and
            # adds no useful hierarchy. Scenes are created only for a real split.
            if len(scene_ranges) < 2:
                continue

            scene_index = 0
            for speaker_line, end_line in scene_ranges:
                created = add_mark(
                    speaker_line,
                    end_line,
                    scene_depth,
                    HierarchyType.STRUCTURE,
                    text=name_for(scene_index),
                )
                if created is not None:
                    scene_index += 1
            if scene_index:
                completed_targets.add(target_key)
