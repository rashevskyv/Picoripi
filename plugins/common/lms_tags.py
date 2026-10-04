"""Readable ``{tags}`` for MSBT control tags, driven by a game's tag catalogue (TotK, Skyward Sword).

A plugin gives a catalogue ``{(group, type): (name, argument types, description)}`` and value names
``{(name, argument index): {value: label}}``; ``TagCodec`` turns tokens into editor text and back:
  ``{name}`` / ``{name:arg:arg}``  a known tag whose bytes it reproduces exactly
  ``{tag:G:T}`` / ``{tag:G:T:hex}``  any other tag, raw
  ``{/name}`` / ``{/tag:G:T}``     a closing tag
A tag is only shown by name when its readable form encodes back to the same bytes, so a file always
round-trips. Arguments with an odd byte length are padded with 0xCD, as Nintendo's files are.
Argument types: u8, s8, bool, u16, s16, u32, f32, str (u16 byte length + UTF-16).
"""
from __future__ import annotations

import re
import struct
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from plugins.common.msbt import EndTag, Tag, Token

PAD = 0xCD
TAG_RE = re.compile(r"\{/?[A-Za-z][A-Za-z0-9_]*(?::[^{}:]*)*\}")
_TAG_PARTS_RE = re.compile(r"\{(/?)([A-Za-z][A-Za-z0-9_]*)((?::[^{}:]*)*)\}")
_INT_FORMATS = {"u8": "B", "s8": "b", "bool": "B", "u16": "H", "s16": "h", "u32": "I", "f32": "f"}

Catalogue = Dict[Tuple[int, int], Tuple[str, Tuple[str, ...], str]]


def float_text(value: float) -> str:
    """The shortest text that reads back as the same 32-bit float (``0.6``, not ``0.6000000238418579``)."""
    packed = struct.pack("<f", value)
    for digits in range(1, 10):
        text = f"{value:.{digits}g}"
        if struct.pack("<f", float(text)) == packed:
            return text
    return repr(value)


def _decode_args(types: Tuple[str, ...], params: bytes, e: str) -> Optional[List]:
    values, position = [], 0
    try:
        for kind in types:
            if kind == "str":
                length = struct.unpack_from(e + "H", params, position)[0]
                position += 2
                chunk = params[position:position + length]
                if len(chunk) != length:
                    return None
                values.append(chunk.decode("utf-16-le" if e == "<" else "utf-16-be"))
                position += length
            else:
                fmt = _INT_FORMATS[kind]
                values.append(struct.unpack_from(e + fmt, params, position)[0])
                position += struct.calcsize(fmt)
    except (struct.error, UnicodeDecodeError):
        return None
    rest = params[position:]
    if rest and not (len(rest) == 1 and rest[0] == PAD):
        return None
    return values


def _encode_args(types: Tuple[str, ...], values: List, e: str) -> bytes:
    out = bytearray()
    for kind, value in zip(types, values):
        if kind == "str":
            data = value.encode("utf-16-le" if e == "<" else "utf-16-be")
            out += struct.pack(e + "H", len(data)) + data
        else:
            out += struct.pack(e + _INT_FORMATS[kind], value)
    if len(out) % 2:
        out.append(PAD)
    return bytes(out)


class TagCodec:
    """Editor text <-> MSBT tokens for one game's catalogue."""

    def __init__(self, tags: Catalogue, value_names: Optional[Dict[Tuple[str, int], Dict[int, str]]] = None):
        self.tags = tags
        self.value_names = value_names or {}
        self.by_name = {name: key for key, (name, _types, _description) in tags.items()}
        self.render_tag = lru_cache(maxsize=8192)(self._render_tag)

    def _readable(self, tag: Tag, e: str) -> Optional[str]:
        known = self.tags.get((tag.group, tag.type))
        if known is None:
            return None
        name, types, _description = known
        values = _decode_args(types, tag.params, e)
        if values is None:
            return None
        shown = []
        for index, value in enumerate(values):
            names = self.value_names.get((name, index))
            if isinstance(value, float):
                shown.append(float_text(value))
            else:
                shown.append(names.get(value, str(value)) if names and isinstance(value, int) else str(value))
        text = "{" + ":".join([name, *shown]) + "}"
        try:
            if self.parse_tag(text, e) != tag:
                return None
        except ValueError:
            return None
        return text

    def _render_tag(self, token, little: bool = True) -> str:
        """The editor form of one ``Tag`` / ``EndTag`` (cached: a game has a few thousand distinct tags)."""
        e = "<" if little else ">"
        if isinstance(token, EndTag):
            known = self.tags.get((token.group, token.type))
            return f"{{/{known[0]}}}" if known else f"{{/tag:{token.group}:{token.type}}}"
        readable = self._readable(token, e)
        if readable:
            return readable
        raw = f"{{tag:{token.group}:{token.type}"
        return raw + (f":{token.params.hex()}}}" if token.params else "}")

    def parse_tag(self, text: str, e: str = "<"):
        """The ``Tag`` / ``EndTag`` an editor tag stands for. ``ValueError`` when it is not one."""
        match = _TAG_PARTS_RE.fullmatch(text)
        if not match:
            raise ValueError(f"Not a tag: {text}")
        closing, name, rest = match.group(1), match.group(2), match.group(3)
        args = rest.split(":")[1:] if rest else []
        try:
            if name == "tag":
                group, kind = int(args[0]), int(args[1])
                if closing:
                    return EndTag(group, kind)
                return Tag(group, kind, bytes.fromhex(args[2]) if len(args) > 2 else b"")
        except (IndexError, ValueError) as error:
            raise ValueError(f"Bad raw tag {text}: {error}") from error
        key = self.by_name.get(name)
        if key is None:
            raise ValueError(f"Unknown tag {text}")
        if closing:
            return EndTag(*key)
        types = self.tags[key][1]
        if len(args) != len(types):
            raise ValueError(f"{text}: {name} takes {len(types)} argument(s)")
        values = []
        for index, (kind, arg) in enumerate(zip(types, args)):
            if kind == "str":
                values.append(arg)
                continue
            names = {label: value for value, label in self.value_names.get((name, index), {}).items()}
            try:
                values.append(float(arg) if kind == "f32" else names[arg] if arg in names else int(arg))
            except ValueError as error:
                raise ValueError(f"{text}: argument {index + 1} must be a number") from error
        try:
            return Tag(key[0], key[1], _encode_args(types, values, e))
        except struct.error as error:
            raise ValueError(f"{text}: {error}") from error

    def to_editor(self, tokens: List[Token], little: bool = True) -> str:
        """A message as editor text."""
        return "".join(token if isinstance(token, str) else self.render_tag(token, little) for token in tokens)

    def from_editor(self, text: str, little: bool = True) -> List[Token]:
        """Editor text back to tokens. ``{...}`` that is not a tag stays text."""
        e = "<" if little else ">"
        tokens: List[Token] = []
        position = 0
        for match in TAG_RE.finditer(text):
            try:
                tag = self.parse_tag(match.group(0), e)
            except ValueError:
                continue
            if match.start() > position:
                tokens.append(text[position:match.start()])
            tokens.append(tag)
            position = match.end()
        if position < len(text):
            tokens.append(text[position:])
        return tokens

    def describe(self, text: str) -> str:
        """Tooltip for an editor tag."""
        match = _TAG_PARTS_RE.fullmatch(text or "")
        if not match:
            return ""
        if match.group(2) == "tag":
            return "Raw MSBT control tag (group:type:parameter bytes)"
        key = self.by_name.get(match.group(2))
        return f"{self.tags[key][2]} (MSBT tag {key[0]}:{key[1]})" if key else ""
