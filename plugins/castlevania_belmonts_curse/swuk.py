"""Import the SWUK Ukrainian translation (a LayeredFS mod of this game) as the translation of the string tables.

The mod's English localization bundle has the same 45 tables and the same key ids as the game's; the Ukrainian texts sit
in the English slot. The import reads them by table name and key id and writes ``translation\\message\\<table>.json``,
the same files the translator edits. A table whose ids differ from the source's is not written and is reported.
"""
from pathlib import Path
from typing import Dict, List, Tuple

from plugins.castlevania_belmonts_curse import tables


def import_swuk(mod_bundle: bytes, source_dir: Path, translation_dir: Path) -> Tuple[int, List[str]]:
    """Write the mod's texts for every matching table; returns (tables written, names of the tables not matched)."""
    source: Dict[str, List[tables.Entry]] = {}
    for path in sorted((source_dir / "message").glob("*.json")):
        name, entries = tables.parse_table_json(path.read_bytes())
        source[name] = entries
    imported = tables.import_translation(mod_bundle, source)
    target = translation_dir / "message"
    target.mkdir(parents=True, exist_ok=True)
    for name, entries in imported.items():
        (target / f"{name}.json").write_bytes(tables.table_json(name, entries))
    missing = sorted(set(source) - set(imported))
    return len(imported), missing


def import_swuk_fonts(font_bundle: bytes, source_dir: Path, translation_dir: Path) -> Tuple[List[str], List[str]]:
    """Write the mod's font pairs (``fonts.font_pairs``) for each font asset the source has; returns (written, missing)."""
    from plugins.castlevania_belmonts_curse import fonts
    pairs = fonts.font_pairs(font_bundle)
    target = translation_dir / fonts.FOLDER
    written = []
    for name in sorted(pairs):
        if not (source_dir / fonts.FOLDER / f"{name}{fonts.SUFFIX}").is_file():
            continue
        target.mkdir(parents=True, exist_ok=True)
        font_json, atlas_png = pairs[name]
        (target / f"{name}{fonts.SUFFIX}").write_bytes(font_json)
        (target / f"{name}.png").write_bytes(atlas_png)
        written.append(name)
    missing = sorted(name for name in _source_fonts(source_dir) if name not in written)
    return written, missing


def _source_fonts(source_dir: Path) -> List[str]:
    from plugins.castlevania_belmonts_curse import fonts
    return [path.name[:-len(fonts.SUFFIX)] for path in (source_dir / fonts.FOLDER).glob("*" + fonts.SUFFIX)]
