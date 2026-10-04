"""The Russian fan translation (Vagrant Story Reborn RUS 1.5f) as a reference language.

The Russian build is the USA disc with its strings replaced in the same files, tables and
places, so a line is found there by the file, table index or offset of the English one. Its
font keeps the Latin capitals, turns the small letters into small capitals and puts the other
Cyrillic letters over the accented Latin ones; a word written only with letters that look alike
(``Meteop``) or with Cyrillic ones is Russian and is read as Cyrillic, any other word stays Latin.
"""
from __future__ import annotations

from typing import Dict

from . import codec

CYRILLIC: Dict[int, str] = {code: char for code, char in zip(range(0x3F, 0x52), "ГДЖЗИЙЛПЁУФЦЧШЩЫЭЮЯ")}
CYRILLIC.update({code: char for code, char in zip(range(0x52, 0x67), "бгджзийлпфцчёшщъыьэюя")})
CYRILLIC.update({0x67: "Б", 0x68: "Ъ", 0x69: "Ь"})
LOOKALIKE: Dict[int, str] = {codec.CODES[latin]: cyr for latin, cyr in zip("ABCEHKMOPTXYabcehkmoptxy",
                                                                           "АВСЕНКМОРТХУавсенкмортху")}


def decode(raw: bytes) -> str:
    """Editor text of a Russian string. A string with a Latin-only word (``Gold``) and no Cyrillic-only
    letter is English left as it was, and stays Latin."""
    out = []
    word: list = []
    codes = [code for code, param in codec.tokens(raw) if param is None]
    english = not any(code in CYRILLIC for code in codes) and any(
        0x0A <= code <= 0x3D and code not in LOOKALIKE for code in codes)

    def flush() -> None:
        if not word:
            return
        cyrillic = not english and all(code in CYRILLIC or code in LOOKALIKE for code in word)
        for code in word:
            if cyrillic:
                out.append(CYRILLIC.get(code) or LOOKALIKE[code])
            else:
                out.append(CYRILLIC.get(code) or codec.CHARS.get(code, "?"))
        word.clear()

    for code, param in codec.tokens(raw):
        if param is None and (0x0A <= code <= 0x3D or code in CYRILLIC):
            word.append(code)
            continue
        flush()
        out.append(codec.decode(bytes((code,)) if param is None else bytes((code, param))))
    flush()
    return "".join(out)
