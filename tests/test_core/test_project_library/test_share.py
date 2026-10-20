"""Share packages: a project goes out without the sender's paths and comes in with the receiver's."""
import json
import zipfile

import pytest

from core.project_library import share


def _project(tmp_path, *, directory_mode=True):
    game = tmp_path / "sender" / "Game"
    source = game / "source"
    (source / "romfs").mkdir(parents=True)
    (source / "romfs" / "a.msbt").write_bytes(b"original")
    project_dir = game / "picoripi"
    project_dir.mkdir()
    glossary = tmp_path / "sender" / "_glossary" / "series.json"
    glossary.parent.mkdir()
    glossary.write_text('{"terms": []}', encoding="utf-8")
    if directory_mode:
        translation = game / "translation"
        (translation / "romfs").mkdir(parents=True)
        (translation / "romfs" / "a.msbt").write_bytes(b"translated")
        (translation / "romfs" / "b.json").write_text('{"keep":   "as is"}', encoding="utf-8")
        source_path = source
    else:
        translation = game / "translation" / "text.json"
        translation.parent.mkdir()
        translation.write_text('{"t": 1}', encoding="utf-8")
        source_path = source / "romfs" / "a.msbt"
    (project_dir / "project.uiproj").write_text(json.dumps({
        "id": "old-id", "name": "Game", "plugin_name": "fake", "blocks": [],
        "metadata": {"source_path": str(source_path), "translation_path": str(translation),
                     "is_directory_mode": directory_mode, "series_glossary": str(glossary),
                     "source_roles": {"base": str(tmp_path / "Downloads" / "game.iso")}},
    }), encoding="utf-8")
    (project_dir / "project_settings.json").write_text(json.dumps({
        "original_file_path": str(source / "romfs" / "a.msbt"),
        "edited_file_path": str(translation if not directory_mode else translation / "romfs" / "a.msbt"),
        "fonts_dir_path": "C:/Fonts/mine",
    }), encoding="utf-8")
    for junk in (".picoripi_session", ".picoripi_session.json", "issues_cache.json", "project.uiproj.bak_1"):
        (project_dir / junk).write_text("{}", encoding="utf-8")
    return project_dir / "project.uiproj"


def test_round_trip_puts_the_receivers_paths_everywhere(tmp_path):
    package = tmp_path / "out" / "game.zip"
    manifest = share.export_project(_project(tmp_path), package)

    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        packed = archive.read("project/project_settings.json").decode("utf-8")
    assert names == {"share.json", "project/project.uiproj", "project/project_settings.json",
                     "translation/romfs/a.msbt", "translation/romfs/b.json", "glossaries/1_series.json"}
    assert "sender" not in packed and "Fonts" not in packed
    assert manifest["translation_files"] == 2 and manifest["glossaries"] == 1
    assert sorted(manifest["cleared"]) == ["project/project.uiproj.metadata.source_roles.base",
                                           "project/project_settings.json.fonts_dir_path"]

    receiver = tmp_path / "receiver"
    own_source = tmp_path / "my games" / "extracted"
    own_source.mkdir(parents=True)
    result = share.import_package(package, receiver, own_source)

    project_file = receiver / "picoripi" / "project.uiproj"
    assert result["project_file"] == str(project_file)
    data = json.loads(project_file.read_text(encoding="utf-8"))
    assert data["id"] != "old-id"
    assert data["metadata"]["source_path"] == str(own_source)
    assert data["metadata"]["translation_path"] == str(receiver / "translation")
    assert data["metadata"]["series_glossary"] == str(receiver / "glossaries" / "1_series.json")
    assert data["metadata"]["source_roles"] == {"base": ""}
    settings = json.loads((receiver / "picoripi" / "project_settings.json").read_text(encoding="utf-8"))
    assert settings["original_file_path"] == str(own_source / "romfs" / "a.msbt")
    assert settings["edited_file_path"] == str(receiver / "translation" / "romfs" / "a.msbt")
    assert (receiver / "translation" / "romfs" / "a.msbt").read_bytes() == b"translated"
    assert (receiver / "translation" / "romfs" / "b.json").read_text(encoding="utf-8") == '{"keep":   "as is"}'
    assert not list(receiver.glob(".share-import-*"))

    with pytest.raises(ValueError):  # a second import over the first one
        share.import_package(package, receiver, own_source)


def test_single_file_project_keeps_its_file_names(tmp_path):
    package = tmp_path / "game.zip"
    share.export_project(_project(tmp_path, directory_mode=False), package)
    own_file = tmp_path / "mine.msbt"
    own_file.write_bytes(b"x")

    share.import_package(package, tmp_path / "receiver", own_file)

    data = json.loads((tmp_path / "receiver" / "picoripi" / "project.uiproj").read_text(encoding="utf-8"))
    assert data["metadata"]["source_path"] == str(own_file)
    assert data["metadata"]["translation_path"] == str(tmp_path / "receiver" / "translation" / "text.json")
    assert (tmp_path / "receiver" / "translation" / "text.json").is_file()


def test_a_member_outside_the_folders_is_refused(tmp_path):
    package = tmp_path / "evil.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("share.json", json.dumps({"format": share.FORMAT}))
        archive.writestr("project/../../escaped.txt", "x")

    with pytest.raises(ValueError):
        share.import_package(package, tmp_path / "receiver", tmp_path)
    assert not (tmp_path / "escaped.txt").exists()
    assert not list((tmp_path / "receiver").glob(".share-import-*"))
