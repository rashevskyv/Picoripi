"""Unpack Castlevania: Belmont's Curse (Switch) in the Project Manager wizard: the English texts, the fonts and the catalog.

The base game and its update are read with Picoripi's Switch reader. The base's RomFS is sparse: the update's BKTR patch
maps most of it into the base, so the update's patched RomFS is the game's RomFS. The unpack writes under ``romfs\\``:
the English localization bundle, the ``fonts-latin`` bundle, every ``ui-*`` and ``room-*`` bundle that shows text, the main
``narration`` bundle (its dialogue graphs and texts) and the Addressables catalog. The project's source folder is ``source``:
``message\\<table>.json`` for each of the 45 string tables (with the scenes and speakers of the dialogue lines,
``dialogue.py``), ``font\\fonts-latin\\<asset>.json`` and ``.png`` for the two TextMesh Pro fonts, and ``ui\\<bundle>.json`` for each
interface, room or narration bundle with shown text (``tables.py``, ``fonts.py``, ``ui_text.py``). The font's JSON is
``<asset>.tmpfont``: ``.json`` files are scanned as blocks.
"""
import re
from pathlib import Path
from typing import Callable, Dict, Optional

from core.containers.image_files import ImageError
from core.i18n import tr
from core.project_library import images
from plugins.castlevania_belmonts_curse import dialogue, fonts, tables, ui_text

BASE_ID = "0100BA4026E94000"
UPDATE_ID = "0100BA4026E94800"       # the base title id plus 0x800
SOURCE_DIR = "source"
ROMFS = "romfs"
CATALOG = "Data/StreamingAssets/aa/catalog.json"
LOCALIZATION = re.compile(r"^Data/StreamingAssets/aa/Switch/localization-string-tables-english\(en\)_assets_all_[0-9a-f]+\.bundle$")


def identify(path: str) -> Optional[Dict[str, object]]:
    """``{"role", "platform", "libraries"}`` of a Castlevania: Belmont's Curse image, else None."""
    found = images.identify(path)
    if found is None or found.get("kind") != images.KIND_SWITCH:
        return None
    game_id = str(found.get("game_id") or "")
    if game_id == BASE_ID:
        return {"role": "base", "platform": "switch", "libraries": []}
    if game_id == UPDATE_ID:
        return {"role": "update", "platform": "switch", "libraries": []}
    return None


def _romfs_path(entry) -> str:
    return entry.path[len(ROMFS) + 1:]


def localization_entries(entries) -> list:
    """The English localization bundle among the patched RomFS entries (``romfs/`` paths)."""
    return [entry for entry in entries if LOCALIZATION.match(_romfs_path(entry))]


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the bundles, the catalog and the source files into ``target_dir``."""
    base, update = sources.get("base"), sources.get("update")
    if not base:
        return None
    found = images.identify(base)
    if found is None or found.get("game_id") != BASE_ID:
        raise ImageError(tr("The base file is not a Castlevania: Belmont's Curse image."))
    if not update:
        raise ImageError(tr("Choose the update file too: the game's RomFS is in the update."))
    with images.open_image(base, target_dir, is_cancelled, progress) as base_reader, \
            images.open_image(update, target_dir, is_cancelled, progress) as update_reader:
        all_entries = update_reader.patched_romfs_entries(base_reader)
        localization = localization_entries(all_entries)
        if not localization:
            raise ImageError(tr("The English localization bundle is not in this image."))
        font_entries = [entry for entry in all_entries if fonts.FONT_BUNDLE.match(_romfs_path(entry))]
        catalog = [entry for entry in all_entries if _romfs_path(entry) == CATALOG]
        candidates = [entry for entry in all_entries if ui_text.UI_BUNDLE.match(_romfs_path(entry))]
        progress(0, tr("Looking for text in {0} interface and room bundles", str(len(candidates))))
        ui_hits = []
        for index, entry in enumerate(candidates):
            if is_cancelled():
                return None
            items, _unread = ui_text.entries(update_reader.read(entry))
            if items:
                ui_hits.append(entry)
            progress(100 * (index + 1) // max(1, len(candidates)), _romfs_path(entry))
        dialogue_entries = [entry for entry in all_entries if dialogue.BUNDLE.match(_romfs_path(entry))]
        wanted = localization + font_entries + ui_hits + catalog
        wanted += [entry for entry in dialogue_entries if entry not in ui_hits]
        progress(0, tr("Writing {0} files", str(len(wanted))))
        if not images.write_entries(update_reader, wanted, target_dir, progress, is_cancelled):
            return None
    root = Path(target_dir)
    dialogue_index = {}
    if dialogue_entries:
        dialogue_index, _outside = dialogue.index((root / dialogue_entries[0].path).read_bytes())
    for entry in localization:
        if is_cancelled():
            return None
        _bundle, serialized = tables.open_bundle((root / entry.path).read_bytes())
        for name, path_id in tables.tables(serialized).items():
            entries = tables.read_entries(serialized, path_id)
            meta = dialogue_index.get(dialogue.collection_of(name))
            _write(root / SOURCE_DIR / "message" / f"{name}.json", tables.table_json(name, entries, meta))
    for entry in font_entries:
        for name, (font_json, atlas_png) in fonts.font_pairs((root / entry.path).read_bytes()).items():
            _write(root / SOURCE_DIR / fonts.FOLDER / f"{name}{fonts.SUFFIX}", font_json)
            _write(root / SOURCE_DIR / fonts.FOLDER / f"{name}.png", atlas_png)
    for entry in ui_hits:
        items, _unread = ui_text.entries((root / entry.path).read_bytes())
        name = ui_text.table_name(Path(entry.path).name)
        _write(root / SOURCE_DIR / ui_text.FOLDER / f"{name}.json", ui_text.table_json(name, items))
    return target_dir


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
