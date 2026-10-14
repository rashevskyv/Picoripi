"""Link's Awakening (Switch) plugin without game data: the v1.0.0 check, the SWUK label mapping and the mod import.

The real SWUK mod is checked when ``PICORIPI_LAS_SWUK`` names its zip (see ``tests/romhacking_root.py`` for the
pattern). Nothing here reads a key file.
"""
import io
import os
import struct
import zipfile
from pathlib import Path

import pytest

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


def test_import_writes_both_slots_and_reports_each_file(tmp_path):
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
    assert any("regionEU/EUen/message/Hint.msbt: 1 matched, 1 kept English" in line for line in report)
    assert any("StartUp.arc: copied (8 bytes; the 1.0.0 file has 4 bytes)" in line for line in report)
    assert _texts((translation / "regionUS/USen/message/Hint.msbt").read_bytes()) == [("A", "english a"),
                                                                                       ("B", "мод b")]
    assert (translation / "region_common/ui/StartUp.arc").read_bytes() == b"abcdefgh"
    assert not (translation / "regionJP").exists()
    assert not (tmp_path / "evil.msbt").exists()


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


def test_the_build_replaces_the_translated_files_and_writes_the_folder_copies(tmp_path):
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
    out = tmp_path / "build"
    out.mkdir()
    recomp.build(str(romfs), str(translation), str(out), lambda done, total: None, lambda: False)
    contents = _romfs_contents((out / recomp.ROMFS_NAME).read_bytes())
    assert contents["romfs/regionEU/EUen/message/Hint.msbt"] == b"new hint"
    assert contents["romfs/region_common/ui/StartUp.arc"] == b"arc2"
    assert "romfs/regionUS/USen/message/Hint.msbt" not in contents
    assert (out / "romfs" / "regionEU" / "EUen" / "message" / "Hint.msbt").read_bytes() == b"new hint"
    assert "romfs.bin" in (out / "README.txt").read_text(encoding="utf-8")


def test_a_cancelled_build_leaves_no_romfs_bin(tmp_path):
    romfs = tmp_path / "romfs"
    romfs.mkdir()
    (romfs / "a.bin").write_bytes(b"a")
    out = tmp_path / "build"
    out.mkdir()
    recomp.build(str(romfs), str(tmp_path / "none"), str(out), lambda done, total: None, lambda: True)
    assert not (out / recomp.ROMFS_NAME).exists()
