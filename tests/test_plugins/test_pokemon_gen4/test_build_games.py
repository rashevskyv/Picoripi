"""Pokémon generation IV (DS) native build, real images of Diamond and HeartGold: the wizard's unpack, one longer
bank, build_target, and the bank read back (skipped without the workspace images)."""
from pathlib import Path

import pytest

import romhacking_root
from core.containers import nds_write
from core.containers.narc_members import narc_members
from plugins.common import gen4msg
from plugins.pokemon_gen4.rules import BUILD_TARGET, GameRules

CHARMAP = Path(__file__).resolve().parents[3] / "plugins" / "pokemon_gen4" / "charmaps" / "charmap_dp_hgss.txt"
CASES = [
    ("Diamond and Pearl", "Pokemon - Diamond Version (USA) (Rev 5).nds", "msgdata+msg.narc", "msgdata/msg.narc"),
    # HeartGold keeps its messages in pbr/msg.narc (the unpack folder name uses +)
    ("HeartGold and SoulSilver", "Pokemon - HeartGold Version (USA).nds", "pbr+msg.narc", "pbr/msg.narc"),
]


@pytest.mark.parametrize("game,image,folder,narc", CASES)
def test_real_unpack_then_build_writes_a_longer_bank(tmp_path, game, image, folder, narc):
    iso = romhacking_root.path("Pokemon", game, "ISO", image)
    if romhacking_root.missing("Pokemon", game, "ISO", image):
        pytest.skip(romhacking_root.missing("Pokemon", game, "ISO", image))
    rules = GameRules(None)
    source, translation = tmp_path / "source", tmp_path / "translation"
    rules.unpack_sources({"base": str(iso)}, str(source), lambda *_: None, lambda: False)
    codec = gen4msg.Codec(str(CHARMAP))
    rel = Path("text") / folder / "0000.msg"
    _c, bank = gen4msg.open_bank((source / rel).read_bytes(), [codec])
    texts = gen4msg.decode_all(bank, codec)
    texts[0] = texts[0] + " A longer line from the test"
    (translation / rel).parent.mkdir(parents=True)
    (translation / rel).write_bytes(gen4msg.encode_bank(gen4msg.encode_all(texts, codec, base=bank)))
    out = tmp_path / "out"
    out.mkdir()
    built_path = Path(rules.build_target(BUILD_TARGET, str(source), str(translation), str(out),
                                         lambda *_: None, lambda: False))
    built = built_path.read_bytes()
    nds_write.check_header(built)
    back = narc_members(nds_write.nitro_files(built)[narc])[0]
    _c2, back_bank = gen4msg.open_bank(back, [codec])
    assert gen4msg.decode_all(back_bank, codec)[0] == texts[0]
