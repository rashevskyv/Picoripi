"""Wind Waker family tags: GameCube escapes and HD tags convert both ways, and the match key drops colour.

Synthetic texts only; the real files are checked in test_family_real.py.
"""
from plugins.common.msbt import Tag
from plugins.zelda_ww import family_tags as ft
from plugins.zelda_ww.tags import render_tag

WAIT_10 = "{escape:0:0007000a}"


def test_gc_tag_becomes_the_hd_tag_and_back():
    tags = ft.TagMap({"E0:0007000a": "T1:6:000a"})
    hd, missing = ft.gc_to_hd(f"Wait{WAIT_10} here", tags)
    assert hd == "Wait[Wait:10] here"
    assert missing == []
    back, missing = ft.hd_to_gc(hd, tags)
    assert back == f"Wait{WAIT_10} here"
    assert missing == []


def test_colour_escapes_follow_the_rule_and_round_trip():
    tags = ft.TagMap({})
    text = "{escape:255:000001}Red{escape:255:000000} end"
    hd, missing = ft.gc_to_hd(text, tags)
    assert hd == "[Red]Red[/C] end"
    assert missing == []
    assert ft.hd_to_gc(hd, tags) == (text, [])


def test_scale_escape_carries_its_value():
    tags = ft.TagMap({})
    hd, _ = ft.gc_to_hd("{escape:255:00010096}big", tags)
    assert hd == "[Size:150]big"
    assert ft.hd_to_gc(hd, tags) == ("{escape:255:00010096}big", [])


def test_white_in_hd_reads_as_gc_colour_zero():
    back, _ = ft.hd_to_gc("x[White]y", ft.TagMap({}))
    assert back == "x{escape:255:000000}y"


def test_unmapped_gc_tag_stays_and_is_reported():
    hd, missing = ft.gc_to_hd("a{escape:0:0044}b", ft.TagMap({}))
    assert hd == "a{escape:0:0044}b"
    assert missing == ["{escape:0:0044}"]


def test_quotes_fold_so_the_editor_curly_apostrophe_matches_the_game():
    tags = ft.TagMap({"E0:0007000a": "T1:6:000a"})
    gc = f"I’ll wait{WAIT_10}"
    hd = "I'll wait[Wait:10]"
    assert ft.match_key(gc, "gc", tags) == ft.match_key(hd, "hd", tags) == "I'll wait[Wait:10]"


def test_match_key_leaves_colour_out():
    tags = ft.TagMap({})
    gc = "a{escape:255:000001}red{escape:255:000000} b"
    hd = "a[Red]red[/C][White] b"
    assert ft.match_key(gc, "gc", tags) == ft.match_key(hd, "hd", tags) == "ared b"


def test_derive_finds_the_shared_tag_and_ignores_noise():
    pairs = [("Start{escape:0:0001}go{escape:0:0002}", "Start[InstanceDispStart]go[InstanceDispEnd]")] * 5
    pairs.append(("plain", "plain"))
    pairs.append(("other text", "other text but different"))  # not compared: text differs
    result = ft.derive(pairs)
    assert result["gc_to_hd"] == {"E0:0001": "T1:0:", "E0:0002": "T1:1:"}
    assert result["compared"] == 6
    assert ft.derive(pairs) == result          # deterministic


def test_derive_gives_each_hd_tag_to_one_gc_tag():
    pairs = [("x{escape:0:0001}", "x[InstanceDispStart]")] * 4
    pairs += [("x{escape:0:0009}", "x[InstanceDispStart]")] * 4   # the HD tag is taken by the first, stronger pair
    result = ft.derive(pairs)
    assert len(set(result["gc_to_hd"].values())) == len(result["gc_to_hd"])


def test_render_of_a_wait_tag_matches_the_editor_form():
    assert render_tag(Tag(1, 6, bytes.fromhex("000a"))) == "[Wait:10]"


def test_gamecube_plugin_highlights_hd_tags_and_icons():
    import re

    from plugins.zelda_tww.rules import GameRules

    patterns = [re.compile(pattern) for pattern, _format in GameRules().get_syntax_highlighting_rules()]
    assert any(p.search("say [Size:150] now") for p in patterns)
    assert any(p.search("press \ue0a0 here") for p in patterns)
