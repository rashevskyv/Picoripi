"""The in-place layout of a 3DS system string: link lookup, the status line, the fallback to the budget box.

Fakes only: the links table, the layout draw and the owner's tools are replaced. The real layouts are in
test_layout_real.py (env PICORIPI_ROMHACKING).
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from plugins.system_3ds import layout_render as lr
from plugins.system_3ds import preview_panel
from plugins.system_3ds.rules import GameRules

LINKS = Path(lr.__file__).resolve().parent / "layout_links.json"
_REAL_LINK_OF = lr.link_of

TABLE = {
    "browser": {
        "Option_ProxyUserID": {"kind": "label", "tid": "0004003000008202", "file": "layout/browse/BasicAuthDialog.arc",
                               "chain": ["./blyt/BasicAuthDialog.bclyt"], "pane": "UserIdTxb"},
    },
    "system_settings": {
        "up_LZ.bin/./blyt/StartTopEU_U_00.bclyt/TextBoxTitle_00#0": {
            "kind": "spec", "tid": "0004001000022000", "file": "up_LZ.bin", "chain": ["./blyt/StartTopEU_U_00.bclyt"],
            "pane": "TextBoxTitle_00", "line": 0},
    },
}


@dataclass
class _Drawn:
    image: Image.Image = field(default_factory=lambda: Image.new("RGBA", (4, 4)))
    pane: str = "UserIdTxb"
    kind: str = "label"
    wrapped: int = 0
    missing_glyphs: list = field(default_factory=list)
    missing_textures: list = field(default_factory=list)


def _request(part="browser", key="Option_ProxyUserID", text="Ім'я", root="C:/owner"):
    return preview_panel._Request(root, text, 157, 1, "", lambda text: [10.0], part, key)


def _fake_box_tools(monkeypatch):
    monkeypatch.setattr(preview_panel.repo_tools, "load_tools", lambda root: SimpleNamespace(bcfnt=None))
    monkeypatch.setattr(preview_panel.repo_tools, "load_font", lambda tools: SimpleNamespace())
    monkeypatch.setattr(preview_panel.cr, "Glyphs", lambda font, bcfnt: _Glyphs())


class _Glyphs:
    width = 6
    height = 8
    ascent = 6
    line_feed = 10
    font = SimpleNamespace(sheets=SimpleNamespace(cell_width=6, cell_height=8))

    def has(self, code):
        return True

    def metrics(self, code):
        return 0, 5, 6

    def cell(self, code):
        return Image.new("L", (5, 7), 255)


def test_a_link_is_read_from_the_table_with_its_fields():
    link = lr.link_of("browser", "Option_ProxyUserID", TABLE)
    assert link == lr.Link("label", "0004003000008202", "layout/browse/BasicAuthDialog.arc",
                           ("./blyt/BasicAuthDialog.bclyt",), "UserIdTxb", -1)
    spec = lr.link_of("system_settings", "up_LZ.bin/./blyt/StartTopEU_U_00.bclyt/TextBoxTitle_00#0", TABLE)
    assert spec.kind == "spec" and spec.line == 0


def test_a_string_without_a_link_has_none():
    assert lr.link_of("browser", "No_such_label", TABLE) is None
    assert lr.link_of("keyboard", "Option_ProxyUserID", TABLE) is None
    assert lr.link_of("", "", TABLE) is None


def test_the_shipped_links_file_holds_the_links_of_the_parts_it_names():
    table = json.loads(LINKS.read_text(encoding="utf-8"))["links"]
    assert set(table) == {"browser", "game_notes", "miiverse", "miiverse_post", "system_settings"}
    assert table["browser"]["Option_ProxyUserID"]["kind"] == "label"
    assert table["system_settings"]["up_LZ.bin/./blyt/StartTopEU_U_00.bclyt/TextBoxTitle_00#0"]["kind"] == "spec"


def test_a_layout_block_has_its_stem_as_part(monkeypatch):
    rules = GameRules()
    monkeypatch.setattr(rules, "_project_blocks", lambda: [SimpleNamespace(source_file="layouts/system_settings.json")])
    assert rules.part_of(0) == "system_settings"


def test_the_status_of_an_in_place_layout_names_the_pane_and_the_backdrop():
    text = preview_panel.layout_status(_Drawn(wrapped=2, missing_glyphs=["\u00e9"]))
    assert "pane UserIdTxb" in text
    assert "2 line(s) of the pane wrap." in text
    assert "Missing glyphs: \u00e9" in text
    assert "Backdrop: placeholder" in text


def test_a_spec_status_says_the_other_languages_are_as_stored():
    text = preview_panel.layout_status(_Drawn(kind="spec", pane="TextBoxTitle_00"))
    assert "Other languages of the pane are drawn as stored." in text


def test_a_linked_string_is_drawn_in_place(monkeypatch):
    monkeypatch.setattr(lr, "link_of", lambda part, key: _REAL_LINK_OF(part, key, TABLE))
    monkeypatch.setattr(lr, "draw_link", lambda root, link, text, stop: _Drawn())
    shown = preview_panel.draw_request(_request(), lambda: False)
    assert shown.status.startswith("In place: pane UserIdTxb")


def test_a_layout_that_does_not_draw_falls_back_to_the_budget_box_and_says_so(monkeypatch):
    monkeypatch.setattr(lr, "link_of", lambda part, key: _REAL_LINK_OF(part, key, TABLE))

    def broken(root, link, text, stop):
        raise ValueError("layout gone")

    monkeypatch.setattr(lr, "draw_link", broken)
    _fake_box_tools(monkeypatch)
    shown = preview_panel.draw_request(_request(), lambda: False)
    assert "did not draw" in shown.status
    assert "Widest line" in shown.status
    assert shown.image.width > 0


def test_a_stopped_layout_draw_returns_nothing(monkeypatch):
    monkeypatch.setattr(lr, "link_of", lambda part, key: _REAL_LINK_OF(part, key, TABLE))
    monkeypatch.setattr(lr, "draw_link", lambda root, link, text, stop: None)
    assert preview_panel.draw_request(_request(), lambda: True) is None


def test_a_missing_folder_is_reported_not_drawn_as_a_box(monkeypatch):
    monkeypatch.setattr(lr, "link_of", lambda part, key: _REAL_LINK_OF(part, key, TABLE))
    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")
    try:
        preview_panel.draw_request(_request(root=""), lambda: False)
    except preview_panel.repo_tools.ToolsError as exc:
        assert str(exc) == preview_panel.repo_tools.NO_FOLDER
    else:
        raise AssertionError("a missing folder must raise ToolsError")


def test_a_string_without_a_link_gets_the_budget_box(monkeypatch):
    monkeypatch.setattr(lr, "link_of", lambda part, key: None)
    _fake_box_tools(monkeypatch)
    shown = preview_panel.draw_request(_request(part="keyboard", key="dlg_dic_title", text="abc"), lambda: False)
    assert shown.status.startswith("Widest line")
