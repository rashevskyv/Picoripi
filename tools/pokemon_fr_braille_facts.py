"""Write the braille facts of a Generation III facts file: the braille character codes and the address of each braille text.

A braille text is a ``.braille`` string of the decompilation (``data/text/braille.inc``). Its bytes are the braille
character codes (``BRAILLE_CHAR_*`` in ``include/characters.h``, the map in ``tools/preproc/asm_file.cpp``) and end with
0xFF. Each text is located in the unedited ROM by its link-map symbol when the symbol's bytes are the text, else by
its bytes, which must occur once. The facts hold the characters, the codes and the offsets only.

Usage (run from the repository root):
    python tools/pokemon_fr_braille_facts.py --decomp <port\\pokefirered> --rom <unedited ROM> \\
        --facts plugins/pokemon_fr/rom_facts/firered_usa_rev0.json --map <pokefirered.map>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from pokemon_fr_rom_facts import map_symbols, nm_symbols  # noqa: E402

BASE = 0x08000000
TERMINATOR = 0xFF
WINDOW_FORMAT = 6        # bytes of a ``brailleformat`` block before its text (the window and the text origin)
DEFINE = re.compile(r"^#define\s+BRAILLE_CHAR_(\w+)\s+0x([0-9A-Fa-f]+)", re.M)
ENTRY = re.compile(r"\{\s*'((?:\\.|[^'\\]))'\s*,\s*BRAILLE_CHAR_(\w+)\s*\}")
# A label, optionally a ``brailleformat`` line (the window data the pointer names, six bytes in Ruby and Emerald),
# then one or more ``.braille`` lines: the assembler joins them into one block of bytes.
TEXT = re.compile(r'^(\w+)::?\s*\n(\s*brailleformat\b[^\n]*\n)?((?:\s*\.braille\s+"(?:[^"\\]|\\.)*")+)', re.M)
PIECE = re.compile(r'\.braille\s+"((?:[^"\\]|\\.)*)"')


def braille_table(decomp: Path) -> List[List[str]]:
    """The braille characters in the decompilation's order: ``[char, hex code]``. The first character of a code wins."""
    header = next(path for path in (decomp / "include" / "characters.h",
                                    decomp / "include" / "constants" / "characters.h") if path.is_file())
    codes = {name: f"{int(value, 16):02X}" for name, value in DEFINE.findall(
        header.read_text(encoding="utf-8", errors="replace"))}
    table: List[List[str]] = []
    seen = set()
    source = (decomp / "tools" / "preproc" / "asm_file.cpp").read_text(encoding="utf-8", errors="replace")
    for char, name in ENTRY.findall(source):
        char = {"\\'": "'", "\\\\": "\\"}.get(char, char)
        if char in seen or name not in codes:
            continue
        seen.add(char)
        table.append([char, codes[name]])
    # The text escape ``\n`` is the line break code (CHAR_NEWLINE), as the decompilation's assembler writes it.
    newline = re.search(r"^#define\s+CHAR_NEWLINE\s+0x([0-9A-Fa-f]+)", header.read_text(encoding="utf-8",
                                                                                          errors="replace"), re.M)
    if newline:
        table.append(["\\n", f"{int(newline.group(1), 16):02X}"])
    return table


def braille_texts(decomp: Path) -> List[Tuple[str, str, bool]]:
    """Each braille label with its text (the ``$`` terminator removed) and whether a window format precedes it."""
    found: List[Tuple[str, str, bool]] = []
    for path in sorted((decomp / "data").rglob("*.inc")) + sorted((decomp / "data").rglob("*.s")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, prefix, lines in TEXT.findall(text):
            content = "".join(PIECE.findall(lines)).replace("\\\"", "\"")
            found.append((label, content.split("$")[0], bool(prefix)))
    return found


def write_keys(path: Path, keys: Dict[str, object]) -> None:
    """Replace the given top-level keys of the facts file, one line per key, as the other facts writers do."""
    lines = [line for line in path.read_text(encoding="utf-8").split("\n")
             if not any(line.startswith(f'"{key}":') for key in keys)]
    end = max(i for i, line in enumerate(lines) if line.strip() == "}")
    if not lines[end - 1].endswith(","):
        lines[end - 1] += ","
    added = [f'"{key}": ' + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + ","
             for key, value in keys.items()]
    lines[end:end] = added
    lines[end + len(added) - 1] = lines[end + len(added) - 1].rstrip(",")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def encode(text: str, table: Dict[str, int]) -> Optional[bytes]:
    """The bytes of a braille text with its terminator; None for a character the table has no code for."""
    out = bytearray()
    at = 0
    while at < len(text):
        key = text[at:at + 2] if text[at:at + 2] == "\\n" else text[at]
        if key not in table:
            return None
        out.append(table[key])
        at += len(key)
    out.append(TERMINATOR)
    return bytes(out)


def _item(label: str, at: int, size: int, windowed: bool, extra: List[int]) -> List[object]:
    """One braille unit: ``[label, offset, size]``, then ``"fixed"`` or ``""`` and the other places when there are any."""
    item: List[object] = [label, at, size]
    if windowed or extra:
        item.append("fixed" if windowed else "")
    if extra:
        item.append(list(extra))
    return item


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--decomp", required=True, type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--map", type=Path)
    parser.add_argument("--nm", type=Path, help="arm-none-eabi-nm output: local labels too (braille labels are often local)")
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    facts = json.loads(args.facts.read_text(encoding="utf-8"))
    if hashlib.sha1(rom).hexdigest() != facts["rom_sha1"]:
        raise SystemExit("this ROM is not the one the facts file was made from")
    table = braille_table(args.decomp)
    codes = {char: int(code, 16) for char, code in table}
    symbols = map_symbols(args.map)[0] if args.map else {}
    if args.nm:
        symbols.update(nm_symbols(args.nm)[0])
    units: List[List[object]] = []
    pending: List[Tuple[str, bytes, bool]] = []
    missing: List[str] = []
    ambiguous: List[str] = []
    for label, content, windowed in braille_texts(args.decomp):
        expected = encode(content, codes)
        if expected is None:
            missing.append(label)
            continue
        at = None
        # A window format is six bytes before the text (its pointer names the format).
        start = symbols[label] - BASE + (WINDOW_FORMAT if windowed else 0) if label in symbols else None
        if start is not None and rom[start:start + len(expected)] == expected:
            at = start
        else:
            hits = []
            spot = rom.find(expected)
            while spot >= 0 and len(hits) < 8:
                hits.append(spot)
                spot = rom.find(expected, spot + 1)
            if len(hits) == 1:
                at = hits[0]
            elif 2 <= len(hits) <= 4 and len(expected) >= 6:
                # The same long text at a few places, and the labels do not tell which: each place is its own unit.
                for k, place in enumerate(hits):
                    units.append([f"{label}_{k}", place, len(expected)] + (["fixed"] if windowed else []))
                continue
            else:
                pending.append((label, expected[:-1], windowed))
                continue
        # A window format before the text: its pointer names the format, so the text cannot move (a budget).
        units.append([label, at, len(expected)] + (["fixed"] if windowed else []))
    # A line that the ROM joins to the next line (0xFE between them, one terminator at the end of the block): the
    # block from the line's place to its terminator is the text. A place already inside a unit is covered by it.
    for label, body, windowed in pending:
        spans = [(int(item[1]), int(item[1]) + int(item[2])) for item in units]
        places = []
        spot = rom.find(body)
        while spot >= 0 and len(places) < 8:
            if not any(start <= spot < end for start, end in spans):
                places.append(spot)
            spot = rom.find(body, spot + 1)
        if not places:
            continue
        # One text in two or more places: the same bytes to the terminator at each, so one unit holds every place.
        ends = [rom.find(bytes([TERMINATOR]), place) for place in places]
        sizes = {end - place + 1 for end, place in zip(ends, places) if end >= 0}
        if len(sizes) != 1 or min(ends) < 0:
            ambiguous.append(label)
            continue
        units.append(_item(label, places[0], sizes.pop(), windowed, places[1:]))
    units.sort(key=lambda item: item[1])
    for (name, start, size, *_flags), (next_name, next_start, _size, *_more) in zip(units, units[1:]):
        if start + size > next_start:
            raise SystemExit(f"braille text {name} overlaps {next_name}")
    write_keys(args.facts, {"braille_chars": table, "braille_units": units})
    print(f"braille characters: {len(table)}; texts located: {len(units)}; "
          f"not encodable: {missing}; ambiguous: {ambiguous}")


if __name__ == "__main__":
    main()
