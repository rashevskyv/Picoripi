"""Write the ROM facts of one Pokemon Red, Blue or Yellow image for plugins/pokemon_gen1/rom_facts/.

Facts are addresses, charmap values, sizes and reference sites. They come from the decompilation (text files and
the charmap), the symbol and map files of its build, and the ROM itself. Every text body is checked before the file
is written, and the tool stops on the first mismatch:

- the body's macro lines encode to exactly the ROM bytes at its label;
- decoding those bytes gives the same editor text as the decompilation (the same ``asm_text.texts``);
- the number of ``text_far`` references found in the ROM equals the number in the decompilation.

Usage: python tools/pokemon_gen1_rom_facts.py <build name> <decomp dir> <sym> <map> <rom> <out json>
Example: python tools/pokemon_gen1_rom_facts.py pokered "<decomp>" pokered.sym pokered.map "<ROM>" out.json
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from plugins.common.gb_rom import BANK_SIZE, offset_of  # noqa: E402
from plugins.pokemon_gen1 import asm_text  # noqa: E402
from plugins.pokemon_gen1 import rom_text  # noqa: E402

TEXT_ASM = 0x08
FAR_OPCODE = 0x17
CHARMAP_LINE = re.compile(r'^\s*charmap\s+"((?:[^"\\]|\\.)*)"\s*,\s*\$([0-9A-Fa-f]{2})')
SYM_LINE = re.compile(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4}) (\S+)$")
SECTION_LINE = re.compile(r"^\s*SECTION: \$([0-9a-f]{4})-\$([0-9a-f]{4}) ", re.I)
BANK_LINE = re.compile(r"^(ROM0|ROMX) bank #(\d+):")


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


def read_sym(path: Path):
    """``(rom_labels, ram_labels)``: name -> (bank, cpu) for ROM labels, name -> address for WRAM labels."""
    rom_labels, ram_labels = {}, {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = SYM_LINE.match(line)
        if not match:
            continue
        bank, addr, name = int(match.group(1), 16), int(match.group(2), 16), match.group(3)
        if 0xC000 <= addr < 0xE000 or 0xFF80 <= addr <= 0xFFFE:
            ram_labels.setdefault(name, addr)
        elif addr < 0x8000:
            rom_labels.setdefault(name, (bank, addr))
    return rom_labels, ram_labels


def read_free_runs(path: Path, rom: bytes):
    """Free runs ``[bank, start, end)`` of the switchable and fixed windows, from the map's SECTION lines."""
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
        cpu_low = low
        offset_low = offset_of(bank, cpu_low)
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


def far_reference_sites(rom: bytes, offset_of_label: dict) -> dict:
    """Operand sites of every ``text_far`` (opcode 0x17 + address + bank) in the ROM, keyed by (bank, cpu)."""
    sites: dict = {}
    at = rom.find(bytes([FAR_OPCODE]))
    while at >= 0:
        cpu = rom[at + 1] | rom[at + 2] << 8
        bank = rom[at + 3] if at + 3 < len(rom) else -1
        sites.setdefault((bank, cpu), []).append(at + 1)
        at = rom.find(bytes([FAR_OPCODE]), at + 1)
    return sites


def pret_far_counts(decomp: Path) -> Counter:
    counts: Counter = Counter()
    for path in decomp.rglob("*.asm"):
        if "text_far" not in path.read_text(encoding="utf-8", errors="replace"):
            continue
        for match in re.finditer(r"text_far\s+([A-Za-z_][\w.]*)", path.read_text(encoding="utf-8", errors="replace")):
            counts[match.group(1)] += 1
    return counts


def main(argv: list) -> int:
    if len(argv) != 7:
        print(__doc__)
        return 2
    build, decomp_text, sym_text, map_text, rom_text_path, out_text = argv[1:]
    decomp, sym_path, map_path, rom_path, out_path = (Path(p) for p in (decomp_text, sym_text, map_text, rom_text_path, out_text))
    rom = rom_path.read_bytes()
    rom_labels, ram_labels = read_sym(sym_path)
    charmap = read_charmap(decomp)
    everything = rom_text.Names(charmap, ram_labels, rom_labels)

    files = []
    all_labels = {}
    total_bytes = 0
    for path in sorted((decomp / "text").glob("*.asm")):
        source = path.read_text(encoding="utf-8")
        groups = rom_text.read_labels(source)
        rel = f"text/{path.name}"
        entries = []
        for label, lines in groups:
            if not label:
                fail(f"{rel}: lines without a label")
            if label not in rom_labels:
                fail(f"{label} is not in the symbol file")
            bank, cpu = rom_labels[label]
            offset = offset_of(bank, cpu)
            try:
                data = rom_text.encode(lines, everything)
            except rom_text.CodecError as error:
                fail(f"{rel} {label}: {error}")
            if rom[offset:offset + len(data)] != data:
                fail(f"{rel} {label}: the decompilation does not encode to the ROM bytes at {offset:#x}")
            bcd_args = [args for word, args in lines if word == "text_bcd"]
            bcd_hex = [index for index, args in enumerate(bcd_args) if "|" not in args]
            entries.append({"label": label, "offset": offset, "size": len(data),
                           "fixed": bool(data) and data[-1] == TEXT_ASM, "lines": lines, "bcd_hex": bcd_hex})
            all_labels[label] = (bank, cpu)
            total_bytes += len(data)
        files.append((rel, entries, source))

    # Names used by the text (the runtime keeps only these).
    used_ram, used_far = {}, {}
    for _rel, entries, _source in files:
        for entry in entries:
            for word, args in entry["lines"]:
                if word in rom_text.COMMAND_BY_NAME and word != "text_far":
                    for token in re.findall(r"[A-Za-z_]\w*", args):
                        if token in ram_labels:
                            used_ram[token] = ram_labels[token]
                if word == "text_far":
                    name = args.strip()
                    used_far[name] = all_labels.get(name, rom_labels.get(name))

    runtime = rom_text.Names(charmap, used_ram, used_far)
    far_hits = far_reference_sites(rom, {})
    far_pret = pret_far_counts(decomp)
    mismatch_far = []
    out_files = []
    for rel, entries, source in files:
        decoded_source = []
        for entry in entries:
            region = rom[entry["offset"]:entry["offset"] + entry["size"]]
            lines = rom_text.decode(region, runtime, entry["bcd_hex"])
            if rom_text.encode(lines, runtime) != region:
                fail(f"{rel} {entry['label']}: decode then encode is not the same bytes")
            decoded_source.append(rom_text.format_body(entry["label"], lines))
            bank, cpu = rom_labels[entry["label"]]
            hits = far_hits.get((bank, cpu), [])
            if len(hits) != far_pret.get(entry["label"], 0):
                mismatch_far.append((entry["label"], len(hits), far_pret.get(entry["label"], 0)))
            entry["far"] = hits
        mine, theirs = asm_text.texts("\n".join(decoded_source)), asm_text.texts(source)
        if mine != theirs:
            pairs = [(a, b) for a, b in zip(mine, theirs) if a != b][:3]
            fail(f"{rel}: decoded text differs (counts {len(mine)} vs {len(theirs)}): {pairs}")
        out_files.append({"file": rel, "labels": [
            {key: value for key, value in entry.items() if key != "lines" and (key != "bcd_hex" or value)}
            for entry in entries]})

    if mismatch_far:
        fail(f"text_far counts differ (label, rom, decomp): {mismatch_far[:10]} ({len(mismatch_far)} labels)")

    gaps = read_free_runs(map_path, rom)
    facts = {
        "build_name": build,
        "rom_sha1": hashlib.sha1(rom).hexdigest(),
        "rom_size": len(rom),
        "charmap": charmap,
        "ram": used_ram,
        "far": {name: list(place) for name, place in used_far.items() if place},
        "files": out_files,
        "gaps": gaps,
    }
    out_path.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    labels = sum(len(item["labels"]) for item in out_files)
    print(f"OK {build}: {len(out_files)} files, {labels} bodies, {total_bytes} text bytes,"
          f" {len(gaps)} free runs ({sum(end - start for _b, start, end, _p in gaps)} bytes), {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
