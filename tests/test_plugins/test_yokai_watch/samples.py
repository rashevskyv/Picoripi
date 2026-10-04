"""Small Level-5 cfg.bin tables built the way the game's tool writes them (invented text)."""
import struct
import zlib


def _pad(data: bytearray, size: int = 16) -> None:
    data += b"\xff" * (-len(data) % size)


def cfg_file(entries, utf8: bool = True) -> bytes:
    """``entries``: ``[(name, [values])]``; a value is str / None (string, -1), int or float."""
    body = bytearray(16)
    table = bytearray()
    offsets = {}
    for name, values in entries:
        kinds = [0 if isinstance(v, str) or v is None else 2 if isinstance(v, float) else 1 for v in values]
        body += struct.pack("<IB", zlib.crc32(name.encode()), len(values))
        for i in range(0, len(kinds), 4):
            body.append(sum(k << 2 * j for j, k in enumerate(kinds[i:i + 4])))
        body += b"\0" * (-len(body) % 4)
        for kind, value in zip(kinds, values):
            if kind == 0:
                if value is None:
                    body += struct.pack("<i", -1)
                    continue
                encoded = value.encode("utf-8" if utf8 else "shift-jis")
                if encoded not in offsets:
                    offsets[encoded] = len(table)
                    table += encoded + b"\0"
                body += struct.pack("<i", offsets[encoded])
            else:
                body += struct.pack("<f", value) if kind == 2 else struct.pack("<I", value & 0xFFFFFFFF)
    _pad(body)
    string_offset = len(body)
    body += table
    _pad(body)
    names = list(dict.fromkeys(name for name, _ in entries))
    keys = bytearray()
    blob = bytearray()
    for name in names:
        keys += struct.pack("<Ii", zlib.crc32(name.encode()), len(blob))
        blob += name.encode() + b"\0"
    key_table = bytearray(16) + keys
    _pad(key_table)
    names_at = len(key_table)
    key_table += blob
    _pad(key_table)
    struct.pack_into("<4I", key_table, 0, len(key_table), len(names), names_at, len(blob))
    body += key_table
    body += b"\x01t2b\xfe\x01" + bytes([1 if utf8 else 0]) + b"\x00\x01\x00"
    _pad(body)
    struct.pack_into("<4I", body, 0, len(entries), string_offset, len(table), len(offsets))
    return bytes(body)


def text_info(text_id: int, number: int, text) -> tuple:
    return ("TEXT_INFO", [text_id, number, text, 0])


def noun_info(noun_id: int, name: str, plural=None, variance: int = 0) -> tuple:
    return ("NOUN_INFO", [noun_id, variance, None, None, None, name, None, None, None, plural, 0, 0, 0, 0])


def dialogue_file() -> bytes:
    return cfg_file([("TEXT_INFO_BEGIN", [4]),
                     text_info(0x1111, 0, "Hey there, <PNAME01>!"),
                     text_info(0x1111, 1, "Let's look for <CG>bugs</C>\\nby the river.<PAGE>Ready?"),
                     text_info(0x2222, 0, "ダミー"),
                     text_info(0x2222, 1, "Hey there, <PNAME01>!"),
                     ("TEXT_INFO_END", [])])
