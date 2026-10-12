"""Family projects: alignment, seeding, fan-out and the store file, on synthetic messages."""
from core.family_projects.align import align
from core.family_projects.store import fanout, load_store, save_store, seed


GC = {"zel_00.bmg": ["Hello", "Press A", "Goodbye"]}


def test_align_pairs_equal_texts_and_reports_the_rest():
    result = align(["a", "b", "c"], ["a", "x", "c", "d"])
    assert result.pairs == ((0, 0), (2, 2))
    assert result.base_only == (1,)
    assert result.console_only == (1, 3)


def test_shared_unit_is_translated_once_and_fans_out_to_every_console():
    sources = {"gc": GC, "hd": {"zel_00.bmg": ["Hello", "Press A", "Goodbye", "GamePad"]}}
    translations = {"gc": {"zel_00.bmg": ["Привіт", "Натисніть A", ""]}}
    store, warnings = seed("gc", sources, translations)
    assert warnings == []
    assert store["units"]["zel_00.bmg#0"]["text"] == "Привіт"
    hd_out, hd_warnings = fanout(store, sources, "hd")
    assert hd_warnings == []
    assert hd_out["zel_00.bmg"] == ["Привіт", "Натисніть A", None, None]
    gc_out, _ = fanout(store, sources, "gc")
    assert gc_out["zel_00.bmg"] == ["Привіт", "Натисніть A", None]


def test_console_only_string_stays_that_consoles_own_override():
    sources = {"gc": GC, "hd": {"zel_00.bmg": ["Hello", "GamePad"]}}
    translations = {"gc": {"zel_00.bmg": ["Привіт", "", ""]}, "hd": {"zel_00.bmg": ["", "Геймпад"]}}
    store, _ = seed("gc", sources, translations)
    assert store["overrides"]["hd"]["zel_00.bmg"]["1"]["text"] == "Геймпад"
    gc_out, _ = fanout(store, sources, "gc")
    assert gc_out["zel_00.bmg"] == ["Привіт", None, None]
    hd_out, _ = fanout(store, sources, "hd")
    assert hd_out["zel_00.bmg"] == ["Привіт", "Геймпад"]


def test_console_translation_that_differs_is_a_warned_override_for_that_console_only():
    sources = {"gc": GC, "hd": {"zel_00.bmg": ["Hello", "Press A", "Goodbye"]}}
    translations = {"gc": {"zel_00.bmg": ["Привіт", "", ""]}, "hd": {"zel_00.bmg": ["Вітаю", "", ""]}}
    store, warnings = seed("gc", sources, translations)
    assert len(warnings) == 1 and "hd zel_00.bmg#0" in warnings[0]
    assert store["units"]["zel_00.bmg#0"]["text"] == "Привіт"
    hd_out, _ = fanout(store, sources, "hd")
    assert hd_out["zel_00.bmg"][0] == "Вітаю"
    wii_out, _ = fanout(store, {**sources, "wii": GC}, "wii")
    assert wii_out["zel_00.bmg"][0] == "Привіт"


def test_untranslated_base_takes_the_console_translation_as_the_unit():
    sources = {"gc": GC, "hd": {"zel_00.bmg": ["Hello", "Press A", "Goodbye"]}}
    translations = {"gc": {}, "hd": {"zel_00.bmg": ["Вітаю", "", ""]}}
    store, warnings = seed("gc", sources, translations)
    assert warnings == []
    assert store["units"]["zel_00.bmg#0"]["text"] == "Вітаю"


def test_override_is_skipped_with_a_warning_when_its_source_text_changed():
    sources = {"gc": GC, "hd": {"zel_00.bmg": ["Hello", "GamePad"]}}
    translations = {"hd": {"zel_00.bmg": ["", "Геймпад"]}}
    store, _ = seed("gc", sources, translations)
    changed = {"gc": GC, "hd": {"zel_00.bmg": ["Hello", "Amiibo"]}}
    hd_out, warnings = fanout(store, changed, "hd")
    assert hd_out["zel_00.bmg"] == [None, None]
    assert warnings and "source text changed" in warnings[0]


def test_store_round_trip_and_version_guard(tmp_path):
    sources = {"gc": GC, "hd": {"zel_00.bmg": ["Hello"]}}
    store, _ = seed("gc", sources, {"gc": {"zel_00.bmg": ["Привіт", "", ""]}})
    path = tmp_path / "family_translations.json"
    save_store(path, store)
    assert load_store(path, "gc") == store
    assert load_store(tmp_path / "missing.json", "gc")["units"] == {}
    path.write_text('{"version": 9}', encoding="utf-8")
    try:
        load_store(path, "gc")
    except ValueError as error:
        assert "version" in str(error)
    else:
        raise AssertionError("unknown version must be refused")
