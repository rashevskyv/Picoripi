"""Eternal Darkness unpack: which disc files the source folder gets, and the decompressed *SK_ASC* files, on a disc
built in the test. The real disc is checked by tests/test_core/test_eternal_darkness_real.py."""
from gc_disc import DOL, build_disc
from plugins.eternal_darkness import unpack
from plugins.eternal_darkness.rules import GameRules

# The *SK_ASC* streams are the encoder's output for these bodies (a u32 size, then the payload); no game bytes.
TEXT = b"Eternal Darkness: Sanity's Requiem. Eternal Darkness, again. abcabcabc!"
SMALL = bytes.fromhex(
    "2a534b5f4153432a0006c9c41444acdbc3decc65ca00b046e38417839770ed1b123b52ad5f961f30689191e12ff1bdb6cb6c302e6d9ce175d5ce0000")
LONG = b"A" * 70000
BIG = bytes.fromhex("2a534b5f4153432a001bea09b69551c7f707fa27d800bb1050d87e0000")


def _disc_file(tmp_path, files: dict, game_id: bytes = b"GEDE01"):
    path = tmp_path / "disc.iso"
    path.write_bytes(build_disc(files, game_id=game_id))
    return path


def _tree(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def _noop(*_):
    pass


def test_packed_files_are_decompressed_and_plain_files_copied(tmp_path):
    disc = _disc_file(tmp_path, {
        "EBootPak.bin": b"boot",
        "EMemcardText.bin": b"card",
        "top.tpl": b"top",
        "Chars/a.tpl": b"chars",
        "RmTxt00.cmp": SMALL,
        "credits/cr0001.cmp": SMALL,
        "Chars/cin0001/cin0001.bin": BIG,
        "other.bin": b"not used",
        "EFakeMenu.cmp": b"not packed",          # E*Menu.cmp by name, but not *SK_ASC*
        "credits/deeper/cr.cmp": SMALL,          # too deep for credits/*.cmp
        "Chars/cin0001/extra.bin": BIG,          # too deep for Chars/cin*/cin*.bin
    })
    out = tmp_path / "game"
    assert unpack.extract(str(disc), str(out), _noop, lambda: False) == str(out)
    assert _tree(out) == {
        "EBootPak.bin": b"boot",
        "EMemcardText.bin": b"card",
        "top.tpl": b"top",
        "Chars/a.tpl": b"chars",
        "RmTxt00.cmp": TEXT,
        "credits/cr0001.cmp": TEXT,
        "Chars/cin0001/cin0001.bin": LONG,
        "sys/main.dol": DOL,
    }


def test_cancel_returns_none(tmp_path):
    disc = _disc_file(tmp_path, {"RmTxt00.cmp": SMALL, "EBootPak.bin": b"boot"})
    assert unpack.extract(str(disc), str(tmp_path / "game"), _noop, lambda: True) is None


def test_rules_recognise_the_disc_and_unpack_it(tmp_path):
    disc = _disc_file(tmp_path, {"EBootPak.bin": b"boot", "RmTxt00.cmp": SMALL})
    rules = GameRules(None)
    assert rules.identify_source(str(disc)) == {"role": "base", "platform": "gc"}
    assert rules.unpack_sources({"base": str(disc)}, str(tmp_path / "game"), _noop, lambda: False) == \
        str(tmp_path / "game")
    assert _tree(tmp_path / "game")["RmTxt00.cmp"] == TEXT


def test_other_discs_are_not_recognised(tmp_path):
    disc = _disc_file(tmp_path, {"EBootPak.bin": b"boot"}, game_id=b"GM8E01")
    assert GameRules(None).identify_source(str(disc)) is None
