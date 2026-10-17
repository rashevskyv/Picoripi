"""The PAL Switch plugin: its own font grid next to the shared Silent Hill text rules."""
from plugins.silent_hill1_switch.rules import GameRules
from plugins.silent_hill_ps1.rules import GameRules as PsxRules


def test_display_name_and_text_rules_come_from_the_ps1_rules():
    rules = GameRules.__new__(GameRules)
    assert rules.get_display_name() == "Silent Hill 1 (Switch, PAL)"
    assert issubclass(GameRules, PsxRules)
    assert GameRules.problem_prefix == PsxRules.problem_prefix


def test_font_grid_is_the_pal_six_row_sheet():
    rules = GameRules.__new__(GameRules)
    fonts = rules.get_font_sources()
    assert [f["path"] for f in fonts] == ["1ST/FONT16.TIM", "1ST/FONT8NOC.TIM", "TIM/FONT8.TIM", "TIM/FONT24.TIM"]
    params = fonts[0]["params"]
    assert len(params["chars"]) == 126 and params["chars"][66] == "і"
    assert params["columns"] == 21
    assert len(params["rows_at"]) == 6
    assert params["rows_at"][-1] == [0, 80]
