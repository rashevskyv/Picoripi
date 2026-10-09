"""Text codec of Castlevania: Symphony of the Night (Saturn, Dracula X Ultimate): the two string encodings.

``a`` ASCII strings (end 0x00): byte 0x01 is a new line, 0x20-0x7E are the characters.
``c`` the game's own minus-0x20 strings (end 0xFF) and ``n`` cutscene speaker names (fixed glyph count):
byte ``b`` < 0x5F is the character ``b + 0x20`` (0x00 a space), 0x0A a new line.
Any other byte is the tag ``[xNN]``.
"""
import re
from typing import List, Tuple

TAG_RE = re.compile(r"\[x[0-9A-F]{2}\]")
_TOKEN = re.compile(r"\[x[0-9A-F]{2}\]|.", re.S)


def decode(kind: str, raw: bytes) -> str:
    out = []
    for b in raw:
        if kind == "a":
            out.append("\n" if b == 1 else chr(b) if 0x20 <= b < 0x7F else f"[x{b:02X}]")
        else:
            out.append("\n" if b == 0x0A else chr(b + 0x20) if b < 0x5F else f"[x{b:02X}]")
    return "".join(out)


def encode(kind: str, text: str) -> Tuple[bytes, List[str]]:
    """The bytes of ``text``; characters the game cannot write become '?' and are returned."""
    out, unknown = bytearray(), []
    for token in _TOKEN.findall(text.replace("\r\n", "\n")):
        if len(token) == 5 and TAG_RE.fullmatch(token):
            out.append(int(token[2:4], 16))
        elif token == "\n":
            out.append(1 if kind == "a" else 0x0A)
        elif 0x20 <= ord(token) < 0x7F and (kind == "a" or ord(token) - 0x20 < 0x5F):
            out.append(ord(token) if kind == "a" else ord(token) - 0x20)
        else:
            unknown.append(token)
            out.append(ord("?") if kind == "a" else ord("?") - 0x20)
    return bytes(out), unknown


def describe(tag: str) -> str:
    if TAG_RE.fullmatch(tag):
        return f"Byte 0x{tag[2:4]} the font has no letter for (a special glyph or a control code)"
    return ""
