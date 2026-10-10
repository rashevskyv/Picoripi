"""English messages inside the executables of Raving Rabbids: Party Collection: the menu's game titles and prompt
(``RRRTExec_R.dol``; the build writes it to ``sys/main.dol`` too) and the disc error messages each executable
(menu, ``rrr1_f.dol``, ``rrr2_eu.dol``, ``rrr3_noe.dol``) shows before its text is loaded. Each message is a
NUL-terminated cp1252 string at a fixed place of its executable (the executable is known by its size); a new
text must fit the string's bytes and the NULs after it (one NUL stays).
"""
from __future__ import annotations

import struct
from typing import Dict, List, Set, Tuple

from .jade_text import decode, encode

# executable size -> (name, [(offset, room)]) -- room: bytes for the text, its NUL excluded
SLOTS: Dict[int, Tuple[str, List[Tuple[int, int]]]] = {
    1108032: ("Menu (RRRTExec_R.dol)", [
        (0xdea48, 31), (0xdecd8, 23), (0xdecf0, 23), (0xded08, 31), (0xded98, 31), (0xdf6d4, 17), (0xdf6e6, 8),
        (0xdf6ef, 31), (0xdf7d4, 27), (0xdf7f0, 12), (0xdf7fd, 21), (0xdf813, 12), (0xdfa53, 23), (0xdfa6b, 24),
        (0xdfa84, 21), (0xdfa9a, 34), (0xdfabd, 31), (0xdfadd, 31)]),
    5331040: ("Rayman Raving Rabbids (rrr1_f.dol)", [
        (0x4c533c, 19), (0x4c5350, 15), (0x4c5360, 31), (0x4c5450, 31), (0x4c5470, 15), (0x4c5480, 23),
        (0x4c5498, 23), (0x4c5930, 35), (0x4c5954, 35), (0x4c5978, 35), (0x4c599c, 35), (0x4c59c0, 15)]),
    3113440: ("Rayman Raving Rabbids 2 (rrr2_eu.dol)", [
        (0x2ae068, 15), (0x2ae078, 15), (0x2ae088, 31), (0x2ae174, 35), (0x2ae198, 15), (0x2ae1a8, 23),
        (0x2ae1c0, 23), (0x2ae5b8, 23), (0x2ae5d0, 27), (0x2ae5ec, 27), (0x2ae608, 27), (0x2ae624, 27),
        (0x2ae640, 31)]),
    6179968: ("Rayman Raving Rabbids TV Party (rrr3_noe.dol)", [
        (0x5af314, 19), (0x5af328, 15), (0x5af338, 31), (0x5af430, 27), (0x5af44c, 19), (0x5af460, 23),
        (0x5af478, 15), (0x5af6c4, 27), (0x5af6e0, 23), (0x5af6f8, 31), (0x5af718, 27), (0x5af734, 35),
        (0x5af758, 19)]),
}


def is_dol(raw: bytes) -> bool:
    return len(raw) in SLOTS and struct.unpack_from(">I", raw, 0)[0] == 0x100


def name(raw: bytes) -> str:
    return SLOTS[len(raw)][0]


def texts(raw: bytes, shown: Dict[str, str]) -> List[str]:
    return [decode(raw[a:raw.index(b"\0", a)], shown) for a, _room in SLOTS[len(raw)][1]]


def build(raw: bytes, new: List[str], translation_map: Dict[str, str], missing: Set[str]) -> bytes:
    places = SLOTS[len(raw)][1]
    if len(new) != len(places):
        raise ValueError(f"the executable has {len(places)} messages, the project {len(new)}")
    out = bytearray(raw)
    for (start, room), text in zip(places, new):
        data = encode(text, translation_map, missing)
        if data == raw[start:raw.index(b"\0", start)]:
            continue
        if len(data) > room:
            raise ValueError(f"'{text}' is {len(data)} bytes; this message has room for {room}")
        out[start:start + room + 1] = data + bytes(room + 1 - len(data))
    return bytes(out)
