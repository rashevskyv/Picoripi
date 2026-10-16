"""The shared Pokémon DS builder (``plugins.common.nds_build``) on a synthetic image: a changed bank goes into its NARC,
a changed picture replaces its NitroFS file, an unknown file is refused and an untouched project gives the image back."""
import pytest

from core.containers import nds_write
from core.containers.narc_members import narc_members
from nds_rom import narc, nds_rom
from plugins.common import nds_build

BASE = nds_rom({
    "msgdata/msg.narc": narc([b"bank zero", b"bank one", b"bank two"]),
    "a/0/0/1": b"picture-data" * 20,
})


def _project(tmp_path, translation):
    source = tmp_path / "source"
    (source / "rom").mkdir(parents=True)
    (source / "rom" / "base.nds").write_bytes(BASE)
    folder = tmp_path / "translation"
    folder.mkdir()
    for rel, data in translation.items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return str(source), str(folder)


def _build(tmp_path, translation):
    source, folder = _project(tmp_path, translation)
    return nds_build.build_text_rom(source, folder, narc_of_folder=lambda name: name.replace("+", "/"),
                                    is_text=lambda data: True)


def test_an_empty_translation_gives_the_clean_image_back(tmp_path):
    assert _build(tmp_path, {}) == BASE


def test_a_changed_bank_goes_into_its_narc_and_the_rest_is_kept(tmp_path):
    longer = b"a much longer bank one, grown past the old length"
    built = _build(tmp_path, {"text/msgdata+msg.narc/0001.msg": longer})
    members = narc_members(nds_write.nitro_files(built)["msgdata/msg.narc"])
    assert members == [b"bank zero", longer, b"bank two"]
    assert nds_write.nitro_files(built)["a/0/0/1"] == b"picture-data" * 20
    nds_write.check_header(built)


def test_a_changed_picture_replaces_its_nitro_file(tmp_path):
    built = _build(tmp_path, {"a/0/0/1": b"new" * 50})
    assert nds_write.nitro_files(built)["a/0/0/1"] == b"new" * 50
    assert narc_members(nds_write.nitro_files(built)["msgdata/msg.narc"]) == [b"bank zero", b"bank one", b"bank two"]


def test_a_bank_index_past_the_archive_is_refused(tmp_path):
    with pytest.raises(nds_build.NdsBuildError, match="members"):
        _build(tmp_path, {"text/msgdata+msg.narc/0009.msg": b"x"})


def test_a_file_the_game_does_not_have_is_refused(tmp_path):
    with pytest.raises(nds_build.NdsBuildError, match="no such file"):
        _build(tmp_path, {"zz/nothing.bin": b"x"})


def test_a_missing_clean_image_is_refused(tmp_path):
    (tmp_path / "source").mkdir()
    (tmp_path / "translation").mkdir()
    with pytest.raises(nds_build.NdsBuildError, match="no clean image"):
        nds_build.build_text_rom(str(tmp_path / "source"), str(tmp_path / "translation"),
                                 narc_of_folder=lambda name: name, is_text=lambda data: True)
