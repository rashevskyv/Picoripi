"""Family engine: alignment by match key, links to parents, seeding, fan-out and the store file (synthetic units)."""
import pytest

from core.family_projects.align import align, key_hash
from core.family_projects.model import FamilyMember, FamilyPlan
from core.family_projects.store import Family, fanout, links, load_store, normalize, save_store, seed, trees


def _gc(texts, prefix="zel_00.bmg#"):
    return [(f"{prefix}{i}", t) for i, t in enumerate(texts)]


def _family(gc, hd=(), hd_us=(), wii=()):
    """wii and hd link to gc; hd_us links to hd first, then to gc."""
    units, parents = {"gc": list(gc)}, {"gc": ()}
    if wii:
        units["wii"], parents["wii"] = list(wii), ("gc",)
    if hd:
        units["hd"], parents["hd"] = list(hd), ("gc",)
    if hd_us:
        units["hd_us"], parents["hd_us"] = list(hd_us), (("hd", "gc") if hd else ("gc",))
    return Family(base="gc", parents=parents, units=units)


GC = _gc(["Hello", "Press A", "Goodbye"])


def test_align_pairs_equal_keys_and_reports_the_rest():
    result = align(["a", "b", "c"], ["a", "x", "c", "d"])
    assert result.pairs == ((0, 0), (2, 2))
    assert result.parent_only == (1,)
    assert result.console_only == (1, 3)


def test_shared_unit_is_translated_once_and_fans_out_to_every_member():
    family = _family(GC, hd=_gc(["Hello", "Press A", "Goodbye", "GamePad"], prefix="hd#"))
    store, warnings = seed(family, {"gc": {"zel_00.bmg#0": "Привіт", "zel_00.bmg#1": "Натисніть A"}})
    assert warnings == []
    assert list(store["texts"]) == ["gc"]  # the shared units live in the base only
    assert fanout(family, store, "hd")[0] == {"hd#0": "Привіт", "hd#1": "Натисніть A", "hd#2": None, "hd#3": None}
    assert fanout(family, store, "gc")[0] == {"zel_00.bmg#0": "Привіт", "zel_00.bmg#1": "Натисніть A",
                                              "zel_00.bmg#2": None}


def test_member_only_string_is_kept_in_that_member_only():
    family = _family(GC, hd=_gc(["Hello", "GamePad"], prefix="hd#"))
    store, warnings = seed(family, {"hd": {"hd#1": "Геймпад"}})
    assert warnings == []
    assert set(store["texts"]["hd"]) == {"hd#1"}
    assert fanout(family, store, "gc")[0] == {"zel_00.bmg#0": None, "zel_00.bmg#1": None, "zel_00.bmg#2": None}


def test_linked_translation_that_differs_is_a_warned_override_for_that_member_only():
    family = _family(GC, hd=_gc(["Hello", "Press A", "Goodbye"], prefix="hd#"))
    store, warnings = seed(family, {"gc": {"zel_00.bmg#0": "Привіт"}, "hd": {"hd#0": "Здрасте"}})
    assert len(warnings) == 1 and "hd hd#0" in warnings[0]
    assert fanout(family, store, "hd")[0]["hd#0"] == "Здрасте"
    assert fanout(family, store, "gc")[0]["zel_00.bmg#0"] == "Привіт"


def test_untranslated_parent_takes_the_member_translation_as_the_shared_unit():
    family = _family(GC, wii=_gc(["Hello"], prefix="wii#"))
    store, warnings = seed(family, {"wii": {"wii#0": "Привіт"}})
    assert warnings == []
    assert fanout(family, store, "gc")[0]["zel_00.bmg#0"] == "Привіт"
    assert fanout(family, store, "wii")[0]["wii#0"] == "Привіт"


def test_chained_member_reads_the_translation_of_the_member_it_links_to():
    family = _family(GC, hd=_gc(["Press A", "Hi"], prefix="hd#"), hd_us=_gc(["Press A", "Hi"], prefix="us#"))
    store, _ = seed(family, {"hd": {"hd#0": "Натисніть A"}})
    assert fanout(family, store, "hd_us")[0] == {"us#0": "Натисніть A", "us#1": None}
    assert links(family)["hd_us"]["us#0"] == ("hd", "hd#0")


def test_stored_text_is_skipped_with_a_warning_when_its_source_text_changed():
    store, _ = seed(_family(GC), {"gc": {"zel_00.bmg#0": "Привіт"}})
    changed = _family(_gc(["Hello there", "Press A", "Goodbye"]))
    out, warnings = fanout(changed, store, "gc")
    assert out["zel_00.bmg#0"] is None
    assert len(warnings) == 1


def test_family_rejects_a_child_listed_before_its_parent_and_unknown_parents():
    with pytest.raises(ValueError):
        Family(base="gc", parents={"gc": (), "hd": ("gc",)}, units={"hd": GC, "gc": GC})
    with pytest.raises(ValueError):
        Family(base="gc", parents={"gc": (), "hd": ("nowhere",)}, units={"gc": GC, "hd": GC})


def test_plan_needs_exactly_one_base():
    assert FamilyPlan(members=(FamilyMember("gc", "GameCube", "x", base=True),), read=lambda key: []).base == "gc"
    with pytest.raises(ValueError):
        FamilyPlan(members=(FamilyMember("a", "A", "x", base=True), FamilyMember("b", "B", "y", base=True)),
                   read=lambda key: []).base


def test_store_round_trip_and_version_guard(tmp_path):
    store, _ = seed(_family(GC), {"gc": {"zel_00.bmg#0": "Привіт"}})
    path = tmp_path / "family_translations.json"
    save_store(path, store)
    assert load_store(path, "gc") == store
    path.write_text('{"version": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_store(path, "gc")


def test_trees_group_linked_units_under_their_root_and_keep_unlinked_units_alone():
    family = _family(GC, hd=_gc(["Hello", "GamePad"], prefix="hd#"), wii=_gc(["Press A"], prefix="wii#"))
    found = {root: nodes for root, nodes in trees(family)}
    assert found[("gc", "zel_00.bmg#0")] == (("gc", "zel_00.bmg#0"), ("hd", "hd#0"))
    assert found[("gc", "zel_00.bmg#1")] == (("gc", "zel_00.bmg#1"), ("wii", "wii#0"))
    assert found[("hd", "hd#1")] == (("hd", "hd#1"),)
    assert found[("gc", "zel_00.bmg#2")] == (("gc", "zel_00.bmg#2"),)


def test_normalize_moves_a_child_text_to_the_root_and_reports_a_differing_child():
    family = _family(GC, hd=_gc(["Hello", "GamePad"], prefix="hd#"))
    store = {"version": 2, "base": "gc", "texts": {"hd": {
        "hd#0": {"source": key_hash("Hello"), "text": "Привіт"},
        "hd#1": {"source": key_hash("GamePad"), "text": "Геймпад"}}}}
    out, overrides = normalize(family, store)
    assert overrides == []
    assert out["texts"]["gc"]["zel_00.bmg#0"]["text"] == "Привіт"
    assert "hd" not in out["texts"] or "hd#0" not in out["texts"]["hd"]
    store["texts"]["gc"] = {"zel_00.bmg#0": {"source": key_hash("Hello"), "text": "Інший"}}
    _out, overrides = normalize(family, store)
    assert overrides == [("hd", "hd#0")]
