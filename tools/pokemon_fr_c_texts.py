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

from plugins.common.gba_rom import pointer_index  # noqa: E402
from plugins.pokemon_fr import rom_text  # noqa: E402
from pokemon_fr_rom_facts import map_symbols, nm_symbols  # noqa: E402

BASE = 0x08000000
TERMINATOR = 0xFF
# A literal of the C source: one or more quoted pieces inside _( ).
LITERAL = re.compile(r'_\(((?:\s*"(?:[^"\\\n]|\\.)*")+)\s*\)', re.S)
PIECE = re.compile(r'"((?:[^"\\\n]|\\.)*)"', re.S)
DECLARED = re.compile(r'(\w+)\s*\[\s*\]\s*=\s*$')
ESCAPES = {"n": "\\n", "p": "\\p", "l": "\\l", '"': '\\"', "\\": "\\\\"}
BARE_BYTES = re.compile(r"\{(\w+)((?: [0-9A-Fa-f]+)+)\}")
MAX_HITS = 256   # occurrences of one literal counted in the ROM
SHORT = 4        # encoded length (terminator included) at or below which a repeated text is a fragment
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


VARIANTS = ("RUBY", "SAPPHIRE", "FIRERED", "LEAFGREEN", "EMERALD")
VERSION_FILE = re.compile(r"_(fr|lg)$")
VERSION_OF = {"fr": "FIRERED", "lg": "LEAFGREEN"}
IF_LINE = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b\s*(.*)$")
IDENTIFIER = re.compile(r"[A-Za-z_]\w*")
EXPRESSION = re.compile(r"\s*(\d+[uUlL]*|[A-Za-z_]\w*|&&|\|\||==|!=|>=|<=|[()!<>])")
COMMENT = re.compile(r"/\*.*?\*/|//.*$")
CONTROL = re.compile(r"\{[^}]*\}|\\[nlp]")
# A fragment of two letters, or one kana or CJK character, is text; other short pieces are code output.
TEXT_PIECE = re.compile(r"[A-Za-z]{2}|[\u3040-\u30ff\u4e00-\u9fff]")


def image_macros(variant: str, revision: int) -> Dict[str, int]:
    """The macros the decompilation's build passes for this image: English, the game version, the revision, and the
    debug flag (0 in the retail build, the Makefile default)."""
    return {"ENGLISH": 1, "DEBUG": 0, "MODERN": 0, "REVISION": revision, variant.upper(): 1}


def condition_value(kind: str, cond: str, macros: Dict[str, int]) -> bool:
    """The truth of one conditional for this image. ``#ifdef`` asks whether a macro is defined; ``#if`` reads the
    expression with C's rule that an undefined name is 0. An expression this reader does not know counts as true."""
    cond = COMMENT.sub("", cond).strip()
    if kind in ("ifdef", "ifndef"):
        defined = bool(cond) and cond.split()[0] in macros
        return defined if kind == "ifdef" else not defined
    cond = re.sub(r"defined\s*\(?\s*(\w+)\s*\)?", lambda m: "1" if m.group(1) in macros else "0", cond)
    parts: List[str] = []
    at = 0
    while at < len(cond):
        match = EXPRESSION.match(cond, at)
        if match is None:
            return True
        token = match.group(1)
        at = match.end()
        if token[0].isdigit():
            parts.append(token.rstrip("uUlL"))
        elif token in ("&&", "||", "!", "==", "!=", ">=", "<=", "<", ">", "(", ")"):
            parts.append({"&&": " and ", "||": " or ", "!": " not "}.get(token, " " + token + " "))
        elif token == "defined":
            return True
        else:
            parts.append(str(macros.get(token, 0)))
    if not parts:
        return True
    # Only digits, operators and parentheses reach eval: every other token was replaced above.
    try:
        return bool(eval(" ".join(parts), {"__builtins__": {}}, {}))
    except SyntaxError:
        return True


def exclusion(cond: str) -> str:
    """Why a branch with this condition is left out: the debug build, another revision, or another language or version."""
    words = set(IDENTIFIER.findall(cond))
    if "DEBUG" in words:
        return "debug"
    if "REVISION" in words:
        return "revision"
    return "other_language"


def conditional_reasons(text: str, variant: str, revision: int) -> List[str]:
    """Per line: "" when this image builds the line, else why it is left out (see ``exclusion``)."""
    macros = image_macros(variant, revision)
    reasons: List[str] = []
    stack: List[Dict[str, object]] = []      # per open conditional: taken (a branch was chosen), active, why
    for line in text.split("\n"):
        match = IF_LINE.match(line)
        if match:
            kind, cond = match.group(1), match.group(2)
            if kind in ("if", "ifdef", "ifndef"):
                value = condition_value(kind, cond, macros)
                stack.append({"taken": value, "active": value, "why": exclusion(cond)})
            elif kind == "elif" and stack:
                frame = stack[-1]
                if frame["taken"]:
                    frame.update(active=False, why=exclusion(cond))
                else:
                    value = condition_value("if", cond, macros)
                    frame.update(taken=value, active=value, why=exclusion(cond))
            elif kind == "else" and stack:
                frame = stack[-1]
                frame.update(active=not frame["taken"], taken=True)
            elif kind == "endif" and stack:
                stack.pop()
        reason = ""
        for frame in stack:
            if not frame["active"]:
                reason = str(frame["why"])
                break
        reasons.append(reason)
    return reasons


def missing_class(why: str, shown: str) -> str:
    """The class of a literal the image does not hold: not built (debug or another revision), a fill of control
    codes and spaces (no visible character), or missing."""
    if why == "debug":
        return "debug_build"
    if why == "revision":
        return "other_revision"
    if why == "other_version":
        return "other_version"
    if not re.search(r"\w", CONTROL.sub("", shown)):
        return "fill"
    return "missing"


def source_files(decomp: Path) -> List[Path]:
    return sorted({path for folder in SOURCE_DIRS for path in (decomp / folder).rglob("*")
                   if path.suffix in (".c", ".h") and "build" not in path.parts
                   and not OTHER_LANGUAGE.search(path.stem) and path.name not in CHARACTER_TABLES
                   and "debug" not in path.parts})


def tally(found: Counter, residue: Optional[List[Dict[str, object]]], key: str, text: str, match: "re.Match",
          shown: str, cls: str) -> None:
    """Count one literal in its class; a residual record (file, line, text) is kept when a list is given."""
    found[cls] += 1
    if residue is not None:
        residue.append({"cls": cls, "file": key, "line": text.count("\n", 0, match.start()) + 1,
                        "text": shown[:90]})


REGION_JSON = "src/data/region_map/region_map_sections.json"


def region_names(decomp: Path) -> List[str]:
    """The unique map section names of the region map data. The decomp builds each one as a C string
    (``sMapsecName_<NAME>[] = _("<name>")``) from this JSON, so the text is in the ROM by its name alone."""
    names: List[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("name"), str) and node["name"] not in names:
                names.append(node["name"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    path = decomp / REGION_JSON
    if path.is_file():
        walk(json.loads(path.read_text(encoding="utf-8")))
    return names


def source_texts(decomp: Path) -> List[Tuple[str, str, str]]:
    """Each source as (key, stem, text): the C and header files, and the region names as C strings."""
    found: List[Tuple[str, str, str]] = []
    for path in source_files(decomp):
        key = str(path.relative_to(decomp)).replace("\\", "/")
        found.append((key, re.sub(r"\W", "_", path.stem), path.read_text(encoding="utf-8", errors="replace")))
    lines = ['static const u8 sMapsecName_%s[] = _("%s");' % (re.sub(r"\W", "_", name), name)
             for name in region_names(decomp)]
    if lines:
        found.append((REGION_JSON, "region_map_sections", "\n".join(lines) + "\n"))
    return found


def scan(decomp: Path, rom: bytes, charmap: rom_text.Charmap, symbols: Dict[str, int],
         covered: Set[int], variant: str, residue: Optional[List[Dict[str, object]]] = None,
         revision: int = 0) -> Tuple[Dict[str, List[List[object]]], Dict[str, Counter]]:
    """The new units per source file, and the count of each class per source file. ``residue`` gets one record per literal
    that was not opened (the class, file, line and text), when a list is passed."""
    units: Dict[str, List[List[object]]] = {}
    counts: Dict[str, Counter] = {}
    claimed: Set[int] = set(covered)
    pointers = pointer_index(rom)
    for key, stem, text in source_texts(decomp):
        found: Counter = Counter()
        version_file = VERSION_FILE.search(stem)
        if version_file and VERSION_OF[version_file.group(1)] != variant.upper():
            # a file named for another version (pokedex_text_lg.h) is included under a guard this reader does not follow
            reasons = ["other_version"] * (text.count("\n") + 1)
        else:
            reasons = conditional_reasons(text, variant, revision)
        for match in LITERAL.finditer(text):
            raw = "".join(PIECE.findall(match.group(1)))
            shown = editor_text(raw)
            why = reasons[text.count("\n", 0, match.start())]
            if why == "other_language":
                tally(found, residue, key, text, match, shown, "other_language")
                continue
            if shown == "":
                tally(found, residue, key, text, match, shown, "empty")
                continue
            try:
                expected = charmap.encode(shown)
            except rom_text.CodecError:
                tally(found, residue, key, text, match, shown, "nocell")
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
                while spot >= 0 and len(hits) < MAX_HITS:
                    hits.append(spot)
                    spot = rom.find(expected, spot + 1)
                if not re.search(r"\w", CONTROL.sub("", shown)):
                    # spaces and control codes found by their bytes: a fill, not a text (it matches many places)
                    tally(found, residue, key, text, match, shown, "fill")
                    continue
                # a place another literal has claimed is covered; a place still free is opened (a text placed twice)
                if hits and all(any(i in claimed for i in range(h, h + len(expected))) for h in hits):
                    tally(found, residue, key, text, match, shown, "covered")
                    continue
                if not hits:
                    tally(found, residue, key, text, match, shown, missing_class(why, shown))
                    continue
                # A start is a byte after a terminator, or a place a pointer names: a text may follow data.
                starts = [h for h in hits if h == 0 or rom[h - 1] in (0x00, TERMINATOR)
                          or BASE + h in pointers]
                if not starts:
                    # One place in the image, after data: a text the code reads by its address (an inline field).
                    if len(hits) != 1 or len(expected) <= 2:
                        tally(found, residue, key, text, match, shown, "not_a_start")
                        continue
                    starts = hits
                if len(expected) <= SHORT and len(starts) > 1 and not TEXT_PIECE.search(shown):
                    # A short piece of code output (a control code, a space): not text, not opened.
                    tally(found, residue, key, text, match, shown, "fragment")
                    continue
                if len(starts) > 1:
                    # the same text in several places: one unit holds every place the code has not claimed (the
                    # first free place is the unit, the others are its places: one edit writes them all)
                    line = text.count(chr(10), 0, match.start()) + 1
                    free = [spot for spot in starts if not any(i in claimed for i in range(spot, spot + len(expected)))]
                    if not free:
                        tally(found, residue, key, text, match, shown, "covered")
                        continue
                    label = f"{stem}_L{line}_{len(units.get(key, []))}"
                    units.setdefault(key, []).append([label, free[0], len(expected), "", free[1:]])
                    for spot in free:
                        claimed.update(range(spot, spot + len(expected)))
                    tally(found, residue, key, text, match, shown, "duplicate")
                    continue
                at = starts[0]
            if any(i in claimed for i in range(at, at + len(expected))):
                tally(found, residue, key, text, match, shown, "covered")
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
    parser.add_argument("--nm", type=Path, help="arm-none-eabi-nm output of the build: local symbols too")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    text = args.facts.read_text(encoding="utf-8")
    facts = json.loads(text)
    if hashlib.sha1(rom).hexdigest() != facts["rom_sha1"]:
        raise SystemExit("this ROM is not the one the facts file was made from")
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts["charmap"])
    symbols = map_symbols(args.map)[0]
    if args.nm:
        symbols.update(nm_symbols(args.nm)[0])     # static arrays are local symbols: nm lists them
    game = facts["game"]
    rev = re.search(r"\brev (\d)", game, re.I)
    revision = int(rev.group(1)) if rev else 0
    variant = next((name for name in VARIANTS if name.lower() in game.lower().replace(" ", "")), "")
    units, counts = scan(args.decomp, rom, charmap, symbols, covered_offsets(facts), variant, None, revision)
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
