"""Durable cache coverage for Zelda BMG auto-width calibration."""

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
