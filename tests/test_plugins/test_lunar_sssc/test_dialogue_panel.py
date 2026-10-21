"""The Lunar dialogue preview widget: draws pages from synthetic sources (no game bytes, no project folder)."""
import struct
import zlib

import romhacking_root  # noqa: F401  (path setup for the repository's packages)

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
    return {"glyphs": glyphs, "files": files, "index": dp.index_faces(files), "palette": palette}


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
