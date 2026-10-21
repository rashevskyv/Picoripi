"""Build the Castlevania: Belmont's Curse Switch mod: the English string tables with the translation's texts.

The build reads ``translation\\message\\<table>.json`` (texts by key id) for each table. A table whose texts differ from
the source's gets the translation's texts; the English localization bundle is rebuilt with them and written to
``atmosphere\\contents\\0100BA4026E94000\\romfs\\<bundle path>``, a LayeredFS mod folder. Every other file of the game is
left alone. The catalog is not changed: the bundle's size and CRC differ from the original, so the mod must be tested on
the console (open item).
"""
from pathlib import Path
from typing import Callable, Dict

from core.i18n import tr
from plugins.castlevania_belmonts_curse import tables, unpack

MOD_DIR = "atmosphere"
TITLE_IDS = (unpack.BASE_ID,)


def changed_texts(source_dir: Path, translation_dir: Path) -> Dict[str, Dict[int, str]]:
    """Table name -> {key id: text} for each translation table whose texts differ from the source table."""
    edits: Dict[str, Dict[int, str]] = {}
    for path in sorted((translation_dir / "message").glob("*.json")):
        original = source_dir / "message" / path.name
        if not original.is_file():
            raise ValueError(tr("This table is not in the game: {0}", path.stem))
        name, texts = tables.parse_table_json(path.read_bytes())
        _name, source = tables.parse_table_json(original.read_bytes())
        source_text = dict(source)
        differs = {key: text for key, text in texts if text and text != source_text.get(key)}
        if differs:
            edits[name] = differs
    return edits


def build_switch(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """Write the mod folder for the edited tables; returns the ``atmosphere`` folder."""
    source, translation, out = Path(source_dir), Path(translation_dir), Path(output_dir)
    romfs = source.parent / "romfs"
    edits = changed_texts(source, translation)
    progress(0, tr("Building {0} edited tables", str(len(edits))))
    if not edits:
        return str(out / MOD_DIR)
    bundles = [path for path in (romfs / "Data" / "StreamingAssets" / "aa" / "Switch").glob("localization-string-tables-english*.bundle")]
    if len(bundles) != 1:
        raise ValueError(tr("The English localization bundle is missing; unpack the game again."))
    if is_cancelled():
        raise InterruptedError()
    built = tables.build_bundle(bundles[0].read_bytes(), edits)
    if built is None:
        return str(out / MOD_DIR)
    rel = bundles[0].relative_to(romfs)
    for title in TITLE_IDS:
        target = out / MOD_DIR / "contents" / title / "romfs" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(built)
    return str(out / MOD_DIR)
