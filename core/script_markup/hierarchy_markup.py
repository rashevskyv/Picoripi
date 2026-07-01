"""Hierarchy markup model for Script Markup Studio.

This module is intentionally Qt-free. It turns manual line annotations into a
small tree and renders that tree to the canonical Markdown syntax that the rest
of Picoripi can parse.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple


class HierarchyType:
    """Markdown-facing type of a marked hierarchy node."""

    STRUCTURE = "structure"
    SPEAKER = "speaker"
    TEXT = "text"
    ACTION = "action"
    NOTE = "note"
    BREAKER = "breaker"
    NARRATOR = "narrator"
    IGNORE = "ignore"
    UNMARKED = "unmarked"


BREAKER_LINE = "~~~~~~~~~~~~~~~~~~~~~~~~"


@dataclass(frozen=True)
class HierarchyTypeDefinition:
    """Default semantics and colour for one hierarchy markup type."""

    type_id: str
    label: str
    description: str
    color: str


@dataclass
class HierarchyMark:
    """A manual mark over one or more source lines.

    ``depth`` is the hierarchy index: 0 is the root/top layer, 1 is nested under
    the previous depth-0 mark, 2 is nested under the previous depth-1 mark, and
    equal depths are siblings.
    """

    start_line: int
    end_line: int
    depth: int
    type_id: str
    text: str = ""
    label: str = ""
    description: str = ""
    color: str = ""
    order: int = 0


@dataclass
class HierarchyNode:
    """Tree node built from a flat list of HierarchyMark objects."""

    mark: Optional[HierarchyMark] = None
    children: List["HierarchyNode"] = field(default_factory=list)


def default_type_definitions() -> Dict[str, HierarchyTypeDefinition]:
    """Return the built-in hierarchy types and their default highlight colours."""

    return {
        HierarchyType.STRUCTURE: HierarchyTypeDefinition(
            HierarchyType.STRUCTURE,
            "Structure",
            "Acts, chapters, scenes, locations, and other heading-like blocks.",
            "#d9ecff",
        ),
        HierarchyType.SPEAKER: HierarchyTypeDefinition(
            HierarchyType.SPEAKER,
            "Speaker",
            "The character or entity that speaks the following text.",
            "#dff6dd",
        ),
        HierarchyType.TEXT: HierarchyTypeDefinition(
            HierarchyType.TEXT,
            "Text",
            "Spoken text attached to the nearest speaker.",
            "#f1faf3",
        ),
        HierarchyType.ACTION: HierarchyTypeDefinition(
            HierarchyType.ACTION,
            "Action",
            "A standalone stage/action direction rendered as italic text in square brackets.",
            "#fff4ce",
        ),
        HierarchyType.NOTE: HierarchyTypeDefinition(
            HierarchyType.NOTE,
            "Note",
            "Inline note rendered in parentheses after the nearest element.",
            "#ede7f6",
        ),
        HierarchyType.BREAKER: HierarchyTypeDefinition(
            HierarchyType.BREAKER,
            "Breaker",
            "A visual/logical separator between parts of the same level.",
            "#eeeeee",
        ),
        HierarchyType.NARRATOR: HierarchyTypeDefinition(
            HierarchyType.NARRATOR,
            "Narrator",
            "Narrative text that is spoken by no character.",
            "#fce4ec",
        ),
        HierarchyType.IGNORE: HierarchyTypeDefinition(
            HierarchyType.IGNORE,
            "Ignored",
            "Source text intentionally skipped from Markdown output.",
            "#e5e5e5",
        ),
        HierarchyType.UNMARKED: HierarchyTypeDefinition(
            HierarchyType.UNMARKED,
            "Unmarked",
            "Source text that still needs a decision.",
            "#ffe5e5",
        ),
    }


def clean_mark_text(text: str) -> str:
    """Normalize marked source text for single-line Markdown output."""

    s = (text or "").replace(chr(0x2029), "\n").strip()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def mark_text(mark: HierarchyMark, raw_lines: List[str]) -> str:
    """Return the Markdown-facing text for a mark.

    Structure nodes are labels/headings, so their explicit text may override the
    source range. Content nodes should preserve the original script text; their
    explicit text is only a fallback when no source text is available.
    """

    explicit = clean_mark_text(mark.text or mark.label)
    if mark.type_id == HierarchyType.STRUCTURE and explicit:
        return explicit
    if not raw_lines:
        return explicit
    start = max(0, min(mark.start_line, len(raw_lines) - 1))
    end = max(start, min(mark.end_line, len(raw_lines) - 1))
    if mark.type_id in (HierarchyType.STRUCTURE, HierarchyType.SPEAKER):
        for idx in range(start, end + 1):
            line = clean_mark_text(raw_lines[idx])
            if line:
                return line
        return explicit
    return clean_mark_text(" ".join(raw_lines[start:end + 1]))


def normalize_mark(mark: HierarchyMark) -> HierarchyMark:
    """Return a copy with sane line and depth values."""

    start = max(0, int(mark.start_line))
    end = max(start, int(mark.end_line))
    return HierarchyMark(
        start_line=start,
        end_line=end,
        depth=max(0, int(mark.depth)),
        type_id=mark.type_id or HierarchyType.TEXT,
        text=mark.text,
        label=mark.label,
        description=mark.description,
        color=mark.color,
        order=int(mark.order),
    )


def sorted_marks(marks: Iterable[HierarchyMark]) -> List[HierarchyMark]:
    """Sort marks by source order while keeping user insertion order stable."""

    return sorted(
        (normalize_mark(mark) for mark in marks),
        key=lambda mark: (mark.start_line, mark.depth, -mark.end_line, mark.order),
    )


def build_hierarchy_tree(marks: Iterable[HierarchyMark]) -> HierarchyNode:
    """Build a tree from depth-indexed marks.

    Equal depths become siblings. A mark becomes a child of the nearest previous
    mark with a smaller depth.
    """

    root = HierarchyNode()
    stack: List[HierarchyNode] = [root]
    for mark in sorted_marks(marks):
        node = HierarchyNode(mark=mark)
        while len(stack) > 1 and stack[-1].mark and stack[-1].mark.depth >= mark.depth:
            stack.pop()
        stack[-1].children.append(node)
        stack.append(node)
    return root


def line_styles_for_marks(
    marks: Iterable[HierarchyMark],
    type_definitions: Optional[Dict[str, HierarchyTypeDefinition]] = None,
) -> Dict[int, Tuple[str, str]]:
    """Return ``line_index -> (type_id, color)`` for highlighters."""

    defs = type_definitions or default_type_definitions()
    styles: Dict[int, Tuple[str, str]] = {}
    for mark in sorted_marks(marks):
        default = defs.get(mark.type_id)
        color = mark.color or (default.color if default else "#ffffff")
        for idx in range(mark.start_line, mark.end_line + 1):
            styles[idx] = (mark.type_id, color)
    return styles


def _append_blank(lines: List[str]):
    if lines and lines[-1] != "":
        lines.append("")


def _append_block(lines: List[str], text: str):
    if not text:
        return
    _append_blank(lines)
    lines.append(text)


def _append_note(lines: List[str], text: str):
    if not text:
        return
    note = f"({text})"
    if lines and lines[-1] != "":
        lines[-1] = f"{lines[-1].rstrip()} {note}"
    else:
        lines.append(note)


def _clean_action_text(text: str) -> str:
    action_text = re.sub(r"^\[\s*(.*?)\s*\]$", r"\1", text or "").strip()
    italic = re.fullmatch(r"(?:\*(?P<star>.*?)\*|_(?P<under>.*?)_)", action_text)
    if italic:
        action_text = (italic.group("star") or italic.group("under") or "").strip()
    return action_text


def render_hierarchy_markdown(
    marks: Iterable[HierarchyMark],
    raw_text: str = "",
    type_definitions: Optional[Dict[str, HierarchyTypeDefinition]] = None,
) -> str:
    """Render hierarchy marks to canonical Markdown.

    Speaker and text are separate nodes in the model, but direct text children of
    a speaker render as one Markdown line: ``**SPEAKER**: dialogue``.
    """

    raw_lines = (raw_text or "").splitlines()
    root = build_hierarchy_tree(marks)
    lines: List[str] = []

    def text_for(mark: HierarchyMark) -> str:
        return mark_text(mark, raw_lines)

    def append_raw_range(start: int, end: int):
        if not raw_lines or end < start:
            return
        start = max(0, min(start, len(raw_lines) - 1))
        end = max(start, min(end, len(raw_lines) - 1))
        raw = [line.rstrip() for line in raw_lines[start:end + 1] if line.strip()]
        if not raw:
            return
        _append_blank(lines)
        for idx, line in enumerate(raw):
            prefix = "> [RAW] " if idx == 0 else "> "
            lines.append(f"{prefix}{line}")
        _append_blank(lines)

    def node_end_line(node: HierarchyNode) -> int:
        end = node.mark.end_line if node.mark else -1
        for child in node.children:
            end = max(end, node_end_line(child))
        return end

    def render_structure_children(node: HierarchyNode, mark: HierarchyMark):
        cursor = mark.start_line + 1
        for child in sorted(node.children, key=lambda n: (n.mark.start_line, n.mark.depth, n.mark.order) if n.mark else (0, 0, 0)):
            if child.mark:
                append_raw_range(cursor, child.mark.start_line - 1)
                render_node(child)
                cursor = max(cursor, node_end_line(child) + 1)
            else:
                render_node(child)
        append_raw_range(cursor, mark.end_line)

    def render_node(node: HierarchyNode):
        if node.mark is None:
            for child in node.children:
                render_node(child)
            return

        mark = node.mark
        type_id = mark.type_id
        text = text_for(mark)

        if type_id == HierarchyType.STRUCTURE:
            _append_blank(lines)
            heading_depth = max(1, min(mark.depth + 1, 6))
            lines.append(f"{'#' * heading_depth} {text}".rstrip())
            _append_blank(lines)
            render_structure_children(node, mark)
            return

        if type_id == HierarchyType.SPEAKER:
            emitted_text = False
            for child in node.children:
                if not child.mark:
                    render_node(child)
                    continue
                child_type = child.mark.type_id
                if child_type == HierarchyType.TEXT:
                    body = text_for(child.mark).strip()
                    if body:
                        _append_block(lines, f"**{text}**: {body}".rstrip())
                        emitted_text = True
                    for grandchild in child.children:
                        render_node(grandchild)
                elif child_type == HierarchyType.NOTE:
                    _append_note(lines, text_for(child.mark))
                else:
                    render_node(child)
            if not emitted_text and not node.children:
                _append_block(lines, f"**{text}**:")
            return

        if type_id == HierarchyType.TEXT:
            if text:
                _append_block(lines, text)
            for child in node.children:
                render_node(child)
            return

        if type_id == HierarchyType.ACTION:
            if text:
                action_text = _clean_action_text(text)
                if action_text:
                    _append_block(lines, f"[*{action_text}*]")
            for child in node.children:
                render_node(child)
            return

        if type_id == HierarchyType.NOTE:
            _append_note(lines, text)
            for child in node.children:
                render_node(child)
            return

        if type_id == HierarchyType.BREAKER:
            _append_blank(lines)
            lines.append(BREAKER_LINE)
            _append_blank(lines)
            for child in node.children:
                render_node(child)
            return

        if type_id == HierarchyType.NARRATOR:
            if text:
                _append_block(lines, f"**{text}**")
            for child in node.children:
                render_node(child)
            return

        if type_id in (HierarchyType.IGNORE, HierarchyType.UNMARKED):
            return

        if text:
            _append_block(lines, text)
        for child in node.children:
            render_node(child)

    render_node(root)
    rendered = "\n".join(lines)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered).strip()
    return f"{rendered}\n" if rendered else ""

