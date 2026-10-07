"""Synthetic TotK files built from the format descriptions, independent of the plugin's own writers."""
import struct


def _section(magic: bytes, body: bytes) -> bytes:
    data = magic + struct.pack("<I", len(body)) + b"\x00" * 8 + body
    return data + b"\xab" * (-len(data) % 16)


def text(*parts) -> bytes:
    """A TXT2 entry: str parts, ("tag", group, type, params) and ("end", group, type)."""
    out = b""
    for part in parts:
        if isinstance(part, str):
            out += part.encode("utf-16-le")
        elif part[0] == "tag":
            out += struct.pack("<HHHH", 0x0E, part[1], part[2], len(part[3])) + part[3]
        else:
            out += struct.pack("<HHH", 0x0F, part[1], part[2])
    return out + b"\x00\x00"


def msbt(entries) -> bytes:
    """An MSBT with LBL1, ATR1, TSY1 and TXT2; ``entries`` is ``[(label, text bytes)]``."""
    slots = 3
    buckets = [[] for _ in range(slots)]
    for index, (label, _text) in enumerate(entries):
        buckets[sum(label.encode()) % slots].append((label, index))
    table = b""
    labels = b""
    base = 4 + slots * 8
    for bucket in buckets:
        table += struct.pack("<II", len(bucket), base + len(labels))
        for label, index in bucket:
            labels += bytes([len(label)]) + label.encode() + struct.pack("<I", index)
    lbl1 = struct.pack("<I", slots) + table + labels
    atr1 = struct.pack("<II", len(entries), 0)
    tsy1 = b"".join(struct.pack("<I", 6) for _ in entries)
    texts = [entry_text for _label, entry_text in entries]
    offsets, position = [], 4 + 4 * len(texts)
    for entry_text in texts:
        offsets.append(position)
        position += len(entry_text)
    txt2 = struct.pack(f"<I{len(texts)}I", len(texts), *offsets) + b"".join(texts)
    body = _section(b"LBL1", lbl1) + _section(b"ATR1", atr1) + _section(b"TSY1", tsy1) + _section(b"TXT2", txt2)
    header = b"MsgStdBn" + b"\xff\xfe" + b"\x00\x00" + bytes([1, 3]) + struct.pack("<HHI", 4, 0, 0x20 + len(body))
    return header + b"\x00" * 10 + body


def _hash(name: str) -> int:
    value = 0
    for char in name.encode():
        value = (value * 0x65 + char) & 0xFFFFFFFF
    return value


def sarc(files: dict, alignment: int = 8, aligns: dict = None) -> bytes:
    """A little-endian SARC of ``{name: bytes}``, nodes sorted by name hash (``aligns``: per-file alignment)."""
    names = sorted(files, key=_hash)
    name_table, name_offsets = b"", {}
    for name in names:
        name_offsets[name] = len(name_table)
        entry = name.encode() + b"\x00"
        name_table += entry + b"\x00" * (-len(entry) % 4)
    data, ranges = b"", {}
    for name in names:
        data += b"\x00" * (-len(data) % (aligns or {}).get(name, alignment))
        ranges[name] = (len(data), len(data) + len(files[name]))
        data += files[name]
    nodes = b"".join(
        struct.pack("<IIII", _hash(name), 0x01000000 | name_offsets[name] // 4, *ranges[name]) for name in names
    )
    head_size = 0x14 + 0x0C + len(nodes) + 8 + len(name_table)
    data_offset = head_size + (-head_size % 0x100)
    header = b"SARC" + struct.pack("<HHIIHH", 0x14, 0xFEFF, data_offset + len(data), data_offset, 0x100, 0)
    sfat = b"SFAT" + struct.pack("<HHI", 0x0C, len(names), 0x65) + nodes
    sfnt = b"SFNT" + struct.pack("<HH", 8, 0) + name_table
    head = header + sfat + sfnt
    return head + b"\x00" * (data_offset - len(head)) + data


def dictionary() -> bytes:
    """A trained zstd dictionary (with its id), like the ones in ZsDic.pack.zs."""
    from compression import zstd

    samples = [msbt([(f"Talk_{i:02d}", text(f"Line {i} of the conversation with person {i * 7}."))])
               for i in range(300)]
    return zstd.train_dict(samples, 4096).dict_content


def zsdic_pack(zs_dictionary: bytes) -> bytes:
    """A ZsDic.pack.zs: a SARC of dictionaries, compressed without one."""
    from compression import zstd

    return zstd.compress(sarc({"zs.zsdic": zs_dictionary}))
