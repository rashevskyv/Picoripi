"""Text of the pret generation IV decompilations (pokediamond, pokeplatinum, pokeheartgold): find the English
messages in a source file, show them, write them back in place.

- ``.gmm`` (pokediamond ``files/msgdata/msg/narc_*.gmm``, pokeheartgold ``msg_*.gmm``): XML; the English text of a
  row is ``<language name="English">...</language>``. The game's control codes are written ``\\n`` (next line), ``\\r``
  and ``\\f`` (two characters each) and ``{STRVAR_1 1, 0}``; XML entities (``&amp;``) are the file's own.
- ``.json`` (pokeplatinum ``res/text/*.json``): ``{"key": N, "messages": [{"id": "...", "en_US": "..." | ["..."]}]}``;
  a long message is a list of strings, each ending with a line break.

The editor text shows a line break as a new line; the codes ``\\r`` and ``\\f`` that stand alone are the tags
``{\\r}`` and ``{\\f}``; ``{STRVAR_1 1, 0}`` and the rest of the ``{...}`` codes are tags. Writing replaces only the
messages whose text changed, character range by character range, so every other byte of the file stays.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

GMM = "gmm"
JSON = "json"
_GMM_ROW = re.compile(r'(<language name="English">)(.*?)(</language>)', re.S)
_JSON_VALUE = re.compile(r'"en_US"\s*:\s*')
TAG_RE = re.compile(r"\{\\[rf]\}|\{[A-Z_0-9]+(?: [^{}]*)?\}")
_DECODER = json.JSONDecoder()


@dataclass
class Unit:
    """One message: ``text`` is what the file holds (decoded: control characters, XML entities resolved)."""

    text: str
    span: Tuple[int, int]
    is_list: bool = False
    indent: str = ""


def kind_of(text: str) -> str:
    return GMM if text.lstrip().startswith("<") else JSON


def _xml_unescape(text: str) -> str:
    return text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'") \
        .replace("&amp;", "&")


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse(text: str) -> List[Unit]:
    if kind_of(text) == GMM:
        return [Unit(_xml_unescape(m.group(2)).replace("\\n", "\n"), m.span(2)) for m in _GMM_ROW.finditer(text)]
    units: List[Unit] = []
    for found in _JSON_VALUE.finditer(text):
        try:
            value, end = _DECODER.raw_decode(text, found.end())
        except ValueError:
            continue
        line_start = text.rfind("\n", 0, found.start()) + 1
        indent = re.match(r"[ \t]*", text[line_start:found.start()]).group(0)
        if isinstance(value, list):
            units.append(Unit("".join(str(v) for v in value), (found.end(), end), True, indent))
        elif isinstance(value, str):
            units.append(Unit(value, (found.end(), end), False, indent))
    return units


def to_editor(unit_text: str, kind: str) -> str:
    """The editor text of a message: ``\\r`` and ``\\f`` become tags; the line break stays a line break."""
    if kind == GMM:
        return unit_text.replace("\\r", "{\\r}").replace("\\f", "{\\f}")
    return unit_text.replace("\r", "{\\r}").replace("\x0c", "{\\f}")


def from_editor(text: str, kind: str) -> str:
    plain = text.replace("\r\n", "\n").replace("{\\r}", "\r").replace("{\\f}", "\x0c")
    if kind == GMM:
        return plain.replace("\r", "\\r").replace("\x0c", "\\f").replace("\n", "\\n")
    return plain


def load(text: str) -> List[str]:
    kind = kind_of(text)
    return [to_editor(unit.text, kind) for unit in parse(text)]


def _json_list(value: str, indent: str) -> str:
    parts = re.findall(r"[^\n\r\x0c]*[\n\r\x0c]|[^\n\r\x0c]+", value) or [value]
    inner = indent + "  "
    return "[\n" + ",\n".join(f"{inner}{json.dumps(p, ensure_ascii=False)}" for p in parts) + f"\n{indent}]"


def write(source: str, texts: Sequence[Optional[str]]) -> str:
    """``source`` with the messages' editor texts ``texts`` (index by index; None or missing stays)."""
    kind = kind_of(source)
    units = parse(source)
    edits: List[Tuple[int, int, str]] = []
    for unit, new in zip(units, texts):
        if new is None or str(new) == to_editor(unit.text, kind):
            continue
        value = from_editor(str(new), kind)
        if kind == GMM:
            edits.append((unit.span[0], unit.span[1], _xml_escape(value)))
        elif unit.is_list or "\n" in value.rstrip("\n"):
            edits.append((unit.span[0], unit.span[1], _json_list(value, unit.indent)))
        else:
            edits.append((unit.span[0], unit.span[1], json.dumps(value, ensure_ascii=False)))
    for start, end, rendered in sorted(edits, reverse=True):
        source = source[:start] + rendered + source[end:]
    return source
