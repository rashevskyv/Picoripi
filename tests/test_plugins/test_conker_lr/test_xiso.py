"""Conker: Live & Reloaded XISO reader on a tiny synthetic image: tree walk, extraction, XBE title id."""
import struct

from plugins.conker_lr import xiso

SECTOR = 2048
ROOT_SECTOR = 33
DIR_SECTOR = 34
TITLE_ID = 0x4D530051


def _entry_bytes(entries):
    """Directory bytes for (name, sector, size, is_dir, left, right); left/right are entry indexes or None."""
    offsets = []
    position = 0
    for name, *_ in entries:
        offsets.append(position)
        position += (14 + len(name) + 3) // 4 * 4
    out = bytearray(position)
    for index, (name, sector, size, is_dir, left, right) in enumerate(entries):
        pos = offsets[index]
        left_value = offsets[left] // 4 if left is not None else 0
        right_value = offsets[right] // 4 if right is not None else 0
        struct.pack_into("<HH", out, pos, left_value, right_value)
        struct.pack_into("<IIBB", out, pos + 4, sector, size, 0x10 if is_dir else 0x20, len(name))
        out[pos + 14:pos + 14 + len(name)] = name.encode("latin-1")
    return bytes(out)


def _image(path):
    """An XISO with: a.txt (file), dir/ (folder) holding c.bin."""
    image = bytearray(40 * SECTOR)
    image[0x10000:0x10000 + 20] = xiso.MAGIC
    sub_bytes = _entry_bytes([("c.bin", 36, 3, False, None, None)])
    root_bytes = _entry_bytes([
        ("dir", DIR_SECTOR, len(sub_bytes), True, None, 1),
        ("a.txt", 35, 5, False, None, None),
    ])
    struct.pack_into("<II", image, 0x10014, ROOT_SECTOR, len(root_bytes))
    image[ROOT_SECTOR * SECTOR:ROOT_SECTOR * SECTOR + len(root_bytes)] = root_bytes
    image[DIR_SECTOR * SECTOR:DIR_SECTOR * SECTOR + len(sub_bytes)] = sub_bytes
    image[35 * SECTOR:35 * SECTOR + 5] = b"hello"
    image[36 * SECTOR:36 * SECTOR + 3] = b"bin"
    path.write_bytes(bytes(image))
    return str(path)


def test_the_tree_is_walked_and_files_are_read(tmp_path):
    path = _image(tmp_path / "disc.iso")
    with xiso.XisoImage(path) as image:
        paths = sorted(e.path for e in image.walk() if not e.is_dir)
        assert paths == ["a.txt", "dir/c.bin"]
        entry = image.find("a.txt")
        assert image.read(entry) == b"hello"


def test_extract_copies_only_the_wanted_files(tmp_path):
    path = _image(tmp_path / "disc.iso")
    out = tmp_path / "out"
    with xiso.XisoImage(path) as image:
        written = image.extract(lambda p: p.startswith("dir/"), str(out), lambda *a: None, lambda: False)
    assert written == ["dir/c.bin"]
    assert (out / "dir" / "c.bin").read_bytes() == b"bin"
    assert not (out / "a.txt").exists()


def test_a_plain_file_is_not_an_xiso(tmp_path):
    path = tmp_path / "plain.bin"
    path.write_bytes(b"\x00" * 0x11000)
    assert not xiso.is_xiso(str(path))


def test_the_xbe_title_id_is_read_from_the_certificate():
    xbe = bytearray(0x200)
    xbe[0:4] = b"XBEH"
    struct.pack_into("<I", xbe, 0x104, 0x10000)      # base address
    struct.pack_into("<I", xbe, 0x118, 0x10100)      # certificate address
    struct.pack_into("<I", xbe, 0x100 + 8, TITLE_ID)  # title id at certificate + 8
    assert xiso.xbe_title_id(bytes(xbe)) == TITLE_ID
    assert xiso.xbe_title_id(b"not an xbe" * 10) is None
