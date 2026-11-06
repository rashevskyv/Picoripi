"""Ocarina of Time (Nintendo Switch 2): the .nup package reader, the wizard hooks and the zstd font files."""
import hashlib
import struct
from pathlib import Path

import pytest

import core.containers.container_manager as container_manager
from core.containers import sarc as sarc_module
from core.font_formats import sources as font_sources
from plugins.testing import check_loads, check_validator
from plugins.common.msbt import Msbt
from plugins.zelda_oot_switch2 import build, nup
from plugins.zelda_totk.tags import to_editor
from plugins.zelda_oot_switch2.rules import GameRules
import romhacking_root
from ..test_zelda_totk import samples

zstd = pytest.importorskip("compression.zstd")

PLUGIN = "zelda_oot_switch2"
TITLE = 0x0400486024DEC000
NUP_NAME = "The Legend of Zelda Ocarina of Time [0400486024DEC000][v131072].nup"


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch):
    """The plugin registers its archive type and dictionary folders; keep that out of other tests."""
    monkeypatch.setattr(container_manager, "_CONTAINER_TYPES", list(container_manager._CONTAINER_TYPES))
    monkeypatch.setattr(container_manager, "_ARCHIVE_EXTENSIONS", list(container_manager._ARCHIVE_EXTENSIONS))
    monkeypatch.setattr(sarc_module, "dictionary_dirs", sarc_module.dictionary_dirs)
    monkeypatch.setattr(sarc_module, "_dictionaries", dict(sarc_module._dictionaries))


def package(files, title=TITLE, compressed=()):
    """A .nup with the layout of nup.py: ``files`` maps a path to its bytes; paths in ``compressed`` are zstd."""
    dirs = [("", [])]
    index = {"": 0}
    entries = []
    for path in files:
        parent = ""
        for part in path.split("/")[:-1]:
            child = parent + part + "/"
            if child not in index:
                index[child] = len(dirs)
                dirs.append((part, []))
                dirs[index[parent]][1].append(("dir", index[child]))
            parent = child
        dirs[index[parent]][1].append(("file", len(entries)))
        entries.append(path)
    pool = bytearray()
    names = {}

    def name(text):
        if text not in names:
            names[text] = (len(pool), len(text.encode()))
            pool.extend(text.encode())
        return names[text]

    children, dir_table = [], bytearray()
    for part, kids in dirs:
        dir_table += struct.pack("<4I8x", *name(part), len(children), len(kids))
        children += [kid if kind == "dir" else len(dirs) + kid for kind, kid in kids]
    file_names = [name(path.split("/")[-1]) for path in entries]   # the whole pool comes before the data
    toc_end = nup.DIRECTORIES + len(dir_table) + 80 * len(entries) + 4 * len(children) + len(pool)
    data_start = toc_end + -toc_end % 16
    file_table, blob = bytearray(), bytearray()
    for path, file_name in zip(entries, file_names):
        raw = files[path]
        stored = zstd.compress(raw) if path in compressed else raw
        blob += bytes(-len(blob) % 16)
        file_table += struct.pack("<IIQQQ32sI12x", *file_name, len(raw), data_start + len(blob),
                                  len(stored), hashlib.sha256(raw).digest(), int(path in compressed))
        blob += stored
    blob += bytes(-len(blob) % 16)
    pool_offset = nup.DIRECTORIES + len(dir_table) + len(file_table) + 4 * len(children) - nup.TOC
    head = bytearray(nup.DIRECTORIES)
    head[:4] = nup.MAGIC
    head[nup.TOC:nup.TOC + 4] = nup.TOC_MAGIC
    struct.pack_into("<QQQQ", head, 0x88, len(dirs), len(entries), pool_offset, len(pool))
    struct.pack_into("<Q", head, 0xB0, title)
    struct.pack_into("<I", head, 0xC4, 131072)
    struct.pack_into("<QQ", head, 0x08, nup.TOC, data_start - nup.TOC)
    struct.pack_into("<QQ", head, 0x38, data_start, data_start + len(blob) + len(TRAILER))
    struct.pack_into("<QQ", head, 0xD0, data_start + len(blob), len(TRAILER))
    meta = head + dir_table + file_table + struct.pack(f"<{len(children)}I", *children) + pool
    meta += bytes(data_start - len(meta))
    meta[0x18:0x38] = hashlib.sha256(bytes(meta[nup.TOC:])).digest()
    return bytes(meta + blob + TRAILER)


TRAILER = b"\x01\x00\x00\x00\x04\x00\x00\x00META"


FILES = {
    "exefs/main": b"NSO0 program",
    "romfs/Mals/USen.Product.110.sarc.zs": samples.sarc({"ActorMsg/Npc.msbt": samples.msbt([("Name", samples.text("Saria"))])}),
    "romfs/Mals/EUru.Product.110.sarc.zs": samples.sarc({"ActorMsg/Npc.msbt": samples.msbt([("Name", samples.text("Сария"))])}),
    "romfs/Pack/ZsDic.pack.zs": b"dictionaries",
    "romfs/Font2/Scalable/ClarimoUDPE-Light.Nin_Ounce_NVN2.bfotf.zs": b"font",
    "romfs/Model/Link.bfres.zs": b"model",
}


def write_package(folder, **kwargs):
    path = folder / "game.nup"
    path.write_bytes(package(FILES, compressed={"exefs/main", "romfs/Pack/ZsDic.pack.zs"}, **kwargs))
    return path


def test_the_plugin_loads_and_validates():
    check_loads(PLUGIN)
    check_validator(PLUGIN)


def test_the_package_lists_every_file_and_reads_plain_and_zstd_entries(tmp_path):
    with open(write_package(tmp_path), "rb") as stream:
        package_ = nup.Nup(stream)
        assert (package_.title_id, package_.version) == ("0400486024DEC000", 131072)
        assert [entry.path for entry in package_.entries] == sorted(FILES)
        by_path = {entry.path: entry for entry in package_.entries}
        assert by_path["exefs/main"].compressed and not by_path["romfs/Model/Link.bfres.zs"].compressed
        assert {entry.path: package_.read(entry) for entry in package_.entries} == FILES


def test_a_file_that_does_not_match_its_sha256_is_refused(tmp_path):
    raw = bytearray(package({"romfs/a.bin": b"abcd"}))
    raw[raw.index(b"abcd")] ^= 0xFF
    path = tmp_path / "bad.nup"
    path.write_bytes(bytes(raw))
    with open(path, "rb") as stream:
        package_ = nup.Nup(stream)
        with pytest.raises(ValueError, match="SHA-256"):
            package_.read(package_.entries[0])


def test_other_files_are_not_packages(tmp_path):
    path = tmp_path / "x.nup"
    path.write_bytes(b"NSP0" + bytes(300))
    with open(path, "rb") as stream, pytest.raises(ValueError, match="not a NUP package"):
        nup.Nup(stream)


def test_the_wizard_knows_this_game_only(tmp_path):
    rules = GameRules()
    assert rules.identify_source(str(write_package(tmp_path))) == {"role": "base", "platform": "switch2"}
    other = tmp_path / "other"
    other.mkdir()
    assert rules.identify_source(str(write_package(other, title=0x0400000000001000))) is None
    assert rules.identify_source(str(tmp_path / "missing.nup")) is None


def test_unpack_copies_only_text_dictionaries_and_fonts(tmp_path):
    target = tmp_path / "unpacked"
    target.mkdir()
    steps = []
    result = GameRules().unpack_sources({"base": str(write_package(tmp_path))}, str(target),
                                        lambda percent, text: steps.append(percent), lambda: False)
    assert result == str(target)
    written = sorted(path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file())
    assert written == sorted([".picoripi_disc.json"] + [
        path for path in FILES if path.startswith(("romfs/Mals", "romfs/Pack", "romfs/Font2"))])
    assert (target / "romfs/Pack/ZsDic.pack.zs").read_bytes() == b"dictionaries"
    assert steps[-1] == 100


def test_a_cancelled_unpack_returns_none(tmp_path):
    target = tmp_path / "unpacked"
    target.mkdir()
    assert GameRules().unpack_sources({"base": str(write_package(tmp_path))}, str(target),
                                      lambda percent, text: None, lambda: True) is None


def test_only_the_english_archive_becomes_blocks():
    rules = GameRules()
    assert rules.get_source_subfolder() == "romfs/Mals"
    assert rules.includes_source_file("USen.Product.110.sarc.zs")
    assert not rules.includes_source_file("EUru.Product.110.sarc.zs")
    assert not rules.includes_source_file("EUen.Product.110.sarc.zs")


def test_a_font_stored_as_one_zstd_frame_opens_plain_and_saves_compressed(tmp_path):
    font = tmp_path / "romfs/Font2/Scalable/ClarimoUDPE-Light.Nin_Ounce_NVN2.bfotf.zs"
    font.parent.mkdir(parents=True)
    font.write_bytes(zstd.compress(b"OpenType font bytes"))
    (tmp_path / "romfs/Mals").mkdir()
    found = font_sources.resolve(GameRules().get_font_sources(), {
        "source_path": str(tmp_path / "romfs/Mals"), "translation_path": str(tmp_path / "translation/Mals")})
    assert [source.label for source in found] == ["Russian slot dialogue, the build's target (ClarimoUDPE Light)"]
    assert found[0].read_current() == b"OpenType font bytes"

    found[0].write(b"edited")

    saved = Path(found[0].translation_path).read_bytes()
    assert saved[:4] == sarc_module.ZSTD_MAGIC and zstd.decompress(saved) == b"edited"
    assert found[0].read_current() == b"edited"


REAL = ("Zelda", "Ocarina of Time", "Switch 2", "ISO", NUP_NAME)


@romhacking_root.needs(REAL)
def test_the_real_package_unpacks_the_english_text(tmp_path):
    target = tmp_path / "unpacked"
    target.mkdir()
    rules = GameRules()
    path = str(romhacking_root.path(*REAL))
    assert rules.identify_source(path) == {"role": "base", "platform": "switch2"}
    rules.unpack_sources({"base": path}, str(target), lambda percent, text: None, lambda: False)
    mals = target / "romfs/Mals"
    sarc_module.dictionary_dirs = lambda: [mals]
    archive = sarc_module.SarcContainer((mals / "USen.Product.110.sarc.zs").read_bytes())
    assert len(archive.list_files()) == 540
    texts = rules.load_data_from_json_obj(archive.read_file("ActorMsg/PouchContent.msbt"))[0][0]
    assert texts[:2] == ["Fish", "You collected a fish in a bottle!"]


# -- the writer ------------------------------------------------------------------


def read_all(path):
    with open(path, "rb") as stream:
        package_ = nup.Nup(stream)
        return {entry.path: package_.read(entry) for entry in package_.entries}


def ignore(*_args):
    return None


def test_a_package_written_without_changes_is_the_same_bytes(tmp_path):
    source = write_package(tmp_path)
    target = tmp_path / "out" / "copy.nup"

    assert nup.write(source, target, {}, ignore, lambda: False) == str(target)

    assert target.read_bytes() == source.read_bytes()
    assert not list(target.parent.glob("*.tmp"))


def test_a_rewritten_file_is_read_back_and_everything_else_stays(tmp_path):
    source = write_package(tmp_path)
    target = tmp_path / "out.nup"
    changes = {"romfs/Model/Link.bfres.zs": b"a new model, longer than before", "exefs/main": b"NSO0 patched"}

    nup.write(source, target, changes, ignore, lambda: False)

    assert read_all(target) == {**FILES, **changes}
    old, new = source.read_bytes(), target.read_bytes()
    with open(target, "rb") as stream:
        package_ = nup.Nup(stream)
        by_path = {entry.path: entry for entry in package_.entries}
    assert by_path["exefs/main"].compressed and by_path["exefs/main"].stored_size != len(changes["exefs/main"])
    assert all(entry.offset % 16 == 0 for entry in package_.entries)
    assert new[package_.data_start:len(old) - len(TRAILER)] == old[package_.data_start:len(old) - len(TRAILER)]
    assert new.endswith(TRAILER) and new[package_.trailer_offset:] == TRAILER
    assert struct.unpack_from("<Q", new, 0x40)[0] == len(new)
    assert new[0x18:0x38] == hashlib.sha256(new[nup.TOC:package_.data_start]).digest()


def test_the_writer_refuses_new_files_and_its_own_source(tmp_path):
    source = write_package(tmp_path)
    with pytest.raises(ValueError, match="not in the NUP package"):
        nup.write(source, tmp_path / "out.nup", {"romfs/new.bin": b"x"}, ignore, lambda: False)
    with pytest.raises(ValueError, match="over its source"):
        nup.write(source, source, {}, ignore, lambda: False)


def test_a_cancelled_write_leaves_nothing(tmp_path):
    source = write_package(tmp_path)
    target = tmp_path / "out" / "copy.nup"
    assert nup.write(source, target, {"exefs/main": b"x"}, ignore, lambda: True) is None
    assert list(target.parent.iterdir()) == []


# -- the build ---------------------------------------------------------------------


def npc_archive(name):
    return samples.sarc({"ActorMsg/Npc.msbt": samples.msbt([("Name", samples.text(name)),
                                                           ("Name2", samples.text("Navi"))])})


def first_texts(raw):
    msbt = Msbt(sarc_module.SarcContainer(raw).read_file("ActorMsg/Npc.msbt"))
    return [to_editor(tokens, msbt.little) for tokens in msbt.messages]


def test_a_translated_message_replaces_the_russian_one_and_the_rest_stays_russian():
    english, russian = npc_archive("Saria"), samples.sarc({"ActorMsg/Npc.msbt": samples.msbt(
        [("Name", samples.text("Сария")), ("Name2", samples.text("Нави"))])})
    translated = samples.sarc({"ActorMsg/Npc.msbt": samples.msbt([("Name", samples.text("Саріа")),
                                                                   ("Name2", samples.text("Navi"))])})

    assert first_texts(build.graft(english, translated, russian)) == ["Саріа", "Нави"]
    assert build.graft(english, english, russian) is None


def test_the_build_writes_a_package_with_the_translation_in_the_russian_slot(tmp_path):
    files = {**FILES, "romfs/Mals/USen.Product.110.sarc.zs": npc_archive("Saria"),
             "romfs/Mals/EUru.Product.110.sarc.zs": npc_archive("Сария"),
             "romfs/Pack/ZsDic.pack.zs": samples.zsdic_pack(samples.dictionary())}
    image = tmp_path / "game.nup"
    image.write_bytes(package(files))
    unpacked = tmp_path / "unpacked"
    GameRules().unpack_sources({"base": str(image)}, str(unpacked), ignore, lambda: False)
    translation = tmp_path / "translation"
    translation.mkdir()
    (translation / "USen.Product.110.sarc.zs").write_bytes(npc_archive("Саріа"))
    rules = GameRules()
    assert [target["id"] for target in rules.get_build_targets()] == ["nup"]

    result = rules.build_target("nup", str(unpacked / "romfs/Mals"), str(translation), str(tmp_path / "build"),
                                ignore, lambda: False)

    assert Path(result).name == "game (UA).nup"
    rebuilt = read_all(result)
    assert first_texts(rebuilt["romfs/Mals/EUru.Product.110.sarc.zs"])[0] == "Саріа"
    assert {path: data for path, data in rebuilt.items() if "EUru" not in path} == {
        path: data for path, data in files.items() if "EUru" not in path}


def test_a_build_without_translated_text_is_refused(tmp_path):
    image = write_package(tmp_path)
    unpacked = tmp_path / "unpacked"
    GameRules().unpack_sources({"base": str(image)}, str(unpacked), ignore, lambda: False)
    with pytest.raises(ValueError, match="no translated text"):
        build.build_nup(str(unpacked / "romfs/Mals"), str(tmp_path / "translation"), str(tmp_path / "build"),
                        ignore, lambda: False)

