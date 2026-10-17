"""Build target of Twilight Princess HD (Wii U): a Cemu graphic pack and the SDCafiine folder for a real console.

The source is the owner's unpacked game ``source/content``: ``res/Msguk`` (the project folder) with the size tables
``FileSizeList.txt`` and ``DecompressedSizeList.txt`` two folders above it. The translation is ``translation/content``
at the same place. A changed file is written to both folders of its pair (``res/Msguk`` and ``res/Msgus``, the fonts
``res/Fonteu`` and ``res/Fontus``) unless the translation has its own copy, so one mod works on the USA and the European
game. Each written file gets its new size in the size tables. A font whose glyph sheets changed gets its GX2 textures
(``*.pack.gz``) redrawn from the sheets: the game draws from those, not from the BFN.

With no changed file no mod is built: the game stays original.
"""
import gzip
import shutil
import struct
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from core.containers import yaz0
from core.containers.rarc_container import RarcContainer
from core.i18n import tr
from core.texture_formats import gx2

from .build import changed_files

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]

PACK_NAME = "Picoripi_UA_TPHD"
SDCAFIINE_MOD = "Picoripi_UA"
# Cemu runs the mod under any of these ids; the update id and the folder placeholder come from the owner's dumps.
TITLE_IDS = ("000500001019E500", "000500001019E600", "000500001019C800")
CEMU_IDS = ("0005000E1019C800", "FFFFFFFF3BC226D1")
# A changed file also goes to its twin folder (USA res/Msgus and Europe res/Msguk, fonts Fontus and Fonteu).
PAIRS = {"res/Msgus/": "res/Msguk/", "res/Msguk/": "res/Msgus/", "res/Fontus/": "res/Fonteu/", "res/Fonteu/": "res/Fontus/"}
SIZE_LISTS = ("FileSizeList.txt", "DecompressedSizeList.txt")
RULES_TXT = f"""[Definition]
titleIds = {",".join(TITLE_IDS + CEMU_IDS)}
name = Picoripi UA
path = "The Legend of Zelda: Twilight Princess HD/Mods/Picoripi UA"
description = Ukrainian translation (text and fonts) built by Picoripi (zelda_bmg plugin).
version = 7
"""


def _content_root(folder: Path) -> Path:
    """The ``content`` folder that holds ``res``: two levels above a ``res/<folder>`` project folder."""
    if folder.parent.name != "res":
        raise ValueError(tr("{0}: the project folder must be the res/Msguk or res/Msgus folder of the game.", str(folder)))
    return folder.parent.parent


def read_pairs(raw: bytes) -> list:
    """FileSizeList.txt: NUL-separated ``path, size`` pairs."""
    items = raw.split(b"\0")
    return [[items[i], items[i + 1]] for i in range(0, len(items) - 1, 2)]


def read_quads(raw: bytes) -> list:
    """DecompressedSizeList.txt: NUL-separated ``compressed, decompressed, ratio%, ./DVDRoot/path`` records."""
    items = raw.split(b"\0")
    return [items[i:i + 4] for i in range(0, len(items) - 3, 4)]


def _join(records: list) -> bytes:
    return b"".join(b"\0".join(r) + b"\0" for r in records)


def update_size_lists(lists: Dict[str, bytes], written: Dict[str, bytes]) -> Dict[str, bytes]:
    """New bytes of the size tables for ``{"res/...": data}`` the mod writes. Unchanged tables are left out."""
    out = {}
    pairs = read_pairs(lists["FileSizeList.txt"])
    index = {p[0].decode("latin-1"): p for p in pairs}
    quads = read_quads(lists["DecompressedSizeList.txt"])
    qindex = {q[3].decode("latin-1"): q for q in quads}
    for rel, data in written.items():
        if rel in index:
            index[rel][1] = str(len(data)).encode()
        if rel.endswith(".pack.gz"):
            key = "./DVDRoot/" + rel[:-3]
            if key in qindex:
                full = len(gzip.decompress(data))
                qindex[key][0:3] = [str(len(data)).encode(), str(full).encode(),
                                    f"{(1 - len(data) / full) * 100:.1f}%".encode()]
    new = _join(pairs)
    if new != lists["FileSizeList.txt"]:
        out["FileSizeList.txt"] = new
    newq = _join(quads)
    if newq != lists["DecompressedSizeList.txt"]:
        out["DecompressedSizeList.txt"] = newq
    return out


# ---------------------------------------------------------------- fonts: BFN sheets -> GX2 textures

def rarc_first_file(data: bytes) -> bytes:
    """The first file of a (Yaz0) RARC archive: the BFN inside res/Font*/*.arc."""
    if data[:4] == b"Yaz0":
        data = yaz0.decompress(data)
    container = RarcContainer(data)
    names = container.list_files()
    if not names:
        raise ValueError(tr("The font archive holds no file."))
    return container.read_file(names[0])


def bfn_sheets(bfn: bytes) -> List[Tuple[int, int, bytes]]:
    """The I8 glyph sheets of a BFN as ``(width, height, linear bytes)``, row by row."""
    offset = 32
    while offset + 8 <= len(bfn):
        magic, size = struct.unpack_from(">4sI", bfn, offset)
        if magic == b"GLY1":
            start, end, _cw, _ch, page, fmt, cols, rows, width, height = struct.unpack_from(
                ">HHHHIHHHHH", bfn, offset + 8)
            if fmt != 1:
                raise ValueError(tr("The font texture format is {0}, not I8.", str(fmt)))
            sheets = []
            for s in range((end - start) // (cols * rows) + 1):
                tiled = bfn[offset + 32 + s * page:offset + 32 + (s + 1) * page]
                linear = bytearray(width * height)
                n = 0
                for ty in range(0, height, 4):
                    for tx in range(0, width, 8):
                        for y in range(ty, ty + 4):
                            linear[y * width + tx:y * width + tx + 8] = tiled[n:n + 8]
                            n += 8
                sheets.append((width, height, bytes(linear)))
            return sheets
        offset += max(size, 32)
        offset = (offset + 31) // 32 * 32
    raise ValueError(tr("The font file has no GLY1 section."))


def regenerate_pack(pack_gz: bytes, bfn: bytes) -> bytes:
    """``res/Font*/X.pack.gz`` with its GX2 textures redrawn from the glyph sheets of the BFN in X.arc.

    The pack (TMPK) holds one GTX whose image blocks are the BFN sheets, tiled for the GPU. Headers stay as they are.
    """
    pack = bytearray(gzip.decompress(pack_gz))
    if pack[:4] != b"TMPK":
        raise ValueError(tr("The font texture file is not a TMPK pack."))
    gtx = struct.unpack_from(">I", pack, 0x14)[0]
    sheets = bfn_sheets(bfn)
    pack = _grow_pack(pack, gtx, len(sheets))
    at = gtx + struct.unpack_from(">I", pack, gtx + 4)[0]
    surface, index = None, 0
    while at + 32 <= len(pack):
        _magic, _hsize, _maj, _min, kind, size = struct.unpack_from(">4sIIIII", pack, at)
        body = at + 32
        if kind == 0x0B:
            surface = struct.unpack_from(">16I", pack, body)
        elif kind == 0x0C and surface is not None:
            width, height, tile, swizzle = surface[1], surface[2], surface[12], surface[13]
            if index >= len(sheets) or sheets[index][:2] != (width, height) or surface[5] != 1:
                raise ValueError(tr("The font texture pack does not match the font's glyph sheets."))
            if width % 128:   # the tiler's pitch for 8-bit surfaces is 128 bytes; a sheet this wide is not checked
                raise ValueError(tr("The font sheet is {0} pixels wide; its texture layout is not checked.", str(width)))
            linear = sheets[index][2]
            raw = bytearray(size)
            for n, pos in enumerate(gx2.element_offsets(width, height, 8, tile, swizzle)):
                raw[pos] = linear[n]
            pack[body:body + size] = raw
            index += 1
        elif kind == 0x01:
            break
        at = body + size
    if index != len(sheets):
        raise ValueError(tr("The font texture pack holds {0} textures, the font {1} sheets.", str(index), str(len(sheets))))
    return gzip.compress(bytes(pack), compresslevel=9, mtime=0)


def _grow_pack(pack: bytearray, gtx: int, sheets: int) -> bytearray:
    """A font with more sheets than the game's (the Ukrainian letters on a new sheet) needs as many textures.

    The last texture (surface block, padding block, image block) is repeated before the end block, as the Russian
    patch's pack does. The pack must hold this one GTX only; its size in the TMPK table grows.
    """
    spans, start, at = [], None, gtx + struct.unpack_from(">I", pack, gtx + 4)[0]
    while at + 32 <= len(pack):
        kind, size = struct.unpack_from(">II", pack, at + 0x10)
        if kind == 0x0B:
            start = at
        elif kind == 0x0C and start is not None:
            spans.append((start, at + 32 + size))
        elif kind == 0x01:
            break
        at += 32 + size
    if len(spans) >= sheets:
        return pack
    if struct.unpack_from(">I", pack, 4)[0] != 1:
        raise ValueError(tr("The font texture pack holds more than one file: a texture cannot be added."))
    last = bytes(pack[spans[-1][0]:spans[-1][1]])
    grown = bytearray(pack[:at]) + last * (sheets - len(spans)) + pack[at:]
    struct.pack_into(">I", grown, 0x18, struct.unpack_from(">I", grown, 0x18)[0] + len(last) * (sheets - len(spans)))
    return grown


# ---------------------------------------------------------------- the mod

def _mod_changes(source: Path, translation: Path) -> Dict[str, bytes]:
    """{content path (res/...): bytes} of every translated file under res (messages, fonts), with their twins."""
    src_content = _content_root(source)
    trn_content = _content_root(translation)
    changes = changed_files([(src_content / "res", trn_content / "res", "res")])
    for inner, data in list(changes.items()):
        for prefix, other in PAIRS.items():
            if inner.startswith(prefix):
                twin = other + inner[len(prefix):]
                if not (trn_content / twin).is_file():
                    changes.setdefault(twin, data)
    return changes


def _redraw_fonts(changes: Dict[str, bytes], content: Path) -> None:
    """Add the redrawn GX2 texture (``X.pack.gz``) of every changed font whose glyph sheets changed."""
    for inner, data in list(changes.items()):
        if not (inner.startswith("res/Font") and inner.endswith(".arc")):
            continue
        pack = inner[:-4] + ".pack.gz"
        if pack in changes:
            continue
        folder = inner.split("/")[1]
        candidates = [content / pack, content / PAIRS["res/" + folder + "/"].rstrip("/") / Path(pack).name]
        base = next((p for p in candidates if p.is_file()), None)
        original = content / inner
        if base is None or (original.is_file() and
                            bfn_sheets(rarc_first_file(original.read_bytes())) == bfn_sheets(rarc_first_file(data))):
            continue
        changes[pack] = regenerate_pack(base.read_bytes(), rarc_first_file(data))


def build_wiiu_mod(source_dir: str, translation_dir: str, output_dir: str,
                   progress: Progress, is_cancelled: Cancelled) -> str:
    """Write the graphic pack and the SDCafiine folder into ``output_dir`` and return ``output_dir``."""
    source, translation = Path(source_dir), Path(translation_dir)
    changes = _mod_changes(source, translation)
    if not changes:
        raise ValueError(tr("No translated file differs from the game: nothing to build."))
    src_content = _content_root(source)
    if not all((src_content / name).is_file() for name in SIZE_LISTS):
        raise ValueError(tr("The size tables FileSizeList.txt and DecompressedSizeList.txt are missing in {0}.",
                            str(src_content)))
    _redraw_fonts(changes, src_content)
    lists = {name: (src_content / name).read_bytes() for name in SIZE_LISTS}
    tables = update_size_lists(lists, changes)
    out = Path(output_dir)
    pack = out / "graphicPacks" / PACK_NAME
    total = len(changes) + len(tables)
    done = 0
    for inner, data in sorted(changes.items()):
        if is_cancelled():
            break
        _write(pack / "content" / inner, data)
        done += 1
        progress(100 * done // total, inner)
    for name, data in tables.items():
        _write(pack / "content" / name, data)
    (pack / "rules.txt").write_text(RULES_TXT, encoding="utf-8")
    content = pack / "content"
    written_files = [path for path in sorted(content.rglob("*")) if path.is_file()]
    for title in TITLE_IDS:
        mod_root = out / "sdcafiine" / "wiiu" / "sdcafiine" / title / SDCAFIINE_MOD / "content"
        for path in written_files:
            target = mod_root / path.relative_to(content)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    progress(100, "")
    return str(out)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
