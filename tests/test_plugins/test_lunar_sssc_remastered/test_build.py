"""Lunar SSS one-translation builds: the PS1 dialogue files and the reference columns (synthetic scripts, no game data)."""
import pytest

from plugins.lunar_sssc_remastered import build, text
from plugins.lunar_sssc_remastered.rules import ENGLISH_LABEL, PS1_LABEL, GameRules
from .test_text import _END, _message, _other, _script

JAPANESE = _script(_message(0x01), _message(0x09), _other(), _message(0x02), _END)
ENGLISH = _script(_message(0x01), _other(), _message(0x02), _END)


def _source(root, ps1=True):
    for folder in ("FIL", "FIL_us", *(("LUNADATA",) if ps1 else ())):
        (root / folder).mkdir(parents=True)
        (root / folder / "TEXT001.DAT").write_bytes(JAPANESE if folder == "FIL" else ENGLISH)
    return root


def _translation(root, lines):
    (root / "FIL").mkdir(parents=True)
    (root / "FIL" / "TEXT001.DAT").write_bytes(text.translation_bytes(lines))
    return root


def test_ps1_build_writes_the_translation_into_the_ps1_english_slots(tmp_path):
    source = _source(tmp_path / "source")
    translation = _translation(tmp_path / "translation", ["Hi there", "", "Second"])
    out = build.build_ps1(str(source), str(translation), str(tmp_path / "out"), lambda *_: None, lambda: False)
    assert text.strings_of((tmp_path / "out" / "LUNADATA" / "TEXT001.DAT").read_bytes(), japanese=False) == \
        ["Hi there", "Second"]
    assert out.endswith("LUNADATA")


def test_ps1_build_without_the_ps1_files_says_so(tmp_path):
    source = _source(tmp_path / "source", ps1=False)
    translation = _translation(tmp_path / "translation", ["Hi"])
    with pytest.raises(ValueError):
        build.build_ps1(str(source), str(translation), str(tmp_path / "out"), lambda *_: None, lambda: False)


def test_reference_has_a_column_per_english_file(tmp_path):
    source = _source(tmp_path / "source")
    columns = GameRules().load_multi_reference(str(source), block_names={0: "FIL/TEXT001.DAT"})
    assert set(columns) == {ENGLISH_LABEL, PS1_LABEL}
    assert set(columns[PS1_LABEL]) == {(0, 0), (0, 2)}


def test_reference_without_the_ps1_disc_has_the_remastered_column_only(tmp_path):
    source = _source(tmp_path / "source", ps1=False)
    assert set(GameRules().load_multi_reference(str(source), block_names={0: "FIL/TEXT001.DAT"})) == {ENGLISH_LABEL}


def test_the_archive_build_takes_the_edited_font_files(tmp_path, monkeypatch):
    source, translation = _source(tmp_path / "src", ps1=False), tmp_path / "tr"
    (source / "data.cpk").write_bytes(b"CPK ")
    fonts = translation / "FIL" / "CUSTOM" / "Font" / "1"
    fonts.mkdir(parents=True)
    (fonts / "test.fnt").write_bytes(b"fnt")
    (fonts / "test_02.dds").write_bytes(b"page")
    taken = {}
    monkeypatch.setattr(build, "patch", lambda stream, replacements, target: taken.update(replacements))
    build.build_pc(str(source), str(translation), str(tmp_path / "out"), lambda *_: None, lambda: False)
    assert taken == {"FIL/CUSTOM/Font/1/test.fnt": b"fnt", "FIL/CUSTOM/Font/1/test_02.dds": b"page"}


def test_both_remastered_fonts_open_in_the_font_editor():
    from core import font_formats
    from plugins.testing import load_rules
    found = load_rules("lunar_sssc_remastered").get_font_sources()
    assert [entry["path"] for entry in found] == ["FIL/CUSTOM/Font/0/test.fnt", "FIL/CUSTOM/Font/1/test.fnt"]
    assert all(font_formats.is_supported(entry["format"]) for entry in found)
