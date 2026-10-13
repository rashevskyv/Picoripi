"""The workspace script (_shared/scripts/zt/dqb.py): nxarc and LINKDATA readers and the append-and-point writers,
on small archives built here (skipped when the scripts are not on this machine)."""
import romhacking_root
import importlib
import struct
import sys
import zlib
from pathlib import Path

import pytest

SCRIPTS = romhacking_root.under('_shared\\scripts')


@pytest.fixture(scope="module")
def zt():
    if not (SCRIPTS / "zt" / "dqb.py").is_file():
        pytest.skip("workspace scripts not found")
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("zt.dqb")


def make_nxarc(path: Path, files: dict) -> None:
    names = b"".join(n.encode() + b"\0" for n in files)
    blobs = [(names, False)] + [(d, True) for d in files.values()]
    count = len(blobs)
    start = 0x18 + 32 * count
    start += -start % 16
    entries, body, at = [], b"", start
    for data, packed in blobs:
        raw = zlib.compress(data) if packed else data
        entries.append(struct.pack("<4Q", len(raw), len(data), at, 1 if packed else 0))
        pad = -len(raw) % 16
        body += raw + bytes(pad)
        at += len(raw) + pad
    head = struct.pack("<4sI4sIII", b"RAXN", 0x10000, b"bilz", 0x18 + 32 * count, 32, count) + b"".join(entries)
    path.write_bytes(head + bytes(start - len(head)) + body)


def make_linkdata(folder: Path, entries: list) -> None:
    """``entries``: bytes or None (an empty entry). Entry 1 is stored in chunks of 8 bytes (zlib), the rest raw."""
    idx, blob = b"", b""
    for i, data in enumerate(entries):
        blob += bytes(-len(blob) % 0x100)
        at = len(blob)
        if data is None:
            idx += struct.pack("<4Q", at, 0, 0, 0)
        elif i == 1:
            chunk, parts, sizes = 8, [], []
            for k in range(0, len(data), chunk):
                piece = data[k:k + chunk]
                packed = struct.pack("<I", len(zlib.compress(piece))) + zlib.compress(piece)
                parts.append(packed)
                sizes.append(len(packed))
            first = -(12 + 4 * len(parts)) // 0x80 * -0x80
            raw = struct.pack("<III", chunk, len(parts), len(data)) + struct.pack(f"<{len(parts)}I", *sizes)
            raw += bytes(first - len(raw))
            for packed in parts:
                raw += packed + bytes(-len(packed) % 0x80)
            blob += raw
            idx += struct.pack("<4Q", at, len(data), len(raw), 1)
        else:
            blob += data
            idx += struct.pack("<4Q", at, len(data), len(data), 0)
    (folder / "LINKDATA.IDX").write_bytes(idx)
    (folder / "LINKDATA.BIN").write_bytes(blob)


def test_nxarc_is_read_and_a_changed_entry_is_appended(zt, tmp_path):
    files = {"excel/A.en.bin": b"hello" * 10, "gra/font/x.phyre": bytes(range(200)), "gra/y.phyre": b"y" * 33}
    original = tmp_path / "romfs" / "binary" / "x.nxarc"
    original.parent.mkdir(parents=True)
    make_nxarc(original, files)
    arc = zt.NxArc(original)
    assert arc.names == list(files) and all(arc.get(n) == d for n, d in files.items())
    out = tmp_path / "build" / "atmosphere" / "contents" / "t" / "romfs" / "binary" / "x.nxarc"
    zt.patch_nxarc(original, out, {"gra/y.phyre": b"new" * 100})
    patched = zt.NxArc(out)
    assert patched.get("gra/y.phyre") == b"new" * 100 and patched.get("excel/A.en.bin") == files["excel/A.en.bin"]
    assert out.stat().st_size % 16 == 0 and not list(out.parent.glob("*.json"))
    assert (tmp_path / "build" / "_base" / "x.nxarc.json").is_file()
    zt.patch_nxarc(original, out, {})                         # nothing changed: the copy is cut back
    assert out.read_bytes() == original.read_bytes()


def test_linkdata_reads_chunks_and_stores_a_changed_entry_at_the_end(zt, tmp_path):
    rom = tmp_path / "romfs"
    rom.mkdir()
    entries = [b"zero" * 5, bytes(range(256)) * 3, None, b"three" * 7]
    make_linkdata(rom, entries)
    ld = zt.LinkData(rom / "LINKDATA.IDX", rom / "LINKDATA.BIN")
    try:
        assert [ld.read(i) for i in range(4)] == [e or b"" for e in entries]
        assert ld.read(1, limit=1)[:8] == bytes(range(8))
    finally:
        ld.close()
    out = tmp_path / "build" / "romfs"
    out.mkdir(parents=True)
    zt.patch_linkdata(rom / "LINKDATA.IDX", rom / "LINKDATA.BIN", out, {3: b"changed!" * 9})
    ld = zt.LinkData(out / "LINKDATA.IDX", out / "LINKDATA.BIN")
    try:
        assert ld.read(3) == b"changed!" * 9 and ld.read(1) == entries[1] and ld.read(0) == entries[0]
        assert ld.entries[3][0] % 0x100 == 0 and ld.entries[3][3] == 0
    finally:
        ld.close()
