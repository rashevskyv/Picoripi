"""Link's Awakening (Switch) plugin without game data: the v1.0.0 check, the SWUK label mapping and the mod import.

The real SWUK mod is checked when ``PICORIPI_LAS_SWUK`` names its zip (see ``tests/romhacking_root.py`` for the
pattern). Nothing here reads a key file.
"""
import io
import json
import os
import struct
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.project_manager import ProjectManager
from core.project_models import Project
from plugins.common.msbt import Msbt
from plugins.zelda_las import recomp, swuk
from plugins.zelda_las.rules import GameRules

SWUK_ENV = "PICORIPI_LAS_SWUK"
REAL_MOD = Path(os.environ.get(SWUK_ENV, "")) if os.environ.get(SWUK_ENV) else None
real = pytest.mark.skipif(not (REAL_MOD and REAL_MOD.is_file()), reason=f"{SWUK_ENV} does not name the SWUK zip")


class _Fake:
    endian, little = "<", True


def _section(magic, body):
    out = magic + struct.pack("<I", len(body)) + bytes(8) + body
    return out + b"\xab" * (-len(out) % 16)


def _msbt(messages):
    """A little-endian UTF-16 MSBT with labels (LBL1) and texts (TXT2) of ``[(label, text), ...]``."""
    bodies = [Msbt.encode_text(_Fake(), [text]) for _label, text in messages]
    offsets, at = [], 4 + 4 * len(bodies)
    for body in bodies:
        offsets.append(at)
        at += len(body)
    txt2 = struct.pack(f"<I{len(bodies)}I", len(bodies), *offsets) + b"".join(bodies)
    labels = b"".join(bytes([len(name)]) + name.encode() + struct.pack("<I", index)
                      for index, (name, _text) in enumerate(messages))
    lbl1 = struct.pack("<III", 1, len(messages), 12) + labels
    out = bytearray(b"MsgStdBn\xff\xfe\x00\x00\x01\x03\x02\x00" + bytes(16))
    out += _section(b"LBL1", lbl1) + _section(b"TXT2", txt2)
    struct.pack_into("<I", out, 0x12, len(out))
    return bytes(out)


def _texts(raw):
    msbt = Msbt(raw)
    return [(msbt.labels[i], tokens[0]) for i, tokens in enumerate(msbt.messages)]


def _romfs_with_exefs(root: Path, build_id: bytes, romfs=True):
    if romfs:
        (root / "romfs").mkdir(parents=True)
    (root / "exefs").mkdir(parents=True)
    (root / "exefs" / "main").write_bytes(bytes(recomp.BUILD_ID_AT) + build_id + b"\x00" * 16)


def test_the_v1_0_0_build_id_passes_and_other_builds_or_updates_are_refused(tmp_path):
    good = tmp_path / "good"
    _romfs_with_exefs(good, recomp.BUILD_ID)
    recomp.check_unpacked(good)
    other = tmp_path / "other"
    _romfs_with_exefs(other, b"\x00" * 8)
    with pytest.raises(ValueError, match="v1.0.0"):
        recomp.check_unpacked(other)
    update = tmp_path / "update"
    _romfs_with_exefs(update, recomp.BUILD_ID, romfs=False)
    with pytest.raises(ValueError, match="update"):
        recomp.check_unpacked(update)


def test_identify_takes_only_the_base_game_of_this_title(tmp_path):
    rules = GameRules()
    other = tmp_path / "other.nsp"
    other.write_bytes(b"not a package")
    assert rules.identify_source(str(other)) is None
    assert rules.unpack_key_consoles() == ["switch"]
    assert rules.get_source_subfolder() == "romfs"
    assert [t["id"] for t in rules.get_build_targets()] == [recomp.TARGET_ID]


def test_messages_are_matched_by_label_and_counted():
    target = _msbt([("A", "english a"), ("B", "english b"), ("C", "english c")])
    mod = _msbt([("B", "мод b"), ("C", "мод c"), ("D", "мод d")])
    out, counts = swuk.map_messages(mod, target)
    assert counts == {"matched": 2, "kept": 1, "extra": 1}
    assert _texts(out) == [("A", "english a"), ("B", "мод b"), ("C", "мод c")]


def test_a_mod_without_a_label_keeps_the_english_text_of_that_message():
    target = _msbt([("A", "english a"), ("B", "english b")])
    mod = _msbt([("A", "мод a")])
    out, counts = swuk.map_messages(mod, target)
    assert counts == {"matched": 1, "kept": 1, "extra": 0}
    assert _texts(out) == [("A", "мод a"), ("B", "english b")]


def test_import_writes_only_the_us_slot_and_reports_each_file(tmp_path):
    romfs = tmp_path / "romfs"
    for slot in ("regionEU/EUen", "regionUS/USen"):
        (romfs / slot / "message").mkdir(parents=True)
        (romfs / slot / "message" / "Hint.msbt").write_bytes(_msbt([("A", "english a"), ("B", "english b")]))
    (romfs / "region_common" / "ui").mkdir(parents=True)
    (romfs / "region_common" / "ui" / "StartUp.arc").write_bytes(b"1234")
    mod = tmp_path / "mod.zip"
    with zipfile.ZipFile(mod, "w") as archive:
        archive.writestr("01006BB00C6F0000/romfs/regionEU/EUen/message/Hint.msbt", _msbt([("B", "мод b")]))
        archive.writestr("01006BB00C6F0000/romfs/region_common/ui/StartUp.arc", b"abcdefgh")
        archive.writestr("01006BB00C6F0000/romfs/regionEU/EUen/message/../../evil.msbt", b"x")
        archive.writestr("01006BB00C6F0000/romfs/regionJP/JPja/message/Hint.msbt", _msbt([("B", "x")]))
    translation = tmp_path / "translation"
    report = swuk.import_mod(mod, romfs, translation)
    assert any("regionUS/USen/message/Hint.msbt: 1 matched, 1 kept English" in line for line in report)
    assert not any("regionEU" in line for line in report)
    assert not (translation / "regionEU").exists()
    assert any("StartUp.arc: copied (8 bytes; the 1.0.0 file has 4 bytes)" in line for line in report)
    assert _texts((translation / "regionUS/USen/message/Hint.msbt").read_bytes()) == [("A", "english a"),
                                                                                       ("B", "мод b")]
    assert (translation / "region_common/ui/StartUp.arc").read_bytes() == b"abcdefgh"
    assert not (translation / "regionJP").exists()
    assert not (tmp_path / "evil.msbt").exists()


def test_only_the_us_slot_becomes_blocks_and_the_others_are_references(tmp_path):
    romfs = tmp_path / "romfs"
    texts = {"regionUS/USen": ("english a", "english b"), "regionEU/EUen": ("english a", "colour b"),
             "regionEU/EUfr": ("français a", "français b"),   # written in label order B, A
             "regionJP/JPja": ("日本 a", None)}
    for slot, (a, b) in texts.items():
        (romfs / slot / "message").mkdir(parents=True)
        messages = [("B", b), ("A", a)] if slot == "regionEU/EUfr" else [("A", a)] + ([("B", b)] if b else [])
        (romfs / slot / "message" / "Hint.msbt").write_bytes(_msbt(messages))
    (romfs / "region_common" / "ui").mkdir(parents=True)
    (romfs / "region_common" / "ui" / "Credit.msbt").write_bytes(_msbt([("A", "x")]))
    manager = ProjectManager()
    manager.project_dir = str(tmp_path)
    manager.project_file_path = str(tmp_path / "project.uiproj")
    manager.project = Project(name="LAS", plugin_name="zelda_las")
    manager.project.metadata = {"source_path": str(romfs), "translation_path": str(tmp_path / "translation"),
                                "is_directory_mode": True}
    eu = "regionEU/EUen/message/Hint.msbt"   # a block of a project made before the hook
    manager.add_block(name="Hint", source_file_path=eu, translation_file_path=eu)
    (tmp_path / "translation" / eu).parent.mkdir(parents=True)
    (tmp_path / "translation" / eu).write_bytes(b"old translation")
    rules = GameRules()
    manager.sync_project_files(plugin=rules)
    sources = [block.source_file for block in manager.project.blocks]
    assert sources == ["regionUS/USen/message/Hint.msbt"]
    assert (tmp_path / "translation" / eu).read_bytes() == b"old translation"   # the block left, its file stays

    rules.mw = SimpleNamespace(project_manager=manager, block_to_project_file_map={})
    us = 0
    references = rules.load_multi_reference(str(romfs), {str(us): "Hint"})
    assert references == {"English (EU)": {(us, 0): "english a", (us, 1): "colour b"},
                          "French (EU)": {(us, 0): "français a", (us, 1): "français b"},
                          "Japanese (JA)": {(us, 0): "日本 a"}}


def _real_mod_messages():
    with zipfile.ZipFile(REAL_MOD) as archive:
        names = [n for n in archive.namelist() if "/romfs/regionEU/EUen/message/" in n and n.endswith(".msbt")]
        return {n.rsplit("/", 1)[1]: archive.read(n) for n in names}


@real
def test_the_real_mod_reads_twelve_messages_and_maps_onto_itself():
    files = swuk.read_mod(REAL_MOD)
    messages = {rel: data for rel, data in files.items() if rel.startswith("regionEU/EUen/message/")}
    assert len(messages) == 12
    assert {rel for rel in files if rel.startswith("region_common/")} == {
        "region_common/ui/jpn_heading.bffnt", "region_common/ui/StartUp.arc"}
    for rel, data in messages.items():
        out, counts = swuk.map_messages(data, data)
        assert counts == {"matched": len(Msbt(data).messages), "kept": 0, "extra": 0}, rel
        assert _texts(out) == _texts(data), rel


@real
def test_a_label_missing_on_either_side_is_counted_in_the_real_mod():
    raw = _real_mod_messages()["Hint.msbt"]
    full = Msbt(raw)
    kept = list(range(len(full.messages) - 1))
    shorter = full.subset(kept, [full.messages[i] for i in kept])
    _out, counts = swuk.map_messages(raw, shorter)
    assert counts["extra"] == 1 and counts["kept"] == 0
    _out, counts = swuk.map_messages(shorter, raw)
    assert counts["kept"] == 1 and counts["extra"] == 0


def _romfs_contents(image: bytes):
    """``{path: bytes}`` of a romfs.bin, read back with the Switch RomFS reader."""
    from core.containers.console_crypto import RangeView
    from core.containers.image_files import ImageReader
    from core.containers.switch_images import _romfs_files
    view = RangeView(io.BytesIO(image), 0, len(image))
    return {entry.path: ImageReader(entry.stream).read_at(entry.offset, entry.size) for entry in _romfs_files(view)}


def _ttf(chars, version=recomp.TRUETYPE, outlines=b"glyf"):
    """A minimal sfnt whose cmap (format 12) maps ``chars``; enough tables for ``bfotf.OpenType``."""
    groups = b"".join(struct.pack(">III", ord(c), ord(c), i + 1) for i, c in enumerate(chars))
    cmap = struct.pack(">HHHHI", 0, 1, 3, 10, 12) + struct.pack(">HHIII", 12, 0, 16 + len(groups), 0, len(chars)) + groups
    tables = {b"cmap": cmap, b"head": bytes(54), b"hhea": bytes(36), b"maxp": bytes(6), outlines: bytes(4)}
    directory, body, at = b"", b"", 12 + 16 * len(tables)
    for tag, data in tables.items():
        directory += tag + struct.pack(">III", 0, at + len(body), len(data))
        body += data + bytes(-len(data) % 4)
    return version + struct.pack(">HHHH", len(tables), 0, 0, 0) + directory + body


def _build_dir(project: Path) -> Path:
    """The folder ``build.run_build`` gives the plugin: ``<project>/build/.<target>-<id>``."""
    out = project / "build" / ".lasrecomp-test"
    out.mkdir(parents=True)
    return out


def test_the_font_check_wants_glyf_outlines_and_every_ukrainian_letter(tmp_path):
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "a_cff.ttf").write_bytes(_ttf(recomp.UKRAINIAN, b"OTTO", b"CFF "))
    (fonts / "b_short.ttf").write_bytes(_ttf("Ііабв"))
    (fonts / "c_broken.ttf").write_bytes(b"\x00\x01\x00\x00")
    with pytest.raises(ValueError) as refused:
        recomp.find_font(tmp_path)
    assert str(refused.value).splitlines()[1:] == [
        "a_cff.ttf: not a TrueType font with glyf outlines", "b_short.ttf: no letters ЇїЄєҐґʼ", "c_broken.ttf: cannot read it"]
    (fonts / "d_good.ttf").write_bytes(_ttf(recomp.UKRAINIAN))
    assert recomp.find_font(tmp_path) == fonts / "d_good.ttf"


def test_the_font_setting_names_a_file_outside_the_project(tmp_path):
    own = tmp_path / "elsewhere" / "Mine.ttf"
    own.parent.mkdir()
    own.write_bytes(_ttf(recomp.UKRAINIAN))
    project = tmp_path / "project"
    project.mkdir()
    (project / "project_settings.json").write_text(json.dumps({recomp.FONT_SETTING: str(own)}), encoding="utf-8")
    assert recomp.find_font(project) == own


def test_a_project_without_a_font_is_refused_before_anything_is_written(tmp_path):
    romfs = tmp_path / "romfs"
    romfs.mkdir()
    (romfs / "a.bin").write_bytes(b"a")
    out = _build_dir(tmp_path)
    with pytest.raises(ValueError, match="TrueType"):
        recomp.build(str(romfs), str(tmp_path / "none"), str(out), lambda done, total: None, lambda: False)
    assert list(out.iterdir()) == []


def test_a_dot_name_in_both_trees_does_not_stop_the_build(tmp_path):
    romfs = tmp_path / "romfs"
    (romfs / "region_common").mkdir(parents=True)
    (romfs / "region_common" / "a.bin").write_bytes(b"a")
    (romfs / ".cache").write_bytes(b"x")
    translation = tmp_path / "translation"
    translation.mkdir()
    (translation / ".cache").write_bytes(b"y")
    (tmp_path / "fonts").mkdir()
    (tmp_path / "fonts" / "UA.ttf").write_bytes(_ttf(recomp.UKRAINIAN))
    out = _build_dir(tmp_path)
    recomp.build(str(romfs), str(translation), str(out), lambda done, total: None, lambda: False)
    assert set(_romfs_contents((out / recomp.ROMFS_NAME).read_bytes())) == {"romfs/region_common/a.bin"}
    assert not (out / "romfs" / ".cache").exists()


def test_the_build_replaces_the_translated_files_and_writes_the_folder_copies(tmp_path):
    (tmp_path / "fonts").mkdir()
    (tmp_path / "fonts" / "UA.ttf").write_bytes(_ttf(recomp.UKRAINIAN))
    (tmp_path / "fonts" / recomp.FONT_LICENCE).write_text("licence", encoding="utf-8")
    romfs = tmp_path / "romfs"
    (romfs / "regionEU" / "EUen" / "message").mkdir(parents=True)
    (romfs / "regionEU" / "EUen" / "message" / "Hint.msbt").write_bytes(b"old hint")
    (romfs / "region_common" / "ui").mkdir(parents=True)
    (romfs / "region_common" / "ui" / "StartUp.arc").write_bytes(b"arc1")
    translation = tmp_path / "translation"
    (translation / "regionEU" / "EUen" / "message").mkdir(parents=True)
    (translation / "regionEU" / "EUen" / "message" / "Hint.msbt").write_bytes(b"new hint")
    (translation / "region_common" / "ui").mkdir(parents=True)
    (translation / "region_common" / "ui" / "StartUp.arc").write_bytes(b"arc2")
    (translation / "regionUS" / "USen" / "message").mkdir(parents=True)
    (translation / "regionUS" / "USen" / "message" / "Hint.msbt").write_bytes(b"not in the dump")
    out = _build_dir(tmp_path)
    recomp.build(str(romfs), str(translation), str(out), lambda done, total: None, lambda: False)
    contents = _romfs_contents((out / recomp.ROMFS_NAME).read_bytes())
    assert contents["romfs/regionEU/EUen/message/Hint.msbt"] == b"new hint"
    assert contents["romfs/region_common/ui/StartUp.arc"] == b"arc2"
    assert "romfs/regionUS/USen/message/Hint.msbt" not in contents
    assert (out / "romfs" / "regionEU" / "EUen" / "message" / "Hint.msbt").read_bytes() == b"new hint"
    assert (out / "fonts" / recomp.FONT_NAME).read_bytes() == (tmp_path / "fonts" / "UA.ttf").read_bytes()
    assert (out / "fonts" / recomp.FONT_LICENCE).read_text(encoding="utf-8") == "licence"
    assert "romfs.bin" in (out / "README.txt").read_text(encoding="utf-8")


def test_a_cancelled_build_leaves_no_romfs_bin(tmp_path):
    romfs = tmp_path / "romfs"
    romfs.mkdir()
    (romfs / "a.bin").write_bytes(b"a")
    (tmp_path / "fonts").mkdir()
    (tmp_path / "fonts" / "UA.ttf").write_bytes(_ttf(recomp.UKRAINIAN))
    out = _build_dir(tmp_path)
    recomp.build(str(romfs), str(tmp_path / "none"), str(out), lambda done, total: None, lambda: True)
    assert not (out / recomp.ROMFS_NAME).exists()
