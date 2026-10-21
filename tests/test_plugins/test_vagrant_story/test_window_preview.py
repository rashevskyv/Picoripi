"""Vagrant Story message windows: geometry, pages and centring (windows.py), the preview widget, and the
staff-roll reserved-byte rule."""
from types import SimpleNamespace

from plugins.vagrant_story import codec, windows
from plugins.vagrant_story.config import PROBLEM_CREDITS
from plugins.vagrant_story.preview_panel import MessageWindowPreview
from plugins.vagrant_story.rules import _FitRule


def test_balloon_and_information_box_sizes_follow_the_decompilation():
    balloon = windows.balloon(13, 3)
    assert (balloon["width"], balloon["height"], balloon["text_x"], balloon["text_y"]) == (166, 43, 5, 3)
    assert balloon["step"] == 13 and balloon["italic"] and balloon["text_width"] == 156
    info = windows.info_box()
    assert (info["width"], info["text_x"], info["lines"]) == (298, 16, 4)


def test_pages_split_at_new_page_and_new_line_codes():
    lines = windows.split_pages(codec.encode("one\ntwo{page}three"), italic=True)
    assert [len(page) for page in lines] == [2, 1]
    assert [code for code, _ in lines[1][0].tokens] == list(codec.encode("three"))


def test_a_centred_line_starts_in_the_middle_of_the_box():
    widths = [6] * 378
    line = windows.Line(tokens=[(0x0A, None), (0x0B, None)], centre=True)
    runs, width = windows.place(line, True, widths, text_x=5, centre_width=156)
    assert width == 12 and runs[0][2] == 5 + (156 - 12) // 2
    plain = windows.Line(tokens=[(0x0A, None), (0x0B, None)])
    assert windows.place(plain, False, widths, text_x=5)[0][0][2] == 5


class _FakeRules:
    """Only what the preview asks of the plugin: its font, its window and its codes."""

    def __init__(self, geometry):
        self._geometry = geometry
        self.char_codes = {ch: codec.CODES[ch] for ch in codec.CODES}

    def load_translation_map(self):
        pass

    def preview_font(self):
        header = b"VSFN" + (27648).to_bytes(4, "little") + (378).to_bytes(4, "little") + bytes(4)
        texture = bytes(27648)
        return header + texture + bytes([6] * 378)

    def preview_geometry(self, block, string):
        return self._geometry


def test_the_preview_widget_draws_pages_and_names_the_overflow(qtbot):
    rules = _FakeRules(windows.balloon(13, 2))
    mw = SimpleNamespace(current_game_rules=rules, data_store=SimpleNamespace(physical_block_idx=0,
                                                                              current_string_idx=0))
    widget = MessageWindowPreview(mw)
    qtbot.addWidget(widget)
    widget.update_preview_text("a\nb\nc")
    widget._render()
    assert not widget._picture.pixmap().isNull()
    assert "shows 2" in widget._status.text()
    widget.update_preview_text("a{page}b")
    widget._render()
    assert widget._page_label.text() == "Page 1 of 2"
    widget.shutdown()


def test_the_widget_says_when_no_project_is_open(qtbot):
    widget = MessageWindowPreview(SimpleNamespace(current_game_rules=None))
    qtbot.addWidget(widget)
    widget.update_preview_text("a")
    widget._render()
    assert widget._status.text()


def test_a_staff_roll_line_that_types_a_reserved_byte_is_flagged():
    class Fake:
        game_rules = None

    project = SimpleNamespace(
        credits_reserved_chars=lambda b, s, text: [c for c in text if c.isascii() and ord(c) in codec.CREDITS_NAMES],
    )
    fake = Fake()
    fake.game_rules = project
    rule = _FitRule(fake, "CREDITS_RESERVED")
    flagged = rule.detect(SimpleNamespace(block_idx=0, string_idx=0, text="Ab!"))
    assert [m.line_index for m in flagged] == [0]
    assert rule.detect(SimpleNamespace(block_idx=0, string_idx=0, text="Ab")) == []
    assert codec.CREDITS_NAMES[0x21] == "Щ" and PROBLEM_CREDITS == "VGS_CREDITS_RESERVED"


def test_the_problem_detail_gives_the_reason_for_every_reserved_character():
    from plugins.vagrant_story.rules import GameRules

    detail = GameRules.get_problem_detail(SimpleNamespace(), 0, 0, PROBLEM_CREDITS)
    assert "'!' = Щ" in detail and "'3' = " in detail and "do not type" in detail
