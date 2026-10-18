"""Skies of Arcadia budget (plugins/skies_of_arcadia): a changed line of a script over the script's budget is flagged,
every changed line of that script; a script within its budget is not; the build refuses an over-budget script.
Synthetic scripts only (no game data)."""
from types import SimpleNamespace

import pytest

from plugins.skies_of_arcadia import build, scripts
from plugins.skies_of_arcadia import rules as rules_module
from plugins.skies_of_arcadia.config import PROBLEM_BYTE_BUDGET
from plugins.skies_of_arcadia.problem_analyzer import ProblemAnalyzer
from plugins.skies_of_arcadia.rules import GameRules
from plugins.skies_of_arcadia.tag_manager import TagManager

from .test_skies_of_arcadia_text import _script


def _rules(monkeypatch, tmp_path, body, texts, big=True):
    """Game rules whose source script is ``body`` and whose current texts are ``texts`` (one per segment)."""
    path = tmp_path / "me201a.sct"
    path.write_bytes(body)
    monkeypatch.setattr(rules_module, "source_of", lambda mw, block_idx: ("field/me201a.sct", path))
    mw = SimpleNamespace(data_processor=SimpleNamespace(get_block_texts=lambda block_idx: list(texts)))
    rules = GameRules(mw)
    rules.big_endian = big
    return rules


def test_a_changed_line_of_an_over_budget_script_is_flagged(monkeypatch, tmp_path):
    body = _script([b"Hi", b"Bye"])
    rules = _rules(monkeypatch, tmp_path, body, ["Hi", "Bye"])
    assert rules.exceeds_byte_budget(0, 0, "Hello there") is True
    detail = rules.get_problem_detail(0, 0, PROBLEM_BYTE_BUDGET)
    assert "17" in detail and "5" in detail and "12" in detail   # 14 + 3 used of 2 + 3 bytes: 12 over


def test_every_changed_line_of_the_script_is_flagged_and_an_unchanged_line_is_not(monkeypatch, tmp_path):
    body = _script([b"Hi", b"Bye"])
    rules = _rules(monkeypatch, tmp_path, body, ["Hello there", "Bye!"])
    assert rules.exceeds_byte_budget(0, 0, "Hello there") is True
    assert rules.exceeds_byte_budget(0, 1, "Bye!") is True
    assert rules.exceeds_byte_budget(0, 1, "Bye") is False   # back to the source text: not changed


def test_a_script_within_its_budget_is_not_flagged(monkeypatch, tmp_path):
    body = _script([b"Hello there", b"Bye and more"])   # budget 23
    rules = _rules(monkeypatch, tmp_path, body, ["Hi", "Bye and more"])
    assert rules.exceeds_byte_budget(0, 0, "Hi") is False
    assert rules.get_problem_detail(0, 0, PROBLEM_BYTE_BUDGET) == ""


def test_a_shorter_line_of_the_same_script_clears_the_flag(monkeypatch, tmp_path):
    body = _script([b"Hi", b"Bye and more text"])   # budget 19
    rules = _rules(monkeypatch, tmp_path, body, ["Hello there", "Bye"])   # 14 + 5 = 19: within the budget
    assert rules.exceeds_byte_budget(0, 0, "Hello there") is False


def test_the_problem_detail_is_only_for_the_budget_problem(monkeypatch, tmp_path):
    body = _script([b"Hi"])
    rules = _rules(monkeypatch, tmp_path, body, ["Hello there"])
    assert rules.exceeds_byte_budget(0, 0, "Hello there") is True
    assert rules.get_problem_detail(0, 0, "SOA_OTHER") == ""


def test_an_unknown_string_or_block_has_no_budget(monkeypatch, tmp_path):
    body = _script([b"Hi"])
    rules = _rules(monkeypatch, tmp_path, body, ["Hi"])
    assert rules.exceeds_byte_budget(0, 5, "Hello there") is False
    monkeypatch.setattr(rules_module, "source_of", lambda mw, block_idx: None)
    assert rules.exceeds_byte_budget(0, 0, "Hello there") is False


class _Rules:
    def __init__(self, answer):
        self.answer = answer

    def exceeds_byte_budget(self, block_idx, string_idx, data_string):
        return self.answer


def test_analyzer_adds_the_budget_problem_from_the_rules():
    analyzer = ProblemAnalyzer(None, None, {}, SimpleNamespace(PROBLEM_BYTE_BUDGET="SOA_BYTE_BUDGET"))
    analyzer.game_rules = _Rules(True)
    analyzer._current_scan_block_idx = 0
    analyzer._current_scan_string_idx = 0
    assert analyzer._over_byte_budget("text") is True
    analyzer.game_rules = _Rules(False)
    assert analyzer._over_byte_budget("text") is False


def test_dreamcast_script_is_flagged_by_the_inherited_analyzer(monkeypatch, tmp_path):
    from plugins.skies_of_arcadia_dc.rules import GameRules as DreamcastRules

    body = _script([b"Hi", b"Bye"])   # no labels: the body reads the same in both byte orders
    path = tmp_path / "me201a.sct"
    path.write_bytes(body)
    monkeypatch.setattr(rules_module, "source_of", lambda mw, block_idx: ("FIELD/ME201A.SCT", path))
    mw = SimpleNamespace(data_processor=SimpleNamespace(get_block_texts=lambda block_idx: ["Hello there", "Bye"]))
    rules = DreamcastRules(mw)
    analyzer = ProblemAnalyzer(None, None, {}, SimpleNamespace(PROBLEM_BYTE_BUDGET="SOA_BYTE_BUDGET"))
    analyzer.game_rules = rules
    analyzer._current_scan_block_idx = 0
    analyzer._current_scan_string_idx = 0
    assert analyzer._over_byte_budget("Hello there") is True


@pytest.mark.parametrize("tag", ["{00}", "{81}", "{ff}"])
def test_byte_tokens_are_legitimate_tags(tag):
    assert tag in TagManager(None).get_legitimate_tags()


def test_build_refuses_an_over_budget_script_and_names_its_lines(tmp_path):
    source, translation = tmp_path / "src", tmp_path / "tr"
    (source / "field").mkdir(parents=True)
    (translation / "field").mkdir(parents=True)
    base = _script([b"Hi", b"Bye"])
    (source / "field" / "me201a.sct").write_bytes(base)
    over = _typed(base, ["Hello there", "Bye"])
    (translation / "field" / "me201a.sct").write_bytes(over)
    with pytest.raises(ValueError) as error:
        build.changed_files(source, translation)
    assert "field/me201a.sct" in str(error.value)
    assert str(error.value).endswith("1.")   # the changed line, 1-based: the build names it


def test_build_accepts_a_script_within_its_budget(tmp_path):
    source, translation = tmp_path / "src", tmp_path / "tr"
    (source / "field").mkdir(parents=True)
    (translation / "field").mkdir(parents=True)
    base = _script([b"Hi", b"Bye and more text"])
    (source / "field" / "me201a.sct").write_bytes(base)
    within = _typed(base, ["Hello there", "Bye"])
    assert len(within) == len(base)
    (translation / "field" / "me201a.sct").write_bytes(within)
    assert build.changed_files(source, translation) == {"field/me201a.sct": within}


def test_build_refuses_a_little_endian_script_over_budget(tmp_path):
    source, translation = tmp_path / "src", tmp_path / "tr"
    (source / "FIELD").mkdir(parents=True)
    (translation / "FIELD").mkdir(parents=True)
    base = _script([b"Hi", b"Bye"])
    (source / "FIELD" / "ME201A.SCT").write_bytes(base)
    over = _typed(base, ["Hello there", "Bye"], big=False)
    (translation / "FIELD" / "ME201A.SCT").write_bytes(over)
    with pytest.raises(ValueError):
        build.changed_files(source, translation, big=False)


def _typed(base, strings, big=True):
    """The translation file the editor saves for ``strings`` (the source body ``base`` is unchanged)."""
    out, _missing = scripts.write_strings(base, strings, big)
    return out
