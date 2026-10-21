"""Build the Castlevania: Belmont's Curse Switch mod: the edited bundles, and the catalog that gives their sizes.

Three kinds of edit are written, each as a rebuilt bundle in ``atmosphere\\contents\\0100BA4026E94000\\romfs\\...``:
the English localization bundle (the string tables, ``tables.py``), the ``fonts-latin`` bundle (the TextMesh Pro fonts,
``fonts.py``) and the interface and room bundles with edited texts (``ui_text.py``). A rebuilt bundle is stored without
compression, as the SWUK mod stores its bundles. The catalog ``aa\\catalog.json`` is written with each rebuilt bundle's new
size (``catalog.py``); every other bundle and file of the game is left alone.
"""
from pathlib import Path
from typing import Callable, Dict

from core.i18n import tr
from plugins.castlevania_belmonts_curse import catalog, fonts, tables, ui_text, unpack

MOD_DIR = "atmosphere"
TITLE_IDS = (unpack.BASE_ID,)
SWITCH = Path("Data") / "StreamingAssets" / "aa" / "Switch"
CATALOG = Path("Data") / "StreamingAssets" / "aa" / "catalog.json"


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


def changed_fonts(source_dir: Path, translation_dir: Path) -> Dict[str, fonts.Pair]:
    """Font asset name -> (JSON, PNG) of each translation pair that differs from the source pair."""
    changed: Dict[str, fonts.Pair] = {}
    for path in sorted((translation_dir / fonts.FOLDER).glob("*" + fonts.SUFFIX)):
        picture = path.with_suffix(".png")
        if not picture.is_file():
            raise ValueError(tr("The font {0} has no picture.", path.stem))
        pair = (path.read_bytes(), picture.read_bytes())
        original = source_dir / fonts.FOLDER / path.name
        if original.is_file() and original.read_bytes() == pair[0] \
                and original.with_suffix(".png").read_bytes() == pair[1]:
            continue
        changed[path.name[:-len(fonts.SUFFIX)]] = pair
    return changed


def changed_ui(source_dir: Path, translation_dir: Path) -> Dict[str, Dict[str, str]]:
    """Bundle name -> {text id: text} for each translation text that is not empty and differs from the source's."""
    edits: Dict[str, Dict[str, str]] = {}
    for path in sorted((translation_dir / ui_text.FOLDER).glob("*.json")):
        original = source_dir / ui_text.FOLDER / path.name
        if not original.is_file():
            raise ValueError(tr("This interface table is not in the game: {0}", path.stem))
        name, texts = ui_text.parse_table_json(path.read_bytes())
        _name, source = ui_text.parse_table_json(original.read_bytes())
        source_text = dict(source)
        unknown = [key for key, _text in texts if key not in source_text]
        if unknown:
            raise ValueError(tr("The text {0} is not in the game.", unknown[0]))
        differs = {key: text for key, text in texts if text and text != source_text[key]}
        if differs:
            edits[name] = differs
    return edits


def _bundle_files(switch: Path, pattern: Callable[[str], bool]) -> Dict[str, Path]:
    """Bundle file name -> path, for the files of ``Switch`` whose romfs path matches ``pattern``."""
    return {raw.name: raw for raw in sorted(switch.iterdir())
            if raw.is_file() and pattern((SWITCH / raw.name).as_posix())}


def build_switch(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """Write the mod folder for the edited texts and fonts; returns the ``atmosphere`` folder."""
    source, translation, out = Path(source_dir), Path(translation_dir), Path(output_dir)
    romfs = source.parent / "romfs"
    switch = romfs / SWITCH
    edits = changed_texts(source, translation)
    font_edits = changed_fonts(source, translation)
    ui_edits = changed_ui(source, translation)
    progress(0, tr("Building {0} edited tables", str(len(edits))))
    built: Dict[str, bytes] = {}
    if edits:
        bundles = [path for path in switch.glob("localization-string-tables-english*.bundle")]
        if len(bundles) != 1:
            raise ValueError(tr("The English localization bundle is missing; unpack the game again."))
        if is_cancelled():
            raise InterruptedError()
        data = tables.build_bundle(bundles[0].read_bytes(), edits)
        if data is not None:
            built[bundles[0].name] = data
    if font_edits:
        progress(0, tr("Building {0} edited fonts", str(len(font_edits))))
        fonts_bundles = list(switch.glob("fonts-latin_assets_all_*.bundle"))
        if len(fonts_bundles) != 1:
            raise ValueError(tr("The fonts bundle is missing; unpack the game again."))
        data = fonts.build_font_bundle(fonts_bundles[0].read_bytes(), font_edits)
        if data is not None:
            built[fonts_bundles[0].name] = data
    if ui_edits:
        progress(0, tr("Building {0} edited interface bundles", str(len(ui_edits))))
        found = _bundle_files(switch, ui_text.UI_BUNDLE.match)
        for name, edited in ui_edits.items():
            matches = [file for file, raw in found.items() if ui_text.table_name(file) == name]
            if len(matches) != 1:
                raise ValueError(tr("The interface bundle {0} is missing; unpack the game again.", name))
            if is_cancelled():
                raise InterruptedError()
            data = ui_text.build_bundle((switch / matches[0]).read_bytes(), edited)
            if data is not None:
                built[matches[0]] = data
    if not built:
        return str(out / MOD_DIR)
    catalog_file = romfs / CATALOG
    if not catalog_file.is_file():
        raise ValueError(tr("The catalog is missing; unpack the game again."))
    for title in TITLE_IDS:
        base = out / MOD_DIR / "contents" / title / "romfs"
        for name, data in built.items():
            target = base / SWITCH / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        patched = catalog.patch_sizes(catalog_file.read_bytes(), {name: len(data) for name, data in built.items()})
        (base / CATALOG).parent.mkdir(parents=True, exist_ok=True)
        (base / CATALOG).write_bytes(patched)
    return str(out / MOD_DIR)
