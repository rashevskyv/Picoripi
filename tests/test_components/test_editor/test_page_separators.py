"""The editor's page lines: after every page_size lines, and after a line that ends with the plugin's page break."""
from types import SimpleNamespace

from components.editor.line_numbered_text_edit import LineNumberedTextEdit
from components.editor.paint_event_logic import LNETPaintEventLogic


class _Rules:
    def __init__(self, shift_enter: str):
        self.shift_enter = shift_enter

    def get_shift_enter_char(self) -> str:
        return self.shift_enter


def _ends(text: str, shift_enter: str, page_size: int = 3) -> set:
    editor = LineNumberedTextEdit(None)
    editor.setPlainText(text)
    window = SimpleNamespace(current_game_rules=_Rules(shift_enter))
    return LNETPaintEventLogic(editor, None)._page_ends(window, page_size)


def test_a_page_break_line_ends_the_page_and_the_count_starts_again(qapp):
    assert _ends("a{pageBreak}\nb\nc\nd\ne", "{pageBreak}\n") == {0, 3}


def test_without_a_page_break_marker_a_page_is_page_size_lines(qapp):
    assert _ends("a\nb\nc\nd\ne\nf\ng", "\n") == {2, 5}
