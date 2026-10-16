"""Synthetic Super Mario Galaxy message archives (BMG + BCSV label table in a RARC or CRAR). Nothing from the game."""
import struct
from typing import List, Optional, Tuple, Union

from plugins.super_mario_galaxy import bcsv
from rarc_fixture import build_rarc

Part = Union[str, Tuple[int, bytes]]   # text, or (tag group, tag bytes in the file's own order)


def bmg(messages: List[List[Part]], little: bool = False) -> bytes:
    """A UTF-16 BMG (INF1 with 8 attribute bytes per item, DAT1, an FLW1 stub). ``little``: the Switch form."""
    e = "<" if little else ">"
    enc = "utf-16-le" if little else "utf-16-be"
    esc = "\x1a".encode(enc)
    dat = bytearray("\0".encode(enc))
    offsets = []
    for message in messages:
        offsets.append(len(dat))
        for part in message:
            if isinstance(part, str):
                dat += part.encode(enc)
            else:
                group, data = part
                dat += esc + bytes([len(esc) + 2 + len(data), group]) + data
        dat += "\0".encode(enc)
    inf = bytearray(16)
    for index, offset in enumerate(offsets):
        inf += struct.pack(e + "I", offset) + bytes([index, 0, 0, 0, 1, 2, 0, 0])
    inf += bytes(-len(inf) % 32)
    struct.pack_into(e + "4sIHHI", inf, 0, b"INF1", len(inf), len(messages), 12, 0)
    dat_section = bytearray(8) + dat
    dat_section += bytes(-len(dat_section) % 32)
    struct.pack_into(e + "4sI", dat_section, 0, b"DAT1", len(dat_section))
    flw = bytearray(32)
    struct.pack_into(e + "4sI", flw, 0, b"FLW1", 32)
    body = bytes(inf + dat_section + flw)
    head = bytearray(0x20)
    struct.pack_into(e + "8sIIB", head, 0, b"MESGbmg1", 0x20 + len(body) - 32, 3, 2)
    out = bytes(head) + body
    if little:   # every magic as a reversed word
        out = bytearray(out)
        out[0:8] = b"GSEM1gmb"
        at = 0x20
        while at < len(out):
            size = struct.unpack_from("<I", out, at + 4)[0]
            out[at:at + 4] = out[at:at + 4][::-1]
            at += size
        out = bytes(out)
    return out


def table(labels: List[str], little: bool = False) -> bytes:
    """A BCSV with the columns ``MessageId`` (string) and ``Index`` (int), sorted by label as the game keeps it."""
    e = "<" if little else ">"
    rows = sorted((label, index) for index, label in enumerate(labels))
    pool = bytearray()
    data = bytearray()
    for label, index in rows:
        data += struct.pack(e + "Ii", len(pool), index)
        pool += label.encode("ascii") + b"\0"
    head = struct.pack(e + "iiII", len(rows), 2, 0x10 + 24, 8)
    fields = struct.pack(e + "IIHBB", bcsv.name_hash("MessageId"), 0xFFFFFFFF, 0, 0, bcsv.STRING) + \
        struct.pack(e + "IIHBB", bcsv.name_hash("Index"), 0xFFFFFFFF, 4, 0, bcsv.INT)
    return head + fields + bytes(data) + bytes(pool)


def message_arc(labels: List[str], messages: List[List[Part]], little: bool = False,
                with_table: Optional[bool] = True) -> bytes:
    files = {"message.bmg": bmg(messages, little)}
    if with_table:
        files["messageid.tbl"] = table(labels, little)
    return build_rarc(files, little=little)
