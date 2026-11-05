"""The text of Lunar SSS Remastered: the Japanese source, the English reference and the Ukrainian translation.

The source of a project is the Japanese ``FIL/TEXTnnn.DAT`` (raw glyph bytes, ``jp_codec``). Its strings are numbered in
file order (every message and every choice answer); that number is the string's ID inside the file.

The English ``FIL_us/TEXTnnn.DAT`` is the file the game shows for English. Its bytecode runs the same instructions as the
Japanese one. ``pairing`` aligns the two by skeleton, so a Japanese string and an English string can share an ID.

A translation file is not a TEXT file: it keeps the translated strings as UTF-8 (``TRANSLATION_MAGIC`` + JSON), so no
character is lost. The build writes the English file again: each translated string goes into its English slot (through
the English encoder of ``plugins/lunar_sssc``). An English slot with no translated string keeps its English text.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Set, Tuple

from plugins.lunar_sssc import codec, doc as english_doc, pairing, script
from plugins.lunar_sssc import jp_codec

TRANSLATION_MAGIC = b"PICORIPI LUNAR SSS TRANSLATION 1\n"


def _texts(data: bytes) -> List[script.Text]:
    return script.parse(data)


def _starts(texts: List[script.Text]) -> List[int]:
    """The first string number of each text."""
    first, out = 0, []
    for text in texts:
        out.append(first)
        first += len(text.strings)
    return out


def _decode(data: bytes, text: script.Text, start: int, end: int, glyphs: Optional[Dict[int, str]]) -> str:
    if glyphs is None:
        return codec.decode_message(data, start, end) if text.kind == script.MESSAGE else codec.decode(data, start, end)
    return (jp_codec.decode_message(data, start, end) if text.kind == script.MESSAGE
            else codec.decode(data, start, end, glyphs=glyphs))


def strings_of(data: bytes, japanese: bool) -> List[str]:
    """Every string of the file in order: Japanese when ``japanese``, else English."""
    glyphs = jp_codec.GLYPHS if japanese else None
    out: List[str] = []
    for text in _texts(data):
        for start, end in text.strings:
            out.append(_decode(data, text, start, end, glyphs))
    return out


def string_pairs(english: bytes, japanese: bytes) -> List[Tuple[int, int]]:
    """``(English string number, Japanese string number)`` of every string that pairs.

    The alignment works on texts (a message or a choice); a paired text gives its strings in order. Strings the
    alignment leaves out (a text added or removed by the translation) are not in the result.
    """
    en_texts, jp_texts = _texts(english), _texts(japanese)
    en_at = {text.start: i for i, text in enumerate(en_texts)}
    jp_at = {text.start: i for i, text in enumerate(jp_texts)}
    en_ops = pairing.instructions(english)
    jp_ops = pairing.instructions(japanese)
    en_first, jp_first = _starts(en_texts), _starts(jp_texts)
    out: List[Tuple[int, int]] = []
    for i, j in pairing.align([op for _, op in en_ops], [op for _, op in jp_ops]):
        a, b = en_at.get(en_ops[i][0]), jp_at.get(jp_ops[j][0])
        if a is None or b is None or en_texts[a].kind != jp_texts[b].kind:
            continue
        for k in range(min(len(en_texts[a].strings), len(jp_texts[b].strings))):
            out.append((en_first[a] + k, jp_first[b] + k))
    return sorted(out)


def reference_for_japanese(english: bytes, japanese: bytes) -> List[str]:
    """The English text of each Japanese string number (empty where no English string pairs)."""
    en = strings_of(english, japanese=False)
    out = [""] * len(strings_of(japanese, japanese=True))
    for e, j in string_pairs(english, japanese):
        if j < len(out) and e < len(en):
            out[j] = en[e]
    return out


def english_with_translation(english: bytes, japanese: bytes, lines: List[str]) -> Tuple[bytes, Set[str]]:
    """The English file with each translated string in its English slot.

    A line is used when it is not empty and differs from the Japanese source. Returns the file and the characters the
    English encoder cannot write (they become '?').
    """
    jp_source = strings_of(japanese, japanese=True)
    slots = strings_of(english, japanese=False)
    for e, j in string_pairs(english, japanese):
        if j < len(lines) and lines[j] and j < len(jp_source) and lines[j] != jp_source[j] and e < len(slots):
            slots[e] = lines[j]
    missing: Set[str] = set()
    out = english_doc.write(english, [slots], missing)
    return out, missing


def translation_bytes(lines: List[str]) -> bytes:
    return TRANSLATION_MAGIC + json.dumps({"strings": lines}, ensure_ascii=False).encode("utf-8")


def read_translation(data: bytes) -> Optional[List[str]]:
    """The translated strings of a translation file, or None when ``data`` is not one."""
    if not data.startswith(TRANSLATION_MAGIC):
        return None
    value = json.loads(data[len(TRANSLATION_MAGIC):].decode("utf-8"))
    return [str(line) for line in value.get("strings", [])]
