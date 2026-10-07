"""Nintendo DS LZ11 and backward LZ (BLZ) compression, NARC archives."""
import random
import struct

import pytest

from core.containers import nitro


def _sample(size: int, seed: int = 1) -> bytes:
    rng = random.Random(seed)
    words = [bytes(rng.randrange(256) for _ in range(rng.randrange(2, 12))) for _ in range(40)]
    out = bytearray()
    while len(out) < size:
        out += rng.choice(words) if rng.random() < 0.8 else bytes([rng.randrange(256)])
    return bytes(out[:size])


@pytest.mark.parametrize("data", [b"", b"a", b"abcabcabcabcabcabc" * 50, bytes(5000), _sample(20000)],
                         ids=["empty", "one", "repeats", "zeros", "sample"])
def test_lz11_round_trip(data):
    packed = nitro.lz11_compress(data)
    assert packed[0] == 0x11 and len(packed) % 4 == 0
    assert nitro.lz11_decompress(packed)[0] == data


def test_lz11_reads_the_long_reference_forms():
    # literal "ab", then a 0x11..0x110 form (length 20) and a 0x111+ form (length 300), both distance 2
    long_ = 300 - 0x111
    stream = bytes([0x11]) + (2 + 20 + 300).to_bytes(3, "little") + bytes([0b00110000]) + b"ab"
    stream += bytes([(20 - 0x11) >> 4, ((20 - 0x11) & 15) << 4 | 0, 1])
    stream += bytes([0x10 | long_ >> 12, long_ >> 4 & 0xFF, (long_ & 15) << 4 | 0, 1])
    assert nitro.lz11_decompress(stream)[0] == b"ab" * 161


def _in_place(packed: bytes) -> bytes:
    """Decompress the way the console does: inside one buffer, the compressed file at its start."""
    compressed, footer, growth = nitro.blz_footer(packed)
    buf = bytearray(packed) + bytes(growth)
    src, dst, stop = len(packed) - footer, len(buf), len(packed) - compressed
    while src > stop:
        src -= 1
        flags = buf[src]
        for bit in range(8):
            if src <= stop:
                break
            if flags & (0x80 >> bit):
                src -= 2
                value = buf[src] | buf[src + 1] << 8
                for _ in range((value >> 12) + 3):
                    dst -= 1
                    buf[dst] = buf[dst + (value & 0xFFF) + 3]
            else:
                src -= 1
                dst -= 1
                buf[dst] = buf[src]
            assert dst >= src, "writing overtook reading"
    return bytes(buf)


@pytest.mark.parametrize("data", [bytes(4096), b"NARC" + _sample(30000, 2), _sample(3000, 3) + bytes(3000)],
                         ids=["zeros", "sample", "sample-then-zeros"])
def test_blz_round_trip_and_in_place_decompression(data):
    packed = nitro.blz_compress(data)
    assert len(packed) < len(data) and len(packed) % 4 == 0
    assert nitro.blz_decompress(packed) == data
    assert _in_place(packed) == data


def test_blz_refuses_data_that_does_not_compress():
    with pytest.raises(ValueError):
        rng = random.Random(5)
        nitro.blz_compress(bytes(rng.randrange(256) for _ in range(256)))


def narc(files: dict) -> bytes:
    """A NARC of ``files`` ({"dir/sub/name": bytes}), with its name table."""
    dirs = {"": ([], [])}                                   # path -> (subfolders, file names)
    for path in files:
        parts = path.split("/")
        for depth in range(len(parts) - 1):
            parent, folder = "/".join(parts[:depth]), "/".join(parts[:depth + 1])
            if folder not in dirs:
                dirs[folder] = ([], [])
                dirs[parent][0].append(folder)
        dirs["/".join(parts[:-1])][1].append(path)
    order = list(dirs)
    ids = {folder: 0xF000 + i for i, folder in enumerate(order)}
    file_order, first = [], {}
    for folder in order:
        first[folder] = len(file_order)
        file_order += dirs[folder][1]
    subtables = []
    for folder in order:
        sub = b"".join(bytes([0x80 | len(s.rsplit("/", 1)[-1])]) + s.rsplit("/", 1)[-1].encode()
                       + struct.pack("<H", ids[s]) for s in dirs[folder][0])
        sub += b"".join(bytes([len(f.rsplit("/", 1)[-1])]) + f.rsplit("/", 1)[-1].encode() for f in dirs[folder][1])
        subtables.append(sub + b"\0")
    main, at = b"", 8 * len(order)
    for i, folder in enumerate(order):
        parent = len(order) if folder == "" else ids[folder.rsplit("/", 1)[0] if "/" in folder else ""]
        main += struct.pack("<IHH", at, first[folder], parent)
        at += len(subtables[i])
    fnt_body = main + b"".join(subtables)
    fnt_body += bytes(-len(fnt_body) % 4)
    fat = b"BTAF" + struct.pack("<IHH", 12 + 8 * len(file_order), len(file_order), 0)
    body = bytearray()
    for path in file_order:
        fat += struct.pack("<II", len(body), len(body) + len(files[path]))
        body += files[path] + b"\xff" * (-len(files[path]) % 4)
    data = (fat + b"BTNF" + struct.pack("<I", 8 + len(fnt_body)) + fnt_body
            + b"GMIF" + struct.pack("<I", 8 + len(body)) + bytes(body))
    return b"NARC" + struct.pack("<HHIHH", 0xFFFE, 0x0100, 16 + len(data), 16, 3) + data


def test_narc_lists_reads_and_repacks():
    data = narc({"d/a.bin": b"one", "d/b.bin": b"second file", "top.bin": b"x"})
    archive = nitro.NarcContainer(data)
    assert nitro.NarcContainer.can_handle(data) and sorted(archive.list_files()) == ["d/a.bin", "d/b.bin", "top.bin"]
    assert archive.read_file("d/b.bin") == b"second file" and archive.read_file("top.bin") == b"x"
    archive.write_file("d/a.bin", b"one")
    assert archive.pack() == data                                  # nothing changed: the same bytes
    archive.write_file("d/a.bin", b"a longer first file")
    again = nitro.NarcContainer(archive.pack())
    assert again.read_file("d/a.bin") == b"a longer first file" and again.read_file("d/b.bin") == b"second file"
