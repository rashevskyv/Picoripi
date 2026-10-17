"""Legends: Z-A message box: the view names its archive (synthetic), the outer layout's offset, and the owner's archive
when the wizard has written it (skipped otherwise)."""
import re

import romhacking_root
import pytest

from core.containers import trinity_pack
from core.containers.game_freak import path_hash as fnv
from core.containers.sarc import Sarc
from plugins.common import flyt_message as fm
from plugins.manual_3ds import console_render as cr
from plugins.pokemon_trinity import unpack

ZA_SOURCE = romhacking_root.under("Pokemon") / "Legends Z-A" / "source"
ZA_BOX_ARC = ZA_SOURCE / "ui" / "data" / "msg" / "msg_body_00.arc"


def test_a_view_names_its_component_archive_in_the_same_folder():
    view = "ui/data/msg/view_msg_body_00.truiv"
    arc = "ui/data/msg/msg_body_00.arc"
    found = {fnv(view): view}
    files = [(fnv(view), b"\x0c\x00\x00\x00"), (fnv(arc), b"SARC....")]
    trinity_pack.name_others(found, files)
    assert found[fnv(arc)] == arc


def test_an_unnamed_archive_takes_the_name_of_its_root_layout_and_its_view_follows():
    view = "ui/data/msg/view_msg_body_01.truiv"
    arc = b"SARC" + b"\0" * 24 + b"blyt/msg_body_01.bflyt\0blyt/msg_01.bflyt\0"
    found = {fnv(view): view}
    trinity_pack.name_others(found, [(fnv(view), b"\x0c\x00"), (fnv("ui/data/msg/msg_body_01.arc"), arc)])
    assert found[fnv("ui/data/msg/msg_body_01.arc")] == "ui/data/msg/msg_body_01.arc"
    # the reverse rule: a named archive names its view
    found = {fnv("ui/data/msg/msg_body_00.arc"): "ui/data/msg/msg_body_00.arc"}
    files = [(fnv("ui/data/msg/view_msg_body_00.truiv"), b"\x0c\x00"), (fnv("ui/data/msg/msg_body_00.arc"), b"SARC")]
    trinity_pack.name_others(found, files)
    assert found[fnv("ui/data/msg/view_msg_body_00.truiv")] == "ui/data/msg/view_msg_body_00.truiv"


def test_a_view_without_its_archive_in_the_pack_names_nothing_extra():
    view = "ui/data/msg/view_msg_btl_00.truiv"
    found = {fnv(view): view}
    trinity_pack.name_others(found, [(fnv(view), b"\x0c\x00")])
    assert list(found.values()) == [view]


def test_the_message_pack_is_unpacked_by_the_z_a_pattern():
    assert re.search(unpack.ZA_PACKS, "arc/uidatamsgview_msg_body_01.truiv.trpak")
    assert not re.search(unpack.ZA_PACKS, "arc/uidatamsgview_msg_body_01.truiv.trpak.bak")


def test_the_outer_layout_offset_moves_both_axes_in_the_canvas_frame():
    pane = cr.Pane("txt1", "T_00", True, 0, 255, 0.0, 6.0, 840.0, 64.0, abs_x=0.0, abs_y=6.0)
    plain = fm._rect(pane, (1920.0, 1080.0))
    moved = fm._rect(pane, (1920.0, 1080.0), (0.0, -370.0))
    assert plain == (540.0, 502.0, 1380.0, 566.0)
    assert moved == (540.0, 872.0, 1380.0, 936.0)


@pytest.mark.skipif(not ZA_BOX_ARC.is_file(), reason="needs the Z-A message box archive from the wizard unpack")
def test_real_z_a_box_has_two_message_panes_named_by_the_spec():
    arc = Sarc(ZA_BOX_ARC.read_bytes())
    layout = fm.read_layout(arc.files["blyt/msg_00.bflyt"], arc.files["fcpx/system42_jpn.bfcpx"],
                            (0.0, -370.0), ("T_00", "T_01"))
    assert [p.name for p in layout.panes] == ["T_00", "T_01"]
    assert layout.name is not None and layout.name.name == "T_name_00"
    assert layout.window is not None and layout.window[1] > 0


def test_the_z_a_box_is_found_only_in_a_z_a_unpack(tmp_path):
    from plugins.common import switch_message_preview as mp

    project = tmp_path / "Legends project"
    (project / "unpacked" / "source" / "ui" / "data" / "msg").mkdir(parents=True)
    assert mp.sibling_layout_exists(str(project), mp.ZA_FIELD_BOX) is False
    (project / "unpacked" / "source" / "ui" / "data" / "msg" / "msg_body_00.arc").write_bytes(b"SARC")
    assert mp.sibling_layout_exists(str(project), mp.ZA_FIELD_BOX) is True
    assert mp.sibling_layout_exists(str(project), mp.SCARLET_VIOLET_SUB_BOX) is False
