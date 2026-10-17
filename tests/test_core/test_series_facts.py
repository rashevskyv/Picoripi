"""The series glossaries a project uses, read for the Project Manager's details (synthetic files only)."""
import json
import os

from core.glossary import series as series_module
from core.project_library import series_facts as facts
from ui.project_manager.window import series_summary


def _project(folder, metadata=None):
    picoripi = folder / "Game" / "picoripi"
    picoripi.mkdir(parents=True, exist_ok=True)
    project_file = picoripi / "project.uiproj"
    project_file.write_text(json.dumps({"name": "Game", "metadata": metadata or {}}), encoding="utf-8")
    return project_file


def _glossary(path, count):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([{"original": f"term{n}", "translation": ""} for n in range(count)]), encoding="utf-8")
    return path


class TestSeriesFacts:
    def test_the_folder_glossary_above_the_project_is_counted_with_its_name(self, tmp_path):
        _glossary(tmp_path / "Series" / "_glossary" / "glossary.json", 3)
        project = _project(tmp_path / "Series")
        found = facts.series_facts(str(project))
        assert [(entry["name"], entry["terms"]) for entry in found["files"]] == [("Series", 3)]
        assert found["terms"] == 3

    def test_an_explicit_link_is_read_too(self, tmp_path):
        linked = _glossary(tmp_path / "elsewhere" / "glossary.json", 2)
        project = _project(tmp_path / "Series", metadata={series_module.METADATA_KEY: str(linked)})
        found = facts.series_facts(str(project))
        assert [entry["terms"] for entry in found["files"]] == [2]

    def test_a_project_with_no_series_glossary_has_no_files(self, tmp_path):
        project = _project(tmp_path / "Lonely")
        assert facts.series_facts(str(project)) == {"files": [], "terms": 0}

    def test_an_unchanged_file_keeps_its_count_and_is_not_read_again(self, tmp_path, monkeypatch):
        _glossary(tmp_path / "Series" / "_glossary" / "glossary.json", 4)
        project = _project(tmp_path / "Series")
        first = facts.series_facts(str(project))

        def must_not_read(path):
            raise AssertionError("an unchanged glossary is read again")

        monkeypatch.setattr(facts, "_terms_of", must_not_read)
        assert facts.series_facts(str(project), first) == first

    def test_a_changed_file_is_counted_again_and_the_project_file_is_not_written(self, tmp_path):
        glossary = _glossary(tmp_path / "Series" / "_glossary" / "glossary.json", 1)
        project = _project(tmp_path / "Series")
        before = project.read_bytes(), os.stat(project).st_mtime_ns
        first = facts.series_facts(str(project))
        _glossary(glossary, 5)
        assert facts.series_facts(str(project), first)["terms"] == 5
        assert (project.read_bytes(), os.stat(project).st_mtime_ns) == before

    def test_the_summary_names_the_glossaries_and_counts_terms(self):
        assert series_summary(None) == "None"
        text = series_summary({"files": [{"name": "Series"}], "terms": 1234})
        assert "Series" in text and "1,234" in text
