"""Build a correspondence between raw source lines (left pane) and standardized
output lines (right pane), so the Studio can sync the two panes by *content*
rather than by scrollbar percentage.

Mode-agnostic: it matches by normalized text, so it works whether the output was
produced by the custom recipe engine or by Picoripi's own parser.
"""
from __future__ import annotations

import re
import bisect
from typing import Dict, List, Optional


def _norm(s: str) -> str:
    """Reduce a line to comparable alphanumerics (case/space/punct-insensitive)."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _output_candidates(line: str) -> List[str]:
    """Possible 'core texts' an output line could correspond to in the source."""
    s = (line or "").strip()
    if not s:
        return []
    cands: List[str] = []
    if s.startswith("### Location:"):
        cands.append(s.split(":", 1)[1])
    elif s.startswith("#"):
        cands.append(s.lstrip("#").strip())
    elif s.startswith("{Action:") and s.endswith("}"):
        cands.append(s[len("{Action:"):-1])
    elif ": " in s:
        cands.append(s.split(": ", 1)[1])   # after 'SPEAKER: '
    cands.append(s)                          # whole line (bare source / markers)
    return cands


def build_line_map(raw_lines: List[str], output_lines: List[str]) -> Dict[int, int]:
    """Return {source_line_index0 -> output_line_index0} by matching text.

    First occurrence wins on both sides, which is the right behaviour for
    scroll/click sync (we want the first place a line appears)."""
    src_index: Dict[str, int] = {}
    for i, ln in enumerate(raw_lines):
        key = _norm(ln)
        if key and key not in src_index:
            src_index[key] = i

    src_to_out: Dict[int, int] = {}
    for o, ln in enumerate(output_lines):
        for cand in _output_candidates(ln):
            key = _norm(cand)
            if not key:
                continue
            si = src_index.get(key)
            if si is not None and si not in src_to_out:
                src_to_out[si] = o
                break
    return src_to_out


def nearest_output(src_to_out: Dict[int, int], mapped_sorted: List[int], src_idx: int) -> Optional[int]:
    """Output line for a source line: exact match, else the nearest mapped line
    at or before it (so clicking dropped narration still lands near its context)."""
    if not src_to_out:
        return None
    if src_idx in src_to_out:
        return src_to_out[src_idx]
    i = bisect.bisect_right(mapped_sorted, src_idx) - 1
    if i >= 0:
        return src_to_out[mapped_sorted[i]]
    return src_to_out[mapped_sorted[0]]
