"""Text of a pret Game Boy decompilation (pokegold, pokecrystal): find it in an asm file, show it, write it back.

A *unit* is one string of the editor:

- a **message**: consecutive text lines (``text``, ``line``, ``cont``, ``para``, ``next``, ``page``, a ``db``
  with one string) and the text commands between them (``text_ram``, ``text_decimal``, ``sound_*``...), up
  to ``done`` / ``prompt`` / ``text_end`` / ``text_asm``, a label or any other line. A message that starts
  with ``db``/``next``/``page`` (Pokédex entries, menus, names) is a *db message*: it also ends at a string
  that ends with the terminator ``@``; that last ``@`` is not shown and is always written back.
- a **literal**: each string of a ``li``, ``dname``, ``dbw``, ``bt_trainer``, ``npctrade``... line, or of a ``db``
  with more than the one string. Shown and written as it is.

The editor shows a message as text: a new line is a ``line``/``cont`` (text messages: ``line`` for the second
line of a box, ``cont`` after it) or a ``next`` (db messages); an empty line starts a new box (``para``) or
Pokédex page (``page``). A command that differs from that default is shown as a tag at the start of its line
(``[cont]``, ``[next]``...); a ``text`` that continues a line is ``[text]``; a text command is shown whole in
brackets (``[text_ram wStringBuffer3]``). The string content is the asm literal as written (charmap names such
as ``<PLAYER>``, ``#``, ``{d:VALUE}``), except that a typed ``"`` is escaped on save.

Writing never moves a unit: a message that is unchanged keeps its lines byte for byte, a changed one is
written again in pret style in the same place (its comments inside are not kept), a literal is replaced in
its line. Every unit always keeps at least one string, so the units of the written file are the units of the
source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

MESSAGE_COMMANDS = ("text", "line", "cont", "para", "next", "page", "db")
TERMINATORS = frozenset({"done", "prompt", "text_end", "text_asm"})
LITERAL_COMMANDS = frozenset({"db", "dbw", "li", "dname", "bt_trainer", "npctrade", "debugtrade"})
TEXT_KIND, DB_KIND, LITERAL_KIND = "text", "db", "literal"
_PARAGRAPH = {TEXT_KIND: "para", DB_KIND: "page"}
_START = {TEXT_KIND: "text", DB_KIND: "db"}

_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')
_DIRECTIVE_RE = re.compile(r"\s*([A-Za-z_]\w*)\b\s*(.*?)\s*$")
_LABEL_RE = re.compile(r"^(?:[A-Za-z_][\w.@#$]*:{1,2}|\.[\w.@#$]+:{0,2})")
# Tags the editor shows: a message command, a text command in brackets.
COMMAND_TAG_RE = re.compile(r"\[(text|line|cont|para|next|page|db)\]")
CONTROL_TAG_RE = re.compile(r"\[((?:text|sound)_\w+(?: [^\]]*)?)\]")
TAG_RE = re.compile(rf"{COMMAND_TAG_RE.pattern}|{CONTROL_TAG_RE.pattern}")


def split_comment(line: str) -> Tuple[str, str]:
    """``(code, comment)``: the comment starts at the first ``;`` outside a string."""
    quoted = False
    index = 0
    while index < len(line):
        char = line[index]
        if char == "\\" and quoted:
            index += 2
            continue
        if char == '"':
            quoted = not quoted
        elif char == ";" and not quoted:
            return line[:index], line[index:]
        index += 1
    return line, ""


def escape(content: str) -> str:
    """A typed ``"`` as ``\\"`` (an already escaped one stays)."""
    return re.sub(r'(?<!\\)"', r'\\"', content)


@dataclass
class Token:
    """One line of a message: a string command (``cmd`` + ``content``) or a text command (``raw``)."""

    cmd: str
    content: str = ""
    raw: str = ""

    @property
    def is_string(self) -> bool:
        return not self.raw


@dataclass
class Unit:
    """One editor string of a file."""

    kind: str                       # "text", "db" (messages) or "literal"
    start: int                      # first line
    end: int                        # line after the last one
    tokens: List[Token] = field(default_factory=list)
    prefix: str = "\t"              # what stands before the command on the first line (label, indent)
    comment: str = ""               # comment of the first line
    label: str = ""                 # the label the unit is under
    literal_index: int = 0          # literal units: which string of the line
    hidden_at: bool = False         # db message whose last string ends with the terminator "@"

    @property
    def is_message(self) -> bool:
        return self.kind != LITERAL_KIND


def _classify(rest: str):
    """``(kind, cmd, payload)`` of a line without its label and comment."""
    match = _DIRECTIVE_RE.match(rest)
    if not match:
        return "other", "", None
    cmd, args = match.group(1), match.group(2)
    strings = list(_STRING_RE.finditer(args))
    if cmd in MESSAGE_COMMANDS and len(strings) == 1 and strings[0].span() == (0, len(args)):
        return "string", cmd, args[1:-1]
    if cmd in TERMINATORS:
        return "end", cmd, None
    if cmd.startswith(("text_", "sound_")):
        return "control", cmd, f"{cmd} {args}".strip()
    if cmd in LITERAL_COMMANDS and strings:
        return "literals", cmd, strings
    return "other", cmd, None


def parse(text: str) -> List[Unit]:
    """The units of an asm file, in order."""
    units: List[Unit] = []
    current: Optional[Unit] = None
    label = ""

    def close() -> None:
        nonlocal current
        if current is not None and any(t.is_string for t in current.tokens):
            units.append(current)
        current = None

    for number, line in enumerate(text.split("\n")):
        code, comment = split_comment(line.rstrip("\r"))
        if not code.strip():
            continue
        prefix, rest = "", code
        if code[0] not in " \t":
            close()
            found = _LABEL_RE.match(code)
            if not found:
                continue
            label = found.group(0).rstrip(":")
            prefix, rest = code[:found.end()], code[found.end():]
            if not rest.strip():
                continue
        kind, cmd, payload = _classify(rest)
        if kind in ("string", "control"):
            if current is None:
                indent = rest[:len(rest) - len(rest.lstrip())]
                current = Unit(kind=TEXT_KIND, start=number, end=number + 1, prefix=prefix + indent,
                               comment=comment, label=label)
            token = Token(cmd, payload) if kind == "string" else Token(cmd, raw=payload)
            if token.is_string and not any(t.is_string for t in current.tokens):
                current.kind = DB_KIND if cmd in ("db", "next", "page") else TEXT_KIND
            current.tokens.append(token)
            current.end = number + 1
            if current.kind == DB_KIND and token.is_string and payload.endswith("@"):
                current.hidden_at = True
                close()
            continue
        close()
        if kind == "literals":
            for index, match in enumerate(payload):
                units.append(Unit(kind=LITERAL_KIND, start=number, end=number + 1, label=label,
                                  literal_index=index, tokens=[Token(cmd, match.group(0)[1:-1])]))
    close()
    for unit in units:
        if unit.hidden_at:
            last = [t for t in unit.tokens if t.is_string][-1]
            last.content = last.content[:-1]
    return units


# -- editor text ----------------------------------------------------------------------------------


class _Box:
    """Which command a line break stands for: the state both directions share."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.lines = 1

    def newline(self) -> str:
        if self.kind == DB_KIND:
            return "next"
        return "line" if self.lines == 1 else "cont"

    def take(self, cmd: str) -> None:
        if cmd == _PARAGRAPH[self.kind]:
            self.lines = 1
        elif cmd not in ("text", "db"):
            self.lines += 1


def to_editor(unit: Unit) -> str:
    """The editor text of a unit."""
    if not unit.is_message:
        return unit.tokens[0].content
    box = _Box(unit.kind)
    out: List[str] = []
    after_control = False
    first = True
    for token in unit.tokens:
        if not token.is_string:
            out.append(f"[{token.raw}]")
            after_control, first = True, False
            continue
        cmd, content = token.cmd, token.content
        tag = f"[{cmd}]"
        if first or cmd in ("text", "db"):
            plain = (first or after_control) and cmd == _START[unit.kind] and content != ""
            out.append(("" if plain else tag) + content)
        elif cmd in ("para", "page"):
            plain = cmd == _PARAGRAPH[unit.kind] and content != ""
            out.append("\n\n" + ("" if plain else tag) + content)
        else:
            plain = cmd == box.newline() and content != ""
            out.append("\n" + ("" if plain else tag) + content)
        box.take(cmd)
        after_control, first = False, False
    return "".join(out)


def _line_items(line: str) -> Iterator[Tuple[str, str]]:
    """``("str", text)``, ``("cmd", name)`` and ``("ctl", raw)`` items of one editor line."""
    position = 0
    for match in TAG_RE.finditer(line):
        if match.start() > position:
            yield "str", line[position:match.start()]
        yield ("cmd", match.group(1)) if match.group(1) else ("ctl", match.group(2))
        position = match.end()
    if position < len(line):
        yield "str", line[position:]


def from_editor(text: str, kind: str, hidden_at: bool = False) -> List[Token]:
    """Tokens of an editor text (the inverse of ``to_editor``)."""
    lines = text.replace("\r\n", "\n").split("\n")
    items: List[Tuple[str, str]] = list(_line_items(lines[0]))
    index = 1
    while index < len(lines):
        if lines[index] == "" and index + 1 < len(lines):
            items.append(("para", ""))
            index += 1
        else:
            items.append(("nl", ""))
        items.extend(_line_items(lines[index]))
        index += 1

    tokens: List[Token] = []
    box = _Box(kind)
    pending: Optional[Tuple[str, bool]] = None      # (command of the next string, implied by a line break)

    def emit(cmd: str, content: str) -> None:
        tokens.append(Token(cmd, content))
        box.take(cmd)

    for what, value in items:
        if what in ("nl", "para"):
            if pending is not None:
                emit(pending[0], "")
            pending = (box.newline() if what == "nl" else _PARAGRAPH[kind], True)
        elif what == "cmd":
            if pending is not None and not pending[1]:
                emit(pending[0], "")
            pending = (value, False)
        elif what == "ctl":
            if pending is not None:
                emit(pending[0], "")
                pending = None
            tokens.append(Token(value.split(" ", 1)[0], raw=value))
        else:
            emit(pending[0] if pending is not None else _START[kind], value)
            pending = None
    if pending is not None:
        emit(pending[0], "")
    strings = [t for t in tokens if t.is_string]
    if not strings:
        tokens.insert(0, Token(_START[kind], ""))
        strings = tokens[:1]
    if kind == DB_KIND:
        for token in strings[:-1]:      # an inner "@" would end the message early
            token.content = token.content.rstrip("@")
        if hidden_at:
            strings[-1].content += "@"
    return tokens


def _render(unit: Unit, tokens: Sequence[Token]) -> List[str]:
    """pret-style asm lines of a changed message."""
    lines: List[str] = []
    for index, token in enumerate(tokens):
        lead = unit.prefix if index == 0 else "\t"
        if not token.is_string:
            lines.append(f"{lead}{token.raw}")
            continue
        if token.cmd in ("para", "page") and index:
            lines.append("")
        cmd = token.cmd if unit.kind == TEXT_KIND else token.cmd.ljust(4)
        lines.append(f'{lead}{cmd} "{escape(token.content)}"')
    if unit.comment:
        lines[0] = f"{lines[0]} {unit.comment}"
    return lines


def write(source: str, texts: Sequence[Optional[str]]) -> str:
    """``source`` with the units' editor texts ``texts`` (index by index; a None or missing one stays)."""
    units = parse(source)
    lines = source.split("\n")
    edits: List[Tuple[int, int, List[str]]] = []
    literal_edits: Dict[int, Dict[int, str]] = {}
    for unit, text in zip(units, texts):
        if text is None or str(text) == to_editor(unit):
            continue
        if not unit.is_message:
            literal_edits.setdefault(unit.start, {})[unit.literal_index] = escape(str(text))
            continue
        edits.append((unit.start, unit.end, _render(unit, from_editor(str(text), unit.kind, unit.hidden_at))))
    for number, replacements in literal_edits.items():
        code, comment = split_comment(lines[number])
        count = [-1]

        def swap(match: "re.Match[str]") -> str:
            count[0] += 1
            return f'"{replacements[count[0]]}"' if count[0] in replacements else match.group(0)
        lines[number] = _STRING_RE.sub(swap, code) + comment
    for start, end, new in sorted(edits, reverse=True):
        lines[start:end] = new
    return "\n".join(lines)


def load(text: str) -> List[str]:
    """The editor texts of an asm file."""
    return [to_editor(unit) for unit in parse(text)]
