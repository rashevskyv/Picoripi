"""Wario Land: Shake It! message text: BMG messages as editable text, and the BMG rebuild.

A message is the BMG text of one INF1 entry. Its characters are kept as they are, and a newline is a newline.
The game's only escape code (type 0xFF, four data bytes) is written as ``{esc:FF:00000100}`` in the text form.
The rebuild starts from the original BMG bytes, so the INF1 attributes, the section order and every message
the translator did not change are written exactly as the game has them.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from plugins.zelda_bmg.bmg_tool import BMGFile

ESCAPE_RE = re.compile(r"\{esc:([0-9A-Fa-f]{2}):((?:[0-9A-Fa-f]{2})*)\}")
ESCAPE_OPEN = "{esc:"


def parts_to_text(parts: List[object]) -> str:
    """The text form of a message's parts: strings as they are, escape codes as ``{esc:TT:HEX}``."""
    out = []
    for part in parts:
        if isinstance(part, str):
            out.append(part)
        else:
            data = part.get("data", "")
            hex_data = data.hex() if isinstance(data, (bytes, bytearray)) else str(data)
            out.append("{esc:%02X:%s}" % (int(part["escape_type"]), hex_data.upper()))
    return "".join(out)


def text_to_parts(text: str) -> List[object]:
    """Parts of a message from its text form. A ``{esc:`` that is not a valid escape code is refused."""
    parts: List[object] = []
    pos = 0
    for match in ESCAPE_RE.finditer(text):
        if match.start() > pos:
            parts.append(text[pos:match.start()])
        parts.append({"type": "escape", "escape_type": int(match.group(1), 16),
                      "data": match.group(2).lower()})  # the tool keeps escape data as lowercase hex
        pos = match.end()
    if ESCAPE_OPEN in text[pos:]:
        raise ValueError("an escape code is not closed or has a wrong form: %r" % text[pos:pos + 24])
    if pos < len(text):
        parts.append(text[pos:])
    return parts


def read_messages(bmg_bytes: bytes) -> List[Dict[str, str]]:
    """``[{"info": hex, "text": str}]`` of every message of a BMG file, in file order."""
    bmg = BMGFile()
    bmg.load(bmg_bytes)
    return [{"info": bytes(message.info).hex(), "text": parts_to_text(message.parts)}
            for message in bmg.messages]


def rebuild(original: bytes, texts: List[Optional[str]]) -> bytes:
    """The BMG file of ``original`` with each message's text replaced; ``None`` keeps the original text.

    The message count must match the original file. Raises ``ValueError`` for a text that cannot be written.
    """
    bmg = BMGFile()
    bmg.load(original)
    if len(texts) != len(bmg.messages):
        raise ValueError("the translation has %d messages, the game file has %d" % (len(texts), len(bmg.messages)))
    for message, text in zip(bmg.messages, texts):
        if text is None:
            continue
        message.parts = text_to_parts(text)
    return bmg.save()
