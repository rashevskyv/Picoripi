"""AI request/response helpers for Script Markup Studio hierarchy markup."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .hierarchy_markup import HierarchyMark, HierarchyTypeDefinition


MAX_AUTO_MARKUP_PROMPT_CHARS = 90000


class HierarchyAIPromptTooLarge(ValueError):
    """Raised when the current auto-markup request is too large for one call."""


@dataclass(frozen=True)
class HierarchyAIMessages:
    """Prepared chat messages plus small diagnostics for the UI."""

    messages: list[dict[str, str]]
    prompt_chars: int
    unmarked_range_count: int


def _json_dumps(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _source_blocks(raw_lines: list[str], unmarked_ranges: Iterable[dict]) -> list[dict]:
    blocks: list[dict] = []
    line_count = len(raw_lines)
    for item in unmarked_ranges:
        try:
            start = int(item.get("start_line", 0))
            end = int(item.get("end_line", start))
        except (TypeError, ValueError):
            continue
        if line_count <= 0:
            continue
        start = max(0, min(start, line_count - 1))
        end = max(start, min(end, line_count - 1))
        blocks.append({
            "start_line_number": start + 1,
            "end_line_number": end + 1,
            "lines": [
                {"line_number": idx + 1, "text": raw_lines[idx]}
                for idx in range(start, end + 1)
            ],
        })
    return blocks


def build_hierarchy_auto_markup_messages(
    project_payload: dict,
    *,
    max_prompt_chars: int = MAX_AUTO_MARKUP_PROMPT_CHARS,
) -> HierarchyAIMessages:
    """Build chat messages that ask AI to mark only currently unmarked ranges."""

    raw_text = str(project_payload.get("raw_text") or "")
    raw_lines = raw_text.splitlines()
    unmarked_ranges = [
        item for item in project_payload.get("unmarked_ranges", [])
        if isinstance(item, dict)
    ]
    source_blocks = _source_blocks(raw_lines, unmarked_ranges)
    type_definitions = project_payload.get("type_definitions", [])
    hierarchy_marks = project_payload.get("hierarchy_marks", [])
    ai_instructions = project_payload.get("ai_instructions", [])

    system_prompt = (
        "You are Script Markup Studio's hierarchy annotator. "
        "Return only valid JSON. Do not explain your answer."
    )
    response_schema = {
        "marks": [
            {
                "start_line_number": 1,
                "end_line_number": 1,
                "depth": 0,
                "type_id": "structure",
                "text": "optional label for structure/speaker",
            }
        ]
    }
    user_payload = {
        "task": (
            "Continue the user's manual hierarchy markup by annotating only the "
            "provided unmarked source blocks."
        ),
        "rules": [
            *ai_instructions,
            "Use 1-based start_line_number/end_line_number values from source_blocks.",
            "Do not return marks for already approved hierarchy_marks.",
            "Use only type_id values present in type_definitions.",
            "For Structure and Speaker nodes, put the human-readable label in text.",
            "For Text, Action, Note, Breaker, and Narrator nodes, leave text empty "
            "unless the source line has no usable text.",
            "If an Action appears inside a dialogue, split the surrounding Text into "
            "separate sibling Text ranges around that Action.",
            "Prefer covering every meaningful unmarked line. Skip junk only when it "
            "should remain unmarked for human review.",
        ],
        "type_definitions": type_definitions,
        "approved_hierarchy_marks": hierarchy_marks,
        "source_blocks": source_blocks,
        "response_schema": response_schema,
    }
    user_prompt = _json_dumps(user_payload)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    prompt_chars = sum(len(message["content"]) for message in messages)
    if prompt_chars > max_prompt_chars:
        raise HierarchyAIPromptTooLarge(
            f"AI markup request is {prompt_chars:,} characters; "
            f"limit is {max_prompt_chars:,}."
        )
    return HierarchyAIMessages(
        messages=messages,
        prompt_chars=prompt_chars,
        unmarked_range_count=len(source_blocks),
    )


def _extract_json_text(text: str) -> str:
    value = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", value, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    first_obj = value.find("{")
    last_obj = value.rfind("}")
    if first_obj >= 0 and last_obj > first_obj:
        return value[first_obj:last_obj + 1].strip()
    first_arr = value.find("[")
    last_arr = value.rfind("]")
    if first_arr >= 0 and last_arr > first_arr:
        return value[first_arr:last_arr + 1].strip()
    return value


def _line_index_from_item(item: dict, base_key: str, number_key: str) -> int | None:
    if number_key in item:
        try:
            return int(item[number_key]) - 1
        except (TypeError, ValueError):
            return None
    if base_key in item:
        try:
            return int(item[base_key])
        except (TypeError, ValueError):
            return None
    return None


def _type_id_from_item(
    item: dict,
    type_definitions: dict[str, HierarchyTypeDefinition],
) -> str | None:
    raw_type = str(item.get("type_id") or "").strip()
    if raw_type in type_definitions:
        return raw_type
    raw_label = str(item.get("type_label") or item.get("type") or "").strip()
    if not raw_label:
        return None
    folded = raw_label.casefold()
    for type_id, type_def in type_definitions.items():
        if type_id.casefold() == folded or type_def.label.casefold() == folded:
            return type_id
    return None


def parse_hierarchy_auto_markup_response(
    response_text: str,
    *,
    raw_line_count: int,
    type_definitions: dict[str, HierarchyTypeDefinition],
) -> tuple[list[HierarchyMark], list[str]]:
    """Parse an AI JSON response into valid hierarchy marks."""

    warnings: list[str] = []
    try:
        parsed = json.loads(_extract_json_text(response_text))
    except Exception as exc:
        raise ValueError(f"AI did not return valid JSON: {exc}") from exc

    raw_items = parsed.get("marks") if isinstance(parsed, dict) else parsed
    if not isinstance(raw_items, list):
        raise ValueError("AI JSON must contain a marks array.")

    marks: list[HierarchyMark] = []
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            warnings.append(f"Skipped mark {index}: not an object.")
            continue
        start = _line_index_from_item(item, "start_line", "start_line_number")
        end = _line_index_from_item(item, "end_line", "end_line_number")
        type_id = _type_id_from_item(item, type_definitions)
        try:
            depth = max(0, int(item.get("depth", 0)))
        except (TypeError, ValueError):
            depth = 0
        if start is None or end is None:
            warnings.append(f"Skipped mark {index}: missing line range.")
            continue
        if type_id is None:
            warnings.append(f"Skipped mark {index}: unknown type.")
            continue
        if raw_line_count <= 0 or start < 0 or start >= raw_line_count:
            warnings.append(f"Skipped mark {index}: start line is outside the file.")
            continue
        end = max(start, min(end, raw_line_count - 1))
        text = str(item.get("text") or item.get("label") or "").strip()
        color = str(item.get("color") or "").strip()
        marks.append(HierarchyMark(start, end, depth, type_id, text=text, color=color))
    return marks, warnings
