"""Seeding a series glossary from a project's game data: terms added, existing entries and translations kept."""
import json
from pathlib import Path

from core.glossary.series_seeds import seed_series_file


class FakeGameRules:
    """A plugin stand-in with a seed hook. It reads the project manager it is handed, as the real hooks do."""

    seen_projects: list = []

    def __init__(self, mw=None):
        self.mw = mw

    def get_glossary_seed_entries(self):
        FakeGameRules.seen_projects.append(self.mw.project_manager.project.name)
        return [
            {"term": "Alpha", "section": "Species", "description": "table", "source_ref": "t 0"},
            {"term": "Beta", "section": "Moves"},
            {"term": "", "section": "Moves"},
        ]


class NoHookRules:
    def __init__(self, mw=None):
        self.mw = mw


def _project(tmp_path: Path, plugin: str) -> Path:
    project_dir = tmp_path / "game" / "picoripi"
    project_dir.mkdir(parents=True)
    project_file = project_dir / "project.uiproj"
    project_file.write_text(json.dumps({
        "id": "p1", "name": "Synthetic game", "plugin_name": plugin, "blocks": [],
    }), encoding="utf-8")
    return project_file


def test_the_game_terms_are_added_as_seeds_without_translations(tmp_path):
    project = _project(tmp_path, "fake")
    series = tmp_path / "series" / "glossary.json"

    counts = seed_series_file(project, series, load_rules=lambda name, mw=None: FakeGameRules(mw))

    assert counts == {"offered": 3, "added": 2, "present": 0}
    rows = json.loads(series.read_text(encoding="utf-8"))
    by_term = {row["original"]: row for row in rows}
    assert set(by_term) == {"Alpha", "Beta"}
    assert by_term["Alpha"]["translation"] == "" and by_term["Beta"]["translation"] == ""
    assert by_term["Alpha"]["status"] == "fragments" and by_term["Beta"]["status"] == "fragments"
    assert by_term["Alpha"]["notes"] == "Synthetic game: table"
    assert by_term["Beta"]["notes"] == "Synthetic game"
    assert FakeGameRules.seen_projects[-1] == "Synthetic game"


def test_a_second_run_adds_nothing_and_keeps_a_translation_the_owner_wrote(tmp_path):
    project = _project(tmp_path, "fake")
    series = tmp_path / "series" / "glossary.json"
    series.parent.mkdir(parents=True)
    series.write_text(json.dumps([{"original": "Alpha", "translation": "Альфа", "status": "confirmed"}]), encoding="utf-8")

    counts = seed_series_file(project, series, load_rules=lambda name, mw=None: FakeGameRules(mw))

    assert counts == {"offered": 3, "added": 1, "present": 1}
    rows = {row["original"]: row for row in json.loads(series.read_text(encoding="utf-8"))}
    assert rows["Alpha"]["translation"] == "Альфа"


def test_a_plugin_without_a_seed_hook_adds_nothing_and_writes_nothing(tmp_path):
    project = _project(tmp_path, "plain")
    series = tmp_path / "series" / "glossary.json"

    counts = seed_series_file(project, series, load_rules=lambda name, mw=None: NoHookRules(mw))

    assert counts == {"offered": 0, "added": 0, "present": 0}
    assert not series.exists()
