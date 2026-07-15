"""Local hierarchy auto-fill for Script Markup Studio.

This module intentionally does not call AI. It uses conservative patterns from
already approved marks and leaves uncertain text unmarked.
"""
from __future__ import annotations

import re
import unicodedata
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
    contexts: int = 0
    items: int = 0
    item_descriptions: int = 0
    other_types: int = 0


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

_STANDARD_RESULT_TYPES = {
    *_GENERIC_PATTERN_EXCLUDED_TYPES,
    HierarchyType.ACTION,
    HierarchyType.CONTEXT,
    HierarchyType.BREAKER,
    HierarchyType.ITEM,
    HierarchyType.ITEM_DESCRIPTION,
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


def _is_breaker_line(text: str) -> bool:
    stripped = text.strip()
    return bool(re.fullmatch(r"[~=_*\-#]{4,}", stripped))


def _speaker_line_is_upper(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    return bool(letters) and all(char.upper() == char for char in letters)


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
