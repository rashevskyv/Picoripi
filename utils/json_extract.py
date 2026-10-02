"""Pull the JSON value out of a model reply.

Models wrap JSON in code fences, talk before and after it, leave trailing
commas, use curly quotes, put raw newlines inside strings and run out of output
mid-array. ``extract_json`` copes with all of that, and when it cannot it raises
``ParseError`` -- it never hands back ``[]`` or ``""`` for a reply it could not
read, because an empty result is indistinguishable from "the model found
nothing" and the unit would be counted as done.
"""
from __future__ import annotations

import json
import re
from typing import Any, List, Tuple

# BOM and zero-width characters models and proxies leave around the payload.
_JUNK = "﻿​‌‍⁠"
_SMART_QUOTES = {"“": '"', "”": '"', "„": '"', "‟": '"'}
_OPEN_RE = re.compile(r"[\[{]")
# How many unbalanced openers in the prose before a structure are tolerated.
_MAX_RESTARTS = 50
_FAILED = object()


class ParseError(json.JSONDecodeError):
    """The reply holds no JSON value of the expected type.

    A ``JSONDecodeError`` so every existing ``except json.JSONDecodeError``
    already treats it as what it is.
    """

    kind = "parse"

    def __init__(self, message: str, raw_text: str = "") -> None:
        super().__init__(message, raw_text or "", 0)
        self.raw_text = raw_text or ""

    def __str__(self) -> str:
        return self.msg


def _loads(text: str) -> Any:
    try:
        # strict=False accepts raw newlines and tabs inside strings.
        return json.loads(text, strict=False)
    except (ValueError, RecursionError):
        return _FAILED


def _matches(value: Any, expect: str) -> bool:
    if expect == "object":
        return isinstance(value, dict)
    if expect == "array":
        return isinstance(value, list)
    return isinstance(value, (dict, list))


def _scan(text: str, start: int) -> Tuple[int, List[str], bool]:
    """Walk the structure opening at ``text[start]``.

    Returns ``(end, open_brackets, in_string)``. ``open_brackets`` is empty when
    the structure closed at ``end``; otherwise the text ran out first.
    """
    stack: List[str] = []
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c in "{[":
            stack.append(c)
        elif c in "}]":
            if stack:
                stack.pop()
            if not stack:
                return i + 1, [], False
    return len(text), stack, in_string


def _repair(text: str) -> str:
    """Fix what models get wrong outside strings: trailing commas, curly quotes, zero-width junk."""
    out: List[str] = []
    in_string = False
    curly = False  # the current string was opened with a curly quote
    escape = False
    n = len(text)
    for i, c in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif curly and c in _SMART_QUOTES:
                in_string = False
                c = '"'
            elif c == '"' and not curly:
                in_string = False
            out.append(c)
            continue
        if c in _JUNK:
            continue
        if c in _SMART_QUOTES:
            in_string = curly = True
            c = '"'
        elif c == '"':
            in_string, curly = True, False
        elif c == ",":
            j = i + 1
            while j < n and (text[j].isspace() or text[j] in _JUNK):
                j += 1
            if j < n and text[j] in "}]":
                continue
        out.append(c)
    return "".join(out)


def _last_comma(text: str) -> int:
    """Index of the last comma outside a string, or -1."""
    last = -1
    in_string = False
    escape = False
    for i, c in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
        elif c == ",":
            last = i
    return last


def _close_truncated(fragment: str) -> Any:
    """Close a structure the model did not finish, dropping the incomplete tail item."""
    for _ in range(4):
        _, stack, in_string = _scan(fragment, 0)
        tail = fragment[:-1] if in_string and fragment.endswith("\\") else fragment
        closers = "".join("}" if c == "{" else "]" for c in reversed(stack))
        value = _loads(_repair(tail + ('"' if in_string else "") + closers))
        if value is not _FAILED:
            return value
        cut = _last_comma(fragment)
        if cut <= 0:
            break
        fragment = fragment[:cut]
    return _FAILED


def _extract(text: Any, expect: str) -> Tuple[Any, List[str], str]:
    raw = text if isinstance(text, str) else str(text or "")
    cleaned = raw.strip().strip(_JUNK).strip()
    if not cleaned:
        raise ParseError("AI response is empty.", raw)

    value = _loads(cleaned)
    if value is not _FAILED and _matches(value, expect):
        return value, [], cleaned

    pos = 0
    restarts = 0
    while True:
        match = _OPEN_RE.search(cleaned, pos)
        if match is None:
            break
        start = match.start()
        end, stack, in_string = _scan(cleaned, start)
        if stack or in_string:
            # Either the reply was cut off here, or this is a stray bracket in
            # the prose. Everything after an unclosed bracket sits inside it, so
            # try the cut-off reading first: taking a complete inner value
            # instead would return one item of a list as if it were the reply.
            value = _close_truncated(cleaned[start:])
            if value is not _FAILED and _matches(value, expect):
                return value, ["truncated"], cleaned[start:]
            restarts += 1
            if restarts > _MAX_RESTARTS:
                break
            pos = start + 1
            continue
        candidate = cleaned[start:end]
        value = _loads(candidate)
        if value is not _FAILED and _matches(value, expect):
            return value, [], candidate
        value = _loads(_repair(candidate))
        if value is not _FAILED and _matches(value, expect):
            return value, ["repaired"], candidate
        # Not what was asked for: skip it whole rather than dig a fragment out.
        pos = end

    wanted = {"object": "a JSON object", "array": "a JSON array"}.get(expect, "JSON")
    raise ParseError(f"AI response does not contain {wanted}.", raw)


def extract_json(text: Any, expect: str = "any") -> Tuple[Any, List[str]]:
    """Return ``(value, notes)`` for the first JSON value of type ``expect`` in ``text``.

    ``expect`` is ``"object"``, ``"array"`` or ``"any"``. ``notes`` lists what had
    to be done to read it: ``"repaired"`` (trailing commas, curly quotes) or
    ``"truncated"`` (the reply ended mid-structure; the incomplete tail item was
    dropped). A caller that needs every item must refuse a truncated value.

    Raises ``ParseError`` when there is nothing to read.
    """
    value, notes, _ = _extract(text, expect)
    return value, notes


def extract_json_text(text: Any, expect: str = "any") -> str:
    """The JSON in ``text`` as a string ``json.loads`` accepts.

    For code that passes cleaned text on instead of a value. The model's own
    text is kept when it is already valid; otherwise the value is re-serialised.
    A truncated reply raises ``ParseError``: the caller will index into the
    result and must not get a silently shorter one.
    """
    value, notes, source = _extract(text, expect)
    if "truncated" in notes:
        raise ParseError("AI response was cut off before the JSON ended.", str(text or ""))
    try:
        json.loads(source)
        return source
    except ValueError:
        return json.dumps(value, ensure_ascii=False)
