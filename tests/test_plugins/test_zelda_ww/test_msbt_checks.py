"""Wind Waker HD MSBT editor texts: the problem checks (plugins/zelda_ww/msbt_checks.py).

The synthetic cases name one kind each. The real-data test checks that the game's own 68 HD files raise no issue.
"""
from pathlib import Path

import pytest

from plugins.common.msbt import Msbt
from plugins.zelda_ww.msbt_checks import check_text
from plugins.zelda_ww.tags import to_editor

HD_MSG = Path("E:/Emulators/RomHacking/Zelda/Wind Waker/HD - Wii U/source/Message")


def kinds(text):
    return [issue.kind for issue in check_text(text)]


def test_a_clean_text_has_no_issue():
    assert check_text("Hello [Size:150] there [Red]red[/C] and [Wait:10] now [A] [SE:163]") == []


def test_a_tag_that_does_not_parse_is_reported():
    assert kinds("Size is [Size:abc] here") == ["unparsed"]


def test_size_outside_the_game_range_is_reported():
    issues = check_text("Big [Size:400] text")
    assert [i.kind for i in issues] == ["size"] and issues[0].text == "[Size:400]"


def test_colour_outside_the_palette_is_reported():
    assert kinds("Colour [Color:99] text") == ["colour"]


def test_an_unknown_tag_is_reported():
    assert kinds("Raw [Tag:9:9] tag") == ["unknown"]


def test_an_icon_the_game_does_not_use_is_reported():
    assert kinds("press \ue0a5 now") == ["icon"]
    assert kinds("press \ue0a0 now") == []


def test_a_closing_tag_without_an_opening_one_is_reported():
    assert kinds("end [/Tag:1:0] here") == ["closing"]
    assert kinds("[Tag:1:0]open [/Tag:1:0]") == []


@pytest.mark.skipif(not HD_MSG.is_dir(), reason="the unpacked Wind Waker HD messages are not on this machine")
def test_the_game_own_hd_messages_raise_no_issue():
    found = []
    for path in sorted(HD_MSG.glob("*.msbt")):
        for index, tokens in enumerate(Msbt(path.read_bytes()).messages):
            for issue in check_text(to_editor(tokens)):
                found.append((path.name, index, issue))
    assert found == []


def test_the_gamecube_plugin_runs_the_checks_on_msbt_text():
    from plugins.zelda_tww.rules import GameRules

    issues = GameRules().check_msbt_text("Big [Size:400] text")
    assert [issue.kind for issue in issues] == ["size"]
