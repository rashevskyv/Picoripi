"""ROM mode of the Pokemon plugin: unpack a game ROM into the editor's text files, build a patched ROM from them.

The unpacked tree holds ``text/messages.inc`` (the project's source root, see ``SOURCE_DIR``) and ``rom/`` beside it:
the base ROM and the facts it was unpacked with. The messages are the decompilation's assembly form, one ``label::``
and ``.string`` lines per message, so the editor loads them with the same parser as the pret source. A build writes
only the messages that differ from the base ROM.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from core.i18n import tr
from plugins.pokemon_fr import pret_text
from plugins.pokemon_fr.rom_text import (CHARMAP_FILE, FACTS_DIR, Charmap, braille_charmap, load_tables, load_units, read_all,
                                        table_files, write_all)

ROM_ROLE = "rom"
SOURCE_DIR = "text"                       # the project's source root, inside the unpacked tree
TEXT_FILE = Path("messages.inc")          # inside the source root (and inside the translation folder)
ROM_DIR = "rom"                           # beside the source root
BASE_ROM = Path(ROM_DIR) / "base.gba"
META_FILE = Path(ROM_DIR) / "meta.json"
Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def _facts_files() -> Dict[str, Dict[str, Any]]:
    """The facts files this build knows, by file name, with their ROM SHA-1 and build name."""
    found: Dict[str, Dict[str, Any]] = {}
    for path in sorted(FACTS_DIR.glob("*.json")):
        if path.name == CHARMAP_FILE:
            continue
        header = json.loads(path.read_text(encoding="utf-8"))
        if "rom_sha1" not in header:
            continue
        found.setdefault(path.name, {"sha1": header["rom_sha1"], "game": header["game"],
                                     "build_name": header.get("build_name", path.stem),
                                     "charmap": header.get("charmap", CHARMAP_FILE)})
    return found


def identify(path: str) -> Optional[Dict[str, str]]:
    """``{"role", "platform"}`` when the file is a ROM this build has facts for, else None. Reads the file once."""
    if not str(path).lower().endswith(".gba"):
        return None
    digest = hashlib.sha1()
    try:
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    except OSError:
        return None
    if any(item["sha1"] == digest.hexdigest() for item in _facts_files().values()):
        return {"role": ROM_ROLE, "platform": "gba"}
    return None


def _facts_for(rom: bytes) -> Tuple[str, Dict[str, Any]]:
    digest = hashlib.sha1(rom).hexdigest()
    for name, item in _facts_files().items():
        if item["sha1"] == digest:
            return name, item
    raise ValueError(tr("This ROM is not a version the Pokemon plugin has text facts for."))


def _asm_text(units, texts: Dict[str, str]) -> str:
    lines = ["@ Messages of the ROM, one label per message. Written by Picoripi; edit the text between the quotes.", ""]
    for unit in units:
        lines.append(f"{unit.label}::")
        lines.append(f'\t.string "{texts[unit.label]}$"')
        lines.append("")
    return "\n".join(lines)


def unpack(rom_path: str, target_dir: str, progress: Progress, is_cancelled: Cancelled) -> Optional[str]:
    """Write ``text/messages.inc`` and ``rom/`` into ``target_dir``; returns ``target_dir`` (the host takes ``text``)."""
    rom = Path(rom_path).read_bytes()
    facts_name, facts = _facts_for(rom)
    progress(10, "Reading the messages")
    units, _floor, _header = load_units(FACTS_DIR / facts_name)
    texts = read_all(rom, units, Charmap.load(FACTS_DIR / facts["charmap"]), braille_charmap(FACTS_DIR / facts_name))
    if is_cancelled():
        return None
    target = Path(target_dir)
    (target / SOURCE_DIR).mkdir(parents=True, exist_ok=True)
    (target / SOURCE_DIR / TEXT_FILE).write_text(_asm_text(units, texts), encoding="utf-8", newline="\n")
    tables = load_tables(FACTS_DIR / facts_name)
    if tables:
        names = read_all(rom, tables, Charmap.load(FACTS_DIR / facts.get("charmap", CHARMAP_FILE)))
        for file, labels in table_files(FACTS_DIR / facts_name).items():
            members = [unit for unit in tables if unit.label in labels]
            (target / SOURCE_DIR / file).write_text(_asm_text(members, names), encoding="utf-8", newline="\n")
    progress(60, "Copying the base ROM")
    (target / ROM_DIR).mkdir(parents=True, exist_ok=True)
    (target / BASE_ROM).write_bytes(rom)
    (target / META_FILE).write_text(json.dumps({"facts": facts_name, "build_name": facts["build_name"]},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    progress(100, "Done")
    return str(target)


def field_budgets(text_dir: str) -> Optional[Tuple[Dict[str, int], Charmap]]:
    """The fixed name fields of the ROM project that holds ``text_dir``: label -> byte size, and the charmap.

    None when the folder is not a ROM project. A message (not a C-built field) has no entry: it may grow.
    """
    meta_path = Path(text_dir).parent / ROM_DIR / "meta.json"
    if not meta_path.is_file():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    facts = FACTS_DIR / meta["facts"]
    header = json.loads(facts.read_text(encoding="utf-8"))
    sizes = {unit.label: unit.size for unit in load_tables(facts) + load_units(facts)[0] if unit.fixed}
    return sizes, Charmap.load(FACTS_DIR / header.get("charmap", CHARMAP_FILE))


def _edited_texts(text_dir: Path, expected: int) -> Dict[str, str]:
    """The messages of a text file. A file with fewer messages than the ROM has is broken: refuse it, do not drop them."""
    path = text_dir / TEXT_FILE
    if not path.is_file():
        return {}
    units = pret_text.parse(path.read_text(encoding="utf-8"), asm=True)
    if len(units) != expected:
        raise ValueError(tr("{0} has {1} messages; the ROM has {2}. Check each label and each .string line.",
                            str(path), str(len(units)), str(expected)))
    return {unit.label: unit.content for unit in units}


def _edited_table_texts(text_dirs: Sequence[Path], facts_name: str) -> Dict[str, str]:
    """The entries of the C-built table files (later folders win). An entry missing from its file is refused."""
    found: Dict[str, str] = {}
    for text_dir in text_dirs:
        for file, labels in table_files(FACTS_DIR / facts_name).items():
            path = text_dir / file
            if not path.is_file():
                continue
            texts = {unit.label: unit.content for unit in pret_text.parse(path.read_text(encoding="utf-8"), asm=True)}
            for label in labels:
                if label not in texts:
                    raise ValueError(tr("{0} has no entry {1}; the ROM has it. Restore the label.", str(path), label))
                found[label] = texts[label]
    return found


def build(source_dir: str, translation_dir: str, output_dir: str, progress: Progress,
          is_cancelled: Cancelled) -> str:
    """Write the patched ROM into ``output_dir``. Messages come from the translation folder, else from the source.

    ``source_dir`` is the text folder (the project's source root); the base ROM is in ``rom/`` beside it.
    """
    source = Path(source_dir)
    rom_dir = source.parent / ROM_DIR
    meta_path = rom_dir / "meta.json"
    if not meta_path.is_file():
        raise ValueError(tr("This project was not unpacked from a ROM."))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    base = (rom_dir / "base.gba").read_bytes()
    units, floor, header = load_units(FACTS_DIR / meta["facts"])
    charmap = Charmap.load(FACTS_DIR / header.get("charmap", CHARMAP_FILE))
    tables = load_tables(FACTS_DIR / meta["facts"])
    braille = braille_charmap(FACTS_DIR / meta["facts"])
    original = read_all(base, units + tables, charmap, braille)
    edited = _edited_texts(source, len(units))
    edited.update(_edited_texts(Path(translation_dir), len(units)))
    edited.update(_edited_table_texts([source, Path(translation_dir)], meta["facts"]))
    changed = {label: text for label, text in edited.items() if label in original and text != original[label]}
    progress(20, f"Writing {len(changed)} changed messages")
    if is_cancelled():
        return ""
    patched = write_all(base, units + tables, charmap, floor, changed, braille)
    out = Path(output_dir) / f"{meta['build_name']}.gba"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(patched)
    progress(100, "Done")
    return str(out)
