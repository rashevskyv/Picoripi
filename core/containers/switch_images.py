"""Nintendo Switch images, identify only: a .nsp (PFS0) names its title from the rights ID of its ticket.

An .xci (HFS0 cartridge image) is recognised, but its title is not read. Every Switch program is encrypted with keys
Picoripi does not read yet (prod.keys), so the reader for these images raises ``encrypted_error``.
"""
from __future__ import annotations

import re
import struct
from typing import Any, Dict, List, Optional, Tuple

from core.containers.image_files import ImageError, ImageReader, check_name

PFS0_MAGIC = b"PFS0"
XCI_MAGIC = b"HEAD"          # at 0x100 of a cartridge image
RIGHTS_ID_AT = 0x2A0         # rights ID (16 bytes) in a Switch ticket: its first 8 bytes are the title ID
MAX_TICKET = 0x4000
MAX_XML = 0x10000
UPDATE_SUFFIX = 0x800        # a title ID with these low bits is the update of its base game


def _pfs0_files(reader: ImageReader) -> List[Dict[str, Any]]:
    """Name, offset and size of each file of a PFS0 archive (absolute offsets)."""
    head = reader.read_at(0, 0x10)
    count, strtab_size = struct.unpack_from("<II", head, 4)
    if count > 4096:
        raise ImageError("the PFS0 archive lists too many files")
    entries = reader.read_at(0x10, count * 0x18)
    names = reader.read_at(0x10 + count * 0x18, strtab_size)
    data_base = 0x10 + count * 0x18 + strtab_size
    files: List[Dict[str, Any]] = []
    for index in range(count):
        offset, size = struct.unpack_from("<QQ", entries, index * 0x18)
        name_at = struct.unpack_from("<I", entries, index * 0x18 + 16)[0]
        if name_at >= len(names):
            raise ImageError("a PFS0 file name is out of range")
        try:
            name = names[name_at:].split(b"\0", 1)[0].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ImageError("unsafe PFS0 file name") from exc
        files.append({"name": check_name(name), "offset": data_base + offset, "size": size})
    return files


def title_kind(title_id: str) -> str:
    """``base``, ``update`` or ``dlc`` for a 16-digit hex title ID, from its low bits; ``""`` when there is none."""
    if not title_id:
        return ""
    low = int(title_id, 16) & 0xFFF
    if low == 0:
        return "base"
    return "update" if low == UPDATE_SUFFIX else "dlc"


_TYPE_KIND = {"Application": "base", "Patch": "update", "AddOnContent": "dlc"}


def _ticket_title(reader: ImageReader, entries: List[Dict[str, Any]]) -> str:
    """The title ID (hex) from the rights ID of the first usable ticket of an NSP, or "" when there is none."""
    for entry in entries:
        if not entry["name"].endswith(".tik") or not RIGHTS_ID_AT + 16 <= entry["size"] <= MAX_TICKET:
            continue
        ticket = reader.read_at(entry["offset"], entry["size"])
        return ticket[RIGHTS_ID_AT:RIGHTS_ID_AT + 8].hex()
    return ""


def _cnmt(reader: ImageReader, entries: List[Dict[str, Any]]) -> Optional[Tuple[str, str]]:
    """``(title ID, kind)`` from the plain-text content meta (``*.cnmt.xml``) of an NSP, or None.

    The XML is not encrypted; it names the title ID and the type (application, patch or add-on content).
    """
    for entry in entries:
        if not entry["name"].endswith(".cnmt.xml") or entry["size"] > MAX_XML:
            continue
        text = reader.read_at(entry["offset"], entry["size"]).decode("utf-8", "replace")
        title = re.search(r"<Id>0x([0-9a-fA-F]{16})</Id>", text)
        kind = re.search(r"<Type>(Application|Patch|AddOnContent)</Type>", text)
        if title and kind:
            return title.group(1).lower(), _TYPE_KIND[kind.group(1)]
    return None


def locate(reader: ImageReader, head: bytes) -> Optional[Dict[str, Any]]:
    """The fields ``core.project_library.images.identify`` reports for a Switch image, or None when it is not one.

    The title comes from the content meta when the NSP has one, else from the rights ID of its ticket.
    """
    if head[:4] == PFS0_MAGIC:
        entries = _pfs0_files(reader)
        meta = _cnmt(reader, entries)
        if meta is not None:
            title_id, kind = meta
        else:
            title_id, kind = _ticket_title(reader, entries), ""
            kind = title_kind(title_id)
        return {"kind": "switch", "game_id": title_id.upper(), "title_id": title_id.upper(), "encrypted": True,
                "title_kind": kind}
    if head[0x100:0x104] == XCI_MAGIC:
        return {"kind": "switch", "game_id": "", "title_id": "", "encrypted": True, "title_kind": ""}
    return None
