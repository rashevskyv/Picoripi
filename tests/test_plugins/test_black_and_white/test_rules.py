"""Black & White rules and build: the source file choice, the save through a template, the SD copy."""
import os

import pytest

from plugins.black_and_white import infoscript
from plugins.black_and_white.rules import GameRules, build_sd_file


class _Context:
    def __init__(self, versions):
        self._versions = versions

    def existing_versions(self):
        return iter(self._versions)


def _call(flag, narrator, key, text):
    return f'ADD_TEXT( {flag}, {narrator}, "{key}", "{text}")'


def _table(*calls):
    return (("﻿") + "\r\n".join(calls) + "\r\n").encode("utf-16-le")


SOURCE = _table(_call(1, "NARRATOR_A", "SYN_A", "Alpha"), _call(0, "NARRATOR_B", "SYN_B", "Beta"))


def test_only_the_info_script_file_becomes_a_block():
    rules = GameRules()
    assert rules.includes_source_file("Scripts/InfoScript2.txt")
    assert rules.includes_source_file("scripts\\infoscript2.TXT")
    assert not rules.includes_source_file("Scripts/Land1.txt")
    assert not rules.includes_source_file("Scripts/InfoScriptPatch2.txt")


def test_load_gives_one_block_of_texts_in_file_order():
    blocks, names = GameRules().load_data_from_json_obj(SOURCE)
    assert blocks == [["Alpha", "Beta"]]
    assert names == {"0": "ADD_TEXT"}


def test_save_writes_the_new_texts_into_the_newest_template():
    rules = GameRules()
    rules.prepare_save_context(_Context([SOURCE]))
    rules.load_data_from_json_obj(SOURCE)
    out = rules.save_data_to_json_obj([["Альфа", "Бета"]], {})
    assert infoscript.texts(out) == ["Альфа", "Бета"]
    assert infoscript.keys(out) == ["SYN_A", "SYN_B"]


def test_save_keeps_the_translation_copy_as_template_when_it_exists():
    translation = _table(_call(1, "NARRATOR_A", "SYN_A", "Old copy"), _call(0, "NARRATOR_B", "SYN_B", "Old two"))
    rules = GameRules()
    rules.prepare_save_context(_Context([translation, SOURCE]))
    out = rules.save_data_to_json_obj([["New one", "New two"]], {})
    assert infoscript.texts(out) == ["New one", "New two"]
    assert infoscript.records(out)[1].narrator == "NARRATOR_B"


def test_save_returns_the_template_when_the_count_changed():
    rules = GameRules()
    rules.prepare_save_context(_Context([SOURCE]))
    assert rules.save_data_to_json_obj([["Only one"]], {}) == SOURCE


def test_identify_source_recognises_the_table_by_content(tmp_path):
    rules = GameRules()
    table = tmp_path / "InfoScript2.txt"
    table.write_bytes(SOURCE)
    assert rules.identify_source(str(table)) == {"role": "base", "platform": ""}
    other = tmp_path / "InfoScript2.txt.bak"
    other.write_bytes(SOURCE)
    assert rules.identify_source(str(other)) is None
    wrong = tmp_path / "InfoScript2.txt"
    wrong.write_bytes(b"not a table")
    assert rules.identify_source(str(wrong)) is None


def test_build_writes_the_translation_to_the_sd_folder(tmp_path):
    source_dir = tmp_path / "source"
    translation_dir = tmp_path / "translation"
    output_dir = tmp_path / "out"
    (source_dir / "Scripts").mkdir(parents=True)
    (translation_dir / "Scripts").mkdir(parents=True)
    output_dir.mkdir()
    (source_dir / "Scripts" / "InfoScript2.txt").write_bytes(SOURCE)
    translated = infoscript.replace_texts(SOURCE, ["Перший", "Другий"])
    (translation_dir / "Scripts" / "InfoScript2.txt").write_bytes(translated)

    rules = GameRules()
    target = rules.build_target("openblack_sd", str(source_dir), str(translation_dir), str(output_dir),
                                lambda *_: None, lambda: False)
    expected = output_dir / "switch" / "openblack" / "game" / "Scripts" / "InfoScript2.txt"
    assert os.path.normpath(target) == os.path.normpath(str(expected))
    assert expected.read_bytes() == translated
    assert sorted(p.name for p in output_dir.rglob("*") if p.is_file()) == ["InfoScript2.txt"]


def test_build_stops_when_the_keys_differ(tmp_path):
    source_dir = tmp_path / "source" / "Scripts"
    translation_dir = tmp_path / "translation" / "Scripts"
    source_dir.mkdir(parents=True)
    translation_dir.mkdir(parents=True)
    (source_dir / "InfoScript2.txt").write_bytes(SOURCE)
    other = _table(_call(1, "NARRATOR_A", "SYN_A", "Alpha"), _call(0, "NARRATOR_B", "SYN_X", "Beta"))
    (translation_dir / "InfoScript2.txt").write_bytes(other)
    with pytest.raises(ValueError):
        build_sd_file(str(tmp_path / "translation"), str(tmp_path / "source"))


def test_build_needs_a_translation_file(tmp_path):
    with pytest.raises(ValueError):
        build_sd_file(str(tmp_path / "missing"), str(tmp_path / "source"))


def test_other_targets_fall_back_to_the_base_class(tmp_path):
    with pytest.raises(ValueError):
        GameRules().build_target("nope", str(tmp_path), str(tmp_path), str(tmp_path), lambda *_: None, lambda: False)
