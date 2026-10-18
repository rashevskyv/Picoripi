"""Series glossary terms that fill a whole string (D45, item 1): the table, the plan, and the apply with its checks."""
from types import SimpleNamespace

from core.data_state_processor import DataStateProcessor
from core.glossary.term_fill import (
    CONFLICT, FILL, GLOSSARY_CONFLICT, SAME, TermFill, build_term_table, plan_fills, term_key, writable,
)
from core.translation.series_memory import source_hash
from handlers import glossary_term_fill
from plugins.common.gfmsg import SERIES_TAG_MAP as GFMSG
from test_core.test_series_memory import window  # noqa: F401  (window fixture)


def test_a_term_and_a_string_with_the_same_text_share_a_key_whatever_the_case_and_spacing():
    assert term_key("Pikachu") == term_key("  pikachu ") == term_key("[color 1]Pikachu[color 0]")


def test_with_a_tag_map_a_control_tag_is_part_of_the_key(tmp_path):
    assert term_key("Pikachu") != term_key("Pikachu {VAR 0100 0000}", GFMSG)
    assert term_key("Hi {VAR 0100 0000}", GFMSG) == term_key("hi  {VAR 0100 0000}", GFMSG)


def test_one_translation_is_a_term_and_two_different_ones_are_a_conflict():
    table = build_term_table([("Pikachu", "Пікачу"), ("pikachu", "Пікачу"), ("Eevee", "Івуй"), ("Eevee", "Івві")])
    assert table.by_key[term_key("Pikachu")] == ("Pikachu", "Пікачу")
    assert term_key("Eevee") in table.conflicts and term_key("Eevee") not in table.by_key


def test_an_untranslated_entry_is_not_a_term():
    assert build_term_table([("Mew", "  "), ("", "Зайве")]).by_key == {}


def test_the_plan_fills_untranslated_strings_and_names_every_other_status():
    table = build_term_table([("Pikachu", "Пікачу"), ("Eevee", "Івуй"), ("Eevee", "Івві")])
    rows = [
        (0, 0, "Pikachu", "", False),          # untranslated: fill
        (0, 1, "PIKACHU", "Пікачу", True),     # already the term: same
        (0, 2, "Pikachu", "Піка", True),       # a different translation: kept
        (0, 3, "Eevee", "", False),            # two glossary entries: nothing is written
        (0, 4, "Hello there", "", False),      # not a term: not planned at all
    ]
    fills = plan_fills(table, rows)
    assert [(f.string_idx, f.status) for f in fills] == [(0, FILL), (1, SAME), (2, CONFLICT), (3, GLOSSARY_CONFLICT)]
    assert [f.string_idx for f in writable(fills)] == [0]
    assert fills[3].translation == "Івуй | Івві"


def test_a_series_term_with_a_control_tag_fills_only_the_same_tags(tmp_path):
    table = build_term_table([("Pikachu {PAGE}", "Пікачу {PAGE}")], GFMSG)
    fills = plan_fills(table, [(0, 0, "Pikachu {PAGE}", "", False), (0, 1, "Pikachu", "", False)], GFMSG)
    assert [(f.string_idx, f.status) for f in fills] == [(0, FILL)]


def test_the_open_project_plan_reads_the_series_entries_and_the_source_index(window, monkeypatch):  # noqa: F811
    manager = window.saved_translations_manager
    manager.source_positions = {source_hash("Yes"): [(0, 3), (7, 10)]}
    series = SimpleNamespace(get_entries=lambda: [SimpleNamespace(original="Yes", translation="Так")])
    monkeypatch.setattr(glossary_term_fill, "series_managers_of", lambda mw: [series])
    window.data_processor = SimpleNamespace(
        get_current_string_text=lambda b, s: ("Так" if (b, s) == (7, 10) else "", ""),
        is_string_translated=lambda b, s: (b, s) == (7, 10),
    )

    _, fills = glossary_term_fill.plan_open_project(window)

    assert sorted((f.block_idx, f.string_idx, f.status) for f in fills) == [(0, 3, FILL), (7, 10, SAME)]


def test_apply_writes_the_untranslated_fills_that_pass_and_refuses_the_others(window):  # noqa: F811
    window.data_processor = DataStateProcessor(window)
    fills = [
        TermFill(0, 3, "Yes", "Yes", "Так", "", FILL),
        TermFill(7, 10, "Yes", "Yes", "Так [ko]", "", FILL),  # a tag the source does not have: refused
    ]

    written, refused = glossary_term_fill.apply_fills(window, fills)

    assert [(f.block_idx, f.string_idx) for f in written] == [(0, 3)]
    assert [(f.block_idx, f.string_idx, reason) for f, reason in refused] == [(7, 10, "tags")]
    assert window.data_processor.get_current_string_text(0, 3)[0] == "Так"
    assert window.data_processor.get_current_string_text(7, 10)[0] == "Yes"
