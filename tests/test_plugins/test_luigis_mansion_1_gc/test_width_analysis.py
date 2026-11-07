"""The width analysis skips a plugin's own tags (<COLOR>(3)): only the letters take width."""
from types import SimpleNamespace

from handlers.text_analysis_handler import TextAnalysisHandler
from handlers.width_calculation_worker import WidthCalculationWorker
from plugins.luigis_mansion_1_gc.rules import GameRules

FONT = {ch: {"width": 10} for ch in "<>()COLRGad0123456789 "}
TAGGED = "<COLOR>(3)Gadd<COLOR>(0)"


class _Strings:
    def get_current_string_text(self, block_idx, string_idx):
        return TAGGED, "src"

    def _get_string_from_source(self, block_idx, string_idx, data, tag):
        return TAGGED


class _Fonts:
    def get_font_map_for_string(self, block_idx, string_idx):
        return FONT


class _Dialog:
    def __init__(self, parent):
        self.shown = None

    def show_entries(self, raw_entries, font_maps, initial_font, precomputed_entries=None):
        self.shown = precomputed_entries


def test_the_block_width_calculation_skips_the_tags(qtbot):
    worker = WidthCalculationWorker(0, [TAGGED], "B", _Fonts(), _Strings(), GameRules(None), {}, {"f": FONT})
    with qtbot.waitSignal(worker.calculation_finished) as result:
        worker.run()
    assert [entry["width_pixels"] for entry in result.args[0]["entries"]] == [40.0]


def test_the_original_text_analysis_skips_the_tags(monkeypatch):
    monkeypatch.setattr("handlers.text_analysis_handler.OriginalTextAnalysisDialog", _Dialog)
    mw = SimpleNamespace(data_store=SimpleNamespace(data=[[TAGGED]]), all_font_maps={"f": FONT},
                         default_font_file="f", current_game_rules=GameRules(None))
    handler = TextAnalysisHandler(mw, None, None)
    handler.analyze_original_text()
    assert [entry["width_pixels"] for entry in handler._dialog.shown] == [40.0]
