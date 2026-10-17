"""Grandia II plugin (plugins/grandia/rules.py): load and save of one message archive, the replacement scan of a build,
and identification of the owner's disc. The disc build itself is checked by machine on the real disc, not in the suite
(it copies 1.2 GB)."""
import json
import os

import pytest

from core.containers import afs
from plugins.grandia import archive, text
from plugins.grandia.rules import REF_NAME, GameRules
from test_core.test_afs_container import make_afs

REAL_CUE = r"E:\Emulators\RomHacking\Grandia\Grandia II\Dreamcast\ISO\Grandia II (USA).cue"


class _Context:
    def __init__(self, versions):
        self._versions = versions

    def existing_versions(self):
        return list(self._versions)


def _record(header_pad: bytes, body: bytes) -> bytes:
    return text.MARK + b"\x08\x24\xa1\x02\x00\x03\x10\x16\x03" + header_pad + text.TEXT_START + body


def _archive():
    return make_afs([b"\x01\x02" + _record(b"", b"Hello \x1fworld"), b"no text here"])


def _entry_bytes(data: bytes, index: int) -> bytes:
    entry = afs.parse(data)[index]
    return data[entry.offset:entry.offset + entry.size]


def test_a_message_archive_loads_as_its_texts_and_saves_with_the_edit():
    rules = GameRules()
    data = _archive()
    blocks, names = rules.load_data_from_json_obj(data)
    assert blocks == [["Hello {1F}world"]]
    assert names["0"].startswith("entry 0")
    rules.prepare_save_context(_Context([data]))
    out = rules.save_data_to_json_obj([["Hello, Ukraine."]], names)
    assert archive.blocks(out)[0] == ["Hello, Ukraine."]
    assert _entry_bytes(out, 1) == b"no text here"


def test_a_file_that_is_not_an_archive_loads_without_texts():
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(b"plain text file")
    assert blocks == [[]] and names == {}


def test_the_build_finds_only_the_archives_whose_translation_differs(tmp_path):
    rules = GameRules()
    source = tmp_path / "source"
    translation = tmp_path / "translation"
    (source / "files" / "MAP").mkdir(parents=True)
    (source / "files" / "MAP" / "1000.AFS").write_bytes(_archive())
    (source / "files" / "MAP" / "1004.AFS").write_bytes(_archive())
    (translation / "files" / "MAP").mkdir(parents=True)
    (translation / "files" / "MAP" / "1004.AFS").write_bytes(_archive())
    assert rules._replacements(str(source), str(translation)) == {}
    (translation / "files" / "MAP" / "1004.AFS").write_bytes(make_afs([b"other"]))
    assert list(rules._replacements(str(source), str(translation))) == ["files/MAP/1004.AFS"]


def test_a_missing_disc_reference_is_refused_before_the_build(tmp_path):
    rules = GameRules()
    (tmp_path / REF_NAME).write_text(json.dumps({"game_id": "T17716N", "cue": str(tmp_path / "gone.cue")}))
    with pytest.raises(ValueError):
        rules.build_target("disc_set", str(tmp_path), str(tmp_path), str(tmp_path / "out"), lambda *_: None,
                           lambda: False)


@pytest.mark.skipif(not os.path.isfile(REAL_CUE), reason="the owner's Grandia II image is not on disk")
def test_the_owners_disc_is_identified_as_grandia_ii_on_dreamcast():
    assert GameRules().identify_source(REAL_CUE) == {"role": "base", "platform": "gdrom"}
