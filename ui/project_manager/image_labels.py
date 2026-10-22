"""The images a game plugin opens, as lines of text for the New Project wizard and the Project Manager row."""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from core.i18n import tr

_KIND_LABELS = {
    "disc": "Disc ID", "title": "Title ID", "code": "Product code", "serial": "Serial", "name": "ROM name",
    "hash": "SHA-1 of the ROM", "unchecked": "Not checked by ID", "any": "Any file",
}


def kind_label(kind: str) -> str:
    """The translated name of an id kind (``disc``, ``title``...)."""
    return tr(_KIND_LABELS[kind]) if kind in _KIND_LABELS else kind


def region_label(region: str) -> str:
    """The region as written; an empty or unstated region and "All regions" are translated."""
    if not region or region == "Not stated":
        return tr("Region not stated")
    if region == "All regions":
        return tr("All regions")
    return region


def summary_lines(entries: Sequence[Dict[str, Any]]) -> List[str]:
    """One line per declaration; the ROM hashes of a plugin share one line with their versions."""
    lines: List[str] = []
    hashes = [item for item in entries if item.get("kind") == "hash"]
    for item in entries:
        kind, ident = str(item.get("kind") or ""), str(item.get("id") or "")
        region, note = str(item.get("region") or ""), str(item.get("note") or "")
        if kind == "hash":
            continue
        if kind in ("any", "unchecked"):
            lines.append(f"{kind_label(kind)}: {region_label(region)}" if region else kind_label(kind))
            continue
        text = f"{kind_label(kind)} {ident}, {region_label(region)}"
        lines.append(f"{text} ({note})" if note else text)
    if hashes:
        names = ", ".join(str(item.get("note") or item.get("region") or "") for item in hashes)
        lines.append(tr("{0} ROM versions: {1}", len(hashes), names))
    return lines
