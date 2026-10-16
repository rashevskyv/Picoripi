"""Build the Brilliant Diamond / Shining Pearl mod: the message bundles with the edited tables, the picture bundles with
the edited pictures and the font bundles with the edited atlases, for both games.

Every ``message\\english_<table>.bdmsg`` of the translation that differs from the source is written as the table's
MonoBehaviour again (``SerializedFile.write``), in the bundle that holds it. A changed bundle is written as a whole
(``Bundle.build``, its blocks stored). A changed picture (``texture\\<bundle>\\<name>.png``) is encoded in its own format
(``assets.encode_texture``) and replaces the same bytes in the bundle's stream file; the size must not change.
The result is ``atmosphere\\contents\\<title id>\\romfs\\...`` for both games.
"""
import json
from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, List, Optional

from PIL import Image

from core.i18n import tr
from plugins.pokemon_bdsp import assets, bundles
from plugins.pokemon_bdsp.widths import Widths, edited_labels

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


def _changed_pngs(source_dir: Path, translation_dir: Path, top: str) -> Dict[str, Dict[str, bytes]]:
    """{folder: {workspace PNG path: new PNG bytes}} for the PNGs under ``top`` that differ from the source.

    The folder is the PNG's parent folder (``texture/<bundle path>`` or ``font/<bundle name>``), keys are as the reader names them.
    """
    root = translation_dir / top
    changed: Dict[str, Dict[str, bytes]] = {}
    if not root.is_dir():
        return changed
    for path in sorted(root.rglob("*.png")):
        rel = path.relative_to(translation_dir).as_posix()
        data = path.read_bytes()
        original = source_dir / rel
        if original.is_file() and original.read_bytes() == data:
            continue
        changed.setdefault(path.parent.relative_to(translation_dir).as_posix(), {})[rel] = data
    return changed


def changed_pictures(source_dir: Path, translation_dir: Path) -> Dict[str, Dict[str, bytes]]:
    """Bundle path (under ``AssetAssistant``) -> {workspace PNG path: new PNG bytes}, for each picture that differs."""
    return {folder[len("texture/"):]: pngs for folder, pngs in _changed_pngs(source_dir, translation_dir, "texture").items()}


def build_fonts(romfs: Path, changes: Dict[str, Dict[str, bytes]], out: Path, is_cancelled: Callable[[], bool]) -> None:
    """Write each font bundle whose atlas picture changed: the TextMesh Pro atlas (inline A8 data) is written again.

    ponytail: only the atlas pictures are written; the glyph tables (the font's JSON) are not, add them when a glyph is added.
    """
    font_dir = romfs / assets.ASSETS[1:] / assets.FONT_FOLDER
    for raw in sorted(font_dir.glob("*")) if font_dir.is_dir() else []:
        if not raw.is_file() or ("font/" + raw.name) not in changes:
            continue
        if is_cancelled():
            raise InterruptedError()
        folder = "font/" + raw.name
        pictures = changes[folder]
        bundle, serialized = assets.open_serialized(raw.read_bytes())
        cab = next(node.name for node in bundle.nodes if not node.name.endswith(".resS"))
        edits: Dict[int, bytes] = {}
        for obj in serialized.objects:
            if obj.class_id != assets.MONOBEHAVIOUR:
                continue
            font = serialized.read(obj.path_id)
            if not font.get("m_GlyphTable") or not font.get("m_AtlasTextures"):
                continue
            rel = f"{folder}/{assets.safe(font.get('m_Name', ''))}.png"
            if rel not in pictures:
                continue
            atlas_id = font["m_AtlasTextures"][0]["m_PathID"]
            atlas = serialized.read(atlas_id)
            try:
                atlas["image data"] = assets.encode_texture(atlas, Image.open(BytesIO(pictures[rel])))
            except assets.UnsupportedTexture as exc:
                raise ValueError(tr("The font atlas {0} does not fit its texture: {1}", rel, str(exc))) from None
            edits[atlas_id] = serialized.write(atlas_id, atlas)
        if not edits:
            continue
        built = bundle.build({cab: serialized.replace(edits)})
        for title in TITLE_IDS:
            target = out / MOD_DIR / "contents" / title / "romfs" / assets.ASSETS[1:] / assets.FONT_FOLDER / raw.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(built)


def build_pictures(romfs: Path, changes: Dict[str, Dict[str, bytes]], out: Path,
                   is_cancelled: Callable[[], bool]) -> None:
    """Write each changed picture bundle, with its edited pictures in its stream files, for both title ids."""
    for short, pictures in sorted(changes.items()):
        if is_cancelled():
            raise InterruptedError()
        raw_rel = assets.ASSETS[1:] + short
        raw_path = romfs / raw_rel
        if not raw_path.is_file():
            raise ValueError(tr("The picture bundle {0} is missing; unpack the game again.", short))
        bundle, serialized = assets.open_serialized(raw_path.read_bytes())
        streams: Dict[str, bytearray] = {}
        for name, _path_id, value in assets.texture_objects(serialized, "texture/" + short):
            if name not in pictures:
                continue
            stream = value.get("m_StreamData") or {}
            if value.get("image data") or not stream:
                raise ValueError(tr("The picture {0} is not stored in a stream file: it cannot be written.", name))
            node = str(stream.get("path", "")).split("/")[-1]
            data = streams.get(node)
            if data is None:
                data = streams[node] = bytearray(bundle.read(node))
            try:
                encoded = assets.encode_texture(value, Image.open(BytesIO(pictures[name])))
            except assets.UnsupportedTexture as exc:
                raise ValueError(tr("The picture {0} does not fit its texture: {1}", name, str(exc))) from None
            offset, size = int(stream.get("offset", 0)), int(stream.get("size", 0))
            if len(encoded) != size:
                raise ValueError(tr("The picture {0} would change its size; it must keep the texture's format.", name))
            data[offset:offset + size] = encoded
        if not streams:
            continue
        built = bundle.build({node: bytes(data) for node, data in streams.items()})
        for title in TITLE_IDS:
            target = out / MOD_DIR / "contents" / title / "romfs" / raw_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(built)


def build_switch(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    source, translation, out = Path(source_dir), Path(translation_dir), Path(output_dir)
    romfs = source.parent / "romfs"
    edits = changed_tables(source, translation)
    pictures = changed_pictures(source, translation)
    progress(0, tr("Building {0} edited tables", str(len(edits))))
    remaining = dict(edits)
    widths: Optional[Widths] = None

    def pick(rel):
        for root in (translation, source):
            if (root / rel).is_file():
                return root / rel
        return None
    for rel in (bundles.MESSAGE_BUNDLES if edits else ()):
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
            original = source / "message" / f"{name}.bdmsg"
            old = json.loads(original.read_text(encoding="utf-8")) if original.is_file() else {}
            edited = edited_labels(value, old)
            if edited:
                widths = widths or Widths(pick)
                for label in edited:
                    widths.label(label)
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
    if pictures:
        progress(0, tr("Building {0} edited picture bundles", str(len(pictures))))
        build_pictures(romfs, pictures, out, is_cancelled)
    fonts = _changed_pngs(source, translation, "font")
    if fonts:
        progress(0, tr("Building {0} edited font bundles", str(len(fonts))))
        build_fonts(romfs, fonts, out, is_cancelled)
    return str(out / MOD_DIR)
