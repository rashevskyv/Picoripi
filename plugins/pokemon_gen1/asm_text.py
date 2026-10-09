"""The game text inside a pret decomp (pokered / pokeyellow) asm file, as editable units, and back.

A *unit* is what the editor shows as one string:

- a run of text macro lines -- ``text``, ``line``, ``cont``, ``para``, ``next``, ``page`` or a ``db`` with
  one string -- with the text commands between them (``text_ram wStringBuffer`` ...). Blank and comment lines
  inside the run belong to it; a label, a terminator (``done``, ``prompt``, ``text_end``, ``dex``), a
  ``text_far`` or any other line ends it. Text commands just before the first string join the unit, so a
  name can be moved anywhere in the sentence;
- one string of a name or list line: ``li``, ``dname``, ``npctrade``, ``ld_hli_a_string`` or a ``db`` with
  more arguments than one string.

Editor form: line breaks for ``line``/``cont``/``next``, an empty line for ``para``/``page``, text commands
as ``{text_ram wStringBuffer}``. A break typed without a marker takes the macro its position needs (the
second line of a paragraph is ``line``, later ones ``cont``; in a list every line is ``next``); where the
game used another one the editor shows it as ``{cont}``, ``{line}``... after the break. ``@`` (end of a
string) stays visible. A unit the editor did not change is written back with its original lines.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

FLOW = ("text", "line", "cont", "para", "next", "page", "db")
SINGLE = ("li", "dname", "npctrade", "ld_hli_a_string", "db")
BOUNDARY_TEXT = ("text_far", "text_end", "text_asm")
BREAK = {"line": "\n", "cont": "\n", "next": "\n", "para": "\n\n", "page": "\n\n", "text": "", "db": "\n"}
DIALOGUE = {"line", "cont", "para"}

_LABEL = re.compile(r"^(\s*)([A-Za-z_.][\w.]*:{1,2})(\s*)")
_KEYWORD = re.compile(r"^(\s*)([A-Za-z_]\w*)(\s+|$)")
_TAG = re.compile(r"\{([a-z_]\w*(?: [^{}]*)?)\}")


def split_comment(line: str) -> Tuple[str, str]:
    """``(code, comment)``: the comment starts at the first ``;`` outside a string."""
    in_string = escaped = False
    for index, char in enumerate(line):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == ";":
            return line[:index], line[index:]
    return line, ""


def literals(code: str) -> List[Tuple[int, int]]:
    """``(start, end)`` of each string literal in ``code``, quotes included."""
    spans, start, escaped = [], None, False
    for index, char in enumerate(code):
        if start is None:
            if char == '"':
                start = index
        elif escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            spans.append((start, index + 1))
            start = None
    return spans


def unescape(body: str) -> str:
    return re.sub(r"\\(.)", lambda m: m.group(1), body)


def escape(text: str) -> str:
    return re.sub(r'([\\"])', r"\\\1", text)


@dataclass
class Line:
    """One asm line, classified."""

    raw: str
    kind: str = "other"       # flow, single, inline, label, blank, comment, other
    keyword: str = ""
    prefix: str = ""          # flow: everything before the keyword (indent, label)
    label: str = ""           # the label this line defines, if any
    text: str = ""            # flow / single: the string, unescaped
    span: Tuple[int, int] = (0, 0)   # single: the literal in ``raw``
    command: str = ""         # inline: the command as written, without its comment


def classify(raw: str) -> Line:
    line = Line(raw)
    code, comment = split_comment(raw)
    if not code.strip():
        line.kind = "comment" if comment else "blank"
        return line
    rest, prefix = code, ""
    label = _LABEL.match(code)
    if label and not code[label.end():].startswith("="):
        line.label = label.group(2).rstrip(":")
        prefix, rest = label.group(0), code[label.end():]
        if not rest.strip():
            line.kind = "label"
            return line
    keyword = _KEYWORD.match(rest)
    if not keyword:
        return line
    word = keyword.group(2)
    args = rest[keyword.end():].strip()
    spans = literals(code)
    line.keyword = word
    if word in FLOW and len(spans) == 1 and args == code[spans[0][0]:spans[0][1]]:
        line.kind = "flow"
        line.prefix = prefix + keyword.group(1)
        line.text = unescape(code[spans[0][0] + 1:spans[0][1] - 1])
        if line.label:
            line.kind = "flow_label"
    elif word in SINGLE and len(spans) == 1:
        line.kind = "single"
        line.span = spans[0]
        line.text = unescape(code[spans[0][0] + 1:spans[0][1] - 1])
    elif (word.startswith("text_") and word not in BOUNDARY_TEXT) or word.startswith("sound_"):
        line.kind = "label" if line.label else "inline"
        line.command = " ".join(rest.split())
    return line


@dataclass
class Unit:
    """The lines of one editable string: ``start`` .. ``end`` (exclusive) of the file's lines."""

    start: int
    end: int
    single: bool = False
    label: str = ""
    lines: List[Line] = field(default_factory=list)

    @property
    def mode(self) -> str:
        """``dialogue`` (line / cont / para), ``db`` (one ``db`` per line) or ``list`` (next / page)."""
        words = {line.keyword for line in self.lines if line.kind in ("flow", "flow_label")}
        return "dialogue" if words & DIALOGUE else "db" if words == {"db"} else "list"


def parse(source: str) -> Tuple[List[str], List[Unit]]:
    """The file's lines (with their line ends) and its text units in order."""
    raws = source.splitlines(keepends=True)
    lines = [classify(raw.rstrip("\r\n")) for raw in raws]
    units: List[Unit] = []
    current: Optional[Unit] = None
    lead: List[int] = []      # text commands (and blank lines) after a boundary, before any string
    label = ""

    def close():
        nonlocal current
        if current is not None:
            units.append(current)
        current = None

    for index, line in enumerate(lines):
        if line.label:
            label = line.label
        kind = line.kind
        if kind in ("flow", "flow_label"):
            if kind == "flow_label" or current is None:
                close()
                first = lead[0] if lead and kind == "flow" else index
                current = Unit(first, index + 1, label=label)
            else:
                current.end = index + 1
            lead = []
        elif kind in ("inline", "blank", "comment"):
            if current is None and (kind == "inline" or lead):
                lead.append(index)
        else:
            close()
            lead = []
            if kind == "single":
                units.append(Unit(index, index + 1, single=True, label=label))
    close()
    for unit in units:
        unit.lines = lines[unit.start:unit.end]
        while unit.lines and unit.lines[0].kind in ("blank", "comment"):
            unit.start += 1
            unit.lines.pop(0)
    return raws, units


# -- editor form --------------------------------------------------------------------------------

def _next_keyword(previous: str, mode: str, breaks: int) -> str:
    if mode == "db":
        return "db"
    if mode == "list":
        return "page" if breaks > 1 else "next"
    if breaks > 1:
        return "para"
    return "cont" if previous in ("line", "cont") else "line"


def to_editor(unit: Unit) -> str:
    if unit.single:
        return unit.lines[0].text
    out, mode, previous, started = [], unit.mode, "", False
    for line in unit.lines:
        if line.kind == "inline":
            out.append("{" + line.command + "}")
            started = True
            continue
        if line.kind not in ("flow", "flow_label"):
            continue
        word = line.keyword
        if started:
            gap = BREAK[word]
            out.append(gap)
            if gap and (not line.text or word != _next_keyword(previous, mode, len(gap))):
                out.append("{" + word + "}")
        if BREAK[word] or not started:
            previous = word
        out.append(line.text)
        started = True
    return "".join(out)


def from_editor(text: str, unit: Unit) -> List[Tuple[str, str]]:
    """``[(keyword, string)]`` and ``("{}", command)`` items of an edited unit."""
    first = next((line.keyword for line in unit.lines if line.kind in ("flow", "flow_label")), "text")
    mode = unit.mode
    items: List[Tuple[str, str]] = []
    state = {"previous": "", "breaks": 0, "forced": ""}

    def string(value: str) -> None:
        breaks = state["breaks"]
        if breaks and not items:
            items.append((first, ""))
            state["previous"] = first
        if breaks:
            word = state["forced"] or _next_keyword(state["previous"], mode, breaks)
            state["previous"] = word
        elif not items:
            word = state["previous"] = first
        else:
            word = "db" if first == "db" else "text"
        items.append((word, value))
        state["breaks"], state["forced"] = 0, ""

    for token in re.split(r"(\{[a-z_]\w*(?: [^{}]*)?\}|\n)", text.replace("\r\n", "\n")):
        tag = _TAG.fullmatch(token)
        if token == "\n":
            if state["forced"]:
                string("")
            state["breaks"] += 1
        elif tag and tag.group(1) in BREAK and state["breaks"]:
            state["forced"] = tag.group(1)
        elif tag:
            if state["breaks"]:
                string("")
            items.append(("{}", tag.group(1)))
        elif token:
            string(token)
    if state["breaks"] or not any(word != "{}" for word, _ in items):
        string("")
    return items


def render(items: List[Tuple[str, str]], unit: Unit) -> List[str]:
    """Asm lines (without line ends) of an edited unit, in the decomp's style."""
    head = next((line for line in unit.lines if line.kind in ("flow", "flow_label", "inline")), None)
    indent = re.match(r"\s*", head.raw).group(0) if head is not None else "\t"
    first_prefix = head.prefix if head is not None and head.kind == "flow_label" else ""
    out: List[str] = []
    for word, value in items:
        if word == "{}":
            out.append(f"{indent}{value}")
            continue
        if word in ("para", "page") and out and out[-1].strip():
            out.append("")
        prefix = first_prefix if first_prefix and not out else indent
        out.append(f'{prefix}{word} "{escape(value)}"')
    return out


def apply(source: str, texts: List[str]) -> str:
    """``source`` with each unit replaced by its text from ``texts`` (same order); unchanged units stay."""
    raws, units = parse(source)
    if len(texts) != len(units):
        raise ValueError(f"The file has {len(units)} texts, the editor {len(texts)}")
    newline = "\r\n" if source.count("\r\n") * 2 > source.count("\n") else "\n"
    out: List[str] = []
    cursor = 0
    for unit, text in zip(units, texts):
        out.extend(raws[cursor:unit.start])
        cursor = unit.end
        text = "" if text is None else str(text)
        if text == to_editor(unit):
            out.extend(raws[unit.start:unit.end])
            continue
        if unit.single:
            raw = unit.lines[0].raw
            start, end = unit.lines[0].span
            ending = raws[unit.start][len(raw):]
            out.append(raw[:start] + '"' + escape(text.replace("\n", "")) + '"' + raw[end:] + ending)
            continue
        ending = raws[unit.end - 1][len(unit.lines[-1].raw):] or newline
        out.extend(line + newline for line in render(from_editor(text, unit), unit))
        if out and ending != newline:
            out[-1] = out[-1][:-len(newline)] + ending
    out.extend(raws[cursor:])
    return "".join(out)


def texts(source: str) -> List[str]:
    """The editor strings of a file, in order."""
    return [to_editor(unit) for unit in parse(source)[1]]
