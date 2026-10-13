"""Unpack steps of Castlevania DS, Tactics A2 and Dragon Quest IX: the files equal the owner's workspace source files.

Needs ``PICORIPI_ROMHACKING`` (see tests/romhacking_root.py); each test skips with the reason when its file is missing.
"""
import hashlib

import romhacking_root

CV_DOS = ("Castlevania", "Dawn of Sorrow")
CV_POR = ("Castlevania", "Portrait of Ruin")
CV_OOE = ("Castlevania", "Order of Ecclesia")
A2 = ("Final Fantasy", "Tactics A2")
DQ9 = ("Dragon Quest", "Dragon Quest IX")


def _tree(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file()}


def _check(tmp_path, game, rom, module, key=None):
    source = romhacking_root.path(*game, "source", *([key] if key else []))
    out = tmp_path / "unpacked"
    folder = module.extract(str(romhacking_root.path(*game, "ISO", rom)), str(out),
                            lambda p, t: None, lambda: False)
    assert folder == str(out)
    unpacked = _tree(out / key) if key else _tree(out)
    workspace = _tree(source)
    assert {path: unpacked.get(path) for path in workspace} == workspace


@romhacking_root.needs((*CV_DOS, "ISO", "Castlevania - Dawn of Sorrow (USA).nds"), (*CV_DOS, "source", "dos"))
def test_castlevania_dawn_of_sorrow_unpack_equals_the_workspace(tmp_path):
    from plugins.castlevania_ds import unpack
    _check(tmp_path, CV_DOS, "Castlevania - Dawn of Sorrow (USA).nds", unpack, "dos")


@romhacking_root.needs((*CV_POR, "ISO", "Castlevania - Portrait of Ruin (USA).nds"), (*CV_POR, "source", "por"))
def test_castlevania_portrait_of_ruin_unpack_equals_the_workspace(tmp_path):
    from plugins.castlevania_ds import unpack
    _check(tmp_path, CV_POR, "Castlevania - Portrait of Ruin (USA).nds", unpack, "por")


@romhacking_root.needs((*CV_OOE, "ISO", "Castlevania - Order of Ecclesia (USA) (En,Fr).nds"), (*CV_OOE, "source", "ooe"))
def test_castlevania_order_of_ecclesia_unpack_equals_the_workspace(tmp_path):
    from plugins.castlevania_ds import unpack
    _check(tmp_path, CV_OOE, "Castlevania - Order of Ecclesia (USA) (En,Fr).nds", unpack, "ooe")


@romhacking_root.needs((*A2, "ISO", "Final Fantasy Tactics A2 - Grimoire of the Rift (Europe) (En,Fr,De,Es).nds"),
                       (*A2, "source"))
def test_tactics_a2_unpack_equals_the_workspace(tmp_path):
    from plugins.ffta2 import unpack
    _check(tmp_path, A2, "Final Fantasy Tactics A2 - Grimoire of the Rift (Europe) (En,Fr,De,Es).nds", unpack)


@romhacking_root.needs((*DQ9, "ISO", "Dragon Quest IX - Sentinels of the Starry Skies (Europe) (En,Fr,De,Es,It).nds"),
                       (*DQ9, "source"))
def test_dragon_quest_ix_unpack_equals_the_workspace(tmp_path):
    from plugins.dq9 import unpack
    _check(tmp_path, DQ9, "Dragon Quest IX - Sentinels of the Starry Skies (Europe) (En,Fr,De,Es,It).nds", unpack)
