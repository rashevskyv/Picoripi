"""Metroid Prime (GameCube) unpack: the text, font and interface texture files of the disc's packages, on a disc
built in the test. The real disc is checked by tests/test_core/test_metroid_prime_real.py."""
import struct
import zlib

from gc_disc import build_disc
from plugins.metroid_prime_trilogy import unpack
from plugins.metroid_prime_trilogy.rules import GameRules


def _font(name: str, texture: int) -> bytes:
    """A version 0 FONT form with no glyphs: the name at offset 26, then the texture id (the layout ``font_parts`` reads)."""
    return b"FONT" + struct.pack(">I", 0) + bytes(18) + name.encode() + b"\0" + struct.pack(">IIII", texture, 0, 0, 0)


def _pak(resources: list) -> bytes:
    """A Prime 1 package. ``resources``: (type, id, name, body, compressed) in directory order."""
    named = [(kind, rid, name) for kind, rid, name, _body, _c in resources if name]
    names = struct.pack(">I", len(named)) + b"".join(
        kind.encode() + struct.pack(">II", rid, len(name)) + name.encode() for kind, rid, name in named)
    header_size = 8 + len(names) + 4 + 20 * len(resources)
    body, directory = bytearray(), []
    for kind, rid, _name, data, compressed in resources:
        stored = struct.pack(">I", len(data)) + zlib.compress(data) if compressed else data
        directory.append(struct.pack(">I4sIII", 1 if compressed else 0, kind.encode(), rid, len(stored),
                                     header_size + len(body)))
        body += stored
    head = b"\x00\x03\x00\x05" + bytes(4)
    return head + names + struct.pack(">I", len(resources)) + b"".join(directory) + bytes(body)


FONT = _font("FONT_Small", 0xABCD)
PAKS = {
    "Aaa.pak": _pak([("STRG", 0x1234, "STRG_Greeting", b"FIRST", True)]),
    "gguisys.pak": _pak([("TXTR", 0xABCD, "TXTR_Button", b"TXTR-BODY", False),
                         ("TXTR", 0xBEEF, "TXTR_Panel", b"PANEL", False)]),
    "Test.pak": _pak([("STRG", 0x1234, "STRG_Greeting", b"SECOND", False),
                      ("STRG", 0x9999, "STRG_Other", b"OTHER", True),
                      ("FONT", 0x5678, "FONT_Small", FONT, False)]),
}
# Aaa.pak sorts first, so its table with id 0x1234 is the one written; the font's texture is written with the font.
EXPECTED = {
    "text/Aaa/Greeting.00001234.strg": b"FIRST",
    "text/Test/Other.00009999.strg": b"OTHER",
    "font/Small.00005678.font": FONT + b"TXTR-BODY",
    "texture/gguisys/Panel.0000BEEF.txtr": b"PANEL",
}


def _disc_file(tmp_path, game_id: bytes = b"GM8E01", wii: bool = False):
    path = tmp_path / "disc.iso"
    path.write_bytes(build_disc(dict(PAKS), game_id=game_id, wii=wii))
    return path


def _tree(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def _noop(*_):
    pass


def test_text_fonts_and_interface_textures_of_every_package(tmp_path):
    out = tmp_path / "source"
    assert unpack.extract(str(_disc_file(tmp_path)), str(out), _noop, lambda: False) == str(out)
    assert _tree(out) == EXPECTED


def test_other_discs_are_left_alone(tmp_path):
    assert unpack.extract(str(_disc_file(tmp_path, game_id=b"GM8P01")), str(tmp_path / "pal"), _noop,
                          lambda: False) is None
    assert unpack.extract(str(_disc_file(tmp_path, game_id=b"R3ME01", wii=True)), str(tmp_path / "wii"), _noop,
                          lambda: False) is None


def test_cancel_returns_none(tmp_path):
    assert unpack.extract(str(_disc_file(tmp_path)), str(tmp_path / "out"), _noop, lambda: True) is None


def test_rules_unpack_a_gc_disc_and_leave_a_wii_disc_alone(tmp_path):
    rules = GameRules(None)
    assert rules.unpack_sources({"base": str(_disc_file(tmp_path))}, str(tmp_path / "out"), _noop,
                                lambda: False) == str(tmp_path / "out")
    assert rules.unpack_sources({"base": str(_disc_file(tmp_path, game_id=b"R3ME01", wii=True))},
                                str(tmp_path / "wii"), _noop, lambda: False) is None
