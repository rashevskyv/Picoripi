"""Build the Brilliant Diamond / Shining Pearl mod: the message bundles with the edited tables, for both games.

Every ``message\\english_<table>.bdmsg`` of the translation that differs from the source is written as the table's
MonoBehaviour again (``SerializedFile.write``), in the bundle that holds it. A changed bundle is written as a whole
(``Bundle.build``, its blocks stored). The result is ``atmosphere\\contents\\<title id>\\romfs\\...`` for both games.
"""
import json
from pathlib import Path
from typing import Callable, Dict, List

from core.i18n import tr
from plugins.pokemon_bdsp import bundles

TITLE_IDS = ("0100000011D90000", "010018E011D92000")   # Brilliant Diamond, Shining Pearl (same romfs)
MOD_DIR = "atmosphere"


def changed_tables(source_dir: Path, translation_dir: Path) -> Dict[str, bytes]:
    """Table name -> the translation's JSON bytes, for each table file that differs from the source."""
    changed = {}
    for path in sorted((translation_dir / "message").glob("english_*.bdmsg")):
        original = source_dir / "message" / path.name
        data = path.read_bytes()
        if not original.is_file() or original.read_bytes() != data:
            changed[path.stem] = data
    return changed


def build_switch(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    source, translation, out = Path(source_dir), Path(translation_dir), Path(output_dir)
    romfs = source.parent / "romfs"
    edits = changed_tables(source, translation)
    progress(0, tr("Building {0} edited tables", str(len(edits))))
    if not edits:
        return str(out / MOD_DIR)
    remaining = dict(edits)
    for rel in bundles.MESSAGE_BUNDLES:
        if is_cancelled():
            raise InterruptedError()
        raw_path = romfs / rel
        if not raw_path.is_file():
            raise ValueError(tr("The message bundles are missing; unpack the game again."))
        bundle, serialized = bundles.open_bundle(raw_path.read_bytes())
        names = bundles.tables(serialized)
        changes: Dict[int, bytes] = {}
        for name in list(remaining):
            if name not in names:
                continue
            value = json.loads(remaining.pop(name).decode("utf-8"))
            changes[names[name]] = serialized.write(names[name], value)
        if not changes:
            continue
        new_file = serialized.replace(changes)
        built = bundle.build({bundle.nodes[0].name: new_file})
        for title in TITLE_IDS:
            target = out / MOD_DIR / "contents" / title / "romfs" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(built)
    if remaining:
        names: List[str] = sorted(remaining)
        raise ValueError(tr("These tables are not in the game: {0}", ", ".join(names)))
    return str(out / MOD_DIR)
