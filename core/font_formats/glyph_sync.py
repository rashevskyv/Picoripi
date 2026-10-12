"""Copy glyph changes between two identical copies of a bitmap font, by character code, in order of change.

Two copies are identical when they have the same format, the same cell size and the same code-to-glyph layout
(pixels and widths may differ). Only identical copies are linked: a different cell size or format is never a
candidate, so no scaling is done.

A change is a glyph whose content (cell pixels, kerning, width) differs from the copy as it was loaded. Each change
is recorded with a time in ``font_sync.json`` (the state file): the latest change per code wins everywhere, and a
revert is a change too. On save, a copy first takes the newer glyphs of its partner (for codes it did not change
itself), then writes; then its own latest changes are copied to the partner. A copy with no change of its own
copies nothing, so an old drawing cannot come back after a revert in the other copy.

Pure: works on the editor's model ``(metadata, sheets)`` (RGBA sheets) and on plain dicts. The caller reads and
writes the files.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.font_formats import Metadata, Sheets, char_map

Model = Tuple[Metadata, Sheets]
STATE_FILE = "font_sync.json"
LOG_LIMIT = 5000


def _cell_box(metadata: Metadata, glyph: int):
    """``(sheet, x, y, cell width, cell height)`` of a glyph in the GLY1 grid, or None."""
    for gly in metadata.get("GLY1", []):
        start, end = gly["start_glyph"], gly["end_glyph"]
        if not start <= glyph <= end:
            continue
        columns, rows = gly["glyph_horizontal_count"], gly["glyph_vertical_count"]
        sheet, cell = divmod(glyph - start, columns * rows)
        width, height = gly["cell_width"], gly["cell_height"]
        return sheet, (cell % columns) * width, (cell // columns) * height, width, height
    return None


def _packet(metadata: Metadata, glyph: int) -> Optional[Dict[str, int]]:
    """The WID1 packet (kerning, width) of a glyph, or None."""
    for block in metadata.get("WID1", []):
        first, packets = block["first_code_included"], block["packets"]
        if first <= glyph < first + len(packets):
            return packets[glyph - first]
    return None


def cell_size(metadata: Metadata) -> Optional[Tuple[int, int]]:
    """The cell size of the font's glyph grid, or None when it has no grid."""
    gly = metadata.get("GLY1") or []
    return (gly[0]["cell_width"], gly[0]["cell_height"]) if gly else None


def identical(a: Model, b: Model, format_a: str, format_b: str) -> bool:
    """True when two copies share the format, the cell size and the code-to-glyph layout."""
    if format_a != format_b or cell_size(a[0]) is None or cell_size(a[0]) != cell_size(b[0]):
        return False
    return char_map(a[0]) == char_map(b[0])


def glyph_hashes(model: Model) -> Dict[str, str]:
    """Content hash per mapped code (cell pixels, cell size, kerning and width). Codes without a cell are left out."""
    metadata, sheets = model
    hashes: Dict[str, str] = {}
    for char, glyph in char_map(metadata).items():
        box = _cell_box(metadata, glyph)
        packet = _packet(metadata, glyph)
        if box is None or packet is None or box[0] >= len(sheets):
            continue
        sheet, x, y, width, height = box
        cell = sheets[sheet].crop((x, y, x + width, y + height)).tobytes()
        digest = hashlib.sha256()
        digest.update(f"{width}x{height}:{packet['kerning']}:{packet['width']}:".encode("ascii"))
        digest.update(cell)
        hashes[char] = digest.hexdigest()
    return hashes


def dirty_codes(loaded: Dict[str, str], model: Model) -> List[str]:
    """The codes whose glyph differs from the copy as it was loaded (``loaded`` = its glyph hashes then)."""
    now = glyph_hashes(model)
    return sorted(char for char in set(now) | set(loaded) if now.get(char) != loaded.get(char))


def copy_glyph(into: Model, owner: Model, char: str) -> None:
    """Write the owner's glyph for ``char`` (cell pixels, kerning, width) into ``into``, in place."""
    metadata, sheets = owner
    target_meta, target_sheets = into
    glyph = char_map(metadata)[char]
    target = char_map(target_meta)[char]
    sheet, x, y, width, height = _cell_box(metadata, glyph)
    cell = sheets[sheet].crop((x, y, x + width, y + height))
    t_sheet, t_x, t_y, _w, _h = _cell_box(target_meta, target)
    target_sheets[t_sheet].paste(cell, (t_x, t_y))
    packet, target_packet = _packet(metadata, glyph), _packet(target_meta, target)
    target_packet["kerning"], target_packet["width"] = packet["kerning"], packet["width"]


# -- the state file ----------------------------------------------------------------------------------

def new_state() -> Dict[str, Any]:
    return {"version": 1, "latest": {}, "log": []}


def pair_key(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


def load_state(path: Path) -> Dict[str, Any]:
    """The state file, or a new state when there is none."""
    if not Path(path).is_file():
        return new_state()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError(f"{path}: unknown font sync version {data.get('version')!r}")
    return data


def save_state(path: Path, state: Dict[str, Any]) -> None:
    from utils.atomic_io import atomic_write_json

    atomic_write_json(Path(path), state, ensure_ascii=False, indent=1)


def record_changes(state: Dict[str, Any], font: str, codes: Iterable[str], hashes: Dict[str, str], now: float) -> None:
    """Make ``font``'s glyphs for ``codes`` the latest changes, and log them. A code with no glyph is not recorded."""
    for char in codes:
        if char not in hashes:
            continue
        state["latest"][char] = {"font": font, "time": now, "hash": hashes[char]}
        state["log"].append({"font": font, "code": char, "time": now, "hash": hashes[char]})
    del state["log"][:-LOG_LIMIT]


def carry(state: Dict[str, Any], owner: str, owner_model: Model, into: str, into_model: Model,
          skip: Iterable[str] = ()) -> Tuple[Model, List[str]]:
    """``into_model`` with every latest change of ``owner`` that it lacks, and the codes copied.

    A code in ``skip`` (changed by ``into`` itself) is not touched. The owner's glyph must still hold the hash that
    was recorded for it, otherwise it is not copied.
    """
    skip = set(skip)
    owner_hashes = glyph_hashes(owner_model)
    into_hashes = glyph_hashes(into_model)
    wanted = [char for char, entry in sorted(state["latest"].items())
              if entry["font"] == owner and char not in skip and char in owner_hashes
              and owner_hashes[char] == entry["hash"] and into_hashes.get(char) != entry["hash"]]
    if not wanted:
        return into_model, []
    result: Model = (copy.deepcopy(into_model[0]), [sheet.copy() for sheet in into_model[1]])
    for char in wanted:
        copy_glyph(result, owner_model, char)
    return result, wanted


def pair_enabled(pairs: Dict[str, Dict[str, Any]], a: str, b: str) -> bool:
    """Whether the user copies changes between two copies. ``pairs`` is the project's ``font_sync_pairs`` mapping;
    a pair is off until the user turns it on."""
    return bool(pairs.get(pair_key(a, b), {}).get("enabled", False))


def set_pair(pairs: Dict[str, Dict[str, Any]], a: str, b: str, enabled: bool, prompted: bool = True) -> None:
    """Turn a pair on or off in the project's ``font_sync_pairs`` mapping (``prompted``: the one-time question was shown)."""
    entry = pairs.setdefault(pair_key(a, b), {})
    entry["enabled"] = bool(enabled)
    entry["prompted"] = bool(prompted)
