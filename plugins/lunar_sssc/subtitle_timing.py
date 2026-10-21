"""Timing of the opening monologue's subtitle cues: when each line shows and the pauses between the lines.

A cue is one subtitle line. It shows from ``start`` to ``end``, in whole frames (60 Hz) from the speech onset
of the clip. The pause after a cue is the next cue's start minus this cue's end; the box is closed during it.
``offset`` is the delay in frames from the clip-start op to the speech onset, and it moves every cue. The
editor shows seconds with 0.01 precision. The file is ``translation\\voice\\subtitle_timing.json``; without it
the built-in timing (``SEGMENTS``) applies.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

FPS = 60                    # NTSC frames: the game's pause control counts frames
READING_SPEED = 20.0        # characters per second a cue must allow (a shorter cue is a problem)
TIMING_FILE = "subtitle_timing.json"
TIMING_FORMAT = 1
# voice.speech_spans of the original clip (fraction 0.05, min_silence 0.4 s, min_speech 0.5 s), in seconds
SEGMENTS_SECONDS: Tuple[Tuple[float, float], ...] = (
    (0.00, 2.20), (2.80, 6.25), (6.80, 8.80), (9.70, 10.20),
    (10.80, 13.25), (13.80, 17.20), (17.60, 23.15), (23.70, 28.45),
)
SEGMENTS: Tuple[Tuple[int, int], ...] = tuple((round(a * FPS), round(b * FPS)) for a, b in SEGMENTS_SECONDS)
_TAG = re.compile(r"\{[^}]*\}")


def seconds(frames: int) -> float:
    """Frames as seconds (for display: two decimals)."""
    return round(frames / FPS, 2)


def frames_of(value: float) -> int:
    """Seconds as the nearest whole frame."""
    return round(float(value) * FPS)


@dataclass(frozen=True)
class Cue:
    start: int              # frames from the speech onset
    end: int


@dataclass(frozen=True)
class Timing:
    offset: int             # frames from the clip-start op to the speech onset
    cues: Tuple[Cue, ...]

    def fitted(self, count: int) -> Tuple[Cue, ...]:
        """The cues, cut or padded to ``count``; a padded cue has no length, at the last end."""
        cues = list(self.cues[:count])
        last = cues[-1].end if cues else 0
        cues += [Cue(last, last)] * (count - len(cues))
        return tuple(cues)

    def frames(self, count: int) -> List[Tuple[int, int]]:
        """``(start, end)`` of each cue in frames from the clip-start op, for ``count`` cues."""
        out = []
        for cue in self.fitted(count):
            a = self.offset + cue.start
            out.append((a, max(a, self.offset + cue.end)))
        return out


def defaults(count: int = len(SEGMENTS)) -> Timing:
    """The built-in timing: the speech spans of the original clip, for ``count`` cues."""
    return Timing(0, tuple(Cue(a, b) for a, b in SEGMENTS[:count]))


def _int(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"subtitle timing: {what} is not a whole number of frames")
    return value


def from_json(obj: object) -> Timing:
    """The timing of a parsed JSON file; ValueError for any other shape."""
    if not isinstance(obj, dict) or not isinstance(obj.get("cues"), list):
        raise ValueError("subtitle timing: expected an object with a 'cues' list")
    cues = []
    for item in obj["cues"]:
        if not isinstance(item, dict):
            raise ValueError("subtitle timing: a cue is not an object")
        start = _int(item.get("start_frame"), "start")
        end = _int(item.get("end_frame"), "end")
        if end < start:
            raise ValueError("subtitle timing: a cue ends before it starts")
        cues.append(Cue(start, end))
    return Timing(_int(obj.get("offset_frames", 0), "offset"), tuple(cues))


def to_json(timing: Timing) -> dict:
    return {
        "format": TIMING_FORMAT,
        "offset_frames": timing.offset,
        "cues": [{"start_frame": c.start, "end_frame": c.end} for c in timing.cues],
    }


def read_file(path: str | Path) -> Optional[Timing]:
    """The saved timing, or None when there is no file. ValueError for a file that is not timing."""
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return from_json(json.loads(p.read_text(encoding="utf-8")))
    except json.JSONDecodeError as error:
        raise ValueError(f"subtitle timing: {p.name} is not JSON ({error})") from error


def write_file(path: str | Path, timing: Timing) -> None:
    """Write the timing atomically: a temporary file in the same folder, then ``os.replace``."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(to_json(timing), f, indent=2)
            f.write("\n")
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def from_spans(spans: Sequence[Tuple[float, float]], offset: int = 0) -> Timing:
    """A timing with one cue per speech span given in seconds (the editor's reset)."""
    return Timing(offset, tuple(Cue(frames_of(a), frames_of(b)) for a, b in spans))


def reading_seconds(text: str) -> float:
    """Seconds a reader needs for ``text`` (tags are not read)."""
    return len(_TAG.sub("", text).strip()) / READING_SPEED


def problems(timing: Timing, texts: Sequence[str], duration: Optional[float] = None) -> List[tuple]:
    """Problems of the timing for these cue texts, as tuples the editor words:
    ``("count", lines, cues)``, ``("overlap", i)``, ``("short", i, seconds_needed)``, ``("past_end", i)``.
    ``duration`` is the clip length in seconds."""
    out: List[tuple] = []
    if len(texts) != len(timing.cues):
        out.append(("count", len(texts), len(timing.cues)))
    prev_end: Optional[int] = None
    for i, cue in enumerate(timing.fitted(len(texts))):
        if prev_end is not None and cue.start < prev_end:
            out.append(("overlap", i))
        prev_end = cue.end
        need = reading_seconds(texts[i])
        if need > 0 and (cue.end - cue.start) / FPS < need - 1e-9:
            out.append(("short", i, round(need, 2)))
        if duration is not None and (timing.offset + cue.end) / FPS > duration + 1e-9:
            out.append(("past_end", i))
    return out


# ---------------------------------------------------------------- editing (pure; the editor calls these)

def move(timing: Timing, index: int, delta: int) -> Timing:
    """Move cue ``index`` by ``delta`` frames. It keeps its length and stays after the previous cue's end."""
    cues = list(timing.cues)
    cue = cues[index]
    length = cue.end - cue.start
    lo = cues[index - 1].end if index > 0 else 0
    hi = cues[index + 1].start - length if index + 1 < len(cues) else cue.start + delta
    start = min(max(cue.start + delta, lo), max(lo, hi))
    cues[index] = Cue(start, start + length)
    return Timing(timing.offset, tuple(cues))


def set_edge(timing: Timing, index: int, edge: str, frame: int) -> Timing:
    """Set the ``start`` or the ``end`` of cue ``index``; it stays between its neighbours, at least 1 frame long."""
    cues = list(timing.cues)
    cue = cues[index]
    frame = max(0, int(frame))
    if edge == "start":
        lo = cues[index - 1].end if index > 0 else 0
        cues[index] = Cue(min(max(frame, lo), cue.end - 1), cue.end)
    else:
        hi = cues[index + 1].start if index + 1 < len(cues) else frame
        cues[index] = Cue(cue.start, max(min(frame, hi), cue.start + 1))
    return Timing(timing.offset, tuple(cues))


def split(timing: Timing, index: int) -> Timing:
    """Cue ``index`` becomes two cues of half its length (the translator splits the text too)."""
    cues = list(timing.cues)
    cue = cues[index]
    mid = (cue.start + cue.end) // 2
    cues[index:index + 1] = [Cue(cue.start, mid), Cue(mid, cue.end)]
    return Timing(timing.offset, tuple(cues))


def merge(timing: Timing, index: int) -> Timing:
    """Cue ``index + 1`` joins cue ``index`` (the text of the removed cue must be empty first)."""
    cues = list(timing.cues)
    cues[index:index + 2] = [Cue(cues[index].start, cues[index + 1].end)]
    return Timing(timing.offset, tuple(cues))
