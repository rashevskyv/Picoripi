"""Hierarchy AI job preparation and workers for Script Markup Studio."""
from __future__ import annotations

import re
from collections.abc import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from .hierarchy_ai import (
    MAX_AUTO_MARKUP_PROMPT_CHARS,
    HierarchyAIPromptTooLarge,
    build_hierarchy_auto_markup_messages,
    parse_hierarchy_auto_markup_response,
)
from .hierarchy_markup import (
    HierarchyMark,
    HierarchyType,
    HierarchyTypeDefinition,
    mark_text,
)


HIERARCHY_PROJECT_FORMAT = "picoripi.script_markup_studio.hierarchy_project"
HIERARCHY_FORMAT_VERSION = 1
HIERARCHY_AI_REQUEST_TIMEOUT_SECONDS = 60

HierarchyMessageBuilder = Callable[..., object]


def clean_hierarchy_mark_text_value(text: str) -> str:
    s = (text or "").replace(chr(0x2029), "\n").strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^\[\s*(?:Chapter|Location)\s*:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^\{\s*(?:Action|Context)\s*:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^[\[\{]\s*", "", s)
    s = re.sub(r"\s*[\]\}]\s*$", "", s)
    return s.strip()


def source_text_for_lines_value(start: int, end: int, lines: list[str]) -> str:
    if not lines:
        return ""
    start = max(0, min(start, len(lines) - 1))
    end = max(start, min(end, len(lines) - 1))
    return clean_hierarchy_mark_text_value(" ".join(lines[start:end + 1]))


def format_raw_line_range_value(start_line: int, end_line: int) -> str:
    start = start_line + 1
    end = end_line + 1
    if start == end:
        return f"raw script line {start}"
    return f"raw script lines {start}-{end}"


def hierarchy_mark_display_text_value(
    mark: HierarchyMark,
    raw_lines: list[str],
    limit: int = 96,
) -> str:
    text = mark_text(mark, raw_lines)
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + "..."


def hierarchy_mark_payload_value(
    mark: HierarchyMark,
    raw_lines: list[str],
    type_definitions: dict[str, HierarchyTypeDefinition],
) -> dict:
    type_def = type_definitions.get(mark.type_id)
    return {
        "start_line": mark.start_line,
        "end_line": mark.end_line,
        "start_line_number": mark.start_line + 1,
        "end_line_number": mark.end_line + 1,
        "depth": mark.depth,
        "type_id": mark.type_id,
        "type_label": type_def.label if type_def else mark.type_id,
        "text": mark.text,
        "label": mark.label,
        "description": mark.description or (type_def.description if type_def else ""),
        "color": mark.color or (type_def.color if type_def else ""),
        "order": mark.order,
        "source_excerpt": source_text_for_lines_value(mark.start_line, mark.end_line, raw_lines),
    }


def hierarchy_type_definitions_payload_value(
    type_definitions: dict[str, HierarchyTypeDefinition],
) -> list[dict[str, str]]:
    return [
        {
            "type_id": type_def.type_id,
            "label": type_def.label,
            "description": type_def.description,
            "color": type_def.color,
        }
        for type_def in type_definitions.values()
    ]


def hierarchy_ai_base_payload(snapshot: dict) -> dict:
    raw_lines = snapshot["raw_lines"]
    type_definitions = snapshot["type_definitions"]
    return {
        "format": HIERARCHY_PROJECT_FORMAT,
        "version": HIERARCHY_FORMAT_VERSION,
        "source_path": snapshot.get("source_path", ""),
        "raw_text": snapshot["raw_text"],
        "type_definitions": hierarchy_type_definitions_payload_value(type_definitions),
        "hierarchy_marks": [
            hierarchy_mark_payload_value(mark, raw_lines, type_definitions)
            for mark in sorted(snapshot["hierarchy_marks"], key=lambda m: (m.start_line, m.depth, m.order))
        ],
        "rendered_markdown": snapshot.get("rendered_markdown", ""),
        "ai_instructions": snapshot["ai_instructions"],
    }


def hierarchy_scope_payload_from_snapshot(
    snapshot: dict,
    unmarked_ranges: list[tuple[int, int]],
    *,
    label: str,
    start_line: int,
    end_line: int,
) -> dict:
    raw_lines = snapshot["raw_lines"]
    payload = hierarchy_ai_base_payload(snapshot)
    payload["unmarked_ranges"] = [
        {
            "start_line": start,
            "end_line": end,
            "start_line_number": start + 1,
            "end_line_number": end + 1,
            "source_excerpt": source_text_for_lines_value(start, end, raw_lines),
        }
        for start, end in unmarked_ranges
    ]
    payload["scope"] = {
        "label": label,
        "start_line_number": start_line + 1,
        "end_line_number": end_line + 1,
    }
    return payload


def build_hierarchy_ai_job_for_ranges_from_snapshot(
    snapshot: dict,
    ranges: list[tuple[int, int]],
    *,
    label_prefix: str,
    message_builder: HierarchyMessageBuilder = build_hierarchy_auto_markup_messages,
):
    start_line = min(start for start, _end in ranges)
    end_line = max(end for _start, end in ranges)
    payload = hierarchy_scope_payload_from_snapshot(
        snapshot,
        ranges,
        label=f"{label_prefix} ({format_raw_line_range_value(start_line, end_line)})",
        start_line=start_line,
        end_line=end_line,
    )
    return message_builder(
        payload,
        max_prompt_chars=MAX_AUTO_MARKUP_PROMPT_CHARS,
    )


def split_hierarchy_raw_range_jobs_from_snapshot(
    snapshot: dict,
    start_line: int,
    end_line: int,
    *,
    label_prefix: str,
    message_builder: HierarchyMessageBuilder = build_hierarchy_auto_markup_messages,
) -> list:
    jobs = []
    chunk_start = start_line
    while chunk_start <= end_line:
        best_end = None
        best_job = None
        low = chunk_start
        high = end_line
        while low <= high:
            mid = (low + high) // 2
            try:
                candidate = build_hierarchy_ai_job_for_ranges_from_snapshot(
                    snapshot,
                    [(chunk_start, mid)],
                    label_prefix=label_prefix,
                    message_builder=message_builder,
                )
                best_end = mid
                best_job = candidate
                low = mid + 1
            except HierarchyAIPromptTooLarge:
                high = mid - 1
        if best_job is None or best_end is None:
            raise HierarchyAIPromptTooLarge(
                "A raw script section is too large for one AI markup request.\n\n"
                f"Split {format_raw_line_range_value(chunk_start, chunk_start)} manually, "
                "then run AI mark missing again."
            )
        jobs.append(best_job)
        chunk_start = best_end + 1
    return jobs


def prepare_hierarchy_raw_scope_jobs_from_snapshot(
    snapshot: dict,
    ranges: list[tuple[int, int]],
    *,
    label_prefix: str = "Unstructured source",
    message_builder: HierarchyMessageBuilder = build_hierarchy_auto_markup_messages,
) -> list:
    jobs = []
    pending_ranges: list[tuple[int, int]] = []
    pending_job = None

    for item in ranges:
        candidate_ranges = [*pending_ranges, item]
        try:
            candidate_job = build_hierarchy_ai_job_for_ranges_from_snapshot(
                snapshot,
                candidate_ranges,
                label_prefix=label_prefix,
                message_builder=message_builder,
            )
            pending_ranges = candidate_ranges
            pending_job = candidate_job
            continue
        except HierarchyAIPromptTooLarge:
            if pending_job is not None:
                jobs.append(pending_job)
                pending_ranges = []
                pending_job = None
            try:
                pending_job = build_hierarchy_ai_job_for_ranges_from_snapshot(
                    snapshot,
                    [item],
                    label_prefix=label_prefix,
                    message_builder=message_builder,
                )
                pending_ranges = [item]
            except HierarchyAIPromptTooLarge:
                jobs.extend(split_hierarchy_raw_range_jobs_from_snapshot(
                    snapshot,
                    item[0],
                    item[1],
                    label_prefix=label_prefix,
                    message_builder=message_builder,
                ))

    if pending_job is not None:
        jobs.append(pending_job)
    return jobs


def prepare_hierarchy_ai_jobs_from_snapshot(
    snapshot: dict,
    unmarked_ranges: list[tuple[int, int]],
    *,
    message_builder: HierarchyMessageBuilder = build_hierarchy_auto_markup_messages,
) -> list:
    raw_lines = snapshot["raw_lines"]
    full_payload = hierarchy_scope_payload_from_snapshot(
        snapshot,
        unmarked_ranges,
        label="full script",
        start_line=0,
        end_line=max(0, len(raw_lines) - 1),
    )
    try:
        return [message_builder(
            full_payload,
            max_prompt_chars=MAX_AUTO_MARKUP_PROMPT_CHARS,
        )]
    except HierarchyAIPromptTooLarge:
        pass

    structures = sorted(
        [mark for mark in snapshot["hierarchy_marks"] if mark.type_id == HierarchyType.STRUCTURE],
        key=lambda mark: (mark.start_line, mark.depth, -mark.end_line, mark.order),
    )
    if not structures:
        return prepare_hierarchy_raw_scope_jobs_from_snapshot(
            snapshot,
            unmarked_ranges,
            label_prefix="Unstructured source",
            message_builder=message_builder,
        )

    uncovered = list(unmarked_ranges)
    jobs = []
    while uncovered:
        current_start, current_end = uncovered[0]
        enclosing = [
            mark for mark in structures
            if mark.start_line <= current_start and current_end <= mark.end_line
        ]
        enclosing.sort(key=lambda mark: (mark.depth, mark.start_line, -mark.end_line))
        if not enclosing:
            outside_ranges = []
            for item in uncovered:
                has_structure = any(
                    mark.start_line <= item[0] and item[1] <= mark.end_line
                    for mark in structures
                )
                if has_structure:
                    break
                outside_ranges.append(item)
            jobs.extend(prepare_hierarchy_raw_scope_jobs_from_snapshot(
                snapshot,
                outside_ranges or [(current_start, current_end)],
                label_prefix="Unstructured source",
                message_builder=message_builder,
            ))
            outside_set = set(outside_ranges or [(current_start, current_end)])
            uncovered = [item for item in uncovered if item not in outside_set]
            continue

        selected = None
        last_too_large = None
        for structure in enclosing:
            scoped_ranges = [
                item for item in uncovered
                if structure.start_line <= item[0] and item[1] <= structure.end_line
            ]
            if not scoped_ranges:
                continue
            text = hierarchy_mark_display_text_value(structure, raw_lines)
            label = f"{text or 'Structure'} ({format_raw_line_range_value(structure.start_line, structure.end_line)})"
            payload = hierarchy_scope_payload_from_snapshot(
                snapshot,
                scoped_ranges,
                label=label,
                start_line=structure.start_line,
                end_line=structure.end_line,
            )
            try:
                selected = (
                    structure,
                    scoped_ranges,
                    message_builder(
                        payload,
                        max_prompt_chars=MAX_AUTO_MARKUP_PROMPT_CHARS,
                    ),
                )
                break
            except HierarchyAIPromptTooLarge as exc:
                last_too_large = (structure, exc)

        if selected is None:
            structure, exc = last_too_large or (enclosing[-1], None)
            text = hierarchy_mark_display_text_value(structure, raw_lines)
            label = f"{text or 'Structure'} ({format_raw_line_range_value(structure.start_line, structure.end_line)})"
            scoped_ranges = [
                item for item in uncovered
                if structure.start_line <= item[0] and item[1] <= structure.end_line
            ]
            try:
                jobs.extend(prepare_hierarchy_raw_scope_jobs_from_snapshot(
                    snapshot,
                    scoped_ranges,
                    label_prefix=label,
                    message_builder=message_builder,
                ))
            except HierarchyAIPromptTooLarge as split_exc:
                detail = f"\n\nTechnical detail: {split_exc or exc}" if (split_exc or exc) else ""
                raise HierarchyAIPromptTooLarge(
                    "The smallest available Structure node is still too large for one AI markup request.\n\n"
                    f"Split `{label}` into smaller Structure nodes, such as chapters or scenes, "
                    "then run AI mark missing again."
                    f"{detail}"
                ) from split_exc
            scoped_set = set(scoped_ranges)
            uncovered = [item for item in uncovered if item not in scoped_set]
            continue

        _structure, scoped_ranges, prepared = selected
        jobs.append(prepared)
        scoped_set = set(scoped_ranges)
        uncovered = [item for item in uncovered if item not in scoped_set]

    return jobs


class HierarchyAIPrepareWorker(QObject):
    """Background worker for prompt/job preparation before an AI call."""

    success = pyqtSignal(list)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, snapshot: dict, unmarked_ranges: list[tuple[int, int]]):
        super().__init__()
        self.snapshot = snapshot
        self.unmarked_ranges = list(unmarked_ranges)
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        try:
            jobs = prepare_hierarchy_ai_jobs_from_snapshot(self.snapshot, self.unmarked_ranges)
            if not self.is_cancelled:
                self.success.emit(jobs)
        except Exception as exc:
            if not self.is_cancelled:
                self.error.emit(str(exc))
        finally:
            self.finished.emit()


class HierarchyAIWorker(QObject):
    """Background worker for one-shot hierarchy auto-markup."""

    success = pyqtSignal(list, list, str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal()

    def __init__(
        self,
        provider,
        jobs: list,
        raw_line_count: int,
        type_definitions: dict[str, HierarchyTypeDefinition],
    ):
        super().__init__()
        self.provider = provider
        self.jobs = jobs
        self.raw_line_count = raw_line_count
        self.type_definitions = type_definitions
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True
        cancel_stream = getattr(self.provider, "cancel_active_stream", None)
        if callable(cancel_stream):
            cancel_stream()

    def run(self):
        try:
            all_marks: list[HierarchyMark] = []
            all_warnings: list[str] = []
            responses: list[str] = []
            total = len(self.jobs)
            for index, job in enumerate(self.jobs, start=1):
                if self.is_cancelled:
                    return
                self.progress.emit(index, total, job.scope_label)
                response = self.provider.translate(
                    job.messages,
                    session=None,
                    settings_override={
                        "temperature": 0.0,
                        "timeout": HIERARCHY_AI_REQUEST_TIMEOUT_SECONDS,
                    },
                )
                if self.is_cancelled:
                    return
                response_text = response.text or ""
                marks, warnings = parse_hierarchy_auto_markup_response(
                    response_text,
                    raw_line_count=self.raw_line_count,
                    type_definitions=self.type_definitions,
                )
                all_marks.extend(marks)
                all_warnings.extend(f"{job.scope_label}: {warning}" for warning in warnings)
                responses.append(f"--- {job.scope_label} ---\n{response_text}")
            if self.is_cancelled:
                return
            self.success.emit(all_marks, all_warnings, "\n\n".join(responses))
        except Exception as exc:
            if not self.is_cancelled:
                self.error.emit(str(exc))
        finally:
            self.finished.emit()
