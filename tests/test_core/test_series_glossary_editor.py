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


class TestBatchSeed:
    """``seed_entries`` gives the answers of ``seed_entry`` one term at a time, in one pass (synthetic terms only)."""

    SEEDS = [
        {"term": "Zorblet", "section": "Pokémon", "description": "table one"},
        {"term": "zorblet", "section": "Pokémon"},            # the same term in other case
        {"term": "Quaxlys", "section": "Pokémon"},             # a plural of Quaxly (canonical key)
        {"term": "Quaxly", "section": "Pokémon"},
        {"term": "Frimble", "section": "Items", "description": "fragment"},
        {"term": "", "section": "Items"},
        {"term": "Frimble", "section": "Moves"},              # already seeded above in this batch
    ]

    def _start(self, tmp_path):
        return _glossary(tmp_path / "s.json", [("Pebble", "Галька")])

    def test_the_batch_adds_each_new_term_once_and_counts_the_present_ones(self, tmp_path):
        glossary = self._start(tmp_path)
        added, present = glossary.seed_entries(self.SEEDS)
        assert (added, present) == (3, 3)
        assert [e.original for e in glossary.get_entries()] == ["Pebble", "Zorblet", "Quaxlys", "Frimble"]

    def test_the_batch_gives_the_same_terms_as_one_term_at_a_time(self, tmp_path):
        one = self._start(tmp_path / "one")
        for seed in self.SEEDS:
            if seed["term"] and one.find_entry(seed["term"]) is None:
                one.seed_entry(seed["term"], section=seed.get("section"), description=seed.get("description", ""),
                               status="fragments" if seed.get("description") else "seeded")
        many = self._start(tmp_path / "many")
        many.seed_entries([{"term": s["term"], "section": s.get("section"), "description": s.get("description", ""),
                            "status": "fragments" if s.get("description") else "seeded"} for s in self.SEEDS])
        assert [(e.original, e.section, e.status, e.notes) for e in many.get_entries()] == \
               [(e.original, e.section, e.status, e.notes) for e in one.get_entries()]

    def test_an_existing_term_is_never_changed(self, tmp_path):
        glossary = self._start(tmp_path)
        glossary.seed_entries([{"term": "Pebble", "section": "Items", "description": "new"}])
        pebble = glossary.find_entry("Pebble")
        assert (pebble.translation, pebble.section) == ("Галька", "Pokémon")
