"""Text of a pret generation III decompilation (pokeruby, pokefirered, pokeemerald): find it in a source file,
show it, write it back.

A *unit* is one message of the editor:

- in an assembly file (``.inc``, ``.s``): the consecutive ``.string "..."`` (or ``.braille "..."``) lines of one
  label, up to the line whose text ends with the terminator ``$`` (or the first line that is not such a line);
- in a C file (``.c``, ``.h``): the string literals inside one ``_("...")`` (adjacent literals are one message);
- in a JSON file the game's tools build from (``map_sections`` of the region map, ``items`` of FireRed): the string
  value of a ``name`` / ``english`` / ``description_english`` key, one message per value.

The editor text is the message as the game's other tools show it (the plugin's JSON files): the literals joined,
with the control escapes ``\\n`` (next line), ``\\l`` (scroll a line), ``\\p`` (next box) and the ``{...}`` codes as
they are, without the terminating ``$`` (it is not shown and is always written back). A typed ``"`` is escaped on
save. Writing never moves a unit: a message that is unchanged keeps its lines byte for byte, a changed one is
written again in pret style (one ``.string`` per line break) in the same place.
"""
from __future__ import annotations

import bisect
import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

_STRING_LINE = re.compile(r'^(?P<prefix>[ \t]*(?:[A-Za-z_][\w.@$]*:{1,2}[ \t]*)?)\.(?P<directive>string|braille)[ \t]+"'
                          r'(?P<body>(?:[^"\\]|\\.)*)"(?P<rest>(?:[ \t]*,[ \t]*[^,@"\n]*)?[ \t]*(?:@.*)?)$')
_ASM_DIRECTIVE = re.compile(r'^[ \t]*(?:[A-Za-z_][\w.@$]*:{1,2}[ \t]*)?\.(?:string|braille)[ \t]', re.M)
_LITERAL = re.compile(r'"(?:[^"\\\n]|\\.)*"')
_C_CALL = re.compile(r'(?<![\w])_\(\s*(?P<lits>"(?:[^"\\\n]|\\.)*"(?:\s*"(?:[^"\\\n]|\\.)*")*)\s*\)')
_ASSIGNED = re.compile(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*=\s*\(?\s*$")
_BREAK = re.compile(r'\\[nlp]')
_JSON_TEXT = re.compile(r'"(?P<key>name|english|description_english)"[ \t]*:[ \t]*"(?P<body>(?:[^"\\]|\\.)*)"')
ASM_SUFFIXES = (".inc", ".s")
C_SUFFIXES = (".c", ".h")
JSON_SUFFIXES = (".json",)
SUFFIXES = ASM_SUFFIXES + C_SUFFIXES + JSON_SUFFIXES
# The top-level keys of the JSON files the game builds its text from (tools/jsonproc templates in the decompilation).
PRET_JSON_ROOTS = ("map_sections", "items")


@dataclass
class Unit:
    """One message: ``content`` without the ``$``; ``span`` is the character range of the source it occupies."""

    kind: str                     # "asm", "c" or "json"
    content: str
    hidden_end: bool
    span: Tuple[int, int]
    label: str = ""
    first_line: int = 0           # 0-based line of the first line of the unit
    indent: str = "\t"            # asm: the whitespace before the directive; c: indent of the second literal
    prefix: str = ""              # asm: what stands before the directive on the first line (label, spaces)
    comment: str = ""             # asm: what follows the first line's string: ``, 13`` and/or ``@ ...``, as written
    literals: int = 1             # c: how many literals the call had
    directive: str = "string"     # asm: ``string`` or ``braille``


def escape(content: str) -> str:
    """A typed ``"`` as ``\\"`` (an already escaped one stays)."""
    return re.sub(r'(?<!\\)"', r'\\"', content)


def _split_end(joined: str) -> Tuple[str, bool]:
    if joined.endswith("$") and not joined.endswith("\\$"):
        return joined[:-1], True
    return joined, False


def is_asm(path: str) -> bool:
    return str(path).lower().endswith(ASM_SUFFIXES)


def parse(text: str, asm: bool) -> List[Unit]:
    """The units of a source file, in order."""
    return _parse_asm(text) if asm else _parse_c(text)


def _parse_asm(text: str) -> List[Unit]:
    units: List[Unit] = []
    offset = 0
    label = ""
    current: Optional[dict] = None

    def close() -> None:
        nonlocal current
        if current is not None:
            content, hidden = _split_end("".join(current["bodies"]))
            units.append(Unit("asm", content, hidden, (current["start"], current["end"]), current["label"],
                              current["line"], current["indent"], current["prefix"], current["comment"],
                              directive=current["directive"]))
        current = None

    for number, raw in enumerate(text.split("\n")):
        line = raw.rstrip("\r")
        end = offset + len(raw) + 1
        found = _STRING_LINE.match(line)
        if found is None:
            close()
            name = re.match(r"^([A-Za-z_][\w.@$]*):{1,2}", line)
            if name:
                label = name.group(1)
            offset = end
            continue
        prefix, body, rest = found.group("prefix"), found.group("body"), found.group("rest")
        if current is not None and current["directive"] != found.group("directive"):
            close()                       # a .string run and a .braille run are two messages
        if current is None:
            name = re.match(r"^[ \t]*([A-Za-z_][\w.@$]*):{1,2}", prefix)
            if name:
                label = name.group(1)
            current = {"bodies": [], "start": offset, "end": end, "label": label, "line": number,
                       "prefix": prefix, "comment": rest, "directive": found.group("directive"),
                       "indent": re.match(r"[ \t]*", prefix.split(":")[-1]
                                          if ":" in prefix else prefix).group(0)}
        else:
            current["end"] = end
        current["bodies"].append(body)
        if body.endswith("$") and not body.endswith("\\$"):
            close()
        offset = end
    close()
    return units


def _parse_c(text: str) -> List[Unit]:
    units: List[Unit] = []
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]
    for found in _C_CALL.finditer(text):
        lits = _LITERAL.findall(found.group("lits"))
        content, hidden = _split_end("".join(lit[1:-1] for lit in lits))
        first_line = bisect.bisect_left(newlines, found.start())
        line_start = newlines[first_line - 1] + 1 if first_line else 0
        if len(lits) > 1:
            second = text.find(lits[1], found.start("lits") + len(lits[0]))
            second_start = text.rfind("\n", 0, second) + 1
            indent = text[second_start:second] if text[second_start:second].strip() == "" else "    "
        else:
            indent = re.match(r"[ \t]*", text[line_start:found.start()]).group(0)
        # the identifier the call is assigned to (``static const u8 sName[] = _(...)``, ``.name = _(...)``)
        head = text[max(0, found.start() - 160):found.start()]
        names = _ASSIGNED.findall(head)
        units.append(Unit("c", content, hidden, (found.start("lits"), found.end("lits")), names[-1] if names else "",
                          first_line, indent, literals=len(lits)))
    return units


def load(text: str, asm: bool) -> List[str]:
    """The editor texts of a source file."""
    return [unit.content for unit in parse(text, asm)]


def is_asm_text(text: str) -> bool:
    """An assembly file: a ``.string`` or ``.braille`` line starts it."""
    return _ASM_DIRECTIVE.search(text) is not None


def is_pret_json(text: str) -> bool:
    """A JSON file the game builds its text from: one of PRET_JSON_ROOTS at the top."""
    if not text.lstrip().startswith("{"):
        return False
    try:
        data = json.loads(text)
    except ValueError:
        return False
    return isinstance(data, dict) and any(root in data for root in PRET_JSON_ROOTS)


def _parse_json(text: str) -> List[Unit]:
    units = []
    for found in _JSON_TEXT.finditer(text):
        start, end = found.span("body")
        content = json.loads('"' + found.group("body") + '"')    # the JSON escapes give the C text's escapes
        units.append(Unit("json", content, False, (start, end), found.group("key"), text.count("\n", 0, start)))
    return units


def parse_file(text: str, rel: str) -> List[Unit]:
    """The units of a source file: JSON by its name, assembly or C by its text."""
    if str(rel).lower().endswith(JSON_SUFFIXES):
        return _parse_json(text)
    return parse(text, is_asm(rel))


def load_json(text: str) -> List[str]:
    """The editor texts of a pret JSON file."""
    return [unit.content for unit in _parse_json(text)]


def write_json(text: str, texts: Sequence[Optional[str]]) -> str:
    """``text`` (a pret JSON file) with the units' texts; an unchanged unit keeps its bytes."""
    edits: List[Tuple[int, int, str]] = []
    for unit, new in zip(_parse_json(text), texts):
        if new is None or str(new) == unit.content:
            continue
        edits.append((unit.span[0], unit.span[1], json.dumps(str(new), ensure_ascii=False)[1:-1]))
    for start, end, rendered in sorted(edits, reverse=True):
        text = text[:start] + rendered + text[end:]
    return text


def _segments(content: str) -> List[str]:
    """``content`` cut after every ``\\n``, ``\\l`` and ``\\p``."""
    out, last = [], 0
    for found in _BREAK.finditer(content):
        out.append(content[last:found.end()])
        last = found.end()
    if last < len(content) or not out:
        out.append(content[last:])
    return out


def _render_asm(unit: Unit, content: str) -> str:
    segments = _segments(escape(content))
    if unit.hidden_end:
        segments[-1] += "$"
    lines = []
    for index, segment in enumerate(segments):
        lead = unit.prefix if index == 0 else unit.indent
        lines.append(f'{lead}.{unit.directive} "{segment}"' + (unit.comment if index == 0 else ""))
    return "\n".join(lines) + "\n"


def _render_c(unit: Unit, content: str) -> str:
    body = escape(content) + ("$" if unit.hidden_end else "")
    if unit.literals <= 1:
        return f'"{body}"'
    return ("\n" + unit.indent).join(f'"{segment}"' for segment in _segments(body))


def write(text: str, asm: bool, texts: Sequence[Optional[str]]) -> str:
    """``text`` with the units' editor texts ``texts`` (index by index; a None or missing one stays)."""
    units = parse(text, asm)
    edits: List[Tuple[int, int, str]] = []
    for unit, new in zip(units, texts):
        if new is None or str(new) == unit.content:
            continue
        rendered = _render_asm(unit, str(new)) if asm else _render_c(unit, str(new))
        edits.append((unit.span[0], unit.span[1], rendered))
    for start, end, rendered in sorted(edits, reverse=True):
        text = text[:start] + rendered + text[end:]
    return text


TAG_RE = re.compile(r"\{[A-Za-z_0-9 ]+\}")
CONTEXT_REFERENCE = re.compile(r"[A-Za-z_]\w*")


def references(text: str, labels: Optional[Sequence[str]] = None) -> Dict[str, List[str]]:
    """``{text label: [labels of the scripts that name it]}`` for the assembly ``text``: a script is the lines
    from its global label to the next one. ``labels`` are the text labels to look for (default: the ones of
    ``text``; a map's texts may live in ``text.inc`` while its scripts live in ``scripts.inc``)."""
    wanted = set(labels) if labels is not None else {unit.label for unit in _parse_asm(text) if unit.label}
    out: Dict[str, List[str]] = {}
    script = ""
    for line in text.split("\n"):
        name = re.match(r"^([A-Za-z_][\w.@$]*):{1,2}", line)
        if name:
            script = name.group(1)
            continue
        if not script or line.lstrip().startswith(("@", ".string")):
            continue
        for word in CONTEXT_REFERENCE.findall(line):
            if word in wanted and word != script:
                out.setdefault(word, [])
                if script not in out[word]:
                    out[word].append(script)
    return out
