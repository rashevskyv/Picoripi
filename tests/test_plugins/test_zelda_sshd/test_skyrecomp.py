"""Skyward Sword HD for SkyRecomp: the build target writes the changed members into their U8 archives under the mod
folder, copies the changed plain files and refuses a game folder of another build. Synthetic archives only."""
import struct

import pytest

from core.containers.u8_container import U8Container
from plugins.zelda_sshd import skyrecomp
from plugins.zelda_sshd.rules import GameRules

ARC = "US/Object/en_US/1-Town.arc"
MEMBER = "1-Town/100-Town.msbt"
OTHER = "1-Town/101-Shop.msbt"


def _u8(files):
    """A U8 archive of ``files`` ({"folder/name": bytes}): one level of folders, names as Nintendo writes them."""
    names = bytearray(b"\x00")
    nodes = [[0x0100, 0, 0, 0]]            # root: parent 0, one past its last node (set below)
    payload = []
    for folder in sorted({path.split("/")[0] for path in files}):
        directory = len(nodes)
        nodes.append([0x0100, len(names), 0, 0])
        names += folder.encode() + b"\x00"
        for path in sorted(p for p in files if p.split("/")[0] == folder):
            base = path.split("/", 1)[1]
            nodes.append([0x0000, len(names), len(payload), len(files[path])])
            names += base.encode() + b"\x00"
            payload.append(files[path])
        nodes[directory][3] = len(nodes)
    nodes[0][3] = len(nodes)
    table_size = 12 * len(nodes) + len(names)
    data_off = (0x20 + table_size + 31) & ~31
    blob, offsets = b"", []
    for data in payload:
        offsets.append(data_off + len(blob))
        blob += data + bytes(-len(data) % 32)
    rows = b""
    for typ, name, parent_or_offset, size in nodes:
        if typ == 0:                       # a file node keeps its payload index until here
            parent_or_offset = offsets[parent_or_offset]
        rows += struct.pack(">HHII", typ, name, parent_or_offset, size)
    head = struct.pack(">IIII", 0x55AA382D, 0x20, table_size, data_off) + bytes(16) + rows + bytes(names)
    return head + bytes(data_off - len(head)) + blob


def _tree(root, files):
    for rel, data in files.items():
        path = root.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _game(tmp_path, archive_files, font=b"FONT", exefs_build=None):
    """The owner's layout: ``game/romfs`` (raw archives) next to ``game/source`` (the same files, archives unpacked)."""
    game = tmp_path / "game"
    _tree(game / "romfs", {ARC: _u8(archive_files), "US/Font/en_US/normal_00.brfnt": font})
    _tree(game / "source", {f"US/Object/en_US/{p}": d for p, d in archive_files.items()})
    _tree(game / "source", {"US/Font/en_US/normal_00.brfnt": font})
    if exefs_build is not None:
        _tree(game, {"exefs/main": bytes(skyrecomp.BUILD_ID_AT) + exefs_build + b"\x00" * 16})
    return game


def test_archive_paths_map_objects_and_layouts_and_leave_fonts_alone():
    assert skyrecomp.archive_of("US/Object/en_US/1-Town/100-Town.msbt") == (ARC, MEMBER)
    assert skyrecomp.archive_of("Layout/Title2D/text/en_US_titleBG_00.msbt") == (
        "Layout/Title2D.arc", "text/en_US_titleBG_00.msbt")
    assert skyrecomp.archive_of("US/Font/en_US/normal_00.brfnt") is None


def test_a_changed_message_is_repacked_into_its_archive_and_the_rest_stays_as_it_was(tmp_path):
    game = _game(tmp_path, {MEMBER: b"HELLO", OTHER: b"SHOP"})
    translation = tmp_path / "translation"
    _tree(translation, {f"US/Object/en_US/{MEMBER}": b"PRIVIT", "US/Font/en_US/normal_00.brfnt": b"UAFONT"})
    out = tmp_path / "out"
    out.mkdir()
    skyrecomp.build(str(game / "source"), str(translation), str(out), lambda done, text: None, lambda: False)

    mod = out / "mods" / skyrecomp.MOD_NAME / "romfs"
    packed = U8Container((mod / ARC).read_bytes())
    assert packed.read_file(MEMBER) == b"PRIVIT"
    assert packed.read_file(OTHER) == b"SHOP"
    assert (mod / "US" / "Font" / "en_US" / "normal_00.brfnt").read_bytes() == b"UAFONT"
    assert sorted(p.relative_to(mod).as_posix() for p in mod.rglob("*") if p.is_file()) == sorted(
        [ARC, "US/Font/en_US/normal_00.brfnt"])
    assert (out / "README.txt").is_file()


def test_a_name_the_archive_does_not_hold_stops_the_build_before_anything_is_written(tmp_path):
    game = _game(tmp_path, {MEMBER: b"HELLO"})
    translation = tmp_path / "translation"
    _tree(translation, {"US/Object/en_US/1-Town/999-Nope.msbt": b"X"})
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError, match="999-Nope"):
        skyrecomp.build(str(game / "source"), str(translation), str(out), lambda done, text: None, lambda: False)
    assert not (out / "mods").exists()


def test_the_build_needs_the_raw_romfs_folder_next_to_the_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="romfs"):
        skyrecomp.build(str(source), str(tmp_path / "t"), str(tmp_path / "o"), lambda done, text: None, lambda: False)


def test_a_game_folder_of_another_build_is_refused_and_v1_0_0_passes(tmp_path):
    other = _game(tmp_path / "other", {MEMBER: b"HELLO"}, exefs_build=b"\x01" * 8)
    with pytest.raises(ValueError, match="v1.0.0"):
        skyrecomp.check_build_id(other)
    good = _game(tmp_path / "good", {MEMBER: b"HELLO"}, exefs_build=skyrecomp.BUILD_ID)
    skyrecomp.check_build_id(good)
    skyrecomp.check_build_id(_game(tmp_path / "none", {MEMBER: b"HELLO"}))   # no exefs folder: nothing to compare


def test_a_cancelled_build_writes_no_mod(tmp_path):
    game = _game(tmp_path, {MEMBER: b"HELLO"})
    translation = tmp_path / "translation"
    _tree(translation, {f"US/Object/en_US/{MEMBER}": b"PRIVIT"})
    out = tmp_path / "out"
    out.mkdir()
    skyrecomp.build(str(game / "source"), str(translation), str(out), lambda done, text: None, lambda: True)
    assert not (out / "mods" / skyrecomp.MOD_NAME / "romfs" / ARC).exists()


def test_the_target_is_declared_for_switch_only():
    targets = GameRules().get_build_targets()
    assert [(t["id"], t["platforms"]) for t in targets] == [(skyrecomp.TARGET_ID, ["switch"])]
