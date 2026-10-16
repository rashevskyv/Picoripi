"""The budget box with the real system font and the owner's 3ds-ua strings (env PICORIPI_ROMHACKING).

Every Ukrainian string of three parts fits its width budget by the owner's rule, and the console font draws each
character of them. The box of one label is drawn to a PNG-sized image; the synthetic overflow proves the mark.
"""
import json
from pathlib import Path

import pytest

import romhacking_root
from plugins.system_3ds import box, preview_panel
from plugins.system_3ds.rules import GameRules

REPO = ("_shared", "3ds_sysfont_ua", "repo_manual")
STRINGS = REPO + ("src", "strings")
FONT = REPO + ("work", "0004009B00014002", "cbf_std.bcfnt.lz")
PARTS = ("home_menu", "keyboard", "error_applet")
BUDGETS = Path(box.__file__).with_name("budgets.json")

pytestmark = pytest.mark.skipif(romhacking_root.missing(*STRINGS, "home_menu") is not None,
                                reason=romhacking_root.missing(*STRINGS, "home_menu") or "")


def _entries(part):
    folder = romhacking_root.path(*STRINGS, part)
    out = {}
    for path in sorted(folder.glob("*.json")):
        if path.name.startswith("_"):
            continue
        out.update({key: value for key, value in json.loads(path.read_text(encoding="utf-8")).items()
                    if isinstance(value, dict) and value.get("ua")})
    return out


def test_every_ukrainian_string_of_three_parts_fits_its_width_budget_and_line_budget():
    rules = GameRules()
    table = json.loads(BUDGETS.read_text(encoding="utf-8"))
    too_wide = []
    too_tall = []
    for part in PARTS:
        for label, entry in _entries(part).items():
            widths = rules.line_widths_of(entry["ua"])
            budget = table["labels"].get(part, {}).get(label)
            if budget and any(box.is_wide(width, budget) for width in widths):
                too_wide.append(f"{part}/{label}")
            lines = table.get("lines", {}).get(part, {}).get(label)
            if lines and entry["ua"].count("\n") + 1 > lines:
                too_tall.append(f"{part}/{label}")
    assert too_wide == []
    assert too_tall == []


@pytest.fixture
def real_glyphs():
    skip = romhacking_root.missing(*FONT)
    if skip:
        pytest.skip(skip)
    from plugins.manual_3ds import console_render as cr
    from plugins.manual_3ds import repo_tools
    tools = repo_tools.load_tools(str(romhacking_root.path(*REPO)))
    return cr.Glyphs(repo_tools.load_font(tools), tools.bcfnt)


def test_the_real_font_draws_a_label_and_the_overflow_is_marked(real_glyphs):
    rules = GameRules()
    text = _entries("home_menu")["lau_title_menu"]["ua"]
    fits = box.draw_box(text, rules.line_widths_of(text), 157, 1, real_glyphs)
    assert fits.missing == []
    assert fits.wide_lines == []
    assert fits.image.width == 157 + 2 * box.MARGIN

    longer = text + " Меню HOME Меню HOME Меню HOME"
    over = box.draw_box(longer, rules.line_widths_of(longer), 157, 1, real_glyphs)
    assert over.wide_lines == [1]
    assert "wider than the budget" in preview_panel.status_text(over)


def test_the_panel_draws_a_label_on_the_worker_path(real_glyphs, monkeypatch):
    rules = GameRules()
    monkeypatch.setattr(preview_panel, "load_folder", lambda: str(romhacking_root.path(*REPO)))
    text = _entries("home_menu")["lau_title_menu"]["ua"]
    request = preview_panel._Request("", text, 157, 1, "", rules.line_widths_of)
    result = preview_panel.draw_request(request, lambda: False)
    assert result is not None
    assert result.wide_lines == []
