"""Subtitles for the opening monologue: timed text windows that run while its voice clip plays.

The script op 0x0053 at ``ANCHOR`` (``TEXT001.DAT``, offset 0x444E) starts the clip. Op 0x0052 follows it,
then the script waits for the voice to end. The subtitle messages go between the two. One message per
cue with text, in the cue order. A message shows its text for the cue's frames, then ``{close}`` closes
the window; the pause to the next cue follows the ``{close}`` inside the same message, so the window is
shut during the pause. The message ends with ``{end}`` (no button wait). A cue with an empty line adds
no message. Times and pauses come from ``subtitle_timing.Timing``.
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from . import codec, script, subtitle_timing
from .subtitle_timing import Timing

ANCHOR = 0x444E                        # op 0x0053 that starts the monologue clip (TEXT001.DAT)
FOLLOW = b"\x52\x00\x3f\x00"           # op 0x0052 with argument 0x3F, the next op of the original file
_PAUSE = r"\{F8:[0-9A-F]{2}\}"
_TIMING_TAG = re.compile(_PAUSE + r"|\{close\}|\{end\}")
# lead pauses | text | pauses before {close} | pauses after {close} | {end}
_PARTS = re.compile(r"^((?:%s)*)(.*?)((?:%s)*)\{close\}((?:%s)*)\{end\}$" % (_PAUSE, _PAUSE, _PAUSE), re.S)
_MAP_TOLERANCE = 2                     # frames a message may start away from its cue (a stale file)


def present(data: bytes, anchor: int = ANCHOR) -> bool:
    """True when the file has the clip-start op at ``anchor`` followed by the original op or subtitles."""
    if len(data) < anchor + 4 or data[anchor:anchor + 2] != b"\x53\x00":
        return False
    follow = data[anchor + 2:anchor + 6]
    return follow == FOLLOW or follow[:2] == b"\x02\x00"


def span(data: bytes, anchor: int = ANCHOR) -> Tuple[int, int]:
    """``(start, end)`` of the subtitle messages: the messages between the anchor op and the next op."""
    start = anchor + 2
    o = start
    while o < len(data) and data[o:o + 2] == b"\x02\x00":
        o += script.length(data, o)
    return start, o


def _pauses(frames: int) -> str:
    """``{F8:nn}`` tags for ``frames`` frames (one tag holds up to 255)."""
    tags = []
    while frames > 255:
        tags.append("{F8:FF}")
        frames -= 255
    if frames > 0:
        tags.append("{F8:%02X}" % frames)
    return "".join(tags)


def _sum_pauses(text: str) -> int:
    return sum(int(tag[4:6], 16) for tag in re.findall(_PAUSE, text))


def _message(body: str) -> bytes:
    raw = b"\x02\x00" + codec.Encoder().message(body)
    return raw + bytes(len(raw) & 1)


def build(lines: Sequence[str], timing: Optional[Timing] = None) -> bytes:
    """The subtitle messages for ``lines``, one per cue of ``timing`` (an empty line adds no message).

    The timeline runs in whole frames from the clip start. The first message waits for its cue with a
    pause before its text. Every later message starts when the previous one has closed and paused.
    The result is a multiple of 4 bytes long, so the code after it keeps its alignment.
    """
    timing = timing or subtitle_timing.defaults(len(lines))
    spans = timing.frames(len(lines))
    pieces: List[Tuple[str, int, int]] = [(text, a, b) for text, (a, b) in zip(lines, spans) if text.strip()]
    bodies = []
    for k, (text, a, b) in enumerate(pieces):
        head = _pauses(a) if k == 0 else ""
        tail = _pauses(max(0, pieces[k + 1][1] - b)) if k + 1 < len(pieces) else ""
        bodies.append(head + text + _pauses(max(0, b - a)) + "{close}" + tail + "{end}")
    out = b"".join(_message(body) for body in bodies)
    if len(out) % 4 and bodies:
        # the last message ended off the 4-byte grid: a zero-frame pause before its close adds two bytes
        bodies[-1] = bodies[-1].replace("{close}", "{F8:00}{close}", 1)
        out = b"".join(_message(body) for body in bodies)
    if len(out) % 4:
        raise script.ScriptError("subtitles do not fit the 4-byte alignment")
    if len(out) > 0xFFFF:
        raise ValueError("subtitles are too long for one script")
    return out


def _parse(data: bytes, anchor: int) -> List[Tuple[int, str]]:
    """``(begin frame, text)`` of each subtitle message, begin frames from the file's own pauses."""
    start, end = span(data, anchor)
    found: List[Tuple[int, str]] = []
    now = 0
    for text in script.parse(data):
        if not (start <= text.start < end and text.kind == script.MESSAGE):
            continue
        decoded = codec.decode_message(data, *text.strings[0])
        match = _PARTS.match(decoded)
        if match is None:
            raise ValueError("subtitle message with an unexpected form")
        begin = now + _sum_pauses(match.group(1))
        found.append((begin, _TIMING_TAG.sub("", match.group(2)).strip()))
        now = begin + _sum_pauses(match.group(3)) + _sum_pauses(match.group(4))
    return found


def _cue_of(found: List[Tuple[int, str]], starts: List[int]) -> Optional[List[int]]:
    """The cue index of each message (its nearest cue start), or None when that is not one to one."""
    index = []
    for begin, _text in found:
        i = min(range(len(starts)), key=lambda k: abs(starts[k] - begin))
        if abs(starts[i] - begin) > _MAP_TOLERANCE:
            return None
        index.append(i)
    return index if len(set(index)) == len(index) else None


def lines_of(data: bytes, timing: Optional[Timing] = None, anchor: int = ANCHOR) -> List[str]:
    """One line per cue of ``timing``: the message whose start is nearest to the cue's start.

    A file saved with another timing is read by the defaults; when neither fits, the messages are read
    in order. A cue without a message gets an empty line.
    """
    found = _parse(data, anchor)
    count = len(timing.cues) if timing is not None else len(subtitle_timing.SEGMENTS)
    timing = timing or subtitle_timing.defaults(count)
    lines = [""] * count
    for candidate in (timing, subtitle_timing.defaults(count)):
        index = _cue_of(found, [a for a, _b in candidate.frames(count)])
        if index is not None:
            for (_begin, text), i in zip(found, index):
                lines[i] = text
            return lines
    for i, (_begin, text) in enumerate(found[:count]):
        lines[i] = text
    return lines


def without(data: bytes, anchor: int = ANCHOR) -> bytes:
    """The file with its subtitle messages removed (the same bytes when there were none)."""
    start, end = span(data, anchor)
    return script.splice(data, start, end, b"") if end > start else bytes(data)


def with_lines(data: bytes, lines: Sequence[str], timing: Optional[Timing] = None, anchor: int = ANCHOR) -> bytes:
    """``data`` (with no subtitle messages) plus the subtitle messages of ``lines`` after the anchor op."""
    region = build(lines, timing) if any(text.strip() for text in lines) else b""
    return script.splice(data, anchor + 2, anchor + 2, region)
