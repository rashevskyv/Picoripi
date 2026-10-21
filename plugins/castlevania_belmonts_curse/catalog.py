"""The Addressables catalog (``aa/catalog.json``) of Castlevania: Belmont's Curse, for the bundles a build changed.

Addressables keeps one AssetBundleRequestOptions record per bundle in the catalog's extra data: a .NET-style header (a tag
byte, the assembly and class names, an int32 length) and a UTF-16 JSON body. In this game every record has ``m_Crc`` 0
(no CRC check on load) and ``m_BundleSize`` equal to the bundle's file size. ``patch_sizes`` gives a changed bundle its new
file size and changes nothing else: the CRC, the hash and the bundle name keep their values. A record whose size grows
is appended after the extra data, and its entry points at the new copy; the old copy stays unused.

Every other byte of the catalog is unchanged: the document is written back in the compact form the game uses, which
round-trips byte for byte (``patch_sizes`` returns the file as it was when no size changes).
"""
from __future__ import annotations

import base64
import json
import re
import struct
from typing import Dict, Optional, Tuple

from core.i18n import tr

OPTIONS_CLASS = "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions"
ENTRY_SIZE = 28          # seven int32: internal id, provider, dependency key, dependency hash, extra offset, key, type
_SIZE_FIELD = re.compile(r'"m_BundleSize":(\d+)')


def _read_string(buf: bytes, pos: int) -> Tuple[str, int]:
    """A .NET BinaryWriter string (7-bit length, then UTF-8 bytes): the text and the position after it."""
    length = shift = 0
    while True:
        byte = buf[pos]
        pos += 1
        length |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            break
    return buf[pos:pos + length].decode("utf-8"), pos + length


def _options_at(extra: bytes, offset: int) -> Tuple[int, int]:
    """(position of the body's int32 length, the length) of the options record at ``offset``."""
    if not 0 <= offset < len(extra):
        raise ValueError(tr("catalog extra data offset {0} is outside the catalog", offset))
    _assembly, pos = _read_string(extra, offset + 1)          # the first byte is the record's tag
    klass, pos = _read_string(extra, pos)
    if klass != OPTIONS_CLASS:
        raise ValueError(tr("catalog record at {0} is not an AssetBundle record", offset))
    return pos, struct.unpack_from("<i", extra, pos)[0]


def _body(extra: bytes, offset: int) -> Tuple[int, str]:
    """(position of the body's length, the decoded JSON text of the options record at ``offset``)."""
    at, length = _options_at(extra, offset)
    return at, extra[at + 4:at + 4 + length].decode("utf-16-le")


def _document(catalog: bytes) -> dict:
    return json.loads(catalog.decode("utf-8"))


def bundle_options(catalog: bytes) -> Dict[str, dict]:
    """Bundle file name -> its options (``m_Hash``, ``m_Crc``, ``m_BundleName``, ``m_BundleSize`` ...) from the catalog."""
    doc = _document(catalog)
    ids = doc["m_InternalIds"]
    entries = base64.b64decode(doc["m_EntryDataString"])
    extra = base64.b64decode(doc["m_ExtraDataString"])
    found: Dict[str, dict] = {}
    for at in range(4, 4 + ENTRY_SIZE * struct.unpack_from("<i", entries, 0)[0], ENTRY_SIZE):
        internal, _provider, _dep, _dep_hash, offset, _key, _kind = struct.unpack_from("<7i", entries, at)
        name = ids[internal].rsplit("/", 1)[-1] if 0 <= internal < len(ids) else ""
        if not name.endswith(".bundle") or offset < 0 or name in found:
            continue
        try:
            _at, text = _body(extra, offset)
        except ValueError:
            continue
        found[name] = json.loads(text)
    return found


def patch_sizes(catalog: bytes, sizes: Dict[str, int]) -> bytes:
    """The catalog with ``m_BundleSize`` set to ``sizes`` (bundle file name -> bytes) for each bundle it names.

    Raises ValueError when a named bundle is not in the catalog. Returns ``catalog`` itself when every size already
    matches.
    """
    doc = _document(catalog)
    ids = doc["m_InternalIds"]
    by_index = {index: sizes[name.rsplit("/", 1)[-1]] for index, name in enumerate(ids)
                if name.rsplit("/", 1)[-1] in sizes}
    missing = sorted(set(sizes) - {name.rsplit("/", 1)[-1] for name in ids})
    if missing:
        raise ValueError(tr("the catalog has no bundle {0}", missing[0]))
    entries = bytearray(base64.b64decode(doc["m_EntryDataString"]))
    extra = bytearray(base64.b64decode(doc["m_ExtraDataString"]))
    moved: Dict[int, int] = {}          # old extra offset -> offset of its patched copy
    changed = False
    for at in range(4, 4 + ENTRY_SIZE * struct.unpack_from("<i", entries, 0)[0], ENTRY_SIZE):
        internal, _provider, _dep, _dep_hash, offset, _key, _kind = struct.unpack_from("<7i", entries, at)
        if internal not in by_index or offset < 0:
            continue
        size = by_index[internal]
        if offset not in moved:
            moved[offset] = _patched_copy(extra, offset, size)
        if moved[offset] is None:
            continue
        struct.pack_into("<i", entries, at + 16, moved[offset])
        changed = True
    if not changed:
        return catalog
    doc["m_EntryDataString"] = base64.b64encode(bytes(entries)).decode("ascii")
    doc["m_ExtraDataString"] = base64.b64encode(bytes(extra)).decode("ascii")
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _patched_copy(extra: bytearray, offset: int, size: int) -> Optional[int]:
    """Give the record at ``offset`` the size; returns the offset of the copy, or None when its size is already right.

    The copy is appended to ``extra``: a record whose length changes cannot be resized in place.
    """
    at, text = _body(bytes(extra), offset)
    match = _SIZE_FIELD.search(text)
    if match is None:
        raise ValueError(tr("catalog record at {0} has no bundle size", offset))
    if int(match.group(1)) == size:
        return None
    new_text = text[:match.start(1)] + str(size) + text[match.end(1):]
    body = new_text.encode("utf-16-le")
    head = bytes(extra[offset:at])
    new_offset = len(extra)
    extra += head + struct.pack("<i", len(body)) + body
    return new_offset
