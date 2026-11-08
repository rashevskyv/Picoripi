"""Ocarina of Time (Switch 2): Auto-fix wraps by the width the editor's markers draw (owner's project, 2026-11-08)."""
from types import SimpleNamespace

from plugins.zelda_oot_switch2.rules import GameRules
from utils.width import max_line_width, measure_width

# The owner's settings: warning width 280, window width 300, three lines a page, no font map with letters.
WARN, LIMIT = 280, 300
TRANSLATION = "Давно-давно існувала земля\nпід назвою Гайрул, створена вищими\nбожественними істотами."
SOURCE = "Long ago, there was a land called Hyrule,\ncreated by beings of supreme divinity."


def _rules():
    mw = SimpleNamespace(
        icon_sequences=[], default_tag_mappings={}, string_metadata={}, lines_per_page=3,
        game_dialog_max_width_pixels=LIMIT, line_width_warning_threshold_pixels=WARN,
        align_sentences_to_original_pages=False, prevent_empty_lines_in_autofix=False,
        data_store=SimpleNamespace(data=[[SOURCE]]),
    )
    rules = GameRules(mw)
    mw.current_game_rules = rules
    # Auto-fix as the owner has it: the short-line merge on, the width wrap off.
    mw.autofix_enabled = {rules.problem_analyzer.registry.get_prefixed_id(name): True
                          for name in ("BAD_SPACING", "SHORT_LINE", "MISSING_ICON_SPACING", "BROKEN_ICON_HYPHEN")}
    return rules, set(mw.autofix_enabled)


def test_auto_fix_keeps_every_line_inside_the_markers_warning_width():
    rules, allowed = _rules()
    fixed, _changed = rules.autofix_data_string(TRANSLATION, {}, WARN, logical_hard_limit=LIMIT,
                                                allowed_problems=allowed, block_idx=0, string_idx=0)
    widths = [measure_width(rules, line, {}) for line in fixed.split("\n")]
    assert max(widths) <= WARN, list(zip(fixed.split("\n"), widths))


def test_the_original_width_is_measured_without_a_letter_map():
    rules, _allowed = _rules()
    # "Long ago, there was a land called Hyrule," has 41 characters; no glyph map, so 8 px each, as the markers draw.
    assert max_line_width(rules, SOURCE, {}) == 41 * 8
