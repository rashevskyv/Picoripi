"""Find the texts the C code of a Generation III decompilation builds in the ROM: the ``c_texts`` entry of a facts file.

A C text is a string literal, ``_("...")``, in a source file. The game reads it from the ROM, so the text sits in the
image as text ending in 0xFF. Each literal is located in the unedited ROM in one of two ways:

- ``symbol``: the literal is declared as ``NAME[] = _("...")`` and the linker map has ``NAME`` at a ROM address whose
  bytes are the literal;
- ``search``: the encoded literal occurs exactly once in the ROM, at the start of a string (the byte before it is 0x00
  or 0xFF).

A literal that occurs more than once, or that the ROM does not hold, is not opened here. A literal whose bytes are
already a unit of the facts (a name table, a message, a pointer text) is counted as covered and not added again.
Each new unit is a text that may grow: it moves to free space when it grows, and its pointers follow.

The report gives the literal count per source file and the count in each class. Nothing is written without ``--write``.

Usage (run from the repository root):
    python tools/pokemon_fr_c_texts.py --decomp <port\\pokefirered> --rom <unedited ROM> \\
        --facts plugins/pokemon_fr/rom_facts/firered_usa_rev0.json --map <pokefirered.map> [--write]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from plugins.pokemon_fr import rom_text  # noqa: E402
from pokemon_fr_rom_facts import map_symbols  # noqa: E402

BASE = 0x08000000
TERMINATOR = 0xFF
# A literal of the C source: one or more quoted pieces inside _( ).
LITERAL = re.compile(r'_\(((?:\s*"(?:[^"\\\n]|\\.)*")+)\s*\)', re.S)
PIECE = re.compile(r'"((?:[^"\\\n]|\\.)*)"', re.S)
DECLARED = re.compile(r'(\w+)\s*\[\s*\]\s*=\s*$')
ESCAPES = {"n": "\\n", "p": "\\p", "l": "\\l", '"': '\\"', "\\": "\\\\"}
BARE_BYTES = re.compile(r"\{(\w+)((?: [0-9A-Fa-f]+)+)\}")
KANA = re.compile("[\u3040-\u30ff]")
# Tables of characters, not messages: the naming screen's key rows and the hex digit table.
CHARACTER_TABLES = {"naming_screen.c", "string_util.c"}
SOURCE_DIRS = ("src", "data")


def editor_text(raw: str) -> str:
    """The text the editor shows for a C literal: the escape codes stay as the editor writes them.

    The C source writes a control code's bytes bare (``{COLOR 01}``); the editor writes them with ``0x``. A ``$``
    starts the padding after the terminator, which the field carries as 0xFF, so the text ends there.
    """
    out: List[str] = []
    at = 0
    while at < len(raw):
        if raw[at] == "\\" and at + 1 < len(raw):
            out.append(ESCAPES.get(raw[at + 1], raw[at + 1]))
            at += 2
            continue
        out.append(raw[at])
        at += 1
    text = "".join(out).split("$")[0]
    return BARE_BYTES.sub(lambda m: "{" + m.group(1) + " " + " ".join(_byte(b) for b in m.group(2).split()) + "}", text)


def _byte(token: str) -> str:
    """A control code's argument as the editor writes it: decimal (``127``) or bare hex (``01``, ``1F``)."""
    if token.lower().startswith("0x"):
        return token
    if token.isdigit() and token[0] != "0":
        return f"0x{int(token):02X}"
    if token.isdigit():
        return "0x" + token
    return "0x" + token


def covered_offsets(facts: Dict[str, object]) -> Set[int]:
    """The ROM offsets already opened: messages, name tables and pointer texts (C texts are found again)."""
    covered: Set[int] = set()
    for _label, offset, size in facts.get("units", []):
        covered.update(range(int(offset), int(offset) + int(size)))
    for table in facts.get("c_tables", []):
        if table.get("kind") == "pointer":
            for _index, offset, size in table["units"]:
                covered.update(range(int(offset), int(offset) + int(size)))
        else:
            size = int(table.get("size", table.get("stride", 0)))
            for index in range(int(table["count"])):
                start = int(table["offset"]) + index * int(table["stride"])
                covered.update(range(start, start + size))
    return covered


# The decompilations keep the other languages' texts beside the English ones (trainers_de.h, ...): the ROM is English.
OTHER_LANGUAGE = re.compile(r"_(de|fr|it|es|ja|ko|zh|jp)$")


LANGUAGE = re.compile(r"\b(ENGLISH|GERMAN|FRENCH|ITALIAN|SPANISH|JAPANESE)\b")
IF_LINE = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b\s*(.*)$")


VARIANTS = ("RUBY", "SAPPHIRE", "FIRERED", "LEAFGREEN", "EMERALD")


def language_excluded_lines(text: str, variant: str) -> List[bool]:
    """Per line: True inside a branch that does not belong to this image.

    Two kinds of conditional are read: a language chain (``#if ENGLISH`` / ``#elif GERMAN``), where only the English
    branch is kept, and a version switch (``#ifdef SAPPHIRE`` / ``#else``), where only the branch of this image's
    version is kept. A frame is ``[first branch excluded, current branch excluded]``.
    """
    flags: List[bool] = []
    stack: List[List[bool]] = []
    for line in text.split("\n"):
        match = IF_LINE.match(line)
        if match:
            kind, cond = match.group(1), match.group(2)
            words = set(LANGUAGE.findall(cond)) | set(re.findall(r"\b(" + "|".join(VARIANTS) + r")\b", cond))
            if kind in ("if", "ifdef", "ifndef"):
                if words & set(VARIANTS) and not (words & {"ENGLISH", "GERMAN", "FRENCH", "ITALIAN", "SPANISH",
                                                            "JAPANESE"}):
                    mine = variant in words
                    first = (not mine) if kind != "ifndef" else mine
                    stack.append([first, first])
                elif words:
                    first = "ENGLISH" not in words
                    stack.append([first, first])
                else:
                    stack.append([False, False])
            elif kind == "elif" and stack:
                if words:
                    top = stack[-1]
                    top[1] = ("ENGLISH" not in words) if not (words & set(VARIANTS)) else (variant not in words)
            elif kind == "else" and stack:
                top = stack[-1]
                top[1] = not top[0]
            elif kind == "endif" and stack:
                stack.pop()
        flags.append(any(frame[1] for frame in stack))
    return flags


def source_files(decomp: Path) -> List[Path]:
    return sorted({path for folder in SOURCE_DIRS for path in (decomp / folder).rglob("*")
                   if path.suffix in (".c", ".h") and "build" not in path.parts
                   and not OTHER_LANGUAGE.search(path.stem) and path.name not in CHARACTER_TABLES
                   and "debug" not in path.parts})


def scan(decomp: Path, rom: bytes, charmap: rom_text.Charmap, symbols: Dict[str, int],
         covered: Set[int], variant: str) -> Tuple[Dict[str, List[List[object]]], Dict[str, Counter]]:
    """The new units per source file, and the count of each class per source file."""
    units: Dict[str, List[List[object]]] = {}
    counts: Dict[str, Counter] = {}
    claimed: Set[int] = set(covered)
    for path in source_files(decomp):
        text = path.read_text(encoding="utf-8", errors="replace")
        key = str(path.relative_to(decomp)).replace("\\", "/")
        stem = re.sub(r"\W", "_", path.stem)
        found: Counter = Counter()
        flags = language_excluded_lines(text, variant)
        for match in LITERAL.finditer(text):
            raw = "".join(PIECE.findall(match.group(1)))
            shown = editor_text(raw)
            if flags[text.count("\n", 0, match.start())]:
                found["other_language"] += 1
                continue
            if KANA.search(shown):
                found["japanese"] += 1
                continue
            try:
                expected = charmap.encode(shown)
            except rom_text.CodecError:
                found["nocell"] += 1
                continue
            declared = DECLARED.search(text[max(0, match.start() - 120):match.start()])
            name = declared.group(1) if declared else None
            at: Optional[int] = None
            how = "search"
            if name and name in symbols:
                cand = symbols[name] - BASE
                if rom[cand:cand + len(expected)] == expected:
                    at, how = cand, "symbol"
            if at is None:
                hits: List[int] = []
                spot = rom.find(expected)
                while spot >= 0 and len(hits) < 16:
                    hits.append(spot)
                    spot = rom.find(expected, spot + 1)
                if any(h in claimed for h in hits):
                    found["covered"] += 1
                    continue
                if not hits:
                    found["missing"] += 1
                    continue
                starts = [h for h in hits if h == 0 or rom[h - 1] in (0x00, TERMINATOR)]
                if not starts:
                    found["not_a_start"] += 1
                    continue
                if len(starts) > 1:
                    # the same text in several places: each place the code has not claimed becomes a unit
                    line = text.count(chr(10), 0, match.start()) + 1
                    for k, spot_k in enumerate(starts):
                        if any(i in claimed for i in range(spot_k, spot_k + len(expected))):
                            continue
                        units.setdefault(key, []).append([f"{stem}_L{line}_{k}", spot_k, len(expected)])
                        claimed.update(range(spot_k, spot_k + len(expected)))
                        found["duplicate"] += 1
                    continue
                at = starts[0]
            if any(i in claimed for i in range(at, at + len(expected))):
                found["covered"] += 1
                continue
            label = name if how == "symbol" else f"{stem}_L{text.count(chr(10), 0, match.start()) + 1}"
            units.setdefault(key, []).append([label, at, len(expected)])
            claimed.update(range(at, at + len(expected)))
            found[how] += 1
        counts[key] = found
    return units, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--decomp", required=True, type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--map", required=True, type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    text = args.facts.read_text(encoding="utf-8")
    facts = json.loads(text)
    if hashlib.sha1(rom).hexdigest() != facts["rom_sha1"]:
        raise SystemExit("this ROM is not the one the facts file was made from")
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts["charmap"])
    symbols = map_symbols(args.map)[0]
    game = facts["game"]
    variant = next((name for name in VARIANTS if name.lower() in game.lower().replace(" ", "")), "")
    units, counts = scan(args.decomp, rom, charmap, symbols, covered_offsets(facts), variant)
    total: Counter = Counter()
    for file_counts in counts.values():
        total.update(file_counts)
    print("literals", sum(total.values()), dict(total), flush=True)
    for name, file_counts in sorted(counts.items(), key=lambda kv: -sum(kv[1].values()))[:30]:
        if sum(file_counts.values()):
            print(sum(file_counts.values()), name, dict(file_counts), flush=True)
    if args.write:
        texts = []
        for name in sorted(units):
            stem = re.sub(r"\W", "_", Path(name).stem)
            texts.append({"name": f"c_{stem}", "file": f"c_{stem}.inc", "units": units[name]})
        lines = [item for item in text.split("\n") if not item.startswith('"c_texts":')]
        at = next(i for i, item in enumerate(lines) if item.startswith('"c_tables"'))
        lines.insert(at + 1, '"c_texts": ' + json.dumps(texts, ensure_ascii=False) + ",")
        args.facts.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        print("wrote", sum(len(item["units"]) for item in texts), "units in", len(texts), "files", flush=True)


if __name__ == "__main__":
    main()
