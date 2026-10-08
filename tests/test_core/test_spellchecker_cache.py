"""The parsed-dictionary disk cache: written, reused, invalidated by a changed file, rebuilt when corrupt."""
import os

import pytest

from core import spellchecker_cache
from utils import constants

AFF = "SET UTF-8\nSFX S Y 1\nSFX S 0 s .\n"
# Taken at import, before tests/conftest.py points the cache at one folder for the session.
_settings_cache_dir = spellchecker_cache._cache_dir


@pytest.fixture
def basename(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "SETTINGS_DIR", tmp_path / "settings")
    monkeypatch.setattr(spellchecker_cache, "_cache_dir", _settings_cache_dir)
    folder = tmp_path / "dict"
    folder.mkdir()
    (folder / "xx.aff").write_text(AFF, encoding="utf-8")
    (folder / "xx.dic").write_text("2\ncat/S\ndog\n", encoding="utf-8")
    return folder / "xx"


def _no_parse(monkeypatch):
    def fail(path):
        raise AssertionError("parsed although the cache is current")
    monkeypatch.setattr(spellchecker_cache.Dictionary, "from_files", staticmethod(fail))


def test_cache_is_written_and_reused(basename, monkeypatch):
    first = spellchecker_cache.load_dictionary(basename)
    cache = spellchecker_cache._cache_path(basename)
    assert cache.is_file()
    assert cache.is_relative_to(constants.SETTINGS_DIR)

    _no_parse(monkeypatch)
    cached = spellchecker_cache.load_dictionary(basename)
    for word in ("cat", "cats", "dog", "Cats"):
        assert cached.lookup(word) is True
    assert cached.lookup("dogs") is False
    assert "cat" in list(cached.suggest("cta"))
    assert [w.stem for w in cached.dic.words] == [w.stem for w in first.dic.words]


def test_changed_dictionary_invalidates_the_cache(basename):
    spellchecker_cache.load_dictionary(basename)
    dic = basename.with_suffix(".dic")
    dic.write_text("3\ncat/S\ndog\nbird/S\n", encoding="utf-8")
    stat = dic.stat()
    os.utime(dic, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    assert spellchecker_cache.load_dictionary(basename).lookup("birds") is True


def test_corrupt_cache_falls_back_to_parsing_and_is_rewritten(basename, monkeypatch):
    spellchecker_cache.load_dictionary(basename)
    cache = spellchecker_cache._cache_path(basename)
    cache.write_bytes(b"not a pickle")

    assert spellchecker_cache.load_dictionary(basename).lookup("cats") is True

    _no_parse(monkeypatch)
    assert spellchecker_cache.load_dictionary(basename).lookup("cats") is True
