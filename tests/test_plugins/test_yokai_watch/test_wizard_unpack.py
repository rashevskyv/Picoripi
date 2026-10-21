"""Yo-kai Watch 1 wizard unpack: the ARC0 archives are read in place in the image, ``source/`` and ``meta/`` written.

The synthetic tests build a small 3DS card image and two small archives. The real-data tests run through
``build.run_unpack`` (the wizard's own job) on the owner's images, compare the result with the zt workspace, and skip
when the files are not on disk. The Switch key path comes from the shared env file and is given to Picoripi's reader as a path only.
"""
import hashlib
import io
import shutil
import struct
from pathlib import Path

import pytest
import romhacking_root

from core.containers import console_crypto
from core.containers.image_files import ImageError, ImageFile, ImageReader
from core.project_library import build
from core.project_library.source_folder import validate_source_folder
from plugins.testing import load_rules
from plugins.yokai_watch import unpack
from plugins.yokai_watch.arc0 import Arc0
from plugins.yokai_watch.speakers import game_of
from plugins.yokai_watch.textfile import TextFile
from test_core.test_n3ds_image import NO, _dir_entry, _file_entry, _pad4, build_cci, build_ncch
from test_plugins.test_pokemon_nx.test_unpack import _switch_key_path
from .samples import arc0_file, dialogue_file

TEXT = "data/res/text/system_text_en.cfg.bin"
MEMBERS_3DS = {
    TEXT: dialogue_file(),
    "data/txt/ev/ev01_0010_map.cfg.bin": b"speaker map",
    "fnt/ft_nrm.xf": b"font",
    "data/menu/en/title.xi": b"english image",
    "data/menu/title.xi": b"shared image",
    "data/res/text/system_text_ja.cfg.bin": b"other language",
    "snd/voice.acb": b"voice",
}
WS = romhacking_root.under("Yo-kai Watch/Yo-kai Watch")


def _romfs_of(name: str, data: bytes) -> bytes:
    """An IVFC RomFS whose root holds one file."""
    dir_meta = _dir_entry(0, NO, NO, 0)
    file_meta = _file_entry(0, NO, 0, len(data), name)
    dir_off = 0x28
    file_off = dir_off + len(dir_meta)
    data_off = file_off + len(file_meta)
    header = struct.pack("<10I", 0x28, 0, 0, dir_off, len(dir_meta), 0, 0, file_off, len(file_meta), data_off)
    ivfc = bytearray(0x1000)
    ivfc[0:4] = b"IVFC"
    struct.pack_into("<I", ivfc, 0x4C, 12)
    return bytes(ivfc) + _pad4(_pad4(header + dir_meta) + file_meta) + data


def _card(tmp_path: Path, product: bytes = b"CTR-P-AYWE") -> Path:
    def name(body):
        body[0x150:0x15A] = product
        return body
    path = tmp_path / "game.3ds"
    path.write_bytes(build_cci(build_ncch(romfs=_romfs_of("yw1_a.fa", arc0_file(MEMBERS_3DS)), tamper=name)))
    return path


def _files(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _run(rules, sources, project, is_cancelled=lambda: False, provider=lambda console: None):
    with console_crypto.key_source(provider):
        return build.run_unpack(rules, sources, str(project), lambda percent, text: None, is_cancelled, provider)


def test_3ds_card_unpacks_text_fonts_and_textures_into_source_and_speaker_tables_into_meta(tmp_path):
    rules = load_rules("yokai_watch")
    card = _card(tmp_path)
    assert rules.identify_source(str(card)) == {"role": "base", "platform": "3ds"}
    folder = Path(_run(rules, {"base": str(card)}, tmp_path / "project"))
    assert folder.name == "source"
    assert _files(folder) == {name: MEMBERS_3DS[name] for name in (TEXT, "fnt/ft_nrm.xf", "data/menu/en/title.xi")}
    assert _files(folder.parent / "meta") == {"data/txt/ev/ev01_0010_map.cfg.bin": b"speaker map"}
    # the wizard's check of a source folder finds the text, and the plugin reads it as Yo-kai Watch 1
    assert validate_source_folder(rules, str(folder), lambda: False) == str(folder)
    assert game_of(folder) == "yw1"


def test_another_3ds_game_is_not_identified_and_cancel_leaves_no_folder(tmp_path):
    rules = load_rules("yokai_watch")
    assert rules.identify_source(str(_card(tmp_path, b"CTR-P-TEST"))) is None
    with pytest.raises(build.Cancel):
        _run(rules, {"base": str(_card(tmp_path))}, tmp_path / "project", is_cancelled=lambda: True)
    assert list((tmp_path / "project").iterdir()) == []


def test_switch_update_archive_replaces_the_base_members(tmp_path):
    base = arc0_file({"data/res/text/system_text_ja.cfg.bin": b"base text", "fnt/ft_nrm.xf": b"font",
                      "data/menu/title.xa": b"menu", "data/res/text/system_text_en.cfg.bin": b"not Switch text",
                      "data/res/character/chara_base_0.cfg.bin": b"characters"})
    update = arc0_file({"data/res/text/system_text_ja.cfg.bin": b"update text"})
    reader = ImageReader(io.BytesIO(base + update))
    entries = [ImageFile("romfs/yw1_a.fa", 0, len(base)), ImageFile("romfs/yw1_1_1.fa", len(base), len(update))]
    assert unpack.write_archives(reader, entries, "switch", str(tmp_path), lambda p, t: None, lambda: False)
    assert _files(tmp_path / "source") == {"data/res/text/system_text_ja.cfg.bin": b"update text",
                                           "fnt/ft_nrm.xf": b"font", "data/menu/title.xa": b"menu"}
    assert _files(tmp_path / "meta") == {"data/res/character/chara_base_0.cfg.bin": b"characters"}


def test_archive_read_from_a_stream_lists_and_reads_the_same_members_as_from_its_file(tmp_path):
    raw = arc0_file(MEMBERS_3DS)
    path = tmp_path / "yw1_a.fa"
    path.write_bytes(raw)
    from_file, from_stream = Arc0(path), Arc0(io.BytesIO(raw))
    assert from_file.files == from_stream.files and from_stream.read(TEXT) == MEMBERS_3DS[TEXT]


# -- the owner's images ------------------------------------------------------------------------------------------------

def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}


def _same_as_workspace(folder: Path, home: Path) -> None:
    """``source`` and ``meta`` equal the workspace's, but for what the English fan mod changed (Switch): a table the
    mod translated equals its Japanese original in ``reference_ja``, a file only the mod has is missing."""
    english, japanese = _tree(home / "english"), _tree(home / "reference_ja")
    for part in ("source", "meta"):
        ours, theirs = _tree(folder.parent / part), _tree(home / part)
        assert set(ours) == {name for name in theirs if name in ours or name not in english}
        for name, path in ours.items():
            if name in japanese:
                assert _sha(path) == _sha(japanese[name]), name
            elif name not in english:
                assert _sha(path) == _sha(theirs[name]), name


@pytest.mark.timeout(600)  # reads the 386 MB archive and hashes about 5,000 files: slow under parallel load
def test_3ds_image_unpacks_like_the_workspace_and_the_text_loads(tmp_path):
    image = WS / "3DS/ISO/Yo-Kai Watch (USA).3ds"
    if not image.is_file() or not (WS / "3DS/source").is_dir():
        pytest.skip("the owner's Yo-kai Watch 3DS image or workspace is not on disk")
    rules = load_rules("yokai_watch")
    folder = Path(_run(rules, {"base": str(image)}, tmp_path / "project"))
    _same_as_workspace(folder, WS / "3DS")
    event = next((folder / "data/txt/ev").glob("*_en.cfg.bin"))
    assert any(TextFile(event.read_bytes(), event.name).texts())


@pytest.mark.timeout(900)  # the base .nsz is decompressed (4.4 GB): about 80 s alone, more under load
def test_switch_images_unpack_like_the_workspace(tmp_path):
    iso = WS / "Switch/ISO"
    base = next(iter(iso.glob("*[[]0100C0000CEEA000[]]*.ns[pz]")), None) if iso.is_dir() else None
    update = next(iter(iso.glob("*[[]0100C0000CEEA800[]]*.ns[pz]")), None) if iso.is_dir() else None
    if base is None or update is None or not (WS / "Switch/source").is_dir():
        pytest.skip("the owner's Yo-kai Watch Switch packages or workspace are not on disk")
    keys = _switch_key_path()
    if keys is None:
        pytest.skip("the Switch key path is not in the shared env file")
    if shutil.disk_usage(tmp_path).free < 12 << 30:
        pytest.skip("the unpack of the .nsz needs about 12 GB free")
    rules = load_rules("yokai_watch")
    assert rules.identify_source(str(update)) == {"role": "update", "platform": "switch"}
    with pytest.raises(ImageError):   # the base game alone: refused before anything is decompressed
        rules.unpack_sources({"base": str(base)}, str(tmp_path), lambda p, t: None, lambda: False)
    folder = Path(_run(rules, {"base": str(base), "update": str(update)}, tmp_path / "project",
                       provider=lambda console: keys if console == "switch" else None))
    assert game_of(folder) == "ywnx"
    _same_as_workspace(folder, WS / "Switch")
