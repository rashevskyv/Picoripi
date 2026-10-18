"""Fill whole strings from the series glossary in the open project (D45, item 1).

The plan reads the series glossaries of the open project and the positions of each term (the source index of the
translation memory). The apply writes only untranslated strings whose checks pass (tags and window fit), as one undo step.
"""
# handlers/glossary_term_fill.py
from typing import Any, List, Optional, Tuple

from core.glossary.series import series_managers_of
from core.glossary.term_fill import FILL, TermFill, TermTable, build_term_table, plan_fills
from core.translation.layout_contract import text_fits_place
from core.translation.series_memory import source_hash
from plugins.common.tag_logic import TAG_STATUS_OK, compare_tags


def tag_map_of(mw: Any) -> Any:
    """The plugin's tag kinds (``get_series_tag_map``), or None when the plugin has none."""
    getter = getattr(getattr(mw, "current_game_rules", None), "get_series_tag_map", None)
    return getter() if callable(getter) else None


def series_entries(managers: List[Any]) -> List[Tuple[str, str]]:
    """``(term, translation)`` of every series glossary entry, nearest level first."""
    return [(entry.original, entry.translation) for manager in managers for entry in manager.get_entries()]


def plan_open_project(mw: Any) -> Tuple[TermTable, List[TermFill]]:
    """``(term table, fills)`` for the open project. Reads only the in-memory source index: no file, no parse."""
    tag_map = tag_map_of(mw)
    table = build_term_table(series_entries(series_managers_of(mw)), tag_map)
    saved = getattr(mw, "saved_translations_manager", None)
    if saved is None:
        return table, []
    terms = [term for term, _ in table.by_key.values()] + [pairs[0][0] for pairs in table.conflicts.values()]
    seen = set()
    positions: List[Tuple[int, int]] = []
    for term in terms:
        for position in saved.source_positions.get(source_hash(term), []):
            if position not in seen:
                seen.add(position)
                positions.append(position)
    rows = []
    data = mw.data_store.data
    for block_idx, string_idx in positions:
        source = data[block_idx][string_idx]
        if not isinstance(source, str):
            continue
        current, _ = mw.data_processor.get_current_string_text(block_idx, string_idx)
        rows.append((block_idx, string_idx, source, current or "", bool(mw.data_processor.is_string_translated(block_idx, string_idx))))
    return table, plan_fills(table, rows, tag_map)


def check_fill(mw: Any, fill: TermFill) -> Optional[str]:
    """None when the fill may be written; otherwise the reason it is refused (tags first, then the window)."""
    if compare_tags(fill.translation, fill.source)[0] != TAG_STATUS_OK:
        return "tags"
    if not text_fits_place(mw, fill.source, fill.translation, fill.block_idx, fill.string_idx):
        return "window"
    return None


def apply_fills(mw: Any, fills: List[TermFill]) -> Tuple[List[TermFill], List[Tuple[TermFill, str]]]:
    """Write the untranslated fills that pass the checks, as one undo step. Returns ``(written, refused with reason)``."""
    written: List[TermFill] = []
    refused: List[Tuple[TermFill, str]] = []
    for fill in fills:
        if fill.status != FILL:
            continue
        reason = check_fill(mw, fill)
        if reason is None:
            written.append(fill)
        else:
            refused.append((fill, reason))
    if not written:
        return written, refused
    undo = getattr(mw, "undo_manager", None)
    if undo is not None:
        undo.begin_group()
    try:
        for fill in written:
            mw.data_processor.update_edited_data(fill.block_idx, fill.string_idx, fill.translation,
                                                 action_type="FILL_TERMS", skip_ui_refresh=True)
            scanner = getattr(mw, "text_operation_handler", None)
            if scanner:
                scanner._rescan_issues_for_current_string(fill.block_idx, fill.string_idx, fill.translation)
    finally:
        if undo is not None:
            undo.end_group("FILL_TERMS")
    ui = mw.ui_updater
    for block_idx in {fill.block_idx for fill in written}:
        ui.update_block_item_text_with_problem_count(block_idx)
    ui.populate_current_view(force=True)
    ui.update_text_views()
    return written, refused
