"""Builders of a tiny Zone of the Enders STAGE.DAT, stage script and disc image for the tests (no game data)."""
import struct
import zlib
from typing import Dict, List, Tuple

from plugins.zoe2_ps2 import stagedat as sd

SECTOR = 2048
SEED = 0x3E2F87DB


def make_scx(strings: List[bytes]) -> bytes:
    """A script: one pointer instruction per string, a label string, a jump table-like byte run, then the strings."""
    code_len = 7 * (len(strings) + 1) + 3
    offsets = []
    at = code_len
    pool = b""
    for raw in strings + [b"obj1"]:
        offsets.append(at + len(pool))
        pool += raw + b"\x00"
    code = b"".join(b"\x80\xb0\xc2" + struct.pack("<I", off) for off in offsets) + b"\xc3\x09\x00"
    data = code + pool
    return data + b"\x00" * (-len(data) % 16)


def _blob(parts: List[bytes], key5: int) -> Tuple[bytes, int, int, List[int]]:
    data, offsets = sd.join_members(parts)
    stream = sd.ZLIB_HEAD + zlib.compress(data, 9)[2:]
    return sd.encode_blob(stream, key5), len(stream), len(data), offsets


def make_stage(name: str, groups: List[Tuple[str, list]], seed: int = SEED) -> bytes:
    """Stored bytes of a stage. A group is ``("cache", [(ext name, bytes), ...])`` or ``("sound", [bytes])`` (plain)."""
    entries: List[Tuple[int, int, int]] = []
    spans: List[bytes] = []
    cursor = 0
    for number, (kind, members) in enumerate(groups):
        if kind == "sound":
            raw = b"".join(members)
            entries.append((0x7F000010, 0, len(raw)))
            at = 0
            for part in members:
                entries.append((sd.str_code32("bin"), 0, at))
                at += len(part)
            entries.append((sd.END_GROUP, 0, len(raw)))
            spans.append(raw + b"\x00" * (-len(raw) % SECTOR))
        else:
            blob, stored, size, offsets = _blob([data for _ext, data in members], 0x1234 + number)
            entries.append((0x7F000002, 0, size))
            entries.append((0x7E000000 | stored, 0, cursor))
            for (ext, _data), off in zip(members, offsets):
                entries.append((sd.str_code32(ext), sd.str_code32(f"{name}.{ext}"), off))
            entries.append((sd.END_GROUP, 0, size))
            spans.append(blob + b"\x00" * (-len(blob) % SECTOR))
        cursor += len(spans[-1])
    entries.append((0, 0, 0))
    index = struct.pack("<I", len(entries)) + b"".join(struct.pack("<III", *e) for e in entries)
    coded = sd.code_stage_index(index, name, seed)
    return coded + b"\x00" * (-len(coded) % SECTOR) + b"".join(spans)


def make_dat(stages: Dict[str, bytes], seed: int = SEED) -> bytes:
    """A STAGE.DAT of the stored stages (name -> bytes), in the given order."""
    count = len(stages)
    first = (4 + 12 + 20 * count + SECTOR - 1) // SECTOR
    sector = first
    listing = b""
    body = b""
    for name, stored in stages.items():
        listing += name.encode().ljust(16, b"\x00") + struct.pack("<I", sector)
        body += stored
        sector += len(stored) // SECTOR
    head = struct.pack("<HHHHI", 1, 2, count, sd.GAME_ID, 0x53067) + listing
    coded = struct.pack("<I", seed) + sd._xor_header(head, seed)
    return coded + b"\x00" * (first * SECTOR - len(coded)) + body


def _record(name: bytes, lba: int, size: int, is_dir: bool) -> bytes:
    body = struct.pack("<BB", 0, 0) + struct.pack("<I", lba) + struct.pack(">I", lba) + struct.pack("<I", size) \
        + struct.pack(">I", size) + bytes(7) + bytes([2 if is_dir else 0, 0, 0]) + struct.pack("<H", 1) \
        + struct.pack(">H", 1) + bytes([len(name)]) + name
    body += b"\x00" * (len(body) % 2)
    return bytes([len(body) + 0]) + body[1:]


def make_iso(files: Dict[str, bytes]) -> bytes:
    """A disc image: SYSTEM.CNF and ZOE2/STAGE.DAT of ``files`` ({"SYSTEM.CNF": ..., "STAGE.DAT": ...})."""
    cnf, dat = files["SYSTEM.CNF"], files["STAGE.DAT"]
    root_lba, zoe_lba, cnf_lba = 18, 19, 20
    dat_lba = cnf_lba + 1
    root = _record(b"\x00", root_lba, SECTOR, True) + _record(b"\x01", root_lba, SECTOR, True) \
        + _record(b"SYSTEM.CNF;1", cnf_lba, len(cnf), False) + _record(b"ZOE2", zoe_lba, SECTOR, True)
    zoe = _record(b"\x00", zoe_lba, SECTOR, True) + _record(b"\x01", root_lba, SECTOR, True) \
        + _record(b"STAGE.DAT;1", dat_lba, len(dat), False)
    total = dat_lba + (len(dat) + SECTOR - 1) // SECTOR
    pvd = bytearray(SECTOR)
    pvd[0:6] = b"\x01CD001"
    pvd[80:88] = struct.pack("<I", total) + struct.pack(">I", total)
    pvd[156:156 + 34] = _record(b"\x00", root_lba, SECTOR, True)
    image = bytearray(total * SECTOR)
    image[16 * SECTOR:17 * SECTOR] = pvd
    image[root_lba * SECTOR:root_lba * SECTOR + len(root)] = root
    image[zoe_lba * SECTOR:zoe_lba * SECTOR + len(zoe)] = zoe
    image[cnf_lba * SECTOR:cnf_lba * SECTOR + len(cnf)] = cnf
    image[dat_lba * SECTOR:dat_lba * SECTOR + len(dat)] = dat
    return bytes(image)
