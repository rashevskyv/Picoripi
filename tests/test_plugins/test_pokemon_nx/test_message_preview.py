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
from plugins.pokemon_nx import message_preview as mp

ROOT = romhacking_root.under("Pokemon")
SOURCE = ROOT / "Sword and Shield" / "source" if ROOT else None
HAS_SOURCE = SOURCE is not None and (SOURCE / "bin/appli/msg/bin/msg_00.arc").is_file()
PANE_WIDTH = 1080.0


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
    assert mp.sibling_layout_exists(str(project)) is False
    layout = tmp_path / "source" / "bin" / "appli" / "msg" / "bin"
    layout.mkdir(parents=True)
    (layout / "msg_00.arc").write_bytes(b"SARC")
    assert mp.sibling_layout_exists(str(project)) is True


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
def test_hand_broken_game_lines_fit_the_pane_at_the_measured_em():
    """The width rule behind MESSAGE_EM: the game's own hard-broken dialogue lines fit the 1080 px pane."""
    faces = [fm.Face.from_bfotf(path.read_bytes())
             for path in mp.font_files(SOURCE / "bin/font", mp.MESSAGE_FONTS)]
    chain = fm.FontChain(faces)
    widest = 0.0
    seen = 0
    for dat in sorted((SOURCE / "bin/message/English/script").glob("*.dat"))[:120]:
        data = dat.read_bytes()
        if not gfmsg.is_gfmsg(data):
            continue
        for units, _flag in gfmsg.read(data):
            for part in gfmsg.to_editor(units).split("\n")[:-1]:
                for page in split_pages(part):
                    for line, _colour in page:
                        if line.strip():
                            seen += 1
                            widest = max(widest, chain.width(line, mp.MESSAGE_EM))
    assert seen > 500
    assert widest <= PANE_WIDTH
