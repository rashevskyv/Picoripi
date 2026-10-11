"""Castlevania: Lords of Shadow - Mirror of Fate (3DS): the game's localization text files.

``system/localization/english.txt`` (and the six other languages) is a CRLF text file with one message a line:
``KEY##text`` or ``KEY#Speaker#text``. In the text ``|`` is a line break (``||`` a blank line) and ``@[NAME]`` a
button icon or a variable (``@[A]``, ``@[D-UP]``, ``@[$XP1]``). The bytes are Windows-1252 (one byte a character,
the font ``system/fonts/*.bfont`` is indexed by the byte). Bytes that Windows-1252 leaves undefined (0x81, 0x8D,
0x8F, 0x90, 0x9D) are kept as the control characters U+0081.. so every file round-trips.

The editor form of a text: ``|`` is a line break and ``@[NAME]`` is shown as ``{NAME}``. A project may have a
``translation_map.json`` (``{"Є": "Æ"}``): a letter the font has no byte for is written as the byte of the
character it is mapped to and shown back as the letter.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

CRLF = "\r\n"
TAG_RE = re.compile(r"\{[^{}\r\n]+\}")
_AT_TAG = re.compile(r"@\[([^\]\r\n]*)\]")
_CURLY_TAG = re.compile(r"\{([^{}\r\n]+)\}")
_UNDEFINED = {0x81, 0x8D, 0x8F, 0x90, 0x9D}


def decode(raw: bytes) -> str:
    """Windows-1252, undefined bytes as U+0081.. (reversible)."""
    return "".join(chr(b) if b in _UNDEFINED else bytes([b]).decode("cp1252") for b in raw)


def encode_char(char: str) -> Optional[bytes]:
    if 0x80 <= ord(char) <= 0x9F and ord(char) in _UNDEFINED:
        return bytes([ord(char)])
    try:
        return char.encode("cp1252")
    except UnicodeEncodeError:
        return None


def to_editor(value: str, reverse_map: Optional[Dict[str, str]] = None) -> str:
    text = _AT_TAG.sub(lambda m: "{" + m.group(1) + "}", value).replace("|", "\n")
    if reverse_map:
        text = "".join(reverse_map.get(ch, ch) for ch in text)
    return text


def from_editor(text: str, translation_map: Optional[Dict[str, str]] = None) -> str:
    if translation_map:
        text = "".join(translation_map.get(ch, ch) for ch in text)
    return _CURLY_TAG.sub(lambda m: "@[" + m.group(1) + "]", text.replace("\r\n", "\n").replace("\n", "|"))


def encode(text: str, missing: Optional[Set[str]] = None) -> bytes:
    """The file bytes of a text; a character with no byte is written as ``?`` and added to ``missing``."""
    out = bytearray()
    for char in text:
        data = encode_char(char)
        if data is None:
            data = b"?"
            if missing is not None:
                missing.add(char)
        out += data
    return bytes(out)


class MofText:
    """One localization file: ``entries`` is ``[(key, speaker, value)]`` and ``raw`` lines that are not messages."""

    def __init__(self, raw: bytes):
        text = decode(raw)
        self.final_newline = text.endswith(CRLF)
        if self.final_newline:
            text = text[:-len(CRLF)]
        self.lines: List[Tuple[str, Optional[str], str, Optional[str]]] = []   # (key, speaker, value, raw)
        for line in text.split(CRLF) if text else []:
            parts = line.split("#", 2)
            if len(parts) == 3 and parts[0]:
                self.lines.append((parts[0], parts[1], parts[2], None))
            else:
                self.lines.append(("", None, "", line))

    @property
    def messages(self) -> List[Tuple[str, str, str]]:
        return [(key, speaker or "", value) for key, speaker, value, raw in self.lines if raw is None]

    def build(self, values: List[str]) -> str:
        """The file text with the message values replaced (in message order; a short list keeps the rest)."""
        out, index = [], 0
        for key, speaker, value, raw in self.lines:
            if raw is not None:
                out.append(raw)
                continue
            new = values[index] if index < len(values) else value
            index += 1
            out.append(f"{key}#{speaker}#{new}")
        return CRLF.join(out) + (CRLF if self.final_newline else "")


def build_bytes(source: bytes, values: List[str], missing: Optional[Set[str]] = None) -> bytes:
    return encode(MofText(source).build(values), missing)
