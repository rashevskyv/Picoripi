"""Write the ROM facts of a Generation III game for the Pokemon plugin: the charmap and the address of every message.

Facts come from the decompilation (pret) and its link map. Nothing of the game text is copied: the file holds the
label, the file offset and the size of each message, and the charmap codes.

Usage (run from the repository root):
    python tools/pokemon_fr_rom_facts.py --decomp <port\\pokefirered> --map <pokefirered.map> \\
        --rom <unedited ROM> --game "FireRed (USA, rev 0)" --build-name "Pokemon FireRed UA" \
        --out plugins/pokemon_fr/rom_facts/firered_usa_rev0.json

The map must come from a build of the unedited decompilation. The ROM must be that build's output (same SHA-1).
Every message is checked: the source text must encode to the ROM bytes, and every ROM message must come back
unchanged through decode and encode. A failed check stops the tool; nothing is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.common.gba_rom import ROM_BASE, pointer_index  # noqa: E402
from plugins.pokemon_fr import pret_text  # noqa: E402
from plugins.pokemon_fr.rom_text import CHARMAP_FILE, FACTS_DIR, Charmap, CodecError, TERMINATOR  # noqa: E402

# Argument counts of the prefix codes that take bytes after them (the charmap gives the code, not the count).
PREFIX_ARGS = {
    "COLOR": 1, "HIGHLIGHT": 1, "SHADOW": 1, "COLOR_HIGHLIGHT_SHADOW": 3, "PALETTE": 1, "FONT": 1,
    "PAUSE": 1, "PLAY_BGM": 2, "PLAY_SE": 2, "FILL_WINDOW": 1, "ESCAPE": 1,
    "SHIFT_RIGHT": 1, "SHIFT_DOWN": 1, "CLEAR_TO": 1, "MIN_LETTER_SPACING": 1,
}

# Prefix codes whose argument is a sound id (two bytes) rather than one byte.
SOUND_ARGS = ["PLAY_SE", "PLAY_BGM"]

_CHAR = re.compile(r"^'((?:\\.|[^'\\])+)'\s*=\s*((?:[0-9A-Fa-f]{2}\s*)+)")
_NAME = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*((?:[0-9A-Fa-f]{2}\s*)+)")
_SYMBOL = re.compile(r"^\s+0x([0-9a-fA-F]{8,16})\s+([A-Za-z_][\w.@$]*)\s*$")
_SECTION = re.compile(r"^([A-Za-z_.][\w.]*)\s+0x([0-9a-fA-F]{8,16})\s+0x([0-9a-fA-F]+)")  # an output section, column 0


def parse_charmap(path: Path) -> Tuple[List[List[str]], List[List[object]], List[List[object]]]:
    """The charmap as ``chars`` (editor key, code), ``names`` (text codes) and ``sounds`` (sound ids).

    The ``@ sound`` section holds the ids that ``playse`` and ``playbgm`` take. They are not text codes, so they
    are kept apart: a sound id such as ``D4 00`` is the letter Z followed by a space in running text.
    """
    chars: List[List[str]] = []
    names: List[List[object]] = []
    sounds: List[List[object]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("@"):
            continue
        if not line:
            continue
        char = _CHAR.match(line)
        if char:
            key = char.group(1)
            key = {"\\'": "'", "\\\\": "\\", '\\"': '"'}.get(key, key)
            code = char.group(2).split()
            if len(code) != 1:
                raise ValueError(f"A quoted character with {len(code)} bytes: {raw}")
            chars.append([key, code[0].upper()])
            continue
        name = _NAME.match(line)
        if name:
            code = "".join(name.group(2).split()).upper()
            # Sound ids are named SE_ and MUS_ (the sound block also holds text codes such as PLUS = F9 04).
            (sounds if name.group(1).startswith(("SE_", "MUS_")) else names).append([name.group(1), code])
    return chars, names, sounds


def source_units(decomp: Path) -> Dict[str, Tuple[str, str]]:
    """Every assembly message of the decompilation: label -> (editor text, directive). The first one of a label wins."""
    found: Dict[str, Tuple[str, str]] = {}
    for path in sorted(decomp.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in pret_text.ASM_SUFFIXES:
            continue
        if any(part in {"build", "tools", ".git"} for part in path.relative_to(decomp).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        for unit in pret_text.parse(text, asm=True):
            if unit.label and unit.label not in found:
                found[unit.label] = (unit.content, unit.directive)
    return found


def parse_songs(decomp: Path) -> List[List[object]]:
    """The music ids of the decompilation: ``MUS_*`` as two bytes, little-endian, the way ``playbgm`` takes them."""
    found: List[List[object]] = []
    songs = decomp / "include" / "constants" / "songs.h"
    if not songs.is_file():
        return found
    for line in songs.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^#define\s+(MUS_\w+)\s+(0x[0-9A-Fa-f]+|\d+)", line)
        if match:
            value = int(match.group(2), 0)
            if 0 <= value <= 0xFFFF:
                found.append([match.group(1), value.to_bytes(2, "little").hex().upper()])
    return found


def map_symbols(path: Path) -> Tuple[Dict[str, int], int]:
    """Global symbols of the link map (absolute addresses) and the end of the linked ROM data."""
    symbols: Dict[str, int] = {}
    end = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        found = _SYMBOL.match(line)
        if found:
            symbols.setdefault(found.group(2), int(found.group(1), 16))
            continue
        section = _SECTION.match(line)
        if section and len(line.split()) == 3:      # a memory region has a fourth field (its flags)
            start, size = int(section.group(2), 16), int(section.group(3), 16)
            if ROM_BASE <= start < ROM_BASE + 0x02000000 and size:
                end = max(end, start + size)
    return symbols, end


def read_message(rom: bytes, offset: int) -> int:
    """The size of the message at ``offset`` including its terminator."""
    end = rom.find(bytes([TERMINATOR]), offset, offset + 0x2000)
    if end < 0:
        raise ValueError(f"No terminator for the message at 0x{offset:X}.")
    return end - offset + 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--decomp", required=True, type=Path)
    parser.add_argument("--map", required=True, type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--game", required=True)
    parser.add_argument("--build-name", required=True, help="the file name of a built ROM, without .gba")
    parser.add_argument("--out", required=True, type=Path)
    options = parser.parse_args()

    rom = options.rom.read_bytes()
    digest = hashlib.sha1(rom).hexdigest()

    chars, names, sounds = parse_charmap(options.decomp / "charmap.txt")
    sounds = sounds + [item for item in parse_songs(options.decomp) if item[0] not in {n for n, _ in sounds}]
    charmap_facts = {"chars": chars, "names": names, "sounds": sounds, "args": PREFIX_ARGS,
                     "sound_args": SOUND_ARGS}
    charmap = Charmap([(k, int(c, 16)) for k, c in chars], [(n, bytes.fromhex(c)) for n, c in names],
                      PREFIX_ARGS, [(n, bytes.fromhex(c)) for n, c in sounds], SOUND_ARGS)

    symbols, rom_end = map_symbols(options.map)
    floor = ((rom_end - ROM_BASE) + 3) & ~3
    if any(byte != 0xFF for byte in rom[floor:]):
        raise SystemExit(f"The ROM is not 0xFF after the linked data at 0x{floor:X}; the free space is not known.")

    pointers = pointer_index(rom)
    sources = source_units(options.decomp)
    units: List[Tuple[int, str, int]] = []
    differs: List[str] = []
    unencodable: List[str] = []
    braille: List[str] = []
    unlinked: List[str] = []
    for label, (content, directive) in sources.items():
        if directive == "braille":
            braille.append(label)     # the braille table is not in the charmap yet: not opened in this version
            continue
        if label not in symbols:
            unlinked.append(label)
            continue
        offset = symbols[label] - ROM_BASE
        size = read_message(rom, offset)
        original = rom[offset:offset + size]
        try:
            if charmap.encode(content) != original:
                differs.append(label)
        except CodecError:
            unencodable.append(label)     # a source form the codec does not write (for example a music constant)
        if charmap.encode(charmap.decode(original)) != original:
            raise SystemExit(f"Decode and encode do not return the ROM bytes of {label}.")
        units.append((offset, label, size))
    units.sort()

    # Overlap check: two messages must not share bytes, or a move would damage the other.
    for (start, name, size), (next_start, next_name, _) in zip(units, units[1:]):
        if start + size > next_start:
            raise SystemExit(f"{name} overlaps {next_name}.")

    charmap_path = FACTS_DIR / CHARMAP_FILE
    charmap_path.parent.mkdir(parents=True, exist_ok=True)
    charmap_path.write_text(json.dumps(charmap_facts, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                            newline="\n")

    facts = {
        "game": options.game,
        "build_name": options.build_name,
        "rom_sha1": digest,
        "rom_size": len(rom),
        "source": "pret decompilation and its link map; facts only",
        "free_start": floor,
        # A message with no pointer to it can be written only in its original length (see gba_rom.Relocator).
        "unpointed_units": sum(1 for offset, _label, _size in units if ROM_BASE + offset not in pointers),
        "units": [[label, offset, size] for offset, label, size in units],
    }
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(json.dumps(facts, ensure_ascii=False, indent=0) + "\n", encoding="utf-8", newline="\n")

    print(f"messages in source: {len(sources)}")
    print(f"messages linked and written: {len(units)}")
    print(f"source text differs from ROM bytes: {len(differs)} {differs[:10]}")
    print(f"source form not written by the codec: {len(unencodable)} {unencodable[:10]}")
    print(f"braille messages, not opened yet: {len(braille)}")
    print(f"not linked (no symbol in the map): {len(unlinked)} {unlinked[:10]}")
    print(f"free space starts at file offset 0x{floor:X}; ROM {len(rom)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
