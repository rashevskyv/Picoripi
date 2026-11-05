"""The disc: unpack the scripts of a tiny image, change one, build, and read the result back."""
import os

from plugins.zoe2_ps2 import build, unpack
from plugins.zoe2_ps2.rules import GameRules

from .helpers import make_dat, make_iso, make_scx, make_stage

CNF = b"BOOT2 = cdrom0:\\SLUS_205.45;1\nVER = 1.01\nVMODE = NTSC\n"


def _image(tmp_path):
    a = make_stage("ca01", [("cache", [("mdz", os.urandom(6000)), ("scx", make_scx([b"Save game.", b"Yes"]))])])
    b = make_stage("af01", [("cache", [("scx", make_scx([b"Hand over Jehuty!"]))])])
    path = tmp_path / "zoe2.iso"
    path.write_bytes(make_iso({"SYSTEM.CNF": CNF, "STAGE.DAT": make_dat({"ca01": a, "af01": b})}))
    return str(path)


def _unpack(image, tmp_path, name):
    folder = tmp_path / name
    folder.mkdir()
    unpack.unpack({"base": image}, str(folder), lambda p, m: None, lambda: False)
    return folder


def _edit(folder, stage, index, text):
    rules = GameRules()
    path = folder / "scx" / f"{stage}.scx"
    blocks, _ = rules.load_data_from_json_obj(path.read_bytes())
    blocks[0][index] = text
    path.write_bytes(rules.save_data_to_json_obj(blocks, {}))


def _build(source, translation, tmp_path):
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    return build.build_ps2(str(source), str(translation), str(out), lambda p, m: None, lambda: False)


def test_the_disc_is_identified_and_the_scripts_unpack(tmp_path):
    image = _image(tmp_path)
    assert unpack.identify(image) == {"role": "base", "platform": "ps2", "libraries": []}
    source = _unpack(image, tmp_path, "source")
    assert sorted(os.listdir(source / "scx")) == ["af01.scx", "ca01.scx"]
    blocks, _ = GameRules().load_data_from_json_obj((source / "scx" / "ca01.scx").read_bytes())
    assert blocks == [["Save game.", "Yes"]]


def test_a_build_without_changes_is_a_copy(tmp_path):
    image = _image(tmp_path)
    source = _unpack(image, tmp_path, "source")
    built = _build(source, source, tmp_path)
    assert open(built, "rb").read() == open(image, "rb").read()


def test_an_edited_line_changes_in_the_rebuilt_disc_and_nothing_else(tmp_path):
    image = _image(tmp_path)
    source = _unpack(image, tmp_path, "source")
    translation = _unpack(image, tmp_path, "translation")
    _edit(translation, "ca01", 0, "Save the game now, please.")
    built = _build(source, translation, tmp_path)
    again = _unpack(built, tmp_path, "again")
    blocks, _ = GameRules().load_data_from_json_obj((again / "scx" / "ca01.scx").read_bytes())
    assert blocks == [["Save the game now, please.", "Yes"]]
    assert (again / "scx" / "af01.scx").read_bytes() == (source / "scx" / "af01.scx").read_bytes()


def test_a_stage_that_outgrows_its_sectors_moves_stage_dat_to_the_end_of_the_image(tmp_path):
    image = _image(tmp_path)
    source = _unpack(image, tmp_path, "source")
    translation = _unpack(image, tmp_path, "translation")
    noise = os.urandom(2000).hex()                                  # does not pack: the stage needs more sectors
    _edit(translation, "af01", 0, noise)
    big = (translation / "scx" / "af01.scx").read_bytes()
    built = _build(source, translation, tmp_path)
    again = _unpack(built, tmp_path, "again")
    assert (again / "scx" / "af01.scx").read_bytes() == big
    assert (again / "scx" / "ca01.scx").read_bytes() == (source / "scx" / "ca01.scx").read_bytes()
    assert os.path.getsize(built) > os.path.getsize(image)
