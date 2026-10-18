"""3DS manual preview: a click selects the paragraph it shows, a drag scrolls, the original sits beside the translation,
a typed line break is a space (NEWLINE) with its autofix, and the fit numbers of a paragraph.

The tests use a synthetic manual and synthetic widths and geometry, installed on the plugin's own data holder. The
last test reads the owner's repo_manual folder only when PICORIPI_ROMHACKING is set.
"""
import json
import pathlib
import random
import string

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QImage, QMouseEvent
from PyQt6.QtWidgets import QApplication

import romhacking_root
from plugins.manual_3ds import config
from plugins.manual_3ds import console_render as cr
from plugins.manual_3ds import layout
from plugins.manual_3ds import preview_panel
from plugins.manual_3ds import rules as m3d
from plugins.manual_3ds import sim_screens as ss
from plugins.manual_3ds.preview_panel import ORIGINAL, TRANSLATION

_REPO_MANUAL = ("_shared", "3ds_sysfont_ua", "repo_manual")
CYRILLIC = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюяАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
KEY_A = "large/Page_003_large_0#0"
KEY_B = "large/Page_003_large_0#1"


@pytest.fixture
def widths(monkeypatch):
    """Letters 10 units, digits 17, space 9 at the console's 25-unit em; no ink overhangs."""
    advances = {ch: 10.0 for ch in string.ascii_letters + CYRILLIC}
    advances.update({digit: 17.0 for digit in string.digits}, **{" ": 9.0})
    table = layout.Widths({"advances": advances, "homoglyphs": {}})
    monkeypatch.setattr(m3d._DATA, "widths", table)
    return table


@pytest.fixture
def geometry(monkeypatch):
    """Two large paragraphs of two lines, one pane each at x 10, box 300 (the fixture of test_rules)."""
    column = {"part": "large", "font_size": 24.0, "char_space": 0.0, "icon_widths": [],
              "lines": [[[10.0, 300.0]], [[10.0, 300.0]]]}
    entries = {KEY_A: column, KEY_B: column}
    table = {m3d.fingerprint([KEY_A, KEY_B]): {"name": "synthetic", "entries": entries}}
    monkeypatch.setattr(m3d._DATA, "geometry", table)
    return table


class _Recorder:
    """What the panel asks of the main window's list selection: the (block, string index) of each selection."""

    def __init__(self):
        self.calls = []

    def navigate_to_physical_string(self, block, index):
        self.calls.append((block, index))
        return True


class _Store:
    """The part of the main window the panel reads: the selected string, the texts and the selection route."""

    def __init__(self, texts):
        self.current_string_idx = 0
        self.current_block_idx = 0
        self.physical_block_idx = 0
        self.blocks = {0: list(texts)}
        self.block_names = {}
        self.list_selection_handler = _Recorder()
        self.data_store = self
        self.data_processor = self

    def get_current_string_text(self, block, index):
        return self.blocks[block][index], "test"


def _run(pane, top, left=10.0, right=60.0):
    """One drawn line of 50 px at page x 10, 20 px high, its top at page y ``top`` (down is negative)."""
    return cr.TextRun(pane=pane, text="Line", x=left, top=top, width=right - left, wrapped=False, ink_right=right,
                      height=20.0, order=0, ink_left=left)


def _page(runs, owners):
    column = QImage(cr.COLUMN_WIDTH, 2400, QImage.Format.Format_RGBA8888)
    overlay = QImage(400, 480, QImage.Format.Format_RGBA8888)
    return preview_panel.PagePreview(column, overlay, 2400, 3, "Title", runs=runs, owners=owners)


def _document(rows):
    """A manual file from (key, en, ru, ua) rows."""
    entries = {key: {"lines": 2, "width": 300.0, "en": en, "ru": ru, "ua": ua} for key, en, ru, ua in rows}
    return json.dumps(entries, ensure_ascii=False)


def _panel(qtbot, monkeypatch, rows, root=""):
    """A large-text panel on block 0 of a manual with ``rows``; the canvases are 400 x 480, so a canvas point is a
    widget point. The folder is ``root`` (the owner's copy in the real-data test, else none)."""
    monkeypatch.setattr(preview_panel, "load_folder", lambda: root)
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(_document(rows))
    store = _Store([ua for _, _, _, ua in rows])
    panel = preview_panel.ManualPreviewPanel(store, rules)
    qtbot.addWidget(panel)
    panel._large = True
    panel._block = 0
    panel._screens.resize(400, 480)
    panel._original_screens.resize(400, 480)
    return panel, store, rules


def _mouse(kind, point):
    return QMouseEvent(kind, QPointF(point), QPointF(point), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier)


TWO_PARAGRAPHS = [(KEY_A, "Hello", "Привет", "Привіт"), (KEY_B, "Note", "Заметка", "Нотатка")]


# -- the problems of a typed line break, the hard break and the fit numbers (no Qt) -----------------------------


def test_a_typed_line_break_is_a_newline_problem(widths, geometry):
    problems = layout.check_entry("Привіт\nсвіт", "Привет мир", {}, None, widths)
    assert [name for name, _ in problems] == ["NEWLINE"]


def test_the_hard_break_is_not_a_newline_or_a_markup_problem_when_the_russian_has_none(widths, geometry):
    assert layout.check_entry("Привіт{br}світ", "Привет мир", {}, None, widths) == []


def test_a_hard_break_needs_a_spare_line_on_the_console(widths, geometry):
    """Two lines in the paragraph: a third line from a hard break is a LINES problem with its numbers."""
    geo = layout.Geometry(part="large", font_size=24.0, char_space=0.0,
                          lines=[[layout.Line(10.0, 300.0)], [layout.Line(10.0, 300.0)]])
    problems = layout.check_entry("один{br}два{br}три", "один два три", {}, geo, widths)
    assert problems == [("LINES", "needs 3 lines, the paragraph has 2")]


def test_the_autofix_turns_typed_line_breaks_into_hard_breaks(widths, geometry):
    rules = m3d.GameRules()
    assert rules.autofix_data_string("a \n b\nc", {}, 0, allowed_problems={m3d.NEWLINE_ID}) == ("a{br}b{br}c", True)
    assert rules.autofix_data_string("a\nb", {}, 0, allowed_problems=set()) == ("a\nb", False)
    assert rules.autofix_data_string("a{br}b", {}, 0, allowed_problems={m3d.NEWLINE_ID}) == ("a{br}b", False)


def test_enter_types_the_hard_break_and_only_the_newline_fix_is_on_by_default():
    assert m3d.GameRules().get_enter_char() == "{br}"
    assert config.DEFAULT_AUTOFIX_SETTINGS["M3D_NEWLINE"] is True
    assert [key for key, on in config.DEFAULT_AUTOFIX_SETTINGS.items() if on] == ["M3D_NEWLINE"]
    assert config.CUSTOM_PROBLEMS["NEWLINE"]["name"] == "Typed line break"


def test_the_fit_hint_gives_the_panes_the_text_needs_and_the_longest_word(widths, geometry):
    geo = layout.Geometry(part="large", font_size=24.0, char_space=0.0,
                          lines=[[layout.Line(10.0, 300.0)], [layout.Line(10.0, 300.0)]])
    hint = layout.fit_hint("Привіт світ", geo, widths)
    assert hint.startswith("Panes: 2 line(s), pane width 300 px. The text needs 1 line(s),")
    assert "Longest word: 'Привіт', 58 px." in hint


def test_a_word_wider_than_the_card_says_its_width_and_the_pane_box(widths, geometry):
    geo = layout.Geometry(part="small", font_size=24.0, char_space=0.0,
                          lines=[[layout.Line(10.0, 120.0)], [layout.Line(10.0, 120.0)]])
    lines, mode, reason = layout.layout_for("а" * 40, geo, widths)
    assert mode == "column-fallback"
    assert reason.startswith("'аааа") and "px wide" in reason and "(pane box 120 px)" in reason


# -- the click, the drag and the Y button on the canvas (pytest-qt) --------------------------------------------


def test_paragraph_at_finds_the_line_key_rect_outlines():
    runs = [_run("pane_a", -300.0), _run("pane_b", -340.0)]
    owners = {"pane_a": KEY_A, "pane_b": KEY_B}
    assert preview_panel.paragraph_at(runs, owners, 20.0, 310.0) == KEY_A
    assert preview_panel.paragraph_at(runs, owners, 20.0, 345.0) == KEY_B
    assert preview_panel.paragraph_at(runs, owners, 200.0, 310.0) is None, "beside the line: nothing"
    assert preview_panel.paragraph_at(runs, owners, 20.0, 100.0) is None, "above the page lines: nothing"


def test_a_click_selects_the_string_under_it_through_the_selection_route(qtbot, monkeypatch, geometry):
    panel, store, _ = _panel(qtbot, monkeypatch, TWO_PARAGRAPHS)
    panel._current_key = KEY_A
    panel._show_result(_page([_run("pane_a", -300.0), _run("pane_b", -380.0)], {"pane_a": KEY_A, "pane_b": KEY_B}))
    for row, index in ((305.0, 0), (385.0, 1)):
        point = QPointF(preview_panel.BOTTOM_X + 20.0, ss.PAGE_TOP + row - panel._scroll)
        QApplication.sendEvent(panel._screens, _mouse(QEvent.Type.MouseButtonPress, point))
        QApplication.sendEvent(panel._screens, _mouse(QEvent.Type.MouseButtonRelease, point))
        assert store.list_selection_handler.calls[-1] == (0, index)
    assert len(store.list_selection_handler.calls) == 2


def test_a_click_on_the_header_or_the_bottom_bar_selects_nothing(qtbot, monkeypatch, geometry):
    panel, store, _ = _panel(qtbot, monkeypatch, TWO_PARAGRAPHS)
    panel._show_result(_page([_run("pane_a", -300.0)], {"pane_a": KEY_A}))
    panel.select_at(TRANSLATION, QPointF(preview_panel.BOTTOM_X + 20.0, 10.0))
    panel.select_at(TRANSLATION, QPointF(preview_panel.BOTTOM_X + 20.0, ss.BOTTOM_BAR_ROW + 5.0))
    assert store.list_selection_handler.calls == []


def test_a_drag_scrolls_the_page_and_selects_nothing(qtbot, monkeypatch, geometry):
    panel, store, _ = _panel(qtbot, monkeypatch, TWO_PARAGRAPHS)
    panel._show_result(_page([_run("pane_a", -300.0)], {"pane_a": KEY_A}))
    panel._scroll = 100.0
    QApplication.sendEvent(panel._screens, _mouse(QEvent.Type.MouseButtonPress, QPointF(200.0, 200.0)))
    QApplication.sendEvent(panel._screens, _mouse(QEvent.Type.MouseMove, QPointF(200.0, 170.0)))
    assert panel._scroll == 130.0, "the page follows the pointer: the pointer up scrolls the page down"
    QApplication.sendEvent(panel._screens, _mouse(QEvent.Type.MouseButtonRelease, QPointF(200.0, 170.0)))
    assert store.list_selection_handler.calls == [], "a drag is not a click"


def test_a_move_within_the_slop_is_still_a_click(qtbot, monkeypatch, geometry):
    panel, store, _ = _panel(qtbot, monkeypatch, TWO_PARAGRAPHS)
    panel._show_result(_page([_run("pane_a", -300.0)], {"pane_a": KEY_A}))
    point = QPointF(preview_panel.BOTTOM_X + 20.0, ss.PAGE_TOP + 305.0 - panel._scroll)
    QApplication.sendEvent(panel._screens, _mouse(QEvent.Type.MouseButtonPress, point))
    QApplication.sendEvent(panel._screens, _mouse(QEvent.Type.MouseMove, QPointF(point.x() + 2, point.y())))
    QApplication.sendEvent(panel._screens, _mouse(QEvent.Type.MouseButtonRelease, point))
    assert store.list_selection_handler.calls == [(0, 0)]


def test_a_click_on_the_y_button_switches_the_size_and_selects_nothing(qtbot, monkeypatch, geometry):
    panel, store, _ = _panel(qtbot, monkeypatch, TWO_PARAGRAPHS)
    panel._show_result(_page([_run("pane_a", -300.0)], {"pane_a": KEY_A}))
    before = panel._large
    point = QPointF(preview_panel.BOTTOM_X + preview_panel.Y_BUTTON_START + 10.0, ss.BOTTOM_BAR_ROW + 5.0)
    QApplication.sendEvent(panel._screens, _mouse(QEvent.Type.MouseButtonPress, point))
    QApplication.sendEvent(panel._screens, _mouse(QEvent.Type.MouseButtonRelease, point))
    assert panel._large is not before
    assert store.list_selection_handler.calls == []


# -- the original beside the translation (pytest-qt, a fake worker) ----------------------------------------------


class _Signal:
    def connect(self, slot):
        pass


class _Worker:
    """A worker that starts nothing: the test delivers the results itself."""

    started = []

    def __init__(self, generation, request, parent):
        self.request = request
        self.rendered = _Signal()
        _Worker.started.append(self)

    def start(self):
        pass

    def isRunning(self):  # noqa: N802 - Qt name
        return False

    def cancel(self):
        pass


@pytest.fixture
def workers(monkeypatch):
    _Worker.started = []
    monkeypatch.setattr(preview_panel, "PageRenderWorker", _Worker)
    return _Worker


def test_the_original_is_drawn_beside_the_translation_and_shares_the_scroll_and_the_selection(qtbot, monkeypatch,
                                                                                            geometry, workers):
    panel, store, _ = _panel(qtbot, monkeypatch, TWO_PARAGRAPHS)
    panel._source_box.setCurrentIndex(1)                       # "Original: Russian (ru)"
    assert panel._source == "ru"
    panel._start_render()
    assert [worker.request.lang for worker in workers.started] == [TRANSLATION], "the original waits for the translation"
    translation = workers.started[0]
    generation = panel._generation
    panel._on_rendered(generation, translation.request.key,
                       _page([_run("pane_a", -300.0), _run("pane_b", -380.0)], {"pane_a": KEY_A, "pane_b": KEY_B}))
    assert [worker.request.lang for worker in workers.started] == [TRANSLATION, "ru"]
    original = workers.started[1]
    assert original.request.texts == {KEY_A: "", KEY_B: ""}, "the Russian is the console's own layout: no text is laid out"
    panel._on_rendered(generation, original.request.key,
                       _page([_run("pane_a", -320.0), _run("pane_b", -390.0)], {"pane_a": KEY_A, "pane_b": KEY_B}))
    assert panel._result is not None and panel._original_result is not None
    assert panel._highlight.top() == 300.0 and panel._original_highlight.top() == 320.0
    panel.scroll_by(50.0)
    assert panel._scroll == 50.0, "one scroll position for both canvases"
    point = QPointF(preview_panel.BOTTOM_X + 20.0, ss.PAGE_TOP + 390.0 + 5.0 - panel._scroll)
    panel.select_at(ORIGINAL, point)
    assert store.list_selection_handler.calls == [(0, 1)], "a click on the original selects its string"


def test_editing_the_translation_does_not_draw_the_original_again(qtbot, monkeypatch, geometry, workers):
    panel, store, _ = _panel(qtbot, monkeypatch, TWO_PARAGRAPHS)
    panel._source_box.setCurrentIndex(1)
    panel._start_render()
    generation = panel._generation
    translation = workers.started[0]
    panel._on_rendered(generation, translation.request.key, _page([_run("pane_a", -300.0)], {"pane_a": KEY_A}))
    original = workers.started[1]
    panel._on_rendered(generation, original.request.key, _page([_run("pane_a", -320.0)], {"pane_a": KEY_A}))
    assert len(workers.started) == 2
    store.blocks[0][0] = "Привіт, друже"                        # an edit of the translation
    panel._start_render()
    assert [worker.request.lang for worker in workers.started] == [TRANSLATION, "ru", TRANSLATION],         "only the translation is drawn again: the original's key is cached"


def test_an_original_that_does_not_pair_with_the_russian_says_so_and_is_not_drawn(qtbot, monkeypatch, geometry,
                                                                                 workers):
    rows = [(KEY_A, "❺", "Нажмите {i0} во время игры", "Натисніть {i0}"), (KEY_B, "Note", "Заметка", "Нотатка")]
    panel, store, _ = _panel(qtbot, monkeypatch, rows)
    panel._source_box.setCurrentIndex(2)                       # "Original: English (en)"
    store.current_string_idx = 1
    panel._start_render()
    assert [worker.request.lang for worker in workers.started] == [TRANSLATION]
    assert panel._original_message == "No English text on this page: it does not line up with the Russian."


def test_the_selector_none_draws_one_canvas_only(qtbot, monkeypatch, geometry, workers):
    panel, _, _ = _panel(qtbot, monkeypatch, TWO_PARAGRAPHS)
    panel._start_render()
    assert [worker.request.lang for worker in workers.started] == [TRANSLATION]
    assert panel._original_result is None


# -- the real manual, offscreen -------------------------------------------------------------------------------

def _real_keys():
    """The key list of home_menu_manual, from the plugin's geometry table (the keys, not the text)."""
    geometry_file = pathlib.Path(m3d.__file__).parent / "geometry.json"
    table = json.loads(geometry_file.read_text(encoding="utf-8"))["manuals"]
    entry = next(value for value in table.values() if value.get("name") == "home_menu_manual")
    return list(entry["entries"].keys())


@pytest.mark.skipif(romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py") is not None,
                    reason=romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py") or "")
def test_real_page_click_maps_twenty_random_panes_to_their_strings(qtbot, monkeypatch):
    """The owner's home_menu_manual: twenty random drawn lines of a small page; a click in each selects the string
    that owns the line, and that string's key is the owner's key."""
    root = str(romhacking_root.path(*_REPO_MANUAL))
    monkeypatch.setattr(preview_panel, "load_folder", lambda: root)
    keys = _real_keys()
    rows = [(key, "", "Слово", "Word word") for key in keys]
    panel, store, rules = _panel(qtbot, monkeypatch, rows, root=root)
    panel._large = False
    store.current_string_idx = rules.strings_of_group(0, "small/Page_002_small")["small/Page_002_small_0#2"]
    panel._start_render()
    qtbot.waitUntil(lambda: panel._result is not None or bool(panel._message), timeout=60000)
    panel.shutdown()
    result = panel._result
    assert result is not None, panel._message
    drawn = [run for run in result.runs if result.owners.get(run.pane)]
    # A line whose ink another line shares is no single paragraph's: the sample takes the lines nothing overlaps.
    alone = [run for run in drawn if not any(
        other is not run and other.ink_left < run.ink_right and run.ink_left < other.ink_right
        and -other.top < -run.top + run.height and -run.top < -other.top + other.height for other in result.runs)]
    assert len(alone) >= 20, f"{len(drawn)} lines, {len(alone)} not shared"
    for run in random.Random(20261018).sample(alone, 20):
        owner = result.owners[run.pane]
        content_y = -run.top + run.height / 2
        panel._scroll = panel._clamped(content_y - 100.0)     # bring the line into the visible rows
        point = QPointF(preview_panel.BOTTOM_X + run.ink_left + 1.0, ss.PAGE_TOP + content_y - panel._scroll)
        before = len(store.list_selection_handler.calls)
        panel.select_at(TRANSLATION, point)
        assert len(store.list_selection_handler.calls) == before + 1, f"no string under {run.pane}"
        block, index = store.list_selection_handler.calls[-1]
        assert rules.string_key(block, index) == owner
