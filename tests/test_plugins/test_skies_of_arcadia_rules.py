"""Skies of Arcadia Legends plugin (plugins/skies_of_arcadia): the disc identity, the source mark and the build's
changed-file map. Synthetic bytes only; the real disc build is checked by machine on the owner's image, not here."""
import pytest

from core.containers import aklz
from plugins.skies_of_arcadia import build
from plugins.skies_of_arcadia.rules import GameRules


def _script(text: bytes) -> bytes:
    return b"AKLZ-body " + text * 4


def test_identity_refuses_a_missing_file():
    assert GameRules().identify_source(r"Z:\no-such-disc.rvz") is None


def test_platform_and_build_target_are_gamecube_iso():
    rules = GameRules()
    assert [p["id"] for p in rules.get_platforms()] == ["gc"]
    targets = rules.get_build_targets()
    assert [t["id"] for t in targets] == ["gc_iso"]
    assert targets[0]["platforms"] == ["gc"]


def test_changed_files_keeps_only_edited_files(tmp_path):
    source, translation = tmp_path / "src", tmp_path / "tr"
    (source / "field").mkdir(parents=True)
    (translation / "field").mkdir(parents=True)
    (source / "field" / "a.sct").write_bytes(_script(b"one"))
    (source / "field" / "b.sct").write_bytes(_script(b"two"))
    (translation / "field" / "a.sct").write_bytes(_script(b"ONE"))
    (translation / "field" / "b.sct").write_bytes(_script(b"two"))
    assert build.changed_files(source, translation) == {"field/a.sct": _script(b"ONE")}


def test_changed_files_refuses_a_file_the_disc_does_not_hold(tmp_path):
    source, translation = tmp_path / "src", tmp_path / "tr"
    source.mkdir()
    (translation / "field").mkdir(parents=True)
    (translation / "field" / "new.sct").write_bytes(b"x")
    with pytest.raises(ValueError):
        build.changed_files(source, translation)


def test_disc_changes_compress_scripts_and_prefix_files():
    decoded = _script(b"text")
    out = build.disc_changes({"field/a.sct": decoded, "other.bin": b"raw"})
    assert aklz.decode(out["files/field/a.sct"]) == decoded
    assert out["files/other.bin"] == b"raw"


def test_source_mark_round_trip_and_size_check(tmp_path):
    image = tmp_path / "disc.rvz"
    image.write_bytes(b"0123456789")
    build.write_source_mark(tmp_path, image)
    assert build.disc_of_source(tmp_path) == image
    image.write_bytes(b"short")
    with pytest.raises(ValueError):
        build.disc_of_source(tmp_path)
