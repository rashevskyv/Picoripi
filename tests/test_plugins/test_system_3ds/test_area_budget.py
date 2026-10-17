"""The `area` country and region files take one width budget each (the owner's validate_area): wider names are a problem."""
from types import SimpleNamespace

from plugins.system_3ds.config import WIDTH_PROBLEM
from plugins.system_3ds.rules import GameRules


def _rules_for(source_file, budgets):
    rules = GameRules()
    rules._blocks = [{"keys": ["0", "1"]}]
    rules._budgets = budgets
    rules._project_blocks = lambda: [SimpleNamespace(source_file=source_file)]
    return rules


def test_an_area_file_has_one_budget_for_all_its_names():
    rules = _rules_for("strings/area/EU_100.json", {"labels": {}, "panes": {}, "areas": {"100": 553}})

    assert rules.budget(0, 0) == 553
    assert rules.budget(0, 1) == 553


def test_a_name_wider_than_its_area_budget_is_a_problem():
    rules = _rules_for("strings/area/EU_100.json", {"labels": {}, "panes": {}, "areas": {"100": 40}})

    assert rules.width_problems(0, 0, "W" * 40) == {WIDTH_PROBLEM}
    assert rules.width_problems(0, 1, "ab") == set()


def test_a_file_with_no_area_budget_shows_width_only():
    rules = _rules_for("strings/area/EU_999.json", {"labels": {}, "panes": {}, "areas": {"100": 40}})

    assert rules.budget(0, 0) is None
    assert rules.width_problems(0, 0, "W" * 400) == set()


def test_the_shipped_budgets_carry_the_area_budgets():
    budgets = GameRules()._budget_table()

    assert budgets["areas"]["100"] > 0
    assert len(budgets["areas"]) >= 60
