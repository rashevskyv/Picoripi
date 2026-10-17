"""Twilight Princess build targets on synthetic data: the GameCube disc image, the Dusklight mod, the Wii U graphic
pack. Nothing from a real game is in these files."""
import json
import zipfile
from pathlib import Path

import pytest

from core.containers.gcm import GameCubeImage
from core.containers.rarc_container import RarcContainer
from gc_disc import build_disc
from plugins.common import disc_source
from plugins.zelda_bmg import build, hd_pack
from plugins.zelda_bmg.rules import GameRules
from rarc_fixture import build_rarc


def _noop(percent, text):
    return None


def _never() -> bool:
    return False


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _disc_file(image: Path, rel: str) -> bytes:
    with open(image, "rb") as stream:
        disc = GameCubeImage(stream)
        return disc.read(next(e for e in disc.entries() if e.path == rel))


# ------------------------------------------------------------------ the source mark and the disc root

def test_find_disc_root_walks_up_from_the_project_subfolder(tmp_path):
    root = tmp_path / "unpacked"
    _write(root / disc_source.SOURCE_MARK, b"{}")
    assert disc_source.find_disc_root(root / "files" / "res" / "Msgus") == root


def test_a_folder_without_a_mark_is_refused_with_the_unpack_hint(tmp_path):
    with pytest.raises(ValueError, match="unpack the disc again"):
        disc_source.find_disc_root(tmp_path / "files" / "res" / "Msgus")


# ------------------------------------------------------------------ GameCube disc image

def _gc_project(tmp_path):
    """A disc with two message archives and a font; the unpacked source; the translation folder (archives only)."""
    archive = build_rarc({"zel_01.bmg": b"OLD-TEXT"})
    font = b"FONT-SOURCE"
    image = _write(tmp_path / "disc.iso", build_disc({
        "res/Msgus/bmgres1.arc": archive,
        "res/Msgus/bmgres2.arc": build_rarc({"zel_02.bmg": b"KEEP"}),
        "res/Fontus/fontres.arc": font,
    }))
    root = tmp_path / "unpacked"
    _write(root / "files/res/Msgus/bmgres1.arc", archive)
    _write(root / "files/res/Msgus/bmgres2.arc", build_rarc({"zel_02.bmg": b"KEEP"}))
    _write(root / "files/res/Fontus/fontres.arc", font)
    disc_source.write_source_mark(root, image)
    return image, root


def test_gc_iso_replaces_the_translated_archive_and_keeps_the_others(tmp_path):
    image, root = _gc_project(tmp_path)
    new = build_rarc({"zel_01.bmg": b"NEW-TEXT-THAT-IS-LONGER-THAN-BEFORE"})
    trn = _write(tmp_path / "translation" / "bmgres1.arc", new).parent
    out = tmp_path / "out"
    out.mkdir()

    result = build.build_gc_iso(str(root / "files/res/Msgus"), str(trn), str(out), _noop, _never)

    assert Path(result).name == build.GC_ISO_NAME
    assert _disc_file(Path(result), "files/res/Msgus/bmgres1.arc") == new
    assert RarcContainer(_disc_file(Path(result), "files/res/Msgus/bmgres1.arc")).read_file("zel_01.bmg") == \
        b"NEW-TEXT-THAT-IS-LONGER-THAN-BEFORE"
    assert _disc_file(Path(result), "files/res/Msgus/bmgres2.arc") == build_rarc({"zel_02.bmg": b"KEEP"})
    assert _disc_file(image, "files/res/Msgus/bmgres1.arc") == build_rarc({"zel_01.bmg": b"OLD-TEXT"})


def test_a_font_beside_the_translation_folder_is_written_to_the_disc(tmp_path):
    _image, root = _gc_project(tmp_path)
    trn_root = tmp_path / "project"
    _write(trn_root / "translation" / "bmgres1.arc", build_rarc({"zel_01.bmg": b"UA"}))
    _write(trn_root / "Fontus" / "fontres.arc", b"FONT-UA")
    out = tmp_path / "out"
    out.mkdir()

    result = build.build_gc_iso(str(root / "files/res/Msgus"), str(trn_root / "translation"), str(out), _noop,
                                _never)

    assert _disc_file(Path(result), "files/res/Fontus/fontres.arc") == b"FONT-UA"


def test_a_translated_file_the_disc_does_not_hold_is_refused(tmp_path):
    _image, root = _gc_project(tmp_path)
    trn = _write(tmp_path / "translation" / "bmgres9.arc", build_rarc({"zel_09.bmg": b"NEW"})).parent
    out = tmp_path / "out"
    out.mkdir()

    with pytest.raises(ValueError, match="not on the disc"):
        build.build_gc_iso(str(root / "files/res/Msgus"), str(trn), str(out), _noop, _never)
    assert not (out / build.GC_ISO_NAME).exists()


def test_an_unpacked_folder_without_a_mark_is_refused(tmp_path):
    _image, root = _gc_project(tmp_path)
    (root / disc_source.SOURCE_MARK).unlink()
    with pytest.raises(ValueError, match="unpack the disc again"):
        build.build_gc_iso(str(root / "files/res/Msgus"), str(tmp_path), str(tmp_path), _noop, _never)


def test_unpack_sources_writes_the_mark_and_the_build_finds_the_disc(tmp_path):
    image = _write(tmp_path / "disc.iso", build_disc({"res/Msgus/bmgres1.arc": build_rarc({"zel_01.bmg": b"A"})}))
    target = tmp_path / "unpacked"
    target.mkdir()
    rules = GameRules()

    done = rules.unpack_sources({"base": str(image)}, str(target), _noop, _never)

    assert done == str(target)
    assert disc_source.disc_of_source(target) == image
    assert disc_source.find_disc_root(target / "files/res/Msgus") == target


# ------------------------------------------------------------------ Dusklight mod

def test_dusk_mod_is_a_zip_with_mod_json_and_overlay_at_the_disc_paths(tmp_path):
    _image, root = _gc_project(tmp_path)
    new = build_rarc({"zel_01.bmg": b"UA"})
    trn = _write(tmp_path / "translation" / "bmgres1.arc", new).parent
    out = tmp_path / "out"
    out.mkdir()

    result = Path(build.build_dusk_mod(str(root / "files/res/Msgus"), str(trn), str(out), _noop, _never))

    assert result.name == build.DUSK_NAME
    with zipfile.ZipFile(result) as bundle:
        assert set(bundle.namelist()) == {"mod.json", "overlay/res/Msgus/bmgres1.arc"}
        assert bundle.read("overlay/res/Msgus/bmgres1.arc") == new
        manifest = json.loads(bundle.read("mod.json"))
    assert manifest["id"] == build.DUSK_ID


def test_dusk_mod_without_a_changed_file_is_refused(tmp_path):
    _image, root = _gc_project(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError, match="nothing to build"):
        build.build_dusk_mod(str(root / "files/res/Msgus"), str(tmp_path / "nothing"), str(out), _noop, _never)


# ------------------------------------------------------------------ Wii U graphic pack

def _hd_tree(tmp_path, english: bytes, changed: bytes):
    """source/content with the size tables and res/Msguk; translation/content with the changed archive."""
    content = tmp_path / "source" / "content"
    _write(content / "FileSizeList.txt", b"res/Msguk/bmgres1.arc\0" + str(len(english)).encode() + b"\0"
           b"res/Msgus/bmgres1.arc\0" + str(len(english)).encode() + b"\0")
    _write(content / "DecompressedSizeList.txt", b"0\0" + b"0\0" + b"0%\0" + b"./DVDRoot/res/Msguk/other.arc\0")
    _write(content / "res/Msguk/bmgres1.arc", english)
    _write(content / "res/Msgus/bmgres1.arc", english)
    trn = tmp_path / "translation" / "content"
    _write(trn / "res/Msguk/bmgres1.arc", changed)
    return content / "res/Msguk", trn / "res/Msguk"


def test_wiiu_pack_writes_both_language_folders_sizes_and_sdcafiine_copies(tmp_path):
    english = build_rarc({"zel_01.bmg": b"EN"})
    changed = build_rarc({"zel_01.bmg": b"U" * 200})   # longer than the 32-byte padding, so the size changes
    source, trn = _hd_tree(tmp_path, english, changed)
    out = tmp_path / "out"
    out.mkdir()

    result = Path(hd_pack.build_wiiu_mod(str(source), str(trn), str(out), _noop, _never))

    pack = result / "graphicPacks" / hd_pack.PACK_NAME
    assert (pack / "content/res/Msguk/bmgres1.arc").read_bytes() == changed
    assert (pack / "content/res/Msgus/bmgres1.arc").read_bytes() == changed
    sizes = (pack / "content/FileSizeList.txt").read_bytes()
    assert sizes == (b"res/Msguk/bmgres1.arc\0" + str(len(changed)).encode() + b"\0"
                     b"res/Msgus/bmgres1.arc\0" + str(len(changed)).encode() + b"\0")
    assert "titleIds = " in (pack / "rules.txt").read_text(encoding="utf-8")
    for title in hd_pack.TITLE_IDS:
        mod = result / "sdcafiine" / "wiiu" / "sdcafiine" / title / hd_pack.SDCAFIINE_MOD / "content"
        assert (mod / "res/Msgus/bmgres1.arc").read_bytes() == changed


def test_wiiu_pack_keeps_a_translated_twin_as_its_own_file(tmp_path):
    english = build_rarc({"zel_01.bmg": b"EN"})
    source, trn = _hd_tree(tmp_path, english, build_rarc({"zel_01.bmg": b"UK"}))
    msgus = _write(trn.parent.parent / "res/Msgus/bmgres1.arc", build_rarc({"zel_01.bmg": b"US"}))
    out = tmp_path / "out"
    out.mkdir()

    result = Path(hd_pack.build_wiiu_mod(str(source), str(trn), str(out), _noop, _never))

    assert (result / "graphicPacks" / hd_pack.PACK_NAME / "content/res/Msgus/bmgres1.arc").read_bytes() == \
        msgus.read_bytes()


def test_wiiu_pack_without_a_changed_file_is_refused(tmp_path):
    english = build_rarc({"zel_01.bmg": b"EN"})
    source, trn = _hd_tree(tmp_path, english, english)
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError, match="nothing to build"):
        hd_pack.build_wiiu_mod(str(source), str(trn), str(out), _noop, _never)


def test_wiiu_source_must_be_a_res_msguk_folder(tmp_path):
    with pytest.raises(ValueError, match="res/Msguk or res/Msgus"):
        hd_pack.build_wiiu_mod(str(tmp_path / "a"), str(tmp_path / "b"), str(tmp_path), _noop, _never)


def test_update_size_lists_leaves_out_tables_that_do_not_change():
    lists = {"FileSizeList.txt": b"res/x.arc\0" + b"5\0", "DecompressedSizeList.txt": b""}
    assert hd_pack.update_size_lists(lists, {"res/other.arc": b"abc"}) == {}


def test_regenerate_pack_refuses_a_file_that_is_not_a_tmpk_pack():
    import gzip
    with pytest.raises(ValueError, match="not a TMPK pack"):
        hd_pack.regenerate_pack(gzip.compress(b"NOPE" + bytes(60)), b"")


def test_rules_declare_the_three_targets_on_declared_platforms():
    rules = GameRules()
    targets = {t["id"]: t for t in rules.get_build_targets()}
    assert set(targets) == {"gc_iso", "dusk_mod", "wiiu_mod"}
    declared = {p["id"] for p in rules.get_platforms()}
    for target in targets.values():
        assert set(target["platforms"]) <= declared


def test_an_undeclared_target_id_is_refused():
    with pytest.raises(ValueError, match="Unknown build target"):
        GameRules().build_target("nope", "a", "b", "c", _noop, _never)


def test_wind_waker_inherits_the_base_class_but_no_twilight_princess_target():
    from plugins.zelda_tww.rules import GameRules as WindWakerRules
    assert WindWakerRules().get_build_targets() == []
