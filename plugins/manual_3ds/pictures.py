"""Picture panes of a manual page: which BCLIM texture each picture pane shows, and the decoded textures.

A picture pane (pic1) names a material (mat1) by index; the material's first texture map names a texture (txl1 of the
page file). The texture is read from the page's own texture archive (EUR_xx_texture.arc) or else from
Common_texture.arc, and decoded with the Picoripi BCLIM decoder. Everything is read from the owner's folder at run
time. A texture that cannot be found or decoded gives None: the caller draws a grey box.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Optional

from PyQt6.QtGui import QImage

from core.texture_formats import flim

COMMON_TEXTURE = "Common_texture"
PICTURE_MATERIAL_AT = 0x5C        # u16 material index of a pic1 pane, after its 0x4C base and 16 bytes of colours
MATERIAL_TEXMAP_AT = 0x34         # u16 texture index of the first texture map
MATERIAL_TEXMAP_MIN = 0x38        # a material with a texture map is at least this long


def _sections(data: bytes):
    """(magic, position, size) of each section of a BCLYT file, in file order."""
    header = struct.unpack_from("<H", data, 0x06)[0]
    count = struct.unpack_from("<H", data, 0x10)[0]
    pos = header
    for _ in range(count):
        magic = data[pos:pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        yield magic, pos, size
        pos += size


def texture_names(data: bytes) -> List[str]:
    """The texture names of the file's txl1 section, in index order."""
    for magic, pos, _size in _sections(data):
        if magic == b"txl1":
            count = struct.unpack_from("<I", data, pos + 8)[0]
            names = []
            for index in range(count):
                start = pos + 12 + struct.unpack_from("<I", data, pos + 12 + 4 * index)[0]
                names.append(data[start:].split(b"\0")[0].decode("ascii", "replace"))
            return names
    return []


def material_textures(data: bytes) -> List[Optional[int]]:
    """For each material of the file's mat1 section: its first texture index, or None when it has no texture map.

    A material is its name, 16 bytes of colour and a texture map record; a material without a map is 0x34 bytes long.
    """
    for magic, pos, size in _sections(data):
        if magic == b"mat1":
            count = struct.unpack_from("<I", data, pos + 8)[0]
            starts = [pos + struct.unpack_from("<I", data, pos + 12 + 4 * index)[0] for index in range(count)]
            out: List[Optional[int]] = []
            for index, start in enumerate(starts):
                end = starts[index + 1] if index + 1 < count else pos + size
                if end - start >= MATERIAL_TEXMAP_MIN:
                    out.append(struct.unpack_from("<H", data, start + MATERIAL_TEXMAP_AT)[0])
                else:
                    out.append(None)
            return out
    return []


def picture_textures(data: bytes) -> List[Optional[str]]:
    """The texture name of each pic1 pane of the file, in file order (None: no texture)."""
    names = texture_names(data)
    materials = material_textures(data)
    out: List[Optional[str]] = []
    for magic, pos, _size in _sections(data):
        if magic != b"pic1":
            continue
        material = struct.unpack_from("<H", data, pos + PICTURE_MATERIAL_AT)[0]
        index = materials[material] if material < len(materials) else None
        out.append(names[index] if index is not None and index < len(names) else None)
    return out


class TextureBank:
    """Decodes the textures of one manual page archive and Common_texture, once each. Not thread-safe: one worker."""

    def __init__(self, archive: Any, page_member: str):
        self._archive = archive
        self._members = (page_member, COMMON_TEXTURE)
        self._files: Dict[str, Dict[str, bytes]] = {}
        self._images: Dict[str, Optional[QImage]] = {}

    def _files_of(self, member: str) -> Dict[str, bytes]:
        if member not in self._files:
            try:
                self._files[member] = self._archive.read(member)
            except Exception:  # the archive has no such member (not every manual has a texture archive)
                self._files[member] = {}
        return self._files[member]

    def image(self, name: Optional[str]) -> Optional[QImage]:
        if not name:
            return None
        if name not in self._images:
            self._images[name] = self._decode(name)
        return self._images[name]

    def _decode(self, name: str) -> Optional[QImage]:
        for member in self._members:
            data = self._files_of(member).get(name)
            if data is None:
                continue
            try:
                pil = flim.read(data, {})[0].image.convert("RGBA")
            except Exception:  # a texture the decoder does not know is drawn as a grey box
                return None
            width, height = pil.size
            pixels = pil.tobytes("raw", "RGBA")
            return QImage(pixels, width, height, 4 * width, QImage.Format.Format_RGBA8888).copy()
        return None
