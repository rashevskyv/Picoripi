"""Skies of Arcadia Legends budget (plugins/skies_of_arcadia): a fixed-size script's text over its source segment is
flagged; other scripts have no budget; the byte tokens are legitimate tags. Synthetic script only."""
import struct
from types import SimpleNamespace

import pytest

from plugins.skies_of_arcadia import rules as rules_module
from plugins.skies_of_arcadia.problem_analyzer import ProblemAnalyzer
from plugins.skies_of_arcadia.rules import GameRules
from plugins.skies_of_arcadia.tag_manager import TagManager


def _script(text_bytes):
    """One page with no labels: header, then the page head, the text and the page end."""
    header = bytes(8) + struct.pack(">I", 0) + bytes(4)
    return header + b"\\h(" + text_bytes + b"\\c"


def _fake_source(monkeypatch, tmp_path, rel, text_bytes):
    path = tmp_path / "me.sct"
    path.write_bytes(_script(text_bytes))
    monkeypatch.setattr(rules_module, "source_of", lambda mw, block_idx: (rel, path))
    return GameRules()


def test_no_per_line_budget_under_the_script_level_model(monkeypatch, tmp_path):
    rules = _fake_source(monkeypatch, tmp_path, "field/me201a.sct", b"Hello")
    assert rules.exceeds_byte_budget(0, 0, "Hello world") is False
    assert rules.exceeds_byte_budget(0, 0, "Hi") is False


def test_every_script_is_on_the_script_level_budget(monkeypatch, tmp_path):
    rules = _fake_source(monkeypatch, tmp_path, "field/me202a.sct", b"Hello")
    assert rules.exceeds_byte_budget(0, 0, "a much longer text than the source") is False


def test_unknown_string_index_has_no_budget(monkeypatch, tmp_path):
    rules = _fake_source(monkeypatch, tmp_path, "field/me201a.sct", b"Hello")
    assert rules.exceeds_byte_budget(0, 5, "Hello world") is False
    assert rules.exceeds_byte_budget(0, "x", "Hello world") is False


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


@pytest.mark.parametrize("tag", ["{00}", "{81}", "{ff}"])
def test_byte_tokens_are_legitimate_tags(tag):
    assert tag in TagManager(None).get_legitimate_tags()
