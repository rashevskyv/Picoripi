"""Pokémon Black / White and Black 2 (DS) ROM build without zt: the wizard's unpack keeps the clean image, the build
writes one longer line into a message file and the ROM lays out again. The Black image is DSi-enhanced, so the build also
turns it into a plain NDS image; Black 2 is a plain NDS image (real data; skipped without the workspace images)."""
from pathlib import Path

import pytest

import romhacking_root
from core.containers import nds_write
from core.containers.narc_members import narc_members
from plugins.common import gen5msg
from plugins.pokemon_gen5.rules import BUILD_TARGET, GameRules

CASES = [
    ("Black and White", "Pokemon - Black Version (DSi Enhanced)(USA) (E)(SweeTnDs).nds"),
    ("Black 2 and White 2", "Pokemon - Black Version 2 (U) (frieNDS).nds"),
]


@pytest.mark.parametrize("game,image", CASES)
def test_real_unpack_then_build_writes_a_longer_line(tmp_path, game, image):
    iso = romhacking_root.path("Pokemon", game, "ISO", image)
    reason = romhacking_root.missing("Pokemon", game, "ISO", image)
    if reason:
        pytest.skip(reason)
    rules = GameRules(None)
    source, translation = tmp_path / "source", tmp_path / "translation"
    rules.unpack_sources({"base": str(iso)}, str(source), lambda *_: None, lambda: False)
    assert (source / "rom" / "base.nds").is_file()

    path = None
    for candidate in sorted((source / "text").rglob("*.msg")):
        lines = gen5msg.read(candidate.read_bytes())
        if lines and lines[0].units:
            path, first = candidate, lines
            break
    assert path is not None, "no message file with lines"
    text = gen5msg.to_editor(first[0].units) + " A longer line from the test"
    first[0] = gen5msg.Line(units=gen5msg.from_editor(text), flags=first[0].flags, packed=first[0].packed)
    edited = translation / path.relative_to(source)
    edited.parent.mkdir(parents=True, exist_ok=True)
    edited.write_bytes(gen5msg.write(first))

    out = tmp_path / "out"
    out.mkdir()
    built = Path(rules.build_target(BUILD_TARGET, str(source), str(translation), str(out),
                                    lambda *_: None, lambda: False)).read_bytes()
    nds_write.check_header(built)
    assert built[0x12] == 0

    # the folder name is the archive name with "/" for "_"; the file name is the member index
    archive = path.parent.name.replace("_", "/")
    index = int(path.stem)
    member = narc_members(nds_write.nitro_files(built)[archive])[index]
    assert gen5msg.to_editor(gen5msg.read(member)[0].units) == text
