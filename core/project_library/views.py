"""Pure rules of the project list: readiness and text buckets, sorting, grouping, and the pinned last-opened row."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

GROUP_MODES = ("folder", "platform", "readiness", "text", "none")
SORT_MODES = ("name", "lines", "platform", "readiness", "modified")
READINESS_ORDER = ("not_started", "in_progress", "done", "unknown")
TEXT_ORDER = ("small", "medium", "large", "unknown")
SMALL_TEXT_LINES = 1000
MEDIUM_TEXT_LINES = 10000

Section = Tuple[str, str, List[Dict[str, Any]]]  # (kind, value, rows); kind is "last", "folder", "platform", ...


def readiness(translated_percent: Optional[int]) -> str:
    if translated_percent is None:
        return "unknown"
    if translated_percent <= 0:
        return "not_started"
    if translated_percent >= 100:
        return "done"
    return "in_progress"


def text_amount(lines: Optional[int]) -> str:
    if lines is None:
        return "unknown"
    if lines < SMALL_TEXT_LINES:
        return "small"
    if lines < MEDIUM_TEXT_LINES:
        return "medium"
    return "large"


def _sort_value(row: Dict[str, Any], sort_by: str) -> Any:
    """The value a row sorts by, or None when unknown (unknown rows go last, by name)."""
    if sort_by == "lines":
        return row.get("lines")
    if sort_by == "platform":
        return row.get("platform") or None
    if sort_by == "readiness":
        state = readiness(row.get("translated"))
        return READINESS_ORDER.index(state) if state != "unknown" else None
    if sort_by == "modified":
        return row.get("modified") or None
    return None  # "name" is the base order, applied first


def ordered(rows: List[Dict[str, Any]], sort_by: str, descending: bool) -> List[Dict[str, Any]]:
    """Rows sorted by name, then by ``sort_by`` (stable, so equal values keep the name order)."""
    by_name = sorted(rows, key=lambda row: str(row.get("name", "")).casefold())
    if sort_by == "name":
        return list(reversed(by_name)) if descending else by_name
    known = [row for row in by_name if _sort_value(row, sort_by) is not None]
    unknown = [row for row in by_name if _sort_value(row, sort_by) is None]
    known.sort(key=lambda row: _sort_value(row, sort_by), reverse=descending)
    return known + unknown


def arrange(rows: List[Dict[str, Any]], view: Dict[str, Any], folder_names: Dict[str, str],
            last_key: Optional[str]) -> List[Section]:
    """The sections to show, top to bottom.

    The last opened project is always the first section, outside any group. Groups follow ``view['group_by']``:
    folders by name, platforms by name, readiness and text amount in their fixed order; projects without a
    folder or platform come last. Inside a group, rows follow ``view['sort_by']`` and ``view['descending']``.
    """
    sort_by = view.get("sort_by", "name")
    descending = bool(view.get("descending", False))
    group_by = view.get("group_by", "folder")
    if group_by not in GROUP_MODES:
        group_by = "folder"

    sections: List[Section] = []
    pinned = [row for row in rows if row.get("key") == last_key]
    rest = [row for row in rows if row.get("key") != last_key]
    if pinned:
        sections.append(("last", "", pinned))

    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in rest:
        groups.setdefault(_group_of(row, group_by), []).append(row)

    for kind, value in _group_order(groups.keys(), group_by, folder_names):
        group_rows = ordered(groups[(kind, value)], sort_by, descending)
        sections.append((kind, value, group_rows))
    return sections


def _group_of(row: Dict[str, Any], group_by: str) -> Tuple[str, str]:
    if group_by == "folder":
        return ("folder", row.get("folder_id") or "")
    if group_by == "platform":
        return ("platform", row.get("platform") or "")
    if group_by == "readiness":
        return ("readiness", readiness(row.get("translated")))
    if group_by == "text":
        return ("text", text_amount(row.get("lines")))
    return ("all", "")


def _group_order(keys, group_by: str, folder_names: Dict[str, str]) -> List[Tuple[str, str]]:
    keys = list(keys)
    if group_by == "folder":
        # Named folders alphabetically; the root ("no folder") last.
        return sorted(keys, key=lambda k: (k[1] == "", folder_names.get(k[1], "").casefold()))
    if group_by == "platform":
        return sorted(keys, key=lambda k: (k[1] == "", k[1].casefold()))
    if group_by == "readiness":
        return sorted(keys, key=lambda k: READINESS_ORDER.index(k[1]))
    if group_by == "text":
        return sorted(keys, key=lambda k: TEXT_ORDER.index(k[1]))
    return keys
