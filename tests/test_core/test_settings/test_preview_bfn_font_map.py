"""A BFN preview font (Wind Waker's message font) feeds the width map, translated letters included."""
from types import SimpleNamespace

from core.bfn_core import BfnCore
from core.settings.font_map_loader import FontMapLoader, _prepare_preview_fonts, _read_translation_map
from handlers.issue_scan_handler import IssueScanHandler
from utils import app_mode


def _font_bytes() -> bytes:
    """A font with 'A' (width 10), 'B' (12) and the game character 'Æ' (17, code 198)."""
    font = BfnCore()
    font.inf1 = [{"encoding": 0, "ascent": 22, "descent": 2, "width": 24, "leading": 2, "fallback_code": 63, "unk1": 0}]
    font.gly1 = [{"start_glyph": 0, "end_glyph": 3, "cell_width": 24, "cell_height": 24, "page_data_size": 256,
                  "texture_format": 0, "glyph_horizontal_count": 5, "glyph_vertical_count": 2,
                  "texture_width": 128, "texture_height": 128, "sheets_binary": [bytes(256)]}]
    font.map1 = [{"mapping_type": 2, "first_char": 65, "last_char": 66, "mapping_entry_count": 2, "entries": [0, 1]},
                 {"mapping_type": 2, "first_char": 198, "last_char": 198, "mapping_entry_count": 1, "entries": [2]}]
    font.wid1 = [{"first_code_included": 0, "last_code_included": 3,
                  "packets": [{"kerning": 0, "width": 10}, {"kerning": 0, "width": 12}, {"kerning": 0, "width": 17}]}]
    return font.save()


class _Source:
    """What ``font_formats.sources.resolve`` returns for one font file."""

    format = "bfn"
    font_map = "message.json"
    name = "message.bfn"
    label = "Message font"
    params: dict = {}

    def read_current(self) -> bytes:
        return _font_bytes()


def test_a_translated_letter_takes_the_width_of_its_game_character(monkeypatch):
    monkeypatch.setattr("core.font_formats.sources.resolve", lambda descriptors, metadata: [_Source()])
    [(name, width_map, font)] = _prepare_preview_fonts([{"label": "x"}], {}, {"Ж": "Æ"})
    assert name == "message.json"
    assert width_map["A"]["width"] == 10
    assert width_map["Ж"]["width"] == 17      # a Latin-only map would not have the letter at all
    assert isinstance(font, BfnCore)


def test_the_translation_map_is_the_projects_else_the_plugins(tmp_path):
    (tmp_path / "translation_map.json").write_text('{"Ж": "Æ"}', encoding="utf-8")
    assert _read_translation_map(str(tmp_path), None) == {"Ж": "Æ"}
    assert _read_translation_map(str(tmp_path / "missing"), None) == {}


def test_the_preview_font_replaces_a_default_map_that_holds_only_the_overrides():
    overrides = {"{tag}": {"width": 0}}
    mw = SimpleNamespace(all_font_maps={}, all_bfn_fonts={}, font_map=dict(overrides), font_map_overrides=overrides,
                         default_font_file="")
    FontMapLoader(mw)._apply_preview_fonts([("message.json", {"A": {"width": 10}}, object())])
    assert mw.font_map["A"]["width"] == 10
    assert mw.font_map["{tag}"]["width"] == 0     # the plugin's overrides are in the new map too


def test_a_default_map_with_real_widths_is_kept():
    mw = SimpleNamespace(all_font_maps={"own.json": {"B": {"width": 5}}}, all_bfn_fonts={}, font_map={"B": {"width": 5}},
                         font_map_overrides={}, default_font_file="own.json")
    FontMapLoader(mw)._apply_preview_fonts([("message.json", {"A": {"width": 10}}, object())])
    assert mw.font_map == {"B": {"width": 5}}


def test_callbacks_wait_for_the_preview_load_and_the_next_load_drops_them(monkeypatch):
    loader = FontMapLoader(SimpleNamespace(all_font_maps={}, all_bfn_fonts={}))
    calls = []
    loader.after_preview_fonts(lambda: calls.append("now"))
    assert calls == ["now"]

    loader._preview_job = object()
    loader._preview_generation = 3
    loader.after_preview_fonts(lambda: calls.append("later"))
    loader._preview_scan_done([], "", 2)            # an older load: dropped, the callback waits
    assert calls == ["now"]
    loader._preview_scan_done([], "", 3)
    assert calls == ["now", "later"]

    loader._preview_job = object()
    loader.after_preview_fonts(lambda: calls.append("stale"))
    project = SimpleNamespace(metadata={})
    rules = SimpleNamespace(get_font_sources=lambda: [])
    loader.mw.current_game_rules = rules
    monkeypatch.setattr(app_mode, "headless", True)
    loader._load_preview_fonts(SimpleNamespace(project=project, project_dir=None))
    assert loader._after_preview == []
    assert "stale" not in calls


class _FakeLoader:
    def __init__(self):
        self.preview_scan_running = True
        self.waiting = []

    def after_preview_fonts(self, callback):
        self.waiting.append(callback)


def test_the_first_issue_scan_waits_for_the_preview_fonts():
    loader = _FakeLoader()
    store = SimpleNamespace(data=[], problems_per_subline={})
    mw = SimpleNamespace(data_store=store, settings_manager=SimpleNamespace(font_map_loader=loader), current_game_rules=None)
    handler = IssueScanHandler(mw, None, None)
    done = []
    handler._perform_initial_silent_scan_all_issues(on_completed=lambda: done.append(1))
    assert done == []                              # nothing was scanned yet
    loader.preview_scan_running = False
    loader.waiting.pop()()                         # the fonts arrived
    assert done == [1]

