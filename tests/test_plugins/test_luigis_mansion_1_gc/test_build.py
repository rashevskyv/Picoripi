"""Build on synthetic data: Yay0 wrap, archive folders, the record-count guard, the disc image with a changed member."""
import pytest

from core.containers import yay0
from core.containers.gcm import GameCubeImage
from core.containers.rarc_container import RarcContainer
from gc_disc import build_disc
from plugins.common.disc_source import write_source_mark
from plugins.luigis_mansion_1_gc import build
from plugins.luigis_mansion_1_gc.rules import GameRules
from rarc_fixture import build_rarc


def _never() -> bool:
    return False


def _noop(percent, text):
    return None


def _write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _archive(messages: bytes) -> bytes:
    return yay0.compress(build_rarc({"message01.csv": messages}))


def test_yay0_wrap_keeps_the_wrapper_and_the_members():
    rarc = build_rarc({"a.csv": b"A\r\n"})
    wrapped = build.wrap(rarc, yay0.compress(rarc))
    assert wrapped[:4] == b"Yay0"
    assert build.unwrap(wrapped) == rarc


def test_fold_archives_turns_a_yay0_archive_into_a_folder(tmp_path):
    _write(tmp_path / "files/Event/event01.szp", _archive(b"hi\r\n"))
    _write(tmp_path / "files/Event/readme.txt", b"keep")
    assert build.fold_archives(tmp_path)
    assert (tmp_path / "files/Event/event01.szp/message01.csv").read_bytes() == b"hi\r\n"
    assert (tmp_path / "files/Event/readme.txt").read_bytes() == b"keep"


def test_archive_split_finds_the_member_inside_an_archive_folder():
    assert build.archive_split("files/Event/event01.szp/message/message01.csv") == (
        "files/Event/event01.szp", "message/message01.csv")
    assert build.archive_split("files/system/system.arc/font_12.bfn") == ("files/system/system.arc", "font_12.bfn")
    assert build.archive_split("files/Event/readme.txt") is None


def test_changed_files_refuses_a_message_file_with_another_record_count(tmp_path):
    src, trn = tmp_path / "src", tmp_path / "trn"
    _write(src / "files/Event/e.szp/message01.csv", b"one\r\ntwo\r\n")
    _write(trn / "files/Event/e.szp/message01.csv", b"one\r\n")
    with pytest.raises(ValueError, match="number of records"):
        build.changed_files(src, trn)


def test_changed_files_refuses_a_file_the_source_does_not_hold(tmp_path):
    src, trn = tmp_path / "src", tmp_path / "trn"
    src.mkdir()
    _write(trn / "files/new.csv", b"x\r\n")
    with pytest.raises(ValueError, match="not on the disc"):
        build.changed_files(src, trn)


def test_build_writes_a_disc_with_one_changed_record_and_the_dol_untouched(tmp_path):
    dol = b"\x00" * 0x120
    disc = tmp_path / "game.iso"
    disc.write_bytes(build_disc({"Event/event01.szp": _archive(b"Aaahhhh!\r\nOuch\r\n")}, game_id=b"GLME01"))
    source = tmp_path / "source"
    _write(source / "sys/main.dol", dol)
    _write(source / "files/Event/event01.szp/message01.csv", b"Aaahhhh!\r\nOuch\r\n")
    write_source_mark(str(source), str(disc))
    trn = tmp_path / "trn"
    _write(trn / "files/Event/event01.szp/message01.csv", b"Aaahhhh!\r\nOUCH UA\r\n")

    out = build.build_gc_iso(str(source), str(trn), str(tmp_path / "out"), _noop, _never)

    with open(out, "rb") as stream:
        image = GameCubeImage(stream)
        entry = next(e for e in image.entries() if e.path == "files/Event/event01.szp")
        member = RarcContainer(build.unwrap(image.read(entry))).read_file("message01.csv")
        assert member == b"Aaahhhh!\r\nOUCH UA\r\n"
        with open(disc, "rb") as original:
            before = GameCubeImage(original)
            assert image.read(next(e for e in image.entries() if e.path == "sys/main.dol")) == before.read(
                next(e for e in before.entries() if e.path == "sys/main.dol"))


def test_rules_identify_source_accepts_glme01_rev0_only(tmp_path):
    rules = GameRules()
    good = tmp_path / "good.iso"
    good.write_bytes(build_disc({"Event/a.bin": b"x"}, game_id=b"GLME01"))
    other = tmp_path / "other.iso"
    other.write_bytes(build_disc({"Event/a.bin": b"x"}, game_id=b"GLMP01"))
    assert rules.identify_source(str(good)) == {"role": "base", "platform": "gc"}
    assert rules.identify_source(str(other)) is None
