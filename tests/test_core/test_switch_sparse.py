"""The sparse layer of a Switch NCA section on synthetic bytes: a bucket tree encrypted with the sparse upper IV, the
mapped ranges read from the physical bytes, the rest read as zeros. The test writes the tree itself, with its own AES."""
import struct

import pytest

pytest.importorskip("Crypto.Cipher.AES", reason="the sparse tests need pycryptodome")
from Crypto.Cipher import AES  # noqa: E402
from Crypto.Util import Counter  # noqa: E402

from core.containers.image_files import ImageError  # noqa: E402
from core.containers.switch_sparse import (  # noqa: E402
    STORAGE_DATA,
    STORAGE_ZERO,
    is_empty_sparse,
    is_sparse,
    open_sparse_section,
)

KEY = bytes(range(16))
NODE = 0x4000
ENTRY = struct.Struct("<qqi")
SECURE = 0x2A2B2C2D
GENERATION = 3
PHYSICAL = 0x100   # physical_offset of the sparse data inside the NCA
TABLE = 0x200      # bucket tree offset relative to the physical offset (16-byte aligned)


def _fsh(entries, table_bytes_len, crypto=1):
    """A section FS header with a sparse layer that points at a table of ``entries``."""
    fsh = bytearray(0x200)
    fsh[4] = crypto
    struct.pack_into("<I", fsh, 0x144, SECURE)
    struct.pack_into("<QQ", fsh, 0x148, TABLE, table_bytes_len)
    fsh[0x158:0x15C] = b"BKTR"
    struct.pack_into("<I", fsh, 0x15C, 1)
    struct.pack_into("<I", fsh, 0x160, len(entries))
    struct.pack_into("<Q", fsh, 0x168, PHYSICAL)
    struct.pack_into("<H", fsh, 0x170, GENERATION)
    return fsh


def _tree(entries):
    """Two nodes: the offset node at 0 and one entry set at NODE; entries are 0x14 bytes each."""
    table = bytearray(2 * NODE)
    struct.pack_into("<iiq", table, 0, 0, 1, 0)
    end = entries[-1][0] + 1 if entries else 0
    struct.pack_into("<iiq", table, NODE, 0, len(entries), end)
    for k, (virt, phys, storage) in enumerate(entries):
        ENTRY.pack_into(table, NODE + 0x10 + k * ENTRY.size, virt, phys, storage)
    return bytes(table)


def _encrypt_table(table, nca_size_needed):
    """The bucket tree as the sparse layer stores it: AES-CTR with the sparse upper IV at its absolute NCA offset."""
    upper = ((SECURE << 32) | (GENERATION << 16)) << 64
    absolute = PHYSICAL + TABLE
    counter = upper | (absolute // 16)
    cipher = AES.new(KEY, AES.MODE_CTR, counter=Counter.new(128, initial_value=counter))
    return cipher.encrypt(table)


def _nca(entries, physical_data, logical_size):
    """Bytes of an NCA holding the encrypted tree and ``physical_data`` at the physical offset."""
    table = _encrypt_table(_tree(entries), 0)
    nca = bytearray(PHYSICAL + TABLE + len(table) + 0x100)
    nca[PHYSICAL:PHYSICAL + len(physical_data)] = physical_data
    nca[PHYSICAL + TABLE:PHYSICAL + TABLE + len(table)] = table
    return bytes(nca)


def _read_all(view):
    view.seek(0)
    return view.read(view.size)


def test_mapped_ranges_read_physical_bytes_and_gaps_read_zeros():
    physical = bytes(range(64))
    entries = [(0, 0, STORAGE_ZERO), (32, 16, STORAGE_DATA), (48, 0, STORAGE_ZERO)]
    fsh = _fsh(entries, 2 * NODE)
    nca = _nca(entries, physical, 64)
    section = (0, 64, bytes(fsh))
    view = open_sparse_section(_stream(nca), 0, section, KEY, len(nca))
    data = _read_all(view)
    assert data[:32] == bytes(32)
    assert data[32:48] == physical[16:32]
    assert data[48:64] == bytes(16)


def test_unsorted_table_is_refused():
    entries = [(32, 0, STORAGE_DATA), (0, 0, STORAGE_ZERO)]
    fsh = _fsh(entries, 2 * NODE)
    nca = _nca(entries, bytes(64), 64)
    with pytest.raises(ImageError):
        open_sparse_section(_stream(nca), 0, (0, 64, bytes(fsh)), KEY, len(nca)).read(8)


def test_sparse_without_entries_reads_zeros_and_is_empty():
    fsh = bytearray(0x200)
    fsh[4] = 1
    fsh[0x158:0x15C] = b"BKTR"
    fsh = bytes(fsh)
    assert is_sparse(fsh) and is_empty_sparse(fsh)
    view = open_sparse_section(_stream(b""), 0, (0, 48, fsh), KEY, 0)
    assert _read_all(view) == bytes(48)


def test_plain_section_without_bktr_is_not_sparse():
    assert not is_sparse(bytes(0x200))


def _stream(data):
    import io
    return io.BytesIO(data)
