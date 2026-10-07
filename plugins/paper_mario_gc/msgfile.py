"""Paper Mario: The Thousand-Year Door message files (``msg/<region>/<area>.txt``).

A file is ``key\\0text\\0`` pairs ended by an empty key (one more ``\\0``, then zero padding in Super Paper
Mario, ``padding``); the game sorts the keys itself
when it loads the file, so the order is free. English text is single-byte: ASCII, the font's Latin-1
letters (only the credits use them) and a few symbols the font keeps in Latin-1 slots (``SYMBOLS``).
Control tags are ``<k>``, ``<p>``, ``<wait 250>``, ``<col c00000ff>`` ...; the editor shows them in braces
(``{k}``), and braces never occur in the game's text, so the conversion is exact.

Some entries of the US files are Japanese leftovers stored as UTF-16 (the game never shows them);
``is_leftover`` finds them so the editor can leave them out, and saving writes them back unchanged.
"""
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

# Font slots that draw a symbol instead of their Latin-1 letter (papermarioset_US.bfn, checked by eye)
SYMBOLS = {0xA4: "○", 0xB2: "↑", 0xB3: "↓", 0xD0: "♡", 0xD8: "♪", 0xDE: "☆"}
BY_SYMBOL = {char: code for code, char in SYMBOLS.items()}
RAW_RE = re.compile(r"\{x([0-9A-Fa-f]{2})\}")          # a byte the text cannot show: {x1F}
EDITOR_TAG_RE = re.compile(r"\{[^{}\n]*\}")
_GAME_TAG = re.compile(rb"<[^<>\n]*>")
_JAPANESE_PAIR = re.compile(rb"[\x41-\x9f]0")           # a kana/kanji code unit of UTF-16LE: xx 30


@dataclass
class Entry:
    key: bytes
    text: bytes

    @property
    def name(self) -> str:
        """The key as text (some keys are Japanese NPC names in Shift-JIS)."""
        return self.key.decode("cp932", "replace")


def parse(data: bytes) -> List[Entry]:
    """The entries of a message file; raises ValueError when it is not one."""
    entries, pos = [], 0
    while True:
        end = data.find(b"\0", pos)
        if end < 0:
            raise ValueError("message file without its closing empty key")
        key = data[pos:end]
        pos = end + 1
        if not key:
            break
        end = data.find(b"\0", pos)
        if end < 0:
            raise ValueError(f"message {key!r} has no end")
        entries.append(Entry(key, data[pos:end]))
        pos = end + 1
    if data[pos:].strip(b"\0"):
        raise ValueError(f"{len(data) - pos} bytes after the closing empty key")
    return entries


def build(entries: List[Entry]) -> bytes:
    return b"".join(e.key + b"\0" + e.text + b"\0" for e in entries) + b"\0"


def padding(data: bytes) -> bytes:
    """The zero bytes after the closing empty key (Super Paper Mario ends its files with one more)."""
    return data[len(build(parse(data))):]


def is_leftover(text: bytes) -> bool:
    """A Japanese leftover in UTF-16 (kana code units ``xx 30``, full-width marks ``xx FF``)."""
    plain = _GAME_TAG.sub(b"", text)
    if re.search(rb"[\x80-\xff][0\xff]", plain) or len(_JAPANESE_PAIR.findall(plain)) >= 2:
        return True
    return bool(re.search(rb"[\x00-\x09\x0b-\x1f]", plain)) and not re.search(rb"[A-Za-z]{4}", plain)


def _char(code: int) -> str:
    if code in SYMBOLS:
        return SYMBOLS[code]
    try:
        return bytes([code]).decode("cp1252")
    except UnicodeDecodeError:
        return chr(code)


def decode(text: bytes, reverse_map: Optional[Dict[str, str]] = None) -> str:
    """Game bytes -> editor text: ``<tag>`` -> ``{tag}``, control bytes -> ``{xNN}``, a font slot that
    holds a translated letter -> that letter (``reverse_map``: slot character -> letter)."""
    out, pos = [], 0
    while pos < len(text):
        tag = _GAME_TAG.match(text, pos)
        if tag:
            out.append("{" + tag.group()[1:-1].decode("latin-1") + "}")
            pos = tag.end()
            continue
        code = text[pos]
        pos += 1
        if code == 0x0A:
            out.append("\n")
        elif code < 0x20 or code in (0x7B, 0x7D):
            out.append(f"{{x{code:02X}}}")
        else:
            char = _char(code)
            out.append(reverse_map.get(char, char) if reverse_map else char)
    return "".join(out)


def encode(text: str, translation_map: Optional[Dict[str, str]] = None,
           missing: Optional[Set[str]] = None) -> bytes:
    """Editor text -> game bytes; a letter of ``translation_map`` is written as its font slot. A character
    the font cannot draw becomes ``?`` and is added to ``missing``."""
    out, pos = bytearray(), 0
    text = text.replace("\r\n", "\n")
    while pos < len(text):
        if text[pos] == "{":
            raw = RAW_RE.match(text, pos)
            if raw:
                out.append(int(raw.group(1), 16))
                pos = raw.end()
                continue
            tag = EDITOR_TAG_RE.match(text, pos)
            if tag:
                out += b"<" + tag.group()[1:-1].encode("latin-1", "replace") + b">"
                pos = tag.end()
                continue
        char = text[pos]
        pos += 1
        if translation_map and char in translation_map:
            char = translation_map[char]
        out += _encode_char(char, missing)
    return bytes(out)


def _encode_char(char: str, missing: Optional[Set[str]]) -> bytes:
    if char == "\n" or " " <= char <= "~":
        return char.encode("ascii")
    if char in BY_SYMBOL:
        return bytes([BY_SYMBOL[char]])
    try:
        return char.encode("cp1252")
    except UnicodeEncodeError:
        if len(char) == 1 and 0x80 <= ord(char) <= 0xFF:
            return bytes([ord(char)])
        if missing is not None:
            missing.add(char)
        return b"?"
