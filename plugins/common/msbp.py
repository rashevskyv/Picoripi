"""MSBP message project files (Nintendo LMS "MsgPrjBn"): colours, attributes, tags and styles of a game's text.

A game's ``*.msbp`` names everything its MSBT files encode by number: ``CLR1``/``CLB1`` colours, ``ATI2``/``ALB1``
/``ALI2`` message attributes, ``TGG2``/``TAG2``/``TGP2``/``TGL2`` control tags (group -> tags -> parameters
-> list items), ``SYL3``/``SLB1`` text styles. ``read`` returns them as plain data; a plugin ships that as
JSON (``python -m plugins.common.msbp main.msbp out.json``) so it can name tags without the file.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List

MAGIC = b"MsgPrjBn"
# TGP2 parameter types; 9 is a list (a u8 index into the parameter's items).
PARAM_TYPES = {0: "u8", 1: "u16", 2: "u32", 3: "s8", 4: "s16", 5: "s32", 6: "f32", 7: "f64", 8: "str", 9: "list"}


def _sections(raw: bytes, e: str) -> Dict[bytes, bytes]:
    count = struct.unpack_from(e + "H", raw, 0x0E)[0]
    found, position = {}, 0x20
    for _ in range(count):
        magic = raw[position:position + 4]
        size = struct.unpack_from(e + "I", raw, position + 4)[0]
        found[magic] = raw[position + 16:position + 16 + size]
        position += 16 + size
        position += -position % 16
    return found


def _cstr(body: bytes, at: int) -> str:
    return body[at:body.index(b"\x00", at)].decode("utf-8", "replace")


def _labels(body: bytes, e: str) -> Dict[int, str]:
    """A hash-table label section (``CLB1``, ``ALB1``, ``SLB1``): ``{index: label}``."""
    labels: Dict[int, str] = {}
    if not body:
        return labels
    for slot in range(struct.unpack_from(e + "I", body, 0)[0]):
        count, offset = struct.unpack_from(e + "II", body, 4 + slot * 8)
        for _ in range(count):
            length = body[offset]
            name = body[offset + 1:offset + 1 + length].decode("utf-8", "replace")
            labels[struct.unpack_from(e + "I", body, offset + 1 + length)[0]] = name
            offset += 1 + length + 4
    return labels


def _table(body: bytes, e: str) -> List[int]:
    """Entry offsets of a ``u16 count, u16 pad, u32 offsets[]`` section."""
    count = struct.unpack_from(e + "H", body, 0)[0]
    return list(struct.unpack_from(f"{e}{count}I", body, 4))


def read(raw: bytes) -> Dict[str, Any]:
    raw = bytes(raw)
    if raw[:8] != MAGIC:
        raise ValueError("Not an MSBP file")
    e = "<" if raw[8:10] == b"\xff\xfe" else ">"
    s = _sections(raw, e)
    result: Dict[str, Any] = {"endian": "little" if e == "<" else "big"}

    clr = s.get(b"CLR1", b"")
    names = _labels(s.get(b"CLB1", b""), e)
    count = struct.unpack_from(e + "I", clr, 0)[0] if clr else 0
    result["colors"] = [{"name": names.get(i, str(i)), "rgba": clr[4 + i * 4:8 + i * 4].hex()} for i in range(count)]

    lists = []
    ali = s.get(b"ALI2", b"")
    if ali:
        for offset in struct.unpack_from(f"{e}{struct.unpack_from(e + 'I', ali, 0)[0]}I", ali, 4):
            items = struct.unpack_from(e + "I", ali, offset)[0]
            lists.append([_cstr(ali, offset + o) for o in struct.unpack_from(f"{e}{items}I", ali, offset + 4)])
    ati = s.get(b"ATI2", b"")
    names = _labels(s.get(b"ALB1", b""), e)
    attributes = []
    for i in range(struct.unpack_from(e + "I", ati, 0)[0] if ati else 0):
        kind, _pad, list_index, offset = struct.unpack_from(e + "BBHI", ati, 4 + i * 8)
        item = {"name": names.get(i, str(i)), "type": PARAM_TYPES.get(kind, kind), "offset": offset}
        if kind == 9:
            item["items"] = lists[list_index] if list_index < len(lists) else []
        attributes.append(item)
    result["attributes"] = sorted(attributes, key=lambda a: a["offset"])

    tgl, tgp, tag, tgg = (s.get(m, b"") for m in (b"TGL2", b"TGP2", b"TAG2", b"TGG2"))
    list_items = [_cstr(tgl, o) for o in _table(tgl, e)] if tgl else []
    params = []
    for o in (_table(tgp, e) if tgp else []):
        kind = tgp[o]
        if kind == 9:
            n = struct.unpack_from(e + "H", tgp, o + 2)[0]
            indices = struct.unpack_from(f"{e}{n}H", tgp, o + 4)
            params.append({"name": _cstr(tgp, o + 4 + 2 * n), "type": "list",
                           "items": [list_items[i] for i in indices]})
        else:
            params.append({"name": _cstr(tgp, o + 1), "type": PARAM_TYPES.get(kind, kind)})
    tags = []
    for o in (_table(tag, e) if tag else []):
        n = struct.unpack_from(e + "H", tag, o)[0]
        indices = struct.unpack_from(f"{e}{n}H", tag, o + 2)
        tags.append({"name": _cstr(tag, o + 2 + 2 * n), "params": [params[i] for i in indices]})
    groups = []
    for number, o in enumerate(_table(tgg, e) if tgg else []):
        if raw[0x0D] < 4:   # version 3 (3DS): no group id; a group's id is its position
            group_id, o = number, o - 2
            n = struct.unpack_from(e + "H", tgg, o + 2)[0]
        else:
            group_id, n = struct.unpack_from(e + "HH", tgg, o)
        indices = struct.unpack_from(f"{e}{n}H", tgg, o + 4)
        groups.append({"id": group_id, "name": _cstr(tgg, o + 4 + 2 * n), "tags": [tags[i] for i in indices]})
    result["tag_groups"] = groups

    syl = s.get(b"SYL3", b"")
    names = _labels(s.get(b"SLB1", b""), e)
    styles = []
    for i in range(struct.unpack_from(e + "I", syl, 0)[0] if syl else 0):
        width, lines, font, color = struct.unpack_from(e + "iiii", syl, 4 + i * 16)
        styles.append({"name": names.get(i, str(i)), "region_width": width, "lines": lines, "font": font,
                       "color": color})
    result["styles"] = styles
    return result


if __name__ == "__main__":
    data = read(Path(sys.argv[1]).read_bytes())
    text = json.dumps(data, ensure_ascii=False, indent=1)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
