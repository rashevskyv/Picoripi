"""Pokémon Black / White (DS) ROM build without zt: the wizard's unpack keeps the clean image, the build writes one
longer line into a message file and the ROM lays out again. The Black image is DSi-enhanced, so the build also turns
it into a plain NDS image (real data; skipped without the workspace image)."""
from pathlib import Path

import pytest

import romhacking_root
from core.containers import nds_write
from core.containers.narc_members import narc_members
from plugins.common import gen5msg
from plugins.pokemon_gen5.rules import BUILD_TARGET, GameRules


def _black_image():
    folder = romhacking_root.path("Pokemon", "Black and White", "ISO")
    images = sorted(folder.glob("*.nds")) if folder.is_dir() else []
    if not images:
        pytest.skip("no Black image on disk under the workspace")
    return images[0]


def test_real_black_unpack_then_build_writes_a_longer_line(tmp_path):
    iso = _black_image()
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
    assert built[0x12] == 0, "the DSi-enhanced image must come out as plain NDS"
    nds_write.check_header(built)

    # the folder name is the archive name with "/" for "_"; the file name is the member index
    archive = path.parent.name.replace("_", "/")
    index = int(path.stem)
    member = narc_members(nds_write.nitro_files(built)[archive])[index]
    assert gen5msg.to_editor(gen5msg.read(member)[0].units) == text
