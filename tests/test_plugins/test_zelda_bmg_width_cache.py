"""Durable cache coverage for Zelda BMG auto-width calibration."""

import os
from types import SimpleNamespace

from plugins.zelda_bmg.rules import GameRules


def _rules(data=None):
    store = SimpleNamespace(data=data or [["original"]])
    mw = SimpleNamespace(
        data_store=store,
        font_map={"A": {"width": 7}},
        icon_sequences=[],
        default_tag_mappings={},
        show_multiple_spaces_as_dots=False,
        newline_display_symbol="↵",
    )
    return GameRules(mw)


def test_calibrated_widths_round_trip_without_recalculation(monkeypatch):
    source = _rules()
    source._auto_kind_widths_cache = ((id(source.mw.data_store.data), 1), {0: 300, 6: 271})
    state = source.export_runtime_session_state()

    restored = _rules()
    restored.restore_runtime_session_state(state)
    monkeypatch.setattr(restored, "_get_bmg_for_block", lambda _idx: (_ for _ in ()).throw(
        AssertionError("persisted calibration must not reopen BMG files")))

    assert restored._get_auto_kind_widths() == {0: 300, 6: 271}


def test_calibrated_widths_are_rejected_when_font_metrics_change():
    source = _rules()
    source._auto_kind_widths_cache = ((id(source.mw.data_store.data), 1), {0: 300})
    state = source.export_runtime_session_state()

    restored = _rules()
    restored.mw.font_map["A"]["width"] = 8
    restored.restore_runtime_session_state(state)

    assert not hasattr(restored, "_auto_kind_widths_cache")


def test_stale_dataset_cache_is_not_exported():
    rules = _rules()
    rules._auto_kind_widths_cache = ((id(rules.mw.data_store.data), 1), {0: 300})
    rules.mw.data_store.data = [["replacement"]]

    assert rules.export_runtime_session_state() == {}


def test_a_raw_tag_gets_its_alias_once_and_again_after_the_alias_is_removed():
    rules = _rules()
    mappings = rules.mw.default_tag_mappings

    shown = rules.replace_tags_with_aliases("a{escape:0:0000}b")
    aliases = [alias for alias, raw in mappings.items() if raw == "{escape:0:0000}"]
    assert len(aliases) == 1 and shown == f"a{aliases[0]}b"
    rules.replace_tags_with_aliases("a{escape:0:0000}b")
    assert [alias for alias, raw in mappings.items() if raw == "{escape:0:0000}"] == aliases

    del mappings[aliases[0]]
    assert rules.replace_tags_with_aliases("a{escape:0:0000}b") == f"a{aliases[0]}b"


def test_the_translation_map_is_read_again_when_the_file_changes(tmp_path, monkeypatch):
    from plugins.zelda_bmg import rules as rules_module
    rules = _rules()
    rules.mw.project_manager = SimpleNamespace(project_dir=str(tmp_path))
    (tmp_path / "translation_map.json").write_text('{"і": "i"}', encoding="utf-8")
    clock = [1000.0]
    monkeypatch.setattr(rules_module.time, "monotonic", lambda: clock[0])

    assert rules.encode_string_with_mapping("і") == "i"
    (tmp_path / "translation_map.json").write_text('{"і": "j", "ї": "k"}', encoding="utf-8")
    os.utime(tmp_path / "translation_map.json", (2_000_000_000, 2_000_000_000))   # a changed file time, whatever the clock tick
    clock[0] += 2                                            # the disk is looked at once a second at most
    assert rules.encode_string_with_mapping("і") == "j"
