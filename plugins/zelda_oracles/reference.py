"""Reference columns for Oracle of Ages and Seasons: the European and Russian-hack ROMs, read-only.

Reference strings are matched to the English (USA) strings by the text index name (TX_xxxx), the same key
the English ROM uses. A reference string without an English counterpart is not shown; an English string
without one shows no reference.

Slots (language index in the ROM's language table, checked by word search in the European ROMs):
  0 English, 1 French, 2 German, 3 Italian, 4 Spanish.
The Russian hacks keep the English slot (0) and put the Russian text in slots 1-4 (the same bytes in
all four); the Russian text is Windows-1251.

Only reading happens here. The reference text is shown to the translator and never written into a ROM.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

from .rom import identify_reference
from .text import TextTables, to_markup

# Special characters of the European text (bytes 0x80 up). '?' marks a byte with no character here; the
# editor shows those as \xNN. The row layout follows the disassembly's special-character table.
_EU_ROWS = (
    "ÀÂÄÆÇÈÉÊËÎÏÑÖŒÙÛ",
    "Üß??????¡¿??????",
    "àâäæçèéêëîïñöœùû",
    "ü´??????????????",
    "Ô°ÁÍÓÚÌÒÅ???????",
    "ôªáíóúìòå???????",
)
EU_SPECIALS = "".join(_EU_ROWS)

# Reference slots: language index -> label shown in the project.
EU_SLOTS = {1: "French (FR)", 2: "German (DE)", 3: "Italian (IT)", 4: "Spanish (ES)"}
RU_SLOT = 1
RU_LABEL = "Russian (RU)"


def _eu_special(byte: int) -> Optional[str]:
    index = byte - 0x80
    if 0 <= index < len(EU_SPECIALS) and EU_SPECIALS[index] != "?":
        return EU_SPECIALS[index]
    return None


def _ru_special(byte: int) -> Optional[str]:
    try:
        return bytes([byte]).decode("cp1251")
    except UnicodeDecodeError:
        return None


def read_slot(data: bytes, language: int, russian: bool = False) -> Dict[str, str]:
    """Every named string of one language slot as markup, keyed by TX name."""
    layout = identify_reference(data)
    tables = TextTables(data, layout, language)
    special: Callable[[int], Optional[str]] = _ru_special if russian else _eu_special
    return {
        span.name: to_markup(tables.expand(span), span.index, special)
        for span in tables.spans
        if not span.is_dictionary
    }


def read_reference_set(eu_rom: bytes, ru_rom: bytes) -> Dict[str, Dict[str, str]]:
    """Reference columns of one game: label -> {TX name: markup}."""
    columns = {label: read_slot(eu_rom, slot) for slot, label in EU_SLOTS.items()}
    columns[RU_LABEL] = read_slot(ru_rom, RU_SLOT, russian=True)
    return columns


def match_counts(english: Dict[str, str], reference: Dict[str, str]) -> Tuple[int, int, int]:
    """(strings matched by TX name, reference strings, English strings without a reference)."""
    matched = sum(1 for name in reference if name in english)
    missing = sum(1 for name in english if name not in reference)
    return matched, len(reference), missing
