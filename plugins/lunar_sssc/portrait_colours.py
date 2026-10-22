"""Portrait colours of ``FACE_*.TIZ`` read from a reference sprite sheet (pure logic, no Qt).

A TIZ frame keeps its palette indices; the sheet keeps the colours. Each frame is matched to the sheet cell whose
opaque pixels agree with the frame's non-zero indices, and whose colour is the same for every pixel with one index.
Matched frames of one TIZ file vote an index -> screen RGB table. The shipped table is
``face_palettes.json``, built by ``scripts/lunar_portrait_colours.py``. Indices without a vote keep the palette fallback.
"""
from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

import numpy as np

from . import dialogue_preview as dp

CELL = dp.PORTRAIT
OPAQUE_ALPHA = 128
MATCH_MIN = 0.95          # colour consistency and mask agreement must both reach this
CANDIDATES = 60           # cells checked for colour per frame (best by mask agreement)
COLOURS_FILE = "portrait_colours.json"

Colours = Dict[str, Dict[int, Tuple[int, int, int]]]


class Cell(NamedTuple):
    """A sheet cell: top-left (x, y), the score (consistency * mask agreement) and its two parts."""

    x: int
    y: int
    score: float
    consistency: float
    mask: float


class SheetIndex:
    """Sheet RGBA array prepared for matching: opaque mask, packed colours and a mask correlation."""

    def __init__(self, sheet: np.ndarray):
        if sheet.ndim != 3 or sheet.shape[2] != 4:
            raise ValueError("the sheet must be an RGBA image")
        self.height, self.width = sheet.shape[:2]
        self.opaque = sheet[:, :, 3] >= OPAQUE_ALPHA
        rgb = sheet[:, :, :3].astype(np.uint32)
        self.key = (rgb[:, :, 0] << 16) | (rgb[:, :, 1] << 8) | rgb[:, :, 2]
        self._sum = np.zeros((self.height + 1, self.width + 1), np.int64)
        self._sum[1:, 1:] = self.opaque.astype(np.int64).cumsum(0).cumsum(1)
        self._spectrum = np.fft.rfft2(self.opaque.astype(np.float64), s=(self.height, self.width))

    def _window_sums(self) -> np.ndarray:
        s = self._sum
        p = CELL
        return s[p:, p:] - s[:-p, p:] - s[p:, :-p] + s[:-p, :-p]

    def best_cell(self, indices: np.ndarray) -> Optional[Cell]:
        """The sheet cell that best matches a 64x64 index array, or None when nothing reaches MATCH_MIN."""
        indices = indices.reshape(CELL, CELL)
        frame = indices > 0
        if not frame.any():
            return None
        padded = np.zeros((self.height, self.width))
        padded[:CELL, :CELL] = frame
        corr = np.fft.irfft2(self._spectrum * np.conj(np.fft.rfft2(padded, s=(self.height, self.width))),
                             s=(self.height, self.width))
        corr = np.rint(corr[:self.height - CELL + 1, :self.width - CELL + 1])
        agree = CELL * CELL - (int(frame.sum()) + self._window_sums() - 2 * corr)
        best: Optional[Cell] = None
        for flat in np.argsort(agree.ravel())[::-1][:CANDIDATES]:
            y, x = divmod(int(flat), self.width - CELL + 1)
            cell = self._score(indices, x, y, int(agree[y, x]) / (CELL * CELL))
            if cell is not None and (best is None or cell.score > best.score):
                best = cell
        if best is None or best.consistency < MATCH_MIN or best.mask < MATCH_MIN:
            return None
        return best

    def _score(self, indices: np.ndarray, x: int, y: int, mask: float) -> Optional[Cell]:
        both = (indices > 0) & self.opaque[y:y + CELL, x:x + CELL]
        total = int(both.sum())
        if total == 0:
            return None
        ids = indices[both].astype(np.uint64)
        keys = (ids << np.uint64(24)) | self.key[y:y + CELL, x:x + CELL][both].astype(np.uint64)
        unique, counts = np.unique(keys, return_counts=True)
        groups = unique >> np.uint64(24)
        starts = np.flatnonzero(np.r_[True, groups[1:] != groups[:-1]])
        consistency = float(np.maximum.reduceat(counts, starts).sum()) / total
        return Cell(x, y, consistency * mask, consistency, mask)


def frames_of(member: bytes) -> List[np.ndarray]:
    """The five 64x64 index arrays of a TIZ member."""
    frames = dp.inflate_member(member)
    return [np.frombuffer(dp.decode_frame(frames, frame), np.uint8).reshape(CELL, CELL)
            for frame in range(dp.FRAMES_PER_FILE)]


def match_file(files: Dict[str, bytes], sheet: SheetIndex) -> Dict[str, Dict[int, Cell]]:
    """Matched cells of every frame of every member: {member: {frame: Cell}} (unmatched frames are absent)."""
    result: Dict[str, Dict[int, Cell]] = {}
    for name in sorted(files):
        for frame, indices in enumerate(frames_of(files[name])):
            cell = sheet.best_cell(indices)
            if cell is not None:
                result.setdefault(name, {})[frame] = cell
    return result


def vote(files: Dict[str, bytes], sheet_rgba: np.ndarray, matches: Dict[str, Dict[int, Cell]]) -> Colours:
    """Index -> screen RGB per member by majority vote over the matched frames' opaque pixels."""
    colours: Colours = {}
    for name, cells in matches.items():
        counts: Dict[int, Counter] = {}
        frames = frames_of(files[name])
        for frame, cell in cells.items():
            indices = frames[frame]
            opaque = sheet_rgba[cell.y:cell.y + CELL, cell.x:cell.x + CELL, 3] >= OPAQUE_ALPHA
            rgb = sheet_rgba[cell.y:cell.y + CELL, cell.x:cell.x + CELL, :3]
            for value, pixel in zip(indices[opaque & (indices > 0)].tolist(), rgb[opaque & (indices > 0)].tolist()):
                counts.setdefault(value, Counter())[tuple(pixel)] += 1
        colours[name] = {value: screen_rgb(c.most_common(1)[0][0]) for value, c in sorted(counts.items())}
    return colours


def screen_rgb(sheet_rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """The colour the console shows for a sheet colour.

    The sheet holds PS1 5-bit channels times 8 (a value 1 higher in some channels). The console widens a 5-bit
    channel to 8 bits by copying its top bits into the low bits: (v << 3) | (v >> 2).
    """
    out = []
    for channel in sheet_rgb:
        v = channel >> 3
        out.append((v << 3) | (v >> 2))
    return out[0], out[1], out[2]


def write_colours(path: Path, colours: Colours) -> None:
    """Write the colour table as {member: {index: "#rrggbb"}} with an atomic replace."""
    data = {name: {str(value): "#%02x%02x%02x" % rgb for value, rgb in table.items()}
            for name, table in sorted(colours.items())}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, separators=(",", ":"))
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def read_colours(path: Path) -> Colours:
    """The colour table written by ``write_colours``; empty when the file is absent."""
    return dp.load_colour_table(path)
