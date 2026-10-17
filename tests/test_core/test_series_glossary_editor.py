"""Series glossaries in the editor: a series term the project does not translate is a hit in the translation, and two
series glossaries that translate one term differently are a conflict (synthetic terms only)."""
import json
from types import SimpleNamespace

from core.glossary.manager import GlossaryManager
from core.glossary.series import series_managers_of, series_pair_conflicts
from handlers.async_issue_scanner import AsyncIssueScanner


def _glossary(path, rows):
    """A glossary of ``rows`` (original, translation); the file is only a name, nothing is written."""
    entries = [{"original": original, "translation": translation, "notes": "", "section": "Pokémon",
                "status": "confirmed", "profiled": False, "id": f"id-{index}"}
               for index, (original, translation) in enumerate(rows)]
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=path, raw_text=json.dumps(entries, ensure_ascii=False))
    return manager


def _scanner(project, series, source, editor):
    return AsyncIssueScanner(
        block_idx=0, string_idx=0, text=editor, font_map={}, width_threshold=100, analyzer=None,
        glossary_manager=project, source_text=source, glossary_enabled=True, editor_text=editor,
        series_glossaries=series,
    )


class TestEditorBridge:
    def test_a_series_term_the_project_does_not_translate_is_a_hit(self, tmp_path):
        project = _glossary(tmp_path / "p.json", [])
        series = _glossary(tmp_path / "s.json", [("Zorblet", "Зорблет")])
        matches = _scanner(project, [series], "Zorblet is here", "Зорблет тут")._run_translation_matches()
        assert [(m["original"], m["translation"]) for m in matches] == [("Zorblet", "Зорблет")]

    def test_the_project_translation_wins_over_the_series_one(self, tmp_path):
        project = _glossary(tmp_path / "p.json", [("Zorblet", "Зорблет")])
        series = _glossary(tmp_path / "s.json", [("Zorblet", "Інше")])
        matches = _scanner(project, [series], "Zorblet is here", "Зорблет тут")._run_translation_matches()
        assert [m["translation"] for m in matches] == ["Зорблет"]

    def test_a_series_term_without_a_translation_is_no_hit(self, tmp_path):
        project = _glossary(tmp_path / "p.json", [])
        series = _glossary(tmp_path / "s.json", [("Zorblet", "")])
        assert _scanner(project, [series], "Zorblet is here", "Зорблет тут")._run_translation_matches() == []

    def test_without_series_glossaries_only_the_project_is_bridged(self, tmp_path):
        project = _glossary(tmp_path / "p.json", [])
        assert _scanner(project, [], "Zorblet is here", "Зорблет тут")._run_translation_matches() == []


class TestSeriesConflicts:
    def test_two_series_glossaries_that_translate_one_term_differently_conflict(self, tmp_path):
        first = _glossary(tmp_path / "a.json", [("Zorblet", "Зорблет"), ("Quaxly", "Квакслі")])
        second = _glossary(tmp_path / "b.json", [("Zorblet", "Зорбл"), ("Quaxly", "квакслі")])
        found = series_pair_conflicts([first, second])
        assert [(a, b, mine, theirs) for a, b, _key, mine, theirs in found] == [(0, 1, "Зорблет", "Зорбл")]

    def test_one_series_glossary_has_no_pair(self, tmp_path):
        assert series_pair_conflicts([_glossary(tmp_path / "a.json", [("Zorblet", "Зорблет")])]) == []

    def test_the_series_of_the_open_project_are_read_from_the_glossary_handler(self, tmp_path):
        first = _glossary(tmp_path / "a.json", [])
        handler = SimpleNamespace(series_glossary_managers=[first])
        window = SimpleNamespace(translation_handler=SimpleNamespace(glossary_handler=handler))
        assert series_managers_of(window) == [first]
        assert series_managers_of(SimpleNamespace()) == []
