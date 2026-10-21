"""Subtitles for the opening monologue: timed text windows that run while its voice clip plays.

The script op 0x0053 at ``ANCHOR`` (``TEXT001.DAT``, offset 0x444E) starts the clip. Op 0x0052 follows it,
then the script waits for the voice to end. The subtitle messages go between the two: each one shows its
line for the speech segment's length, then closes the window without waiting for a button (``{end}``).
Pauses use the game's own pause control (``{F8:nn}``, nn frames). A segment with an empty line adds no
message. The lines are placed back by their start frame, so the editor keeps one line per segment.

The block holds one line per entry of ``SEGMENTS``. The times come from the speech of the clip.
"""
from __future__ import annotations

import re
from typing import List, Sequence, Tuple

from . import codec, script

ANCHOR = 0x444E                        # op 0x0053 that starts the monologue clip (TEXT001.DAT)
FOLLOW = b"\x52\x00\x3f\x00"           # op 0x0052 with argument 0x3F, the next op of the original file
FPS = 60                               # NTSC frames: the pause controls count frames
SEGMENTS: Tuple[Tuple[float, float], ...] = (      # (start, end) in seconds from the clip start
    (0.00, 2.20), (2.80, 6.25), (6.80, 8.80), (9.70, 10.20),
    (10.80, 13.25), (13.80, 17.20), (17.60, 23.15), (23.70, 28.45),
)
_PAUSE = r"\{F8:[0-9A-F]{2}\}"
_TIMING_TAG = re.compile(_PAUSE + r"|\{close\}|\{end\}")
_PARTS = re.compile(r"^((?:%s)*)(.*?)((?:%s)*)\{close\}\{end\}$" % (_PAUSE, _PAUSE), re.S)


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


def _frames(seconds: float) -> int:
    return round(seconds * FPS)


def _pauses(frames: int) -> str:
    """``{F8:nn}`` tags for ``frames`` frames (one tag holds up to 255)."""
    tags = []
    while frames > 255:
        tags.append("{F8:FF}")
        frames -= 255
    if frames > 0:
        tags.append("{F8:%02X}" % frames)
    return "".join(tags)


def _message(body: str) -> bytes:
    raw = b"\x02\x00" + codec.Encoder().message(body)
    return raw + bytes(len(raw) & 1)


def build(lines: Sequence[str], segments: Sequence[Tuple[float, float]] = SEGMENTS) -> bytes:
    """The subtitle messages for ``lines``, one per segment (an empty line adds no message).

    The timeline runs in whole frames from the clip start: a message pauses until its segment starts, shows
    its text for the segment's frames, then closes. The result is a multiple of 4 bytes long, so the code
    after it keeps its alignment.
    """
    if len(lines) != len(segments):
        raise ValueError(f"{len(segments)} subtitle lines expected, got {len(lines)}")
    pieces: List[Tuple[str, int, int]] = []           # (text, pause frames before, shown frames)
    now = 0
    for text, (start, end) in zip(lines, segments):
        first, last = _frames(start), _frames(end)
        if text.strip():
            pieces.append((text, first - now, last - first))
            now = last                                # the game's clock runs through shown messages only
    bodies = [_pauses(before) + text + _pauses(shown) + "{close}{end}" for text, before, shown in pieces]
    out = b"".join(_message(body) for body in bodies)
    if len(out) % 4 and bodies:
        # the last message ended off the 4-byte grid: a zero-frame pause before its close adds two bytes
        last = bodies[-1].replace("{close}{end}", "{F8:00}{close}{end}")
        out = b"".join(_message(body) for body in bodies[:-1]) + _message(last)
    if len(out) % 4:
        raise script.ScriptError("subtitles do not fit the 4-byte alignment")
    if len(out) > 0xFFFF:
        raise ValueError("subtitles are too long for one script")
    return out


def lines_of(data: bytes, anchor: int = ANCHOR) -> List[str]:
    """One line per segment. A message belongs to the segment its timeline reaches, so empty segments
    (which have no message) keep their place."""
    start, end = span(data, anchor)
    lines = [""] * len(SEGMENTS)
    now = 0
    for text in script.parse(data):
        if not (start <= text.start < end and text.kind == script.MESSAGE):
            continue
        decoded = codec.decode_message(data, *text.strings[0])
        match = _PARTS.match(decoded)
        if match is None:
            raise ValueError("subtitle message with an unexpected form")
        before = sum(int(tag[4:6], 16) for tag in re.findall(_PAUSE, match.group(1)))
        after = sum(int(tag[4:6], 16) for tag in re.findall(_PAUSE, match.group(3)))
        begin = now + before
        now = begin + after
        index = min(range(len(SEGMENTS)), key=lambda i: abs(_frames(SEGMENTS[i][0]) - begin))
        lines[index] = _TIMING_TAG.sub("", match.group(2)).strip()
    return lines


def without(data: bytes, anchor: int = ANCHOR) -> bytes:
    """The file with its subtitle messages removed (the same bytes when there were none)."""
    start, end = span(data, anchor)
    return script.splice(data, start, end, b"") if end > start else bytes(data)


def with_lines(data: bytes, lines: Sequence[str], anchor: int = ANCHOR) -> bytes:
    """``data`` (with no subtitle messages) plus the subtitle messages of ``lines`` after the anchor op."""
    region = build(lines) if any(text.strip() for text in lines) else b""
    return script.splice(data, anchor + 2, anchor + 2, region)
