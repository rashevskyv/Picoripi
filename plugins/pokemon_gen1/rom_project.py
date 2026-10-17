"""ROM mode of the Pokemon Gen 1 plugin: unpack a Red, Blue or Yellow ROM into asm text, build a patched ROM from it.

The unpacked tree holds ``text/<file>.asm``, one file per decompilation text file, with one label per text body and
the body's macro lines. ``rom/`` beside it holds the base ROM and the facts it was unpacked with. A build writes only
the bodies that differ from the base ROM. A body that grows moves to free space, and its ``text_far`` references are
rewritten to the new place. A body that ends in ``text_asm`` is followed by code and cannot move.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from core.i18n import tr
from plugins.common.gb_rom import BANK_SIZE, FreeSpace, bank_of, cpu_of, fix_checksums
from plugins.pokemon_gen1 import asm_text, rom_text

ROM_ROLE = "rom"
SOURCE_DIR = "text"                       # the project's source root, inside the unpacked tree
ROM_DIR = "rom"                           # beside the source root
BASE_ROM = Path(ROM_DIR) / "base.gb"
META_FILE = Path(ROM_DIR) / "meta.json"
FACTS_DIR = Path(__file__).with_name("rom_facts")
OUTPUT_NAMES = {"pokered": "Pokemon Red (UA).gb", "pokeblue": "Pokemon Blue (UA).gb",
                "pokeyellow": "Pokemon Yellow (UA).gb", "pokegold": "Pokemon Gold (UA).gbc",
                "pokesilver": "Pokemon Silver (UA).gbc", "pokecrystal": "Pokemon Crystal (UA).gbc",
                "pokecrystal11": "Pokemon Crystal 1.1 (UA).gbc"}
HEADER = "; Written by Picoripi from the ROM. Edit the text between the quotes; keep the macro lines.\n"
Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def _facts_files(facts_dir: Path = FACTS_DIR) -> Dict[str, Dict[str, Any]]:
    """The facts files of this build, by file name. ``facts_dir`` lets another generation reuse this module."""
    return {path.name: json.loads(path.read_text(encoding="utf-8")) for path in sorted(facts_dir.glob("*.json"))}


def identify(path: str, facts_dir: Path = FACTS_DIR) -> Optional[Dict[str, str]]:
    """``{"role", "platform"}`` when the file is a ROM this build has facts for, else None. Reads the file once."""
    if not str(path).lower().endswith((".gb", ".gbc")):
        return None
    digest = hashlib.sha1()
    try:
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    except OSError:
        return None
    if any(item["rom_sha1"] == digest.hexdigest() for item in _facts_files(facts_dir).values()):
        return {"role": ROM_ROLE, "platform": "gb"}
    return None


def _facts_for(rom: bytes, facts_dir: Path = FACTS_DIR) -> Tuple[str, Dict[str, Any]]:
    digest = hashlib.sha1(rom).hexdigest()
    for name, facts in _facts_files(facts_dir).items():
        if facts["rom_sha1"] == digest:
            return name, facts
    raise ValueError(tr("This ROM is not a version the Pokemon plugin has text facts for."))


def unit_name(file: str) -> str:
    """The asm file a decompilation file unpacks to: its path with "/" replaced by "__" (names files repeat)."""
    return file.replace("/", "__")


def _names(facts: Dict[str, Any]) -> rom_text.Names:
    return rom_text.Names(facts["charmap"], facts["ram"], facts["far"], facts.get("profile") == "gen2")


def unpack(rom_path: str, target_dir: str, progress: Progress, is_cancelled: Cancelled,
           facts_dir: Path = FACTS_DIR) -> Optional[str]:
    """Write ``text/*.asm`` and ``rom/`` into ``target_dir``; returns ``target_dir`` (the host takes ``text``)."""
    rom = Path(rom_path).read_bytes()
    facts_name, facts = _facts_for(rom, facts_dir)
    names = _names(facts)
    target = Path(target_dir)
    (target / SOURCE_DIR).mkdir(parents=True, exist_ok=True)
    files = facts["files"]
    budgets: Dict[str, int] = {}
    for index, item in enumerate(files):
        if is_cancelled():
            return None
        bodies = []
        for body in item["labels"]:
            region = rom[body["offset"]:body["offset"] + body["size"]]
            if body.get("mode"):
                lines = rom_text.decode_names(region, names, body["mode"], body["width"])
            else:
                lines = rom_text.decode(region, names, body.get("bcd_hex", ()), body.get("ram_args", ()),
                                        body.get("end_char", False))
            if not body.get("movable"):
                budgets.update(_body_budgets(body, lines, names))
            bodies.append(rom_text.format_body(body["label"], lines))
        text = HEADER + "\n" + "\n".join(bodies)
        (target / SOURCE_DIR / unit_name(item["file"])).write_text(text, encoding="utf-8", newline="\n")
        progress(10 + 80 * (index + 1) // len(files), unit_name(item["file"]))
    (target / ROM_DIR).mkdir(parents=True, exist_ok=True)
    (target / BASE_ROM).write_bytes(rom)
    # The budgets and the names go into meta.json, so the editor's byte-budget check reads that small file only.
    (target / META_FILE).write_text(json.dumps({
        "facts": facts_name, "build_name": facts["build_name"], "budgets": budgets,
        "names": {"charmap": facts["charmap"], "ram": facts["ram"], "far": facts["far"],
                  "gen2": facts.get("profile") == "gen2"}}, ensure_ascii=False, indent=1), encoding="utf-8")
    progress(100, "Done")
    return str(target)


def read_budgets(meta_path: str) -> Optional[Tuple[Dict[str, int], rom_text.Names]]:
    """The byte budgets and the names that unpack wrote into ``rom/meta.json``; None for a project without them."""
    try:
        meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if "budgets" not in meta or "names" not in meta:
        return None
    names = meta["names"]
    return dict(meta["budgets"]), rom_text.Names(names["charmap"], names["ram"], names["far"], names["gen2"])


TERMINATOR_WORDS = {"done", "prompt", "text_end", "dex", "text_asm"}


def _body_budgets(body: Dict[str, Any], lines: Sequence[rom_text.Line], names: rom_text.Names) -> Dict[str, int]:
    """Byte budgets of a body that stays where it is. Keys are ``label#k``, k the unit's index in its body.

    A name field has its table's width. A list entry has its own length (its terminator included). A single text
    unit has its length without the terminator. A body with several text units gets no budget (their space is shared).
    """
    label = body["label"]
    if body.get("mode") == "dname":
        return {f"{label}#{k}": int(body["width"]) for k in range(len(lines))}
    if body.get("mode") == "li":
        return {f"{label}#{k}": rom_text.encoded_length([line], names) for k, line in enumerate(lines)}
    if len(asm_text.parse(rom_text.format_body(label, lines))[1]) != 1:
        return {}
    text = [line for line in lines if line[0] not in TERMINATOR_WORDS]
    return {f"{label}#0": rom_text.encoded_length(text, names)}


def _edited_bodies(text_dirs: Sequence[Path], facts: Dict[str, Any]) -> Dict[str, List[rom_text.Line]]:
    """The lines of every body, from the text folders (later folders win). A file with a missing body is refused."""
    found: Dict[str, List[rom_text.Line]] = {}
    for text_dir in text_dirs:
        for item in facts["files"]:
            path = text_dir / unit_name(item["file"])
            if not path.is_file():
                continue
            bodies = {label: lines for label, lines in rom_text.read_labels(path.read_text(encoding="utf-8"))}
            for body in item["labels"]:
                if body["label"] not in bodies:
                    raise ValueError(tr("{0} has no text body {1}; the ROM has it. Restore the label.",
                                        str(path), body["label"]))
                found[body["label"]] = bodies[body["label"]]
    return found


def build(source_dir: str, translation_dir: str, output_dir: str, progress: Progress,
          is_cancelled: Cancelled, facts_dir: Path = FACTS_DIR) -> str:
    """Write the patched ROM into ``output_dir``. Bodies come from the translation folder, else from the source."""
    source = Path(source_dir)
    rom_dir = source.parent / ROM_DIR
    meta_path = rom_dir / "meta.json"
    if not meta_path.is_file():
        raise ValueError(tr("This project was not unpacked from a ROM."))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    base = (rom_dir / "base.gb").read_bytes()
    facts = json.loads((facts_dir / meta["facts"]).read_text(encoding="utf-8"))
    names = _names(facts)
    edited = _edited_bodies([source, Path(translation_dir)], facts)
    changes: List[Tuple[Dict[str, Any], bytes]] = []
    for item in facts["files"]:
        for body in item["labels"]:
            lines = edited.get(body["label"])
            if lines is None:
                continue
            try:
                data = rom_text.encode(lines, names, body.get("width", 0))
            except rom_text.CodecError as error:
                raise ValueError(f"{body['label']}: {error}") from error
            if data != base[body["offset"]:body["offset"] + body["size"]]:
                changes.append((body, data))
    progress(20, tr("Writing {0} changed texts", str(len(changes))))
    if is_cancelled():
        return ""
    patched = _patched(base, facts, changes)
    out = Path(output_dir) / OUTPUT_NAMES.get(facts["build_name"], f"{facts['build_name']}.gb")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(patched)
    progress(100, "Done")
    return str(out)


def _patched(base: bytes, facts: Dict[str, Any], changes: List[Tuple[Dict[str, Any], bytes]]) -> bytes:
    """A copy of the ROM with the changed bodies written, the moved ones relocated and their references fixed."""
    texts = [(body["offset"], body["offset"] + body["size"]) for item in facts["files"] for body in item["labels"]]
    out = bytearray(base)
    free = FreeSpace(facts["gaps"])
    banks = list(range(1, len(base) // BANK_SIZE))
    moved: List[Tuple[Dict[str, Any], int, bytes]] = []
    for body, data in changes:
        if len(data) <= body["size"]:
            place = body["offset"]
        elif body.get("mode"):
            raise ValueError(tr("{0}: the name table has no room for the longer entries; shorten them.", body["label"]))
        elif body["fixed"] or not body.get("movable"):
            raise ValueError(tr("{0} is longer than its space and cannot move; shorten it.", body["label"]))
        else:
            # A table pointer has no bank byte: the body must stay in the bank its table is read from.
            place = free.take(len(data), [bank_of(body["offset"])] if body.get("pointers") else banks)
            if place is None:
                raise ValueError(tr("No free space for {0}; shorten the text.", body["label"]))
            moved.append((body, place, data))
        out[place:place + len(data)] = data
    for body, place, _data in moved:
        for site in body["far"]:
            if any(low <= site < high for low, high in texts):
                raise ValueError(tr("A reference to {0} sits inside a text body; it cannot be moved.", body["label"]))
            cpu = cpu_of(place)
            out[site] = cpu & 0xFF
            out[site + 1] = cpu >> 8
            out[site + 2] = bank_of(place)
        for site in body.get("pointers", []):
            if any(low <= site < high for low, high in texts):
                raise ValueError(tr("A pointer to {0} sits inside a text body; it cannot be moved.", body["label"]))
            cpu = cpu_of(place)
            out[site] = cpu & 0xFF
            out[site + 1] = cpu >> 8
    fix_checksums(out)
    return bytes(out)
