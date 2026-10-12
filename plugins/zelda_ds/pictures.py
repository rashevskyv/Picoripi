"""Picture archives of the DS Zelda games: LZ10 NARC files (``*.bin``) holding NCGR tiles and NCLR palettes.

A picture file is an LZ10 stream of a NARC archive (``core.containers.nitro.NarcContainer``); the members are
NCGR (``RGCN``: tiles, read and written by ``core.texture_formats.tiles`` with the palette of the NCLR (``RLCN``)
in the same archive), NCLR, NSCR (``RCSN``), NCER (``RECN``), NANR (``RNAN``) and other files kept as bytes.
Nothing is written back unless a member changed: an unedited picture file comes back as the original bytes.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from PIL import Image

from core.containers import lz10
from core.containers.nitro import NarcContainer
from core.texture_formats import tiles
from plugins.zelda_fsae.palettes import nclr_colours


class PictureError(ValueError):
    """Not a picture archive, or a picture that cannot take the image."""


def is_picture_file(data: bytes, depth: int = 0) -> bool:
    """A LZ10 NARC that holds an NCGR (also one archive down, as the child programs keep them), or a bare NCGR / NCLR."""
    if bytes(data[:4]) in (b"RGCN", b"RLCN"):
        return True
    if not data or data[0] != 0x10 or depth > 2:
        return False
    try:
        plain, _ = lz10.decompress(data)
    except (ValueError, IndexError):
        return False
    if plain[:4] != b"NARC":
        return False
    container = NarcContainer(plain)
    for name in container.list_files():
        body = container.read_file(name)
        if body[:4] == b"RGCN" or is_picture_file(body, depth + 1):
            return True
    return False


def _archive(data: bytes) -> Tuple[Optional[bytes], Optional[NarcContainer]]:
    if data[:1] != b"\x10":
        return None, None
    plain, _ = lz10.decompress(data)
    if plain[:4] != b"NARC":
        raise PictureError("LZ10 stream without a NARC")
    return plain, NarcContainer(plain)


def members(data: bytes) -> Dict[str, bytes]:
    """``{member name: bytes}`` of a picture file (a bare NCGR / NCLR is one member named by its file)."""
    if bytes(data[:4]) in (b"RGCN", b"RLCN"):
        return {"": bytes(data)}
    _plain, container = _archive(data)
    if container is None:
        raise PictureError("not a picture file")
    return {name: container.read_file(name) for name in container.list_files()}


def palette_of(member_bytes: Dict[str, bytes]) -> Optional[bytes]:
    for name in sorted(member_bytes):
        if member_bytes[name][:4] == b"RLCN":
            return nclr_colours(member_bytes[name])
    return None


def read_images(data: bytes) -> Dict[str, Image.Image]:
    """The NCGR sheets of a picture file, drawn with the palette of its NCLR (name -> RGBA image)."""
    parts = members(data)
    colours = palette_of(parts)
    out = {}
    for name, body in parts.items():
        if body[:4] == b"RGCN":
            params = {"palette": colours.hex()} if colours else {}
            out[name] = tiles.read(body, params)[0].image
    return out


def write_images(data: bytes, images: Dict[str, Image.Image]) -> bytes:
    """The picture file with the NCGR members in ``images`` redrawn; LZ10 again only when a member changed."""
    if bytes(data[:4]) in (b"RGCN", b"RLCN"):
        raise PictureError("bare NCGR / NCLR files are not written by this module")
    plain, container = _archive(data)
    if container is None:
        raise PictureError("not a picture file")
    parts = members(data)
    colours = palette_of(parts)
    changed = False
    for name, image in images.items():
        if name not in parts or parts[name][:4] != b"RGCN":
            raise PictureError(f"{name!r} is not an NCGR member of this file")
        params = {"palette": colours.hex()} if colours else {}
        body = tiles.write(parts[name], {0: image}, params)
        if body != parts[name]:
            container.write_file(name, body)
            changed = True
    if not changed:
        return bytes(data)
    return lz10.compress(container.pack())
