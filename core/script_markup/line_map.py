"""Map raw source lines to standardized output lines for Studio sync."""
from __future__ import annotations

import bisect
import re
from typing import Dict, List, Optional


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _output_candidates(line: str) -> List[str]:
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
        cands.append(s.split(": ", 1)[1])
    cands.append(s)
    return cands


def build_line_map(raw_lines: List[str], output_lines: List[str]) -> Dict[int, int]:
    src_index: Dict[str, int] = {}
    for i, line in enumerate(raw_lines):
        key = _norm(line)
        if key and key not in src_index:
            src_index[key] = i

    src_to_out: Dict[int, int] = {}
    for output_idx, line in enumerate(output_lines):
        for candidate in _output_candidates(line):
            key = _norm(candidate)
            if not key:
                continue
            source_idx = src_index.get(key)
            if source_idx is not None and source_idx not in src_to_out:
                src_to_out[source_idx] = output_idx
                break
    return src_to_out


def nearest_output(
    src_to_out: Dict[int, int],
    mapped_sorted: List[int],
    src_idx: int,
) -> Optional[int]:
    if not src_to_out:
        return None
    if src_idx in src_to_out:
        return src_to_out[src_idx]
    idx = bisect.bisect_right(mapped_sorted, src_idx) - 1
    if idx >= 0:
        return src_to_out[mapped_sorted[idx]]
    return src_to_out[mapped_sorted[0]]
