"""Super Mario Sunshine plugin on synthetic data: source mark, archive folders, changed members, the INF1 guard, the
GameCube and port builds."""
import struct
from pathlib import Path

import pytest

from core.containers import yaz0
from core.containers.gcm import GameCubeImage
from core.containers.rarc_container import RarcContainer
from gc_disc import build_disc
from plugins.super_mario_sunshine import build
from plugins.super_mario_sunshine.rules import GameRules
from rarc_fixture import build_rarc


def _never() -> bool:
    return False


def _noop(percent, text):
    return None


def bmg(inf1: bytes, dat: bytes = b"DATA") -> bytes:
    """A BMG-shaped file: a 0x20 header, an INF1 section and a DAT1 section. Enough for the section checks."""
    head = bytearray(0x20)
    head[:8] = b"MESGbmg1"
    inf = b"INF1" + struct.pack(">I", 8 + len(inf1)) + inf1
    dat1 = b"DAT1" + struct.pack(">I", 8 + len(dat)) + dat
    return bytes(head) + inf + dat1


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _disc_entry(path: Path, rel: str) -> bytes:
    with open(path, "rb") as stream:
        image = GameCubeImage(stream)
        return image.read(next(e for e in image.entries() if e.path == rel))


def test_changed_files_lists_only_the_files_that_differ(tmp_path):
    src, trn = tmp_path / "src", tmp_path / "trn"
    _write(src / "files/data/a.bin", b"A")
    _write(src / "files/data/b.bin", b"B")
    _write(trn / "files/data/a.bin", b"X")
    _write(trn / "files/data/b.bin", b"B")
    assert build.changed_files(src, trn) == {"files/data/a.bin": b"X"}


def test_a_file_the_disc_does_not_hold_is_refused(tmp_path):
    src, trn = tmp_path / "src", tmp_path / "trn"
    _write(src / "files/data/a.bin", b"A")
    _write(trn / "files/data/new.bin", b"N")
    with pytest.raises(ValueError, match="not on the disc"):
        build.changed_files(src, trn)


def test_a_changed_message_attribute_block_is_refused(tmp_path):
    src, trn = tmp_path / "src", tmp_path / "trn"
    _write(src / "files/data/a.szs/map/m.bmg", bmg(b"\0" * 8))
    _write(trn / "files/data/a.szs/map/m.bmg", bmg(b"\1" * 8))
    with pytest.raises(ValueError, match="INF1"):
        build.changed_files(src, trn)


def test_a_text_change_in_a_member_is_taken_as_it_is(tmp_path):
    src, trn = tmp_path / "src", tmp_path / "trn"
    _write(src / "files/data/a.szs/m.bmg", bmg(b"\0" * 8))
    edited = bmg(b"\0" * 8, b"EDIT")
    _write(trn / "files/data/a.szs/m.bmg", edited)
    assert build.changed_files(src, trn) == {"files/data/a.szs/m.bmg": edited}


def test_archive_split_finds_the_member_inside_an_archive_folder():
    assert build.archive_split("files/data/scene/a.szs/map/m.bmg") == ("files/data/scene/a.szs", "map/m.bmg")
    assert build.archive_split("files/data/b.bin") is None


def test_fold_archives_turns_a_rarc_into_a_folder_and_keeps_other_files(tmp_path):
    root = tmp_path / "source"
    _write(root / "files/data/a.szs", yaz0.compress(build_rarc({"m.bmg": b"BMG-A"})))
    _write(root / "files/data/plain.szs", b"not an archive")
    build.fold_archives(root)
    assert (root / "files/data/a.szs/m.bmg").read_bytes() == b"BMG-A"
    assert (root / "files/data/a.szs").is_dir()
    assert (root / "files/data/plain.szs").read_bytes() == b"not an archive"


def test_an_archive_is_rebuilt_from_the_disc_and_keeps_yaz0(tmp_path):
    disc = _write(tmp_path / "disc.iso", build_disc({
        "data/a.szs": yaz0.compress(build_rarc({"m.bmg": b"OLD", "n.bmg": b"KEEP"}))}))
    raw = build._archive_bytes(disc, "files/data/a.szs", {"m.bmg": b"NEW"})
    assert raw[:4] == b"Yaz0"
    container = RarcContainer(raw)
    assert container.read_file("m.bmg") == b"NEW"
    assert container.read_file("n.bmg") == b"KEEP"


def test_gc_iso_build_refuses_a_main_dol_that_is_not_the_retail_one(tmp_path):
    other = b"B" * 10
    image = _write(tmp_path / "disc.iso", build_disc({
        "data/a.szs": yaz0.compress(build_rarc({"m.bmg": bmg(b"\0" * 8)})), "data/b.bin": other}))
    src, trn, out = tmp_path / "src", tmp_path / "trn", tmp_path / "out"
    out.mkdir()
    _write(src / "files/data/a.szs/m.bmg", bmg(b"\0" * 8))
    _write(src / "files/data/b.bin", other)
    _write(src / "sys/main.dol", b"\x00" * 0x20)   # the synthetic executable is too short for the speech fix
    build.write_source_mark(src, image)
    _write(trn / "files/data/a.szs/m.bmg", bmg(b"\0" * 8, b"EDIT"))
    with pytest.raises(ValueError, match="too short"):
        build.build_gc_iso(str(src), str(trn), str(out), _noop, _never)
    assert not (out / build.ISO_NAME).exists()


def test_port_pack_writes_the_changed_member_under_the_archive_folder(tmp_path):
    src, trn, out = tmp_path / "src", tmp_path / "trn", tmp_path / "out"
    out.mkdir()
    _write(src / "files/data/a.szs/m.bmg", bmg(b"\0" * 8))
    _write(src / "sys/main.dol", b"\x00" * 0x100)
    _write(trn / "files/data/a.szs/m.bmg", bmg(b"\0" * 8, b"EDIT"))
    _write(trn / "sys/main.dol", b"\x01" * 0x100)
    root = Path(build.build_port_pack(str(src), str(trn), str(out), _noop, _never))
    assert (root / "files/data/a.szs/m.bmg").read_bytes() == bmg(b"\0" * 8, b"EDIT")
    assert not (root / "sys").exists()
    assert (root / "README.txt").read_text(encoding="utf-8").startswith("Super Mario Sunshine")


def test_identify_source_accepts_gmse01_rev0_only(tmp_path):
    rules = GameRules()
    good = _write(tmp_path / "good.iso", build_disc({"data/a.bin": b"A"}, game_id=b"GMSE01"))
    assert rules.identify_source(str(good)) == {"role": "base", "platform": "gc"}
    raw = bytearray(good.read_bytes())
    raw[7] = 1
    newer = _write(tmp_path / "rev1.iso", bytes(raw))
    assert rules.identify_source(str(newer)) is None
    other = _write(tmp_path / "wind.iso", build_disc({"data/a.bin": b"A"}, game_id=b"GZLE01"))
    assert rules.identify_source(str(other)) is None


def test_the_system_font_is_declared_as_a_bfn_in_the_stage_archive_folder():
    entries = GameRules().get_font_sources()
    assert [(e["format"], e["path"], e["member"]) for e in entries] == [
        ("bfn", ["files/data/nintendo.szs"], "font/standard_fontex.bfn")]


def test_build_targets_and_an_unknown_target(tmp_path):
    rules = GameRules()
    assert [t["id"] for t in rules.get_build_targets()] == ["gc_iso", "port_pack"]
    with pytest.raises(ValueError):
        rules.build_target("nope", str(tmp_path), str(tmp_path), str(tmp_path), _noop, _never)


def test_source_without_a_mark_cannot_build_the_disc(tmp_path):
    with pytest.raises(ValueError, match="no disc record"):
        build.disc_of_source(tmp_path)
