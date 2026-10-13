"""Game image readers (GameCube discs, Nintendo DS cartridges) and the unpack helper, on images built in the test."""
import io
import struct

import pytest

from core.containers.gcm import GameCubeImage
from core.containers.image_files import ImageError
from core.containers.nds import NdsImage, walk_fnt
from core.project_library import images

GC_NAMES = b"dir\0inner.bin\0top.bin\0"


def _gc_disc(game_id: bytes = b"TSTE01", wii: bool = False, bad_name: bool = False) -> bytes:
    image = bytearray(0x2A00)
    image[0:6] = game_id
    if wii:
        struct.pack_into(">I", image, 0x18, 0x5D1C9EA3)
    else:
        struct.pack_into(">I", image, 0x1C, 0xC2339F3D)
    # apploader at 0x2440: header 0x20, then code size and trailer size (4 and 4 bytes)
    struct.pack_into(">II", image, 0x2454, 4, 4)
    # DOL at 0x2480: a header with one text section of 0x20 bytes at offset 0x100
    dol = 0x2480
    struct.pack_into(">I", image, dol, 0x100)
    struct.pack_into(">I", image, dol + 0x90, 0x20)
    names = b"a:b\0inner.bin\0top.bin\0" if bad_name else GC_NAMES
    fst_size = 4 * 12 + len(names)
    struct.pack_into(">III", image, 0x420, dol, 0x2600, fst_size)
    # FST at 0x2600: root (count 4), dir "dir" (its contents end before index 3), inner.bin, top.bin
    entries = [
        struct.pack(">III", 0x01000000, 0, 4),
        struct.pack(">III", 0x01000000, 0, 3),
        struct.pack(">III", 4, 0x2800, 5),
        struct.pack(">III", 14, 0x2900, 3),
    ]
    image[0x2600:0x2600 + fst_size] = b"".join(entries) + names
    image[0x2800:0x2805] = b"hello"
    image[0x2900:0x2903] = b"abc"
    return bytes(image)


def _nds_rom(code: bytes = b"TSTE") -> bytes:
    rom = bytearray(0x600)
    rom[0:4] = b"TEST"
    rom[0x0C:0x10] = code
    struct.pack_into("<4I", rom, 0x20, 0x200, 0x2000000, 0x2000000, 8)   # ARM9 at 0x200, 8 bytes
    # FNT at 0x300: the root directory (a.bin) and its sub directory (sub/b.bin)
    root_table = b"\x05a.bin" + b"\x83sub" + struct.pack("<H", 0xF001) + b"\x00"
    sub_table = b"\x05b.bin\x00"
    main = struct.pack("<IHH", 16, 0, 0xF000) + struct.pack("<IHH", 16 + len(root_table), 1, 0xF000)
    fnt = main + root_table + sub_table
    rom[0x300:0x300 + len(fnt)] = fnt
    struct.pack_into("<4I", rom, 0x40, 0x300, len(fnt), 0x380, 16)
    struct.pack_into("<II", rom, 0x380, 0x400, 0x405)      # file 0: a.bin
    struct.pack_into("<II", rom, 0x388, 0x500, 0x507)      # file 1: sub/b.bin
    rom[0x200:0x208] = b"ARM9DATA"
    rom[0x400:0x405] = b"hello"
    rom[0x500:0x507] = b"world!!"
    struct.pack_into("<H", rom, 0x15C, 0xCF56)
    return bytes(rom), len(fnt)


def test_gamecube_entries_and_file_contents():
    disc = GameCubeImage(io.BytesIO(_gc_disc()))
    assert disc.game_id == "TSTE01"
    by_path = {entry.path: entry for entry in disc.entries()}
    assert (by_path["sys/boot.bin"].offset, by_path["sys/boot.bin"].size) == (0, 0x440)
    assert (by_path["sys/bi2.bin"].offset, by_path["sys/bi2.bin"].size) == (0x440, 0x2000)
    assert by_path["sys/apploader.img"].size == 0x20 + 4 + 4
    assert by_path["sys/main.dol"].size == 0x120
    assert by_path["sys/fst.bin"].size == 4 * 12 + len(GC_NAMES)
    assert disc.read(by_path["files/dir/inner.bin"]) == b"hello"
    assert disc.read(by_path["files/top.bin"]) == b"abc"


def test_gamecube_rejects_wii_and_unknown_files():
    with pytest.raises(ImageError, match="Wii disc"):
        GameCubeImage(io.BytesIO(_gc_disc(wii=True)))
    with pytest.raises(ImageError, match="not a GameCube"):
        GameCubeImage(io.BytesIO(b"\0" * 0x440))


def test_gamecube_rejects_unsafe_names():
    with pytest.raises(ImageError, match="unsafe file name"):
        GameCubeImage(io.BytesIO(_gc_disc(bad_name=True))).entries()


def test_nds_entries_and_file_contents():
    rom, _fnt_size = _nds_rom()
    cart = NdsImage(io.BytesIO(rom))
    assert cart.game_code == "TSTE"
    by_path = {entry.path: entry for entry in cart.entries()}
    assert cart.read(by_path["main.arm9"]) == b"ARM9DATA"
    assert cart.read(by_path["a.bin"]) == b"hello"
    assert cart.read(by_path["sub/b.bin"]) == b"world!!"


def test_nds_file_name_table_maps_paths_to_file_ids():
    rom, fnt_size = _nds_rom()
    assert walk_fnt(rom[0x300:0x300 + fnt_size]) == {"a.bin": 0, "sub/b.bin": 1}


def test_nds_rejects_other_files():
    with pytest.raises(ImageError, match="Nintendo DS"):
        NdsImage(io.BytesIO(b"\0" * 0x600))


def test_extract_writes_the_selected_files(tmp_path):
    image = tmp_path / "game.iso"
    image.write_bytes(_gc_disc())
    progress = []
    folder = images.extract(image, tmp_path / "out", lambda p, t: progress.append(p), lambda: False)
    assert folder == str(tmp_path / "out")
    assert (tmp_path / "out" / "sys" / "main.dol").stat().st_size == 0x120
    assert (tmp_path / "out" / "files" / "dir" / "inner.bin").read_bytes() == b"hello"
    assert progress[-1] == 100

    only = images.extract(image, tmp_path / "only", lambda p, t: None, lambda: False,
                          select=lambda path: path.startswith("files/top"))
    assert only is not None
    assert sorted(p.name for p in (tmp_path / "only").rglob("*") if p.is_file()) == ["top.bin"]


def test_extract_returns_none_when_cancelled(tmp_path):
    image = tmp_path / "game.iso"
    image.write_bytes(_gc_disc())
    assert images.extract(image, tmp_path / "out", lambda p, t: None, lambda: True) is None


def test_identify_and_unsupported_formats(tmp_path):
    (tmp_path / "rom.nds").write_bytes(_nds_rom(b"KQ9V")[0])
    (tmp_path / "text.iso").write_bytes(b"not an image")
    rvz = tmp_path / "game.rvz"
    rvz.write_bytes(b"RVZ\x01" + b"\0" * 0x500)
    assert images.identify(tmp_path / "rom.nds") == {"kind": "nds", "game_id": "KQ9V"}
    assert images.identify(tmp_path / "text.iso") is None
    assert images.identify(tmp_path / "missing.iso") is None
    with pytest.raises(ImageError, match="RVZ"):
        images.extract(rvz, tmp_path / "out", lambda p, t: None, lambda: False)


def test_base_identity_matches_game_codes(tmp_path):
    (tmp_path / "rom.nds").write_bytes(_nds_rom(b"KQ9V")[0])
    assert images.base_identity(tmp_path / "rom.nds", ("KQ9V",)) == {"role": "base", "platform": "nds"}
    assert images.base_identity(tmp_path / "rom.nds", ("AZEE",)) is None


def test_four_swords_plugin_takes_its_files(tmp_path):
    from plugins.zelda_fsae.rules import GameRules

    (tmp_path / "fsae.nds").write_bytes(_nds_rom(b"KQ9V")[0])
    rules = GameRules(None)
    assert rules.get_platforms() == [{"id": "nds", "label": "Nintendo DS"}]
    assert rules.identify_source(str(tmp_path / "fsae.nds")) == {"role": "base", "platform": "nds"}
    folder = rules.unpack_sources({"base": str(tmp_path / "fsae.nds")}, str(tmp_path / "out"),
                                  lambda p, t: None, lambda: False)
    assert folder == str(tmp_path / "out")
    # The synthetic ROM has a.bin and sub/b.bin, neither in the Four Swords set; only main.arm9 is kept.
    assert sorted(p.name for p in (tmp_path / "out").rglob("*") if p.is_file()) == ["main.arm9"]
