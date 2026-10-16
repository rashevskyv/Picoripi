"""Pokémon generation IV (DS) ROM build without zt: the wizard's unpack keeps the clean image and the build writes a
ROM with one longer bank (Platinum, real data; skipped without the workspace image)."""
import romhacking_root
from pathlib import Path

import pytest

from core.containers import nds_write
from core.containers.narc_members import narc_members
from plugins.common import gen4msg
from plugins.pokemon_gen4.rules import BUILD_TARGET, GameRules

CHARMAP = Path(__file__).resolve().parents[3] / "plugins" / "pokemon_gen4" / "charmaps" / "charmap_platinum.txt"
PLATINUM = ("Pokemon", "Platinum", "ISO", "Pokemon - Platinum Version (USA).nds")


def test_the_build_target_is_declared_as_a_nds_patch():
    targets = GameRules(None).get_build_targets()
    assert targets == [{"id": BUILD_TARGET, "label": targets[0]["label"], "platforms": ["nds"], "kind": "patch"}]


def test_real_platinum_unpack_then_build_writes_a_longer_bank(tmp_path):
    reason = romhacking_root.missing(*PLATINUM)
    if reason:
        pytest.skip(reason)
    iso = str(romhacking_root.path(*PLATINUM))
    rules = GameRules(None)
    source = tmp_path / "source"
    translation = tmp_path / "translation"
    rules.unpack_sources({"base": iso}, str(source), lambda *_: None, lambda: False)
    assert (source / "rom" / "base.nds").is_file()

    codec = gen4msg.Codec(str(CHARMAP))
    bank_path = source / "text" / "msgdata+msg.narc" / "0000.msg"
    _codec, bank = gen4msg.open_bank(bank_path.read_bytes(), [codec])
    texts = gen4msg.decode_all(bank, codec)
    texts[0] = texts[0] + " A longer line from the test"
    edited = gen4msg.encode_bank(gen4msg.encode_all(texts, codec, base=bank))
    (translation / "text" / "msgdata+msg.narc").mkdir(parents=True)
    (translation / "text" / "msgdata+msg.narc" / "0000.msg").write_bytes(edited)

    out = tmp_path / "out"
    out.mkdir()
    built_path = Path(rules.build_target(BUILD_TARGET, str(source), str(translation), str(out),
                                         lambda *_: None, lambda: False))
    built = built_path.read_bytes()
    assert built_path.name.endswith("_UA.nds")
    nds_write.check_header(built)
    bank_back = narc_members(nds_write.nitro_files(built)["msgdata/msg.narc"])[0]
    _c, back = gen4msg.open_bank(bank_back, [codec])
    assert gen4msg.decode_all(back, codec)[0] == texts[0]
