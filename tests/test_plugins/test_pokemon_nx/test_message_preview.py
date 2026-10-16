"""The Switch dialogue box: FLYT v9 text panes, the fcpx font chain, the width rule and the project lookup.

The real-data tests read the owner's Sword and Shield unpack (the ``source`` folder next to the project) and skip
without it.
"""
import json

import pytest
import romhacking_root

from core.containers.sarc import Sarc
from plugins.common import flyt_message as fm
from plugins.common import gfmsg
from plugins.common.message_window import split_pages
from plugins.common import switch_message_preview as mp

ROOT = romhacking_root.under("Pokemon")
SOURCE = ROOT / "Sword and Shield" / "source" if ROOT else None
HAS_SOURCE = SOURCE is not None and (SOURCE / "bin/appli/msg/bin/msg_00.arc").is_file()


def test_font_names_keep_otf_names_in_order():
    fcpx = b"FCPX\xff\xfe\x14\x00or_font.otf\x00\x00FOT-RodinNTLGPro-DB.otf\x00junk.bin"
    assert fm.font_names(fcpx) == ["or_font.otf", "FOT-RodinNTLGPro-DB.otf"]


def test_source_folder_reads_metadata_source_path(tmp_path):
    project = tmp_path / "picoripi"
    project.mkdir()
    source = tmp_path / "source"
    (project / "project.uiproj").write_text(
        json.dumps({"metadata": {"source_path": str(source)}}), encoding="utf-8")
    assert mp.source_folder(str(project)) == str(source)


def test_source_folder_is_none_without_project_file(tmp_path):
    assert mp.source_folder(str(tmp_path)) is None


def test_sibling_layout_gate(tmp_path):
    project = tmp_path / "picoripi"
    project.mkdir()
    assert mp.sibling_layout_exists(str(project), mp.SWORD_SHIELD_BOX) is False
    layout = tmp_path / "source" / "bin" / "appli" / "msg" / "bin"
    layout.mkdir(parents=True)
    (layout / "msg_00.arc").write_bytes(b"SARC")
    assert mp.sibling_layout_exists(str(project), mp.SWORD_SHIELD_BOX) is True


@pytest.mark.skipif(not HAS_SOURCE, reason="needs the owner's Sword and Shield unpack with msg_00.arc")
def test_real_sword_dialogue_layout_has_two_message_panes_and_a_name_pane():
    arc = Sarc((SOURCE / "bin/appli/msg/bin/msg_00.arc").read_bytes())
    layout = fm.read_layout(arc.files["blyt/msg_00.bflyt"], arc.files["fcpx/system54_jpn.bfcpx"])
    assert [p.name for p in layout.panes] == ["T_00", "T_01"]
    assert layout.name is not None and layout.name.name == "T_name_00"
    assert layout.canvas == (1920.0, 1080.0)
    assert layout.window == (290.0, 862.0, 1630.0, 1052.0)
    assert layout.panes[0].rect == (410.0, 879.0, 1490.0, 957.0)
    assert layout.fonts == ["or_font.otf", "FOT-RodinNTLGPro-DB.otf"]


@pytest.mark.skipif(not HAS_SOURCE, reason="needs the owner's Sword and Shield unpack with msg_00.arc")
def test_the_game_lines_pile_up_at_the_pane_edge_at_the_layout_size():
    """The wrap cliff: at the layout's own font size, the game's hand-broken dialogue lines end at the pane edge.

    Few lines pass 1.04 of the pane; a wrap that did not fit lines to the pane would spread them far past it.
    """
    arc = Sarc((SOURCE / "bin/appli/msg/bin/msg_00.arc").read_bytes())
    layout = fm.read_layout(arc.files["blyt/msg_00.bflyt"], arc.files["fcpx/system54_jpn.bfcpx"])
    pane = layout.panes[0]
    faces = [fm.Face.from_bfotf(path.read_bytes())
             for path in mp.font_files(SOURCE / "bin/font", ["FOT-UDKakugoC80Pro-DB.otf"])]
    chain = fm.FontChain(faces)
    ratios = []
    for dat in sorted((SOURCE / "bin/message/English/script").glob("*.dat"))[:120]:
        data = dat.read_bytes()
        if not gfmsg.is_gfmsg(data):
            continue
        for units, _flag in gfmsg.read(data):
            for part in gfmsg.to_editor(units).split("\n")[:-1]:
                for page in split_pages(part):
                    for line, _colour in page:
                        if line.strip():
                            ratios.append(chain.width(line, pane.size[0]) / (pane.rect[2] - pane.rect[0]))
    assert len(ratios) > 500
    assert sum(1 for r in ratios if r > 1.04) < 0.01 * len(ratios)
    assert sum(1 for r in ratios if r > 1.0) < 0.05 * len(ratios)


ARCEUS = ROOT / "Legends Arceus" / "source" if ROOT else None
HAS_ARCEUS = ARCEUS is not None and (ARCEUS / mp.ARCEUS_BATTLE_BOX.arc).is_file()
HAS_SV = (ROOT is not None and (ROOT / "Scarlet and Violet" / "source" / mp.SCARLET_VIOLET_SUB_BOX.arc).is_file())


@pytest.mark.skipif(not HAS_ARCEUS, reason="needs the owner's Legends: Arceus unpack with the battle_menu pack")
def test_real_arceus_battle_box_has_two_960_px_panes_and_a_name_pane():
    spec = mp.ARCEUS_BATTLE_BOX
    arc = Sarc((ARCEUS / spec.arc).read_bytes())
    layout = fm.read_layout(arc.files[spec.member], arc.files[spec.fcpx])
    assert [p.name for p in layout.panes] == ["T_00", "T_01"]
    assert layout.name is not None and layout.name.name == "T_name_00"
    assert layout.panes[0].rect[2] - layout.panes[0].rect[0] == 960.0


@pytest.mark.skipif(not HAS_SV, reason="needs the owner's Scarlet / Violet unpack with the msg_sub archive")
def test_real_scarlet_violet_sub_box_has_two_840_px_panes_and_a_name_pane():
    spec = mp.SCARLET_VIOLET_SUB_BOX
    arc = Sarc((ROOT / "Scarlet and Violet" / "source" / spec.arc).read_bytes())
    layout = fm.read_layout(arc.files[spec.member], arc.files[spec.fcpx])
    assert [p.name for p in layout.panes] == ["T_00", "T_01"]
    assert layout.name is not None and layout.name.name == "T_name_00"
    assert layout.panes[0].rect[2] - layout.panes[0].rect[0] == 840.0


class _FixedWidth:
    """A chain double: every character is 10 px wide."""

    def width(self, text, px, char_space=0.0):
        return 10.0 * len(text)


def test_wrap_text_flows_words_into_the_next_line():
    lines, too_long = fm.wrap_text("aaa bbb ccc", 75.0, _FixedWidth(), 10.0)
    assert lines == ["aaa bbb", "ccc"]
    assert too_long is False


def test_a_word_wider_than_the_pane_is_reported_and_kept_whole():
    lines, too_long = fm.wrap_text("xxxxxxxxxx y", 75.0, _FixedWidth(), 10.0)
    assert lines == ["xxxxxxxxxx", "y"]
    assert too_long is True
