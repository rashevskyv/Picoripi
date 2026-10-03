"""WP5 review queue, plugin text rules (5.2), checked against the pre-audit code for every shipped plugin:

- "The 'empty' plugin files were not empty ... width warnings, autofix and short-line merging must behave as
  before": every problem found per subline and per string, the full autofix and the autofix of each single
  problem kind are identical to the old code on a fixed corpus (and, with the dump, on real game text).
- Intended differences, asserted as the new behaviour: Minish Cap and the template plugin expose problem_ids
  (the preview's "empty odd subline" marker); short labels come from the common table; plain text checks
  pasted tags kind by kind.
"""
import json

import pytest

from . import _rq_wp5_helpers as h

GOLDEN = h.FIXTURES / "analyzers"


@pytest.fixture(scope="module")
def results(qapp):
    return {plugin: h.analyze_corpus(plugin, *h.corpus_for(plugin)) for plugin in h.PLUGINS}


def _golden(plugin):
    return json.loads((GOLDEN / f"{plugin}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("plugin", h.PLUGINS)
def test_problems_autofix_and_merging_are_as_before(results, plugin):
    new, old = results[plugin], _golden(plugin)

    assert new["definitions"] == old["definitions"]
    assert [s["text"] for s in new["strings"]] == [s["text"] for s in old["strings"]], "corpus drifted"
    for new_s, old_s in zip(new["strings"], old["strings"]):
        assert new_s["whole"] == old_s["whole"], new_s["text"]
        assert new_s["sublines"] == old_s["sublines"], new_s["text"]
        assert new_s["autofix"] == old_s["autofix"], new_s["text"]
        assert new_s["autofix_each"] == old_s["autofix_each"], new_s["text"]
    for new_t, old_t in zip(new["tag_checks"], old["tag_checks"]):
        assert new_t.get("whole") == old_t.get("whole")
        assert new_t.get("mismatch") == old_t.get("mismatch")
        if plugin != "plain_text":
            assert new_t["paste"] == old_t["paste"]


def test_the_corpus_exercises_the_rules(results):
    """Guard against a corpus that finds nothing: width, short-line, spacing and tag problems all occur,
    and autofix changes something, for every plugin."""
    for plugin, result in results.items():
        found = {pid for s in result["strings"] for line in s["whole"] for pid in line}
        suffixes = {pid.split("_", 1)[1] for pid in found}
        assert {"WIDTH_EXCEEDED", "SHORT_LINE", "BAD_SPACING"} <= suffixes, (plugin, suffixes)
        assert any(s["autofix"][1] for s in result["strings"]), plugin


@pytest.mark.parametrize("plugin", h.PLUGINS)
def test_short_labels_come_from_the_common_table(results, plugin):
    """Changed on purpose: a label the plugin did not define comes from SHORT_PROBLEM_NAMES, not the long name."""
    from plugins.common.config_factory import SHORT_PROBLEM_NAMES, problem_suffix

    rules = h.new_rules(plugin)
    old = _golden(plugin)["short_names"]
    for pid, label in results[plugin]["short_names"].items():
        if label == old[pid]:
            continue
        suffix = problem_suffix(pid, rules.problem_prefix)
        assert label == (rules.short_problem_names.get(suffix) or SHORT_PROBLEM_NAMES[suffix]), pid
        assert old[pid] == rules.get_problem_definitions()[pid]["name"], pid   # it used to be the long name


@pytest.mark.parametrize("plugin", h.PLUGINS)
def test_empty_odd_subline_marker(results, plugin):
    """Changed on purpose for Minish Cap and the template plugin; the rest as before."""
    new, old = results[plugin]["empty_odd_marker"], _golden(plugin)["empty_odd_marker"]
    if plugin in ("zelda_mc", "default_plugin"):
        assert old is None
        assert new == f"{h.new_rules(plugin).problem_prefix}_EMPTY_ODD_SUBLINE_DISPLAY"
        assert new in h.new_rules(plugin).get_problem_definitions()
    else:
        assert new == old


def test_plain_text_checks_pasted_tags_kind_by_kind(results):
    pastes = [t["paste"] for t in results["plain_text"]["tag_checks"]]
    pairs = [(t["original"], t["translation"]) for t in results["plain_text"]["tag_checks"]]

    old = [t["paste"] for t in _golden("plain_text")["tag_checks"]]

    assert [status for _segment, status, _message in pastes] == h.PLAIN_TEXT_PASTE_STATUS, pairs
    # [Color:Red] where the original had [Color:Blue] is fine; every warning names the kind that differs.
    assert pastes[3][1] == "OK" and pairs[3] == ("[Color:Blue]x[/C] y", "[Color:Red]x[/C] y")
    for (_segment, status, message) in pastes:
        if status == "WARNING":
            assert "pasted" in message and "in the original" in message
    # The pasted text itself is cleaned as before; the verdict changed only where curly tags differ.
    assert [p[0] for p in pastes] == [p[0] for p in old]
    changed = tuple(i for i, (new, before) in enumerate(zip(pastes, old)) if new[1] != before[1])
    assert changed == h.PLAIN_TEXT_CHANGED_PAIRS


@pytest.mark.skipif(not (h.TP_DUMP_MSG / h.REAL_ARC).exists(), reason="retail Twilight Princess dump not on this machine")
def test_real_twilight_princess_text_is_analyzed_and_fixed_as_before(qapp):
    golden = json.loads((GOLDEN / "tp_dump_digest.json").read_text(encoding="utf-8"))
    result = h.analyze_corpus("zelda_bmg", h.tp_dump_texts(), [])
    assert h.corpus_digest(result) == golden["digest"]
