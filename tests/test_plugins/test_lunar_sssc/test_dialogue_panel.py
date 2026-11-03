"""The Lunar dialogue preview widget: draws pages from synthetic sources (no game bytes, no project folder)."""
import struct
import zlib

import romhacking_root  # noqa: F401  (path setup for the repository's packages)

from PyQt6.QtWidgets import QLabel

from plugins.lunar_sssc import dialogue_preview as dp
from plugins.lunar_sssc.dialogue_panel import LunarDialoguePreview


class _Manager:
    project_dir = None


class _Window:
    project_manager = _Manager()


def _synthetic_sources():
    member = bytearray(32)
    member[0:4] = b"FACE"
    member[0x10:0x15] = bytes([0x6A, 0x6B, 0x6C, 0x6D, 0x6E])
    packer = zlib.compressobj(9, zlib.DEFLATED, -15)
    frames = b"".join(bytes([1 + n]) * dp.FRAME_BYTES for n in range(5))
    member = bytes(member) + packer.compress(frames) + packer.flush()
    files = {"FACE_022.TIZ": member}
    values = [0] * 256
    values[1] = 0x7C00
    palette = dp.palette_from_file(struct.pack("<256H", *values))
    offset = int(dp.FONT["params"]["offset"], 0)
    count = int(dp.FONT["params"]["count"])
    slus = bytearray(offset + count * 32)
    index_of_a = dp.FONT["params"]["chars"].index("A")
    struct.pack_into(">16H", slus, offset + index_of_a * 32, *([0xFFFF] * 16))
    glyphs = dp.decode_glyphs(bytes(slus))
    return {"glyphs": glyphs, "files": files, "index": dp.index_faces(files), "palette": palette,
            "colours": {}}


def test_widget_draws_the_page_and_pages_through_them(qtbot):
    widget = LunarDialoguePreview(_Window())
    qtbot.addWidget(widget)
    widget._sources = _synthetic_sources()
    widget.update_preview_text("{FA:6E}AAA{page}BBB")
    assert "Page 1 of 2" in widget._page_label.text()
    assert widget._next.isEnabled()
    widget._turn(1)
    assert "Page 2 of 2" in widget._page_label.text()
    assert not widget._next.isEnabled()
    widget.shutdown()


def test_widget_names_the_speaker_and_reports_layout_problems(qtbot):
    widget = LunarDialoguePreview(_Window())
    qtbot.addWidget(widget)
    widget._sources = _synthetic_sources()
    widget.update_preview_text("{FA:6E}a\nb\nc\nd")
    assert widget._speaker.text().endswith("Nall")
    assert "4 lines" in widget._status.text()
    widget.shutdown()


def test_picture_scales_both_ways_and_keeps_the_box_shape(qtbot):
    widget = LunarDialoguePreview(_Window())
    qtbot.addWidget(widget)
    widget._sources = _synthetic_sources()
    widget.update_preview_text("{FA:6E}AAA")
    widget.show()
    qtbot.waitExposed(widget)
    picture = widget._picture
    shape = dp.PICTURE_W / dp.PICTURE_H
    widget.resize(900, 600)
    qtbot.waitUntil(lambda: picture.pixmap() is not None and picture.pixmap().width() > dp.PICTURE_W)
    big = picture.pixmap()
    assert big.width() <= picture.width() and big.height() <= picture.height()
    assert abs(big.width() / big.height() - shape) < 0.05
    widget.resize(200, 200)
    qtbot.waitUntil(lambda: picture.pixmap().width() < big.width())
    small = picture.pixmap()
    assert small.width() <= picture.width() and small.height() <= picture.height()
    assert abs(small.width() / small.height() - shape) < 0.05
    widget.shutdown()


def test_widget_built_before_the_project_loads_its_picture_inside_a_layout(qtbot, monkeypatch):
    """A widget built at startup, before the project folder is known, draws once the host refreshes it."""
    from types import SimpleNamespace

    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    from plugins.lunar_sssc import dialogue_panel as dpanel

    monkeypatch.setattr(dpanel, "load_sources", lambda project_dir: _synthetic_sources())
    manager = SimpleNamespace(project_dir=None)
    window = SimpleNamespace(project_manager=manager)
    host = QWidget()
    qtbot.addWidget(host)
    layout = QVBoxLayout(host)
    widget = LunarDialoguePreview(window)
    layout.addWidget(widget, 1)
    host.resize(640, 480)
    host.show()
    qtbot.waitExposed(host)
    manager.project_dir = "synthetic project folder"
    widget.refresh()
    widget.update_preview_text("{FA:6E}AAA")
    picture = widget._picture
    qtbot.waitUntil(lambda: picture.pixmap() is not None and not picture.pixmap().isNull())
    assert picture.width() > 0 and picture.height() > 0
    image = picture.pixmap().toImage()
    assert image.width() > 0 and image.height() > 0
    assert image.pixelColor(image.width() // 2, image.height() // 2).alpha() > 0   # inside the window box
    widget.shutdown()


def test_speaker_is_one_label_and_shows_the_code_when_no_name_is_known(qtbot):
    widget = LunarDialoguePreview(_Window())
    qtbot.addWidget(widget)
    widget._sources = _synthetic_sources()
    widget.update_preview_text("{FA:03}AAA")          # 03 has no name in speaker_names.json
    assert widget._speaker.text() == "Speaker code 03"
    assert widget._status.isHidden()                   # no layout problem: no status line takes room
    widget.update_preview_text("{FA:6E}AAA")
    assert widget._speaker.text() == "Nall"
    widget.shutdown()


def test_layout_is_strip_picture_bar_like_the_bfn_preview_and_the_name_is_drawn_once(qtbot):
    widget = LunarDialoguePreview(_Window())
    qtbot.addWidget(widget)
    widget._sources = _synthetic_sources()
    widget.update_preview_text("{FA:6E}AAA{page}BBB")
    order = [widget.layout().itemAt(i).widget() for i in range(widget.layout().count())]
    assert order[:3] == [widget._strip, widget._picture, widget._bar]
    assert widget._speaker.parentWidget() is widget._strip
    assert widget._speaker.text() == "Nall"
    labels = [label.text() for label in widget.findChildren(QLabel)]
    assert labels.count("Nall") == 1                    # the name is drawn once, in the strip
    assert widget._prev.parentWidget() is widget._bar and widget._next.parentWidget() is widget._bar
    widget.shutdown()
