"""CPK patch writer: replaced files are read back, the other files keep their bytes (a synthetic archive)."""
import io
import struct

import pytest

from core.containers import cpk
from core.containers.cpk_write import patch

ROW_STRING, ROW_U32, ROW_U64 = 0x5A, 0x54, 0x56
CONSTANT_U32 = 0x34
ROW_U16 = 0x52


def _utf(columns, rows):
    """An @UTF table: ``columns`` is ``[(name, flags)]``, ``rows`` a list of dicts (row columns only)."""
    strings = bytearray(b"\0")

    def string_at(text):
        offset = len(strings)
        strings.extend(text.encode("utf-8") + b"\0")
        return offset

    definitions = b""
    for name, flags in columns:
        definitions += bytes([flags]) + struct.pack(">I", string_at(name))
        if flags & 0xF0 == 0x30:
            definitions += struct.pack(">I", constant_value(name))
    body = b""
    for row in rows:
        for name, flags in columns:
            if flags & 0xF0 != 0x50:
                continue
            value = row[name]
            code = flags & 0x0F
            if code == 0x0A:
                body += struct.pack(">I", string_at(value))
            else:
                body += struct.pack({0x02: ">H", 0x04: ">I", 0x06: ">Q"}[code], value)
    rows_at = 0x18 + len(definitions)
    strings_at = rows_at + len(body)
    width = sum(cpk.TYPE_SIZE[f & 0x0F] for _, f in columns if f & 0xF0 == 0x50)
    base = bytearray(0x18)
    struct.pack_into(">H", base, 2, rows_at)
    struct.pack_into(">I", base, 4, strings_at)
    struct.pack_into(">I", base, 8, strings_at + len(strings))
    struct.pack_into(">H", base, 0x10, len(columns))
    struct.pack_into(">H", base, 0x12, width)
    struct.pack_into(">I", base, 0x14, len(rows))
    payload = bytes(base) + definitions + body + bytes(strings)
    return b"@UTF" + struct.pack(">I", len(payload)) + payload


CONSTANTS = {"Version": 7}


def constant_value(name):
    return CONSTANTS[name]


def _cpk(files):
    """A CPK with the content at 0x800, the TOC and the ETOC after it. ``files`` is ``[(dir, name, data)]``."""
    content = bytearray()
    toc_rows = []
    for folder, name, data in files:
        toc_rows.append({"DirName": folder, "FileName": name, "FileSize": len(data),
                         "ExtractSize": len(data), "FileOffset": len(content)})
        content.extend(data)
        content.extend(b"\0" * (-len(content) % 0x800))
    toc_at = 0x800 + len(content)
    toc_columns = [("DirName", ROW_STRING), ("FileName", ROW_STRING), ("FileSize", ROW_U32),
                   ("ExtractSize", ROW_U32), ("FileOffset", ROW_U64)]
    toc_table = _utf(toc_columns, toc_rows)
    toc = b"TOC " + b"\0" * 12 + toc_table
    etoc_at = toc_at + len(toc) + (-(toc_at + len(toc)) % 0x800)
    etoc = b"ETOC" + b"\x01" * 32
    header_columns = [("ContentOffset", ROW_U64), ("ContentSize", ROW_U64), ("TocOffset", ROW_U64),
                      ("TocSize", ROW_U32), ("EtocOffset", ROW_U64), ("EtocSize", ROW_U32),
                      ("Align", ROW_U16), ("Version", CONSTANT_U32)]
    header_row = {"ContentOffset": 0x800, "ContentSize": toc_at - 0x800, "TocOffset": toc_at,
                  "TocSize": len(toc), "EtocOffset": etoc_at, "EtocSize": len(etoc), "Align": 0x800}
    header = b"CPK " + b"\0" * 12 + _utf(header_columns, [header_row])
    out = bytearray(header.ljust(0x800, b"\0"))
    out.extend(content)
    out.extend(b"\0" * (toc_at - len(out)))
    out.extend(toc)
    out.extend(b"\0" * (etoc_at - len(out)))
    out.extend(etoc)
    return bytes(out), etoc


FILES = [("FIL", "A.DAT", b"A" * 100), ("FIL", "B.DAT", bytes(range(256)) * 3)]


def _read(data):
    stream = io.BytesIO(data)
    entries = cpk.read_cpk(stream)
    return {entry.path: cpk.read_file(stream, entry) for entry in entries}, stream


def test_synthetic_archive_reads_back():
    data, _etoc = _cpk(FILES)
    files, _ = _read(data)
    assert files == {"FIL/A.DAT": FILES[0][2], "FIL/B.DAT": FILES[1][2]}


@pytest.mark.parametrize("new", [b"short", b"x" * 5000], ids=["smaller", "larger"])
def test_patch_replaces_one_file_and_keeps_the_others(new):
    data, etoc = _cpk(FILES)
    out = io.BytesIO()
    where = patch(io.BytesIO(data), {"FIL/B.DAT": new}, out)
    patched = out.getvalue()
    files, stream = _read(patched)
    assert files["FIL/B.DAT"] == new
    assert files["FIL/A.DAT"] == FILES[0][2]
    assert where["FIL/B.DAT"] % 0x800 == 0
    assert patched.endswith(etoc)
    assert patched[len(patched) - len(etoc) - 0:] == etoc


def test_patch_without_replacements_keeps_every_file():
    data, _ = _cpk(FILES)
    out = io.BytesIO()
    patch(io.BytesIO(data), {}, out)
    files, _ = _read(out.getvalue())
    assert files == {"FIL/A.DAT": FILES[0][2], "FIL/B.DAT": FILES[1][2]}


def test_unknown_path_is_refused():
    data, _ = _cpk(FILES)
    with pytest.raises(cpk.CpkError):
        patch(io.BytesIO(data), {"FIL/NOPE.DAT": b"x"}, io.BytesIO())
