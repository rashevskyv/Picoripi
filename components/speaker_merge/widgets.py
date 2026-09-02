from __future__ import annotations

from collections import Counter
from typing import List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QStyledItemDelegate

from core.speaker_alias_merge import NAME_SEPARATOR

_CODE_ROLE = Qt.ItemDataRole.UserRole
_DISPLAY_ROLE = Qt.ItemDataRole.UserRole + 1
_APPLIED_NAME_ROLE = Qt.ItemDataRole.UserRole + 2

_STRONG_COLOR = QColor("#2e7d32")
_SHARED_COLOR = QColor("#e65100")
_WEAK_COLOR = QColor("#1565c0")
_UNMATCHED_COLOR = QColor("#6a1b9a")
_DISPLAY_COLOR = QColor("#00695c")


class NameOnlyDelegate(QStyledItemDelegate):
    """Allow inline editing only on column 1 (Name column)."""

    def createEditor(self, parent, option, index):
        if index.column() == 1:
            return super().createEditor(parent, option, index)
        return None


def _votes_line(counter) -> str:
    return ", ".join(
        f"{name} x{n}" for name, n in sorted((counter or {}).items(), key=lambda kv: -kv[1])
    )


def _top_name(counter) -> str:
    """The name with the most votes: the suggestion to confirm or correct."""
    if not counter:
        return ""
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def extract_candidates(result, code: str) -> List[Tuple[str, int]]:
    """Return [(candidate_name, vote_count), ...] for the given speaker code."""
    if not code:
        return []
    votes = result.evidence.get(code) or []
    counter: Counter[str] = Counter(
        vote.speaker for vote in votes if getattr(vote, "speaker", None)
    )
    unproven = result.unproven.get(code) or {}
    for name, cnt in unproven.items():
        if name and name not in counter:
            counter[name] = cnt
    resolved = result.resolved.get(code) or ""
    resolved_order = {}
    if resolved:
        for idx, part in enumerate(resolved.split(NAME_SEPARATOR)):
            part = part.strip()
            if part:
                resolved_order[part] = idx
                if part not in counter:
                    counter[part] = 1
    return sorted(
        counter.items(),
        key=lambda kv: (-kv[1], resolved_order.get(kv[0], 999), kv[0]),
    )


def describe_code(result, code: str) -> str:
    """The evidence behind one code, as plain text for the right-hand pane."""
    if hasattr(result, "game_display_names") and code in (
        getattr(result, "game_display_names", ()) or ()
    ):
        return (
            f"{code}\n\n"
            "Real display name supplied directly by game data. Excluded from merge "
            "and not saved as an alias."
        )

    name = result.resolved.get(code)
    unproven = result.unproven.get(code)

    if name:
        head = [f"{code}  →  {name}", ""]
        if NAME_SEPARATOR in name:
            head += [
                "This voice is shared by more than one character. That is what "
                "the game does -- a pair of children, a street of townspeople "
                "and a coop of cuccos each speak with one voice -- and the "
                "lines below fall on different rows, so all of these names are "
                "kept rather than one being chosen over the others.",
                "",
            ]
    elif unproven:
        head = [
            f"{code}  →  suggested: {_top_name(unproven)}",
            "",
            "Too few matching lines to decide this on its own -- a single short "
            "line is said by half the cast. Read the line below: if it is "
            "unmistakably this character, keep the name and Apply. If not, type "
            "the right one over it, or clear it to leave the voice unnamed.",
            f"Votes: {_votes_line(unproven)}",
            "",
        ]
    else:
        return f"{code}\n\nNo script line matched this voice."

    votes = result.evidence.get(code) or []
    head.append(f"Decided from {len(votes)} matching script line(s):")
    head.append("")
    for vote in votes:
        where = " ".join(f"[Block {b} • String {s}]" for b, s in vote.rows)
        head.append(f"{vote.speaker}: {vote.text}")
        head.append(f"    {where}")
    return "\n".join(head)
