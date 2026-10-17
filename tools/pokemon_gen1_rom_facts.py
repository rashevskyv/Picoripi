"""Write the ROM facts of one Pokemon Red, Blue or Yellow image for plugins/pokemon_gen1/rom_facts/.

Facts are addresses, charmap values, sizes and reference sites. They come from the decompilation (the text and name
files, the charmap and the constants), the symbol and map files of its build, and the ROM itself. Every body is checked
before the file is written, and the tool stops on the first mismatch:

- the body's macro lines encode to exactly the ROM bytes at its label;
- decoding those bytes gives the same editor text as the decompilation (the same ``asm_text.texts``);
- the number of ``text_far`` references found in the ROM equals the number in the decompilation.

Bodies are the text files (``text/*.asm``) and the name tables (``data/**.asm`` with ``dname`` or ``li`` lines).

Usage: python tools/pokemon_gen1_rom_facts.py <build name> <decomp dir> <sym> <map> <rom> <out json>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from plugins.common.gb_rom import BANK_SIZE, offset_of  # noqa: E402
from plugins.pokemon_gen1 import asm_text  # noqa: E402
from plugins.pokemon_gen1 import rom_text  # noqa: E402

TEXT_ASM = 0x08
FAR_OPCODE = 0x17
GEN2_BUILDS = {"pokegold", "pokesilver", "pokecrystal", "pokecrystal11"}
CHARMAP_LINE = re.compile(r'^\s*charmap\s+"((?:[^"\\]|\\.)*)"\s*,\s*\$([0-9A-Fa-f]{2})')
SYM_LINE = re.compile(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4}) (\S+)$")
SECTION_LINE = re.compile(r"^\s*SECTION: \$([0-9a-f]{4})-\$([0-9a-f]{4}) ", re.I)
BANK_LINE = re.compile(r"^(ROM0|ROMX) bank #(\d+):")
DEF_LINE = re.compile(r"^\s*DEF\s+(\w+)\s+EQU\s+([^;]+?)\s*(?:;.*)?$")
# Files the facts do not cover yet: their bodies are built by code macros (FOR loops), not by text.
EXCLUDED_DATA = set()
# Folders of the decompilation that never hold text bodies.
SKIP_DIRS = {"constants", "macros", "tools", "docs", "vc", "ram", "gfx", "audio", "lib", "scripts_skip"}
# Macro words that belong to a text body (a label's leading text is encoded; the first other line ends it).
BODY_WORDS = (set(rom_text.FLOW_CODE) | set(rom_text.TERMINATOR) | set(rom_text.COMMAND_BY_NAME)
              | set(rom_text.GEN2_COMMAND_BY_NAME)
              | {"db", "dname", "li", "table_width", "list_start", "vc_patch", "vc_patch_end", "text_asm"})
# Yellow: these bodies are referenced only by debug-only or unused code (not in the normal ROM); no reference exists.
FAR_ABSENT_OK = {"_BoxFullDebugText", "_BoxWillBeClearedText", "_ExpressionText"}
# Gold: the ROM holds a 4-byte text_far pattern that points at this label by chance (no text_far names it). The label
# is referenced from code, so it never moves and the extra hit cannot be rewritten.
FAR_COINCIDENCE_OK = {"PCCharText"}
DEFINITION = re.compile(r"^[A-Za-z_][\w.]*::?\s*$")
NAME_LINE = re.compile(r'^\s+(li|dname)\s+"')
# A string the code or a table builds: ``db "...@"``, with or without a label on the same line.
DB_LINE = re.compile(r'^(\s+|[A-Za-z_.][\w.]*:+\s+)db\s+(-?\$?\w+\s*,\s*)?"[^"]*@"')
TEXT_LINE = re.compile(r'^\s+(text|line|cont|para|next|page|done|prompt|dex|text_end)\b')


def fail(message: str) -> None:
    print("FAIL:", message)
    raise SystemExit(1)


def read_charmap(decomp: Path) -> list:
    """The charmap entries. Where two entries share a byte, the one the text uses most comes first: it is shown."""
    out = []
    for line in (decomp / "constants" / "charmap.asm").read_text(encoding="utf-8").splitlines():
        match = CHARMAP_LINE.match(line)
        if match:
            out.append([match.group(1).replace('\\"', '"').replace("\\\\", "\\"), int(match.group(2), 16)])
    text = "\n".join(p.read_text(encoding="utf-8") for p in (decomp / "text").glob("*.asm"))
    out.sort(key=lambda entry: -text.count(entry[0]))
    return out


def read_constants(decomp: Path) -> dict:
    """``DEF NAME EQU expr`` lines of the constants folder, as text (evaluated on use)."""
    defs = {}
    for path in (decomp / "constants").glob("*.asm"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = DEF_LINE.match(line)
            if match:
                defs.setdefault(match.group(1), match.group(2))
    return defs


def evaluate(expr: str, defs: dict, depth: int = 0) -> int:
    """A constant expression of digits, names and + - * / ( ). Names come from the constants folder."""
    if depth > 20:
        fail(f"constant loop at {expr}")
    text = re.sub(r"[A-Za-z_]\w*", lambda m: f"({evaluate(defs[m.group(0)], defs, depth + 1)})"
                  if m.group(0) in defs else fail(f"unknown constant {m.group(0)} in {expr}") or "0", expr.strip())
    if not re.fullmatch(r"[\d\s+\-*/()]+", text):
        fail(f"cannot evaluate {expr}")
    return int(eval(text, {"__builtins__": {}}, {}))  # digits and operators only, checked above


def read_free_runs(path: Path, rom: bytes):
    """Free runs ``[bank, start, end, pad]`` of the switchable and fixed windows, from the map's SECTION lines."""
    bank_kind, bank_no = None, None
    used = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        header = BANK_LINE.match(line)
        if header:
            bank_kind, bank_no = header.group(1), int(header.group(2))
            continue
        section = SECTION_LINE.match(line)
        if section and bank_kind:
            used.setdefault((bank_kind, bank_no), []).append((int(section.group(1), 16), int(section.group(2), 16)))
    runs = []
    for (kind, bank), spans in sorted(used.items(), key=lambda item: (item[0][0] != "ROM0", item[0][1])):
        low, high = (0x0000, 0x4000) if kind == "ROM0" else (0x4000, 0x8000)
        cursor = low
        for start, end in sorted(spans):
            if start > cursor:
                runs.append((bank, cursor, start))
            cursor = max(cursor, end + 1)
        if cursor < high:
            runs.append((bank, cursor, high))
    out = []
    for bank, low, high in runs:
        offset_low = offset_of(bank, low)
        offset_high = offset_of(bank, high - 1) + 1
        if offset_high - offset_low < 16:
            continue
        pad = set(rom[offset_low:offset_high])
        if len(pad) == 1:
            out.append([bank, offset_low, offset_high, pad.pop()])
    # Switchable banks the linker never used are whole free banks when they hold one repeated byte.
    listed = {bank for kind, bank in used if kind == "ROMX"}
    for bank in range(1, len(rom) // BANK_SIZE):
        if bank in listed:
            continue
        start = offset_of(bank, BANK_SIZE)
        chunk = rom[start:start + BANK_SIZE]
        if len(set(chunk)) == 1:
            out.append([bank, start, start + BANK_SIZE, chunk[0]])
    return out


def far_reference_sites(rom: bytes, far_opcode: int = FAR_OPCODE) -> dict:
    """Operand sites of every ``text_far`` (opcode 0x17 + address + bank) in the ROM, keyed by (bank, cpu)."""
    sites: dict = {}
    at = rom.find(bytes([far_opcode]))
    while at >= 0:
        cpu = rom[at + 1] | rom[at + 2] << 8
        bank = rom[at + 3] if at + 3 < len(rom) else -1
        sites.setdefault((bank, cpu), []).append(at + 1)
        at = rom.find(bytes([far_opcode]), at + 1)
    return sites


def other_reference_counts(decomp: Path) -> Counter:
    """How often each identifier appears in code, outside text_far lines and label definitions.

    A text body with no such mention is referred to only by text_far: it may move.
    """
    counts: Counter = Counter()
    for path in decomp.rglob("*.asm"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            code = asm_text.split_comment(line)[0]
            if "text_far" in code or DEFINITION.match(code):
                continue
            counts.update(re.findall(r"[A-Za-z_][\w.]*", code))
    return counts


def pret_far_counts(decomp: Path) -> Counter:
    counts: Counter = Counter()
    for path in decomp.rglob("*.asm"):
        source = path.read_text(encoding="utf-8", errors="replace")
        if "text_far" not in source:
            continue
        for match in re.finditer(r"text_far\s+([A-Za-z_][\w.]*)", source):
            counts[match.group(1)] += 1
    return counts


def name_files(decomp: Path) -> list:
    """The data files with name tables (``li`` or ``dname`` entries) or text macros, in path order."""
    found = []
    for path in sorted(p for p in decomp.rglob("*.asm") if p.relative_to(decomp).parts[0] not in SKIP_DIRS | {"text"}):
        if path.relative_to(decomp).as_posix() in EXCLUDED_DATA:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if any(NAME_LINE.match(line) or TEXT_LINE.match(line) or DB_LINE.match(line) for line in lines):
            found.append(path)
    return found


# The version macro of each build: ``IF DEF(_RED)`` keeps the Red branch and drops the other.
VERSION_MACRO = {"pokered": "_RED", "pokeblue": "_BLUE", "pokeyellow": "_YELLOW", "pokegold": "_GOLD",
                 "pokesilver": "_SILVER"}


def _condition(stripped: str, defines) -> Optional[bool]:
    """The value of an ``IF`` line for this build, or None when the tool does not evaluate it."""
    match = re.match(r"IF\s+DEF\((\w+)\)\s*$", stripped)
    if match:
        return match.group(1) in defines
    if re.match(r"IF\b.*_VC", stripped):          # the Virtual Console build is never this one
        return False
    return None


def _live(stack) -> bool:
    """True when every known frame shows its branch: the IF branch unless ELSE is set."""
    for frame in stack:
        if frame["cond"] is not None and frame["cond"] == frame["else"]:
            return False
    return True


def normal_build(source: str, defines=frozenset()) -> str:
    """The source as this build sees it: conditionals that depend on the version or the VC build are resolved.
    Other conditionals are kept as written (their lines show up as an unknown macro)."""
    out, stack = [], []
    for line in source.splitlines():
        stripped = line.strip()
        word = stripped.split(None, 1)[0] if stripped else ""
        if word == "IF":
            cond = _condition(stripped, defines)
            stack.append({"cond": cond, "else": False})
            if cond is None and _live(stack[:-1]):
                out.append(line)
            continue
        if word == "ELSE" and stack:
            stack[-1]["else"] = True
            if stack[-1]["cond"] is None and _live(stack[:-1]):
                out.append(line)
            continue
        if word == "ENDC" and stack:
            frame = stack.pop()
            if frame["cond"] is None and _live(stack):
                out.append(line)
            continue
        if stripped.startswith("vc_patch") or not _live(stack):
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def ram_arguments(lines, everything, runtime) -> list:
    """The RAM names the body's commands use, in order, when the address alone would give another name (aliases)."""
    names = []
    for word, args in lines:
        code = everything.command_by_name.get(word)
        if code is None or "ram" not in everything.commands[code][1]:
            continue
        name = args.split(",")[0].strip()
        names.append(name)
    if all(runtime.ram_name.get(everything.ram.get(name)) == name for name in names):
        return []
    return names


# ``db -6, "NAME@"``: a number byte before the text (a credit's line type). The charmap shows it as a digit cell.
NUMERIC_LEAD = re.compile(r'^-?\$?[0-9A-Fa-f]+\s*,\s*"')


def text_prefix(lines):
    """The leading text macros of a label. ``text_asm`` ends the text: the code after it is not text."""
    out = []
    for index, (word, args) in enumerate(lines):
        if word == "text_far" or (word not in BODY_WORDS and not word.startswith("assert")):
            break
        if word == "db" and not args.startswith('"'):     # ``db 6,3``: the numbers after a name are not text
            if not (index == 0 and NUMERIC_LEAD.match(args)):
                break
        out.append((word, args))
        if word == "text_asm":
            break
    return out


def body_mode(lines, defs):
    """``(mode, width)`` of a body: a name table has a mode; a text body has none."""
    words = [word for word, _args in lines]
    if "dname" in words:
        width = next((evaluate(args, defs) for word, args in lines if word == "table_width"), 0)
        return "dname", width
    if "li" in words:
        return "li", 0
    return "", 0


def numeric_lead(lines) -> bool:
    return bool(lines) and lines[0][0] == "db" and NUMERIC_LEAD.match(lines[0][1]) is not None


def encodable(lines, names, width: int) -> bool:
    try:
        rom_text.encode(lines, names, width)
    except rom_text.CodecError:
        return False
    return True


# Characters the text census counts as text (the printable ones, and the game's own two-character cells).
RUN_CHARS = set(" !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]abcdefghijklmnopqrstuvwxyz"
                ) | {"é", "'d", "'l", "'s", "'t", "'v", "'r", "'m", "♂", "♀", "▷", "▶", "▼", "×", "¥", "’", "‘", "“",
                     "”", "…", "·", "→", "←", "ぃ"}
# Runs the census reads as letters that are picture or tile data (their bytes spell letters by chance), by build.
GRAPHICS_RUNS = {
    "pokered": {0x321B3: "Muk back picture", 0x33D02: "Starmie front picture", 0x41BB2: "intro graphics"},
    "pokeyellow": {0xE9BD4: "Diploma Mew tilemap (INCBIN)"},
}


def text_runs(rom: bytes, charmap) -> List[Tuple[int, int]]:
    """``[(start, end)]`` of the text runs of the ROM: four or more letters, ended by a terminator (the census rule)."""
    chars = {}
    for token, code in charmap:
        if token in RUN_CHARS:
            chars.setdefault(int(code), token)
    chars[0x50] = "@"
    terms, flow = {0x50, 0x57, 0x58}, {0x4E, 0x4F, 0x51, 0x55, 0x49}
    runs, i, n = [], 0, len(rom)
    while i < n:
        if rom[i] in chars and rom[i] != 0x50:
            j = i
            while j < n and ((rom[j] in chars and rom[j] not in terms) or rom[j] in flow) and rom[j] != 0x50:
                j += 1
            if j < n and rom[j] in terms:
                letters = sum(1 for k in range(i, j) if rom[k] in chars and chars[rom[k]].isalpha())
                if letters >= 4 and j - i >= 5:
                    runs.append((i, j + 1))
                i = j + 1
                continue
            i = max(j, i + 1)
        else:
            i += 1
    return runs


def unlabelled_text_bodies(rom: bytes, out_files: list, names, charmap, build: str, used_ram: dict, used_far: dict,
                           rom_labels: dict) -> list:
    """Text runs of the ROM that no kept labelled body covers, as bodies read from the ROM bytes.

    The decompilation builds these with macros (FOR loops, constants) the tool does not expand, so their lines come
    from the ROM. The bytes must still decode and encode back to the same ROM bytes. A body like this cannot move:
    its size is its budget. The RAM and far names the new bodies use are added to ``used_ram`` and ``used_far``.
    """
    covered = sorted((body["offset"], body["offset"] + body["size"]) for item in out_files for body in item["labels"])
    graphics = GRAPHICS_RUNS.get(build, {})
    groups: Dict[int, list] = {}
    for run_start, run_end in text_runs(rom, charmap):
        if run_start in graphics:
            continue
        # A kept body may cover the start or the end of the run: only the part it does not cover is new text.
        start, end = run_start, run_end
        for low, high in covered:
            if low < end and start < high:
                if low <= start:
                    start = high
                elif high >= end:
                    end = low
                else:
                    start = end = run_start      # covered in the middle: the run stays as the body that covers it
                    break
        if end - start < 2:
            continue
        region = rom[start:end]
        lines = rom_text.decode(region, names, (), (), False)
        if rom_text.encode(lines, names) != region:
            continue
        for word, args in lines:
            if word == "text_far":
                used_far[args.strip()] = rom_labels.get(args.strip())
            elif word in names.command_by_name and word != "text_far":
                for token in re.findall(r"[A-Za-z_]\w*", args):
                    if token in names.ram:
                        used_ram[token] = names.ram[token]
        groups.setdefault(start // BANK_SIZE, []).append({
            "label": f"RomText_{start:05x}", "offset": start, "size": len(region), "fixed": False,
            "bcd_hex": [], "movable": False, "far": [], "rom": True})
    return [{"file": f"rom_text/bank_{bank:02x}.asm", "labels": entries} for bank, entries in sorted(groups.items())]


# Ukrainian letters on the font sheet of the game's plugin (font_sources.json). The font's tile codes start at 0x80,
# one per cell in the sheet's order. A letter the sheet has keeps its own cell; a Cyrillic letter that looks like a
# Latin one takes the Latin cell; the rest take the cells the decision names (a cell whose English glyph the
# translator draws over). These entries come after the game's own, so a byte still reads as the English it is.
UA_LETTERS = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
UA_LOOKALIKE = {"А": "A", "В": "B", "Е": "E", "І": "I", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C",
                "Т": "T", "Х": "X", "а": "a", "е": "e", "і": "i", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x"}
UA_TARGETS_GEN1 = {"ґ": "'d", "є": "'l", "ж": "'s", "й": "'t", "ї": "'v", "ф": "'r", "ц": "'m", "ч": "é", "ш": "¥",
                   "щ": "×", "ю": "<DOT>"}
UA_TARGETS_GEN2 = {"Б": "D", "Г": "F", "Ґ": "G", "Д": "J", "Є": "L", "Ж": "N", "З": "Q", "И": "R", "Ї": "S", "Й": "U",
                   "Л": "V", "П": "W", "У": "Y", "Ф": "Z", "Ц": "Ä", "Ч": "Ö", "Ш": "Ü", "Щ": "d", "Ь": "f", "Ю": "g",
                   "Я": "h", "ґ": "k"}
FONT_BASE = 0x80


def ukrainian_cells(charmap: list, font_sources: Path, gen2: bool) -> list:
    """The game's charmap with the Ukrainian letters appended (see UA_TARGETS_*)."""
    chars = json.loads(font_sources.read_text(encoding="utf-8"))[0]["params"]["chars"]
    index = {label: i for i, label in enumerate(chars)}
    code_of: dict = {}
    for token, code in charmap:
        code_of.setdefault(token, int(code))
    targets = UA_TARGETS_GEN2 if gen2 else UA_TARGETS_GEN1
    extra = []
    for letter in UA_LETTERS:
        if letter in code_of:
            continue
        if letter in index:
            code = FONT_BASE + index[letter]
        elif letter in UA_LOOKALIKE:
            code = code_of[UA_LOOKALIKE[letter]]
        elif letter in targets:
            code = FONT_BASE + index[targets[letter]]
        else:
            continue
        extra.append([letter, code])
    # The charmap's Japanese tokens share some of these codes (0xC0 is a katakana in the Japanese text table). A byte
    # reads as its first entry, so the Ukrainian entries go before the Japanese ones and after the English ones.
    first_japanese = next((i for i, (token, _code) in enumerate(charmap) if any(is_japanese(ch) for ch in token)),
                          len(charmap))
    return list(charmap[:first_japanese]) + extra + list(charmap[first_japanese:])


def is_japanese(char: str) -> bool:
    """A kana, a CJK or a half-width katakana character."""
    return 0x3000 <= ord(char) <= 0x9FFF or 0xFF61 <= ord(char) <= 0xFF9F


IDENT = re.compile(r"[A-Za-z_][\w.]*")
DW_ARGS = re.compile(r"^\s+dw\s+(.*)$")
TABLE_HEAD = re.compile(r"^\s+(table_width|assert_table_length|list_start)\b")


def dw_reference_counts(decomp: Path) -> Counter:
    """How often each identifier is a ``dw`` argument (a pointer-table entry) in the decompilation."""
    counts: Counter = Counter()
    for path in decomp.rglob("*.asm"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = DW_ARGS.match(asm_text.split_comment(line)[0])
            if match:
                counts.update(arg.strip() for arg in match.group(1).split(",") if IDENT.fullmatch(arg.strip()))
    return counts


def table_pointer_sites(rom: bytes, decomp: Path, rom_labels: dict) -> Dict[str, List[int]]:
    """ROM offsets of the pointer-table entries that hold a label's address, by label.

    A table is a global label followed by ``dw`` lines; the argument k of the table sits at the table's offset plus
    2k. Each site is checked against the ROM bytes (the label's CPU address, little endian), so a wrong position
    never counts. Anything but ``dw`` lines ends the table.
    """
    sites: Dict[str, List[int]] = {}
    for path in sorted(decomp.rglob("*.asm")):
        table, index = None, 0
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            code = asm_text.split_comment(line)[0]
            stripped = code.strip()
            if not stripped:
                continue
            if not code[0].isspace() and DEFINITION.match(code):
                name = stripped.rstrip(":")
                table, index = (name if name in rom_labels else None), 0
                continue
            if TABLE_HEAD.match(code):
                continue
            match = DW_ARGS.match(code)
            if not match or table is None:
                table = None
                continue
            bank, cpu = rom_labels[table]
            base = offset_of(bank, cpu)
            for arg in match.group(1).split(","):
                arg = arg.strip()
                if IDENT.fullmatch(arg) and arg in rom_labels:
                    site = base + 2 * index
                    _lbank, lcpu = rom_labels[arg]
                    if rom[site:site + 2] == bytes([lcpu & 0xFF, lcpu >> 8]):
                        sites.setdefault(arg, []).append(site)
                index += 1
    return sites


def main(argv: list) -> int:
    if len(argv) != 7:
        print(__doc__)
        return 2
    build, decomp_text, sym_text, map_text, rom_text_path, out_text = argv[1:]
    decomp, sym_path, map_path, rom_path, out_path = (Path(p) for p in (decomp_text, sym_text, map_text,
                                                                         rom_text_path, out_text))
    rom = rom_path.read_bytes()
    rom_labels, ram_labels = {}, {}
    for line in sym_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = SYM_LINE.match(line)
        if not match:
            continue
        bank, addr, name = int(match.group(1), 16), int(match.group(2), 16), match.group(3)
        if 0xC000 <= addr < 0xE000 or 0xFF80 <= addr <= 0xFFFE:
            ram_labels.setdefault(name, addr)
        elif addr < 0x8000:
            rom_labels.setdefault(name, (bank, addr))
    charmap = read_charmap(decomp)
    defs = read_constants(decomp)
    gen2 = build in GEN2_BUILDS
    font_sources = REPO / ("plugins/pokemon_gsc" if gen2 else "plugins/pokemon_gen1") / "font_sources.json"
    charmap = ukrainian_cells(charmap, font_sources, gen2)
    defines ={VERSION_MACRO[build]} if build in VERSION_MACRO else set()
    everything = rom_text.Names(charmap, ram_labels, rom_labels, gen2)

    sources = sorted((decomp / "text").glob("*.asm")) + name_files(decomp)
    files = []
    all_labels = {}
    skipped = []
    total_bodies = total_bytes = 0
    for path in sources:
        source = normal_build(path.read_text(encoding="utf-8"), defines)
        groups = rom_text.read_labels(source)
        rel = path.relative_to(decomp).as_posix()
        entries = []
        parent = ""
        for label, lines in groups:
            if label and not label.startswith(".") and label in rom_labels:
                parent = label      # a global label owns the local labels after it, even when it holds code
            lines = text_prefix(lines)
            if not lines:
                continue
            if not label:
                continue
            if label.startswith(".") and parent + label in rom_labels:
                label = parent + label      # a local label: the symbol file names it after its global label
            if label not in rom_labels:
                if rel.startswith("text/"):
                    fail(f"{label} is not in the symbol file")
                skipped.append((rel, label, "not in the symbol file"))
                continue    # a local label inside code: no body of its own
            mode, width = body_mode(lines, defs)
            bank, cpu = rom_labels[label]
            offset = offset_of(bank, cpu)
            # In text/ every body must check; elsewhere a label that is code or unsupported is not a body.
            strict = rel.startswith("text/")
            try:
                data = rom_text.encode(lines, everything, width)
            except rom_text.CodecError as error:
                if strict:
                    fail(f"{rel} {label}: {error}")
                skipped.append((rel, label, f"codec: {error}"))
                continue
            if not data:
                continue
            if rom[offset:offset + len(data)] != data:
                if strict:
                    fail(f"{rel} {label}: the decompilation does not encode to the ROM bytes at {offset:#x}")
                skipped.append((rel, label, "ROM bytes differ from the decompilation"))
                continue
            entry = {"label": label, "offset": offset, "size": len(data),
                     "fixed": bool(data) and data[-1] == TEXT_ASM, "lines": lines,
                     "bcd_hex": [i for i, a in enumerate([a for w, a in lines if w == "text_bcd"]) if "|" not in a]}
            if mode:
                entry["mode"], entry["width"] = mode, width
            entries.append(entry)
            all_labels[label] = (bank, cpu)
            total_bodies += 1
            total_bytes += len(data)
        files.append((rel, entries, source))

    # Names used by the text (the runtime keeps only these).
    used_ram, used_far = {}, {}
    for _rel, entries, _source in files:
        for entry in entries:
            for word, args in entry["lines"]:
                if word in everything.command_by_name and word != "text_far":
                    for token in re.findall(r"[A-Za-z_]\w*", args):
                        if token in ram_labels:
                            used_ram[token] = ram_labels[token]
                if word == "text_far":
                    name = args.strip()
                    used_far[name] = all_labels.get(name, rom_labels.get(name))

    runtime = rom_text.Names(charmap, used_ram, used_far, gen2)
    for _rel, entries, _source in files:
        for entry in entries:
            entry["ram_args"] = ram_arguments(entry["lines"], everything, runtime)
            last_word, last_args = entry["lines"][-1] if entry["lines"] else ("", "")
            # A string that ends in "@" inside its literal (``next "CANCEL@"``, ``db "CANCEL@"``) keeps the "@".
            entry["end_char"] = (last_word in rom_text.FLOW_CODE or last_word == "db") and last_args.endswith('@"')
    far_hits = far_reference_sites(rom, rom_text.GEN2_TX_FAR if gen2 else FAR_OPCODE)
    far_pret = pret_far_counts(decomp)
    other_refs = other_reference_counts(decomp)
    dw_pret = dw_reference_counts(decomp)
    pointer_sites = table_pointer_sites(rom, decomp, rom_labels)
    mismatch_far = []
    out_files = []
    for rel, entries, source in files:
        decoded_source = []
        for entry in entries:
            strict = rel.startswith("text/")
            region = rom[entry["offset"]:entry["offset"] + entry["size"]]
            if entry.get("mode"):
                lines = rom_text.decode_names(region, runtime, entry["mode"], entry["width"])
                same = rom_text.encode(lines, runtime, entry["width"]) == region
            else:
                try:
                    lines = rom_text.decode(region, runtime, entry["bcd_hex"], entry.get("ram_args", ()),
                                            entry.get("end_char", False))
                except IndexError:
                    if strict:
                        fail(f"{rel} {entry['label']}: a command runs past the body's {entry['size']} bytes")
                    entry["drop"] = True
                    skipped.append((rel, entry["label"], "a command runs past the body"))
                    continue
                same = rom_text.encode(lines, runtime) == region
            mine_texts = asm_text.texts(rom_text.format_body(entry["label"], lines))
            pret_texts = asm_text.texts(rom_text.format_body(entry["label"], entry["lines"]))
            # The text check needs the decompilation's text in the game's charmap. A number lead or a character the
            # charmap lacks (Japanese kana in a dead menu) leaves only the byte check, which still must hold.
            check_text = not numeric_lead(entry["lines"]) and encodable(entry["lines"], everything, entry.get("width", 0))
            if not same or (check_text and mine_texts != pret_texts):
                if strict:
                    fail(f"{rel} {entry['label']}: decoded text {mine_texts[:2]} differs from {pret_texts[:2]}")
                entry["drop"] = True
                skipped.append((rel, entry["label"], "decoded text differs"))
                continue
            decoded_source.append(rom_text.format_body(entry["label"], lines))
            if entry.get("rom"):          # no symbol and no text_far reference: the entry is fixed in place
                continue
            bank, cpu = rom_labels[entry["label"]]
            # Only a movable body is ever relocated, so only its text_far sites matter. A body that code or a table
            # names stays where it is, and a stray 0x17 byte that happens to hold its address is not a reference.
            label = entry["label"]
            table_refs = dw_pret[label]
            sites = pointer_sites.get(label, [])
            # A pointer table's ``dw`` entries are references too. The body moves only when every one of them is a
            # verified site (the entry's bytes hold the label's address), and it then stays in its own bank.
            entry["movable"] = other_refs[label] - table_refs == 0 and len(sites) == table_refs
            entry["pointers"] = sites if (entry["movable"] and table_refs) else []
            hits = far_hits.get((bank, cpu), []) if entry["movable"] else []
            expected = 0 if (entry["label"] in FAR_ABSENT_OK and not hits) else far_pret.get(entry["label"], 0)
            if expected == 0 and hits:
                hits = []     # the decompilation has no text_far to this body: these bytes only look like one
            if entry["movable"] and len(hits) != expected and entry["label"] not in FAR_COINCIDENCE_OK:
                mismatch_far.append((entry["label"], len(hits), far_pret.get(entry["label"], 0)))
            entry["far"] = hits
        entries = [entry for entry in entries if not entry.get("drop")]
        out_files.append({"file": rel, "labels": [
            {key: value for key, value in entry.items()
             if key not in ("lines",) and not (key in ("bcd_hex", "ram_args", "end_char", "movable", "pointers")
                                               and not value)}
            for entry in entries]})

    if mismatch_far:
        fail(f"text_far counts differ (label, rom, decomp): {mismatch_far[:10]} ({len(mismatch_far)} labels)")

    # Text no kept body covers (macro-built tables, dead menus): bodies read from the ROM bytes, fixed in size.
    out_files.extend(unlabelled_text_bodies(rom, out_files, everything, charmap, build, used_ram, used_far,
                                            rom_labels))
    gaps = read_free_runs(map_path, rom)
    facts = {
        "build_name": build,
        "rom_sha1": hashlib.sha1(rom).hexdigest(),
        "rom_size": len(rom),
        "profile": "gen2" if gen2 else "gen1",
        "charmap": charmap,
        "ram": used_ram,
        "far": {name: list(place) for name, place in used_far.items() if place},
        "files": out_files,
        "gaps": gaps,
    }
    if out_path.is_file():     # keep the font entry that tools/pokemon_gb_font_facts.py wrote
        previous = json.loads(out_path.read_text(encoding="utf-8"))
        if "font" in previous:
            facts["font"] = previous["font"]
    out_path.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    for rel, label, reason in skipped:
        print(f"  skipped {rel} {label}: {reason}")
    print(f"skipped {len(skipped)} labels outside text/")
    print(f"OK {build}: {len(out_files)} files, {total_bodies} bodies, {total_bytes} bytes,"
          f" {len(gaps)} free runs ({sum(end - start for _b, start, end, _p in gaps)} bytes), {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
