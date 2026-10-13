"""The files the unpack step takes from Metroid Prime (GameCube, USA GM8E01): the same set as zt/mpport.py.

Every package (``files/*.pak``) of the disc gives its string tables and fonts; the UI packages also give their
interface textures. Output paths (the zt ``source`` folder): ``text/<package>/<name>.<id>.strg`` (every string
table, once: the first package that has it), ``font/<name>.<id>.font`` (a FONT with its texture, Font Editor
format) and ``texture/<package>/<name>.<id>.txtr`` (Textures window format).

These are Prime 1 packages: big endian, starting with u16 3 and u16 5, resources compressed with zlib (a
compressed resource is u32 size, then the zlib stream). The Wii discs (Trilogy) have another reader and are not
unpacked here: for them, and for any other disc, ``extract`` returns None.
"""
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple

from core.project_library import images
from utils.logging_utils import log_warning

GAME_IDS = ("GM8E01",)
PAK_HEAD = b"\x00\x03\x00\x05"
DIRECTORY_WINDOW = 4 << 20          # the directory of a package sits in its first megabytes
UI_PAKS = {"gguisys", "miscdata", "noaram", "strings", "rs5"}     # interface textures; the world packages hold none


@dataclass
class _Resource:
    type: str
    id: int
    compressed: int
    size: int
    offset: int            # from the start of the package
    name: str = ""

    @property
    def key(self) -> str:
        return f"{self.id:08X}"


def _directory(data: bytes) -> List[_Resource]:
    """The resources of a package from its first bytes: the names table, then the resource directory."""
    names: Dict[Tuple[str, int], str] = {}
    pos = 8
    for _ in range(struct.unpack_from(">I", data, pos)[0]):
        kind, rid, length = struct.unpack_from(">4sII", data, pos + 4)
        names.setdefault((kind.decode("latin-1"), rid), data[pos + 16:pos + 16 + length].decode("latin-1"))
        pos += 12 + length
    count = struct.unpack_from(">I", data, pos + 4)[0]
    pos += 8
    out = []
    for k in range(count):
        compressed, kind, rid, size, offset = struct.unpack_from(">I4sIII", data, pos + 20 * k)
        kind_text = kind.decode("latin-1")
        out.append(_Resource(kind_text, rid, compressed, size, offset, names.get((kind_text, rid), "")))
    return out


class Pak:
    """A package of the disc: its directory, and its resources read from the image on demand."""

    def __init__(self, reader, entry) -> None:
        self.reader = reader
        self.base = entry.offset
        head = reader.read_at(entry.offset, min(entry.size, DIRECTORY_WINDOW))
        if head[:4] != PAK_HEAD:
            raise ValueError(f"{entry.path}: not a Metroid Prime 1 package")
        try:
            self.resources = _directory(head)
        except struct.error:
            self.resources = _directory(reader.read(entry))

    def unique(self, kind: str) -> Dict[int, _Resource]:
        """``{id: first resource}`` of one type."""
        out: Dict[int, _Resource] = {}
        for res in self.resources:
            if res.type == kind:
                out.setdefault(res.id, res)
        return out

    def read(self, res: _Resource) -> bytes:
        raw = self.reader.read_at(self.base + res.offset, res.size)
        if not res.compressed:
            return raw
        if raw[4:5] != b"\x78":
            raise ValueError(f"{res.type} {res.key}: only zlib resources are read (Prime 1)")
        # The u32 in front is the size after decompression: stop one byte past it, so a bad stream cannot grow
        # without limit, and a size that does not match is an error.
        size = struct.unpack_from(">I", raw, 0)[0]
        packer = zlib.decompressobj()
        body = packer.decompress(raw[4:], size + 1)
        if len(body) != size or packer.unconsumed_tail:
            raise ValueError(f"{res.type} {res.key}: the size after decompression does not match")
        return body


def _label(name: str, prefix: str, key: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_ -]+", "_", name[len(prefix):] if name.startswith(prefix) else name).strip()
    return f"{name}.{key}" if name else key


def font_parts(form: bytes) -> Tuple[int, int]:
    """``(FONT size, texture id)`` of a FONT resource of version 0 to 5 (46-byte glyphs up to version 2, then 27)."""
    version = struct.unpack_from(">I", form, 4)[0]
    at = 16 + 4 * (version >= 1) + 4 * (version >= 2) + 10
    end = form.index(b"\0", at) + 1
    width = 8 if version >= 5 else 4
    count = struct.unpack_from(">I", form, end + width + 4)[0]
    kerning = end + width + 8 + (46 if version <= 2 else 27) * count
    return kerning + 4 + 8 * struct.unpack_from(">I", form, kerning)[0], int.from_bytes(form[end:end + width], "big")


def outputs(paks: List[Tuple[str, Pak]]) -> Iterator[Tuple[str, bytes]]:
    """``(path under the output folder, bytes)`` of the text, font and interface texture files of ``paks``."""
    textures: Dict[int, Tuple[Pak, _Resource]] = {}      # a font's texture may sit in another package
    for _stem, pak in paks:
        for rid, res in pak.unique("TXTR").items():
            textures.setdefault(rid, (pak, res))
    seen: Dict[str, set] = {"STRG": set(), "FONT": set(), "TXTR": set()}
    for stem, pak in paks:
        for rid, res in pak.unique("STRG").items():
            if rid not in seen["STRG"]:
                seen["STRG"].add(rid)
                yield f"text/{stem}/{_label(res.name, 'STRG_', res.key)}.strg", pak.read(res)
    for stem, pak in paks:
        for rid, res in pak.unique("FONT").items():
            if rid in seen["FONT"]:
                continue
            seen["FONT"].add(rid)
            form = pak.read(res)
            size, tex = font_parts(form)
            name = res.name or form[0x1A:form.index(b"\0", 0x1A)].decode("latin-1")
            if tex not in textures:
                log_warning(f"metroid_prime_trilogy: font {name} has no texture {tex:X} in the disc; skipped")
                continue
            seen["TXTR"].add(tex)
            tpak, tres = textures[tex]
            yield f"font/{_label(name, 'FONT_', res.key)}.font", form[:size] + tpak.read(tres)
    for stem, pak in paks:
        if stem.lower() not in UI_PAKS:
            continue
        for rid, res in pak.unique("TXTR").items():
            if rid not in seen["TXTR"]:
                seen["TXTR"].add(rid)
                yield f"texture/{stem}/{_label(res.name, 'TXTR_', res.key)}.txtr", pak.read(res)


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    found = images.identify(base)
    if found is None or found["kind"] != "gc" or found["game_id"] not in GAME_IDS:
        return None
    with images.open_image(base) as image:
        packs = sorted((e for e in image.entries() if e.path.startswith("files/") and "/" not in e.path[6:]
                        and e.path.lower().endswith(".pak")), key=lambda e: e.path.lower())
        paks = []
        for entry in packs:
            if is_cancelled():
                return None
            progress(0, entry.path)
            paks.append((entry.path[6:-4], Pak(image, entry)))
        for rel, data in outputs(paks):
            if is_cancelled():
                return None
            progress(50, rel)
            out = Path(target_dir).joinpath(*rel.split("/"))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
    progress(100, "")
    return str(target_dir)
