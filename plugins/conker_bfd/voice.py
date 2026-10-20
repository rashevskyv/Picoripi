"""Voice and music streams of the bank 0x16 index: MPEG-2 Layer III frames with embedded ``L:`` cue records.

The walk reads frame headers only (no audio decoding). A cue is a nine-byte record: ``L:``, six bytes and a
null byte. The game reads a cue after a frame whose copyright bit is set. The walk stops at the first byte
that is neither a cue nor a frame header; the trailer after it (for example an ID3v1 tag) is kept as bytes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_BITRATES_V2_L3_KBPS = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]
_RATES_V2 = [22050, 24000, 16000, 0]
_CUE_PREFIX = b"L:"
_SAMPLES_PER_FRAME_V2_L3 = 576
_COPYRIGHT_BIT = 0x08


def frame_header(head: bytes) -> Optional[Dict[str, int]]:
    """Parse a four-byte MPEG-2 Layer III header. Returns None for anything else."""
    if len(head) < 4 or head[0] != 0xFF or (head[1] & 0xE0) != 0xE0:
        return None
    if (head[1] >> 3) & 3 != 2 or (head[1] >> 1) & 3 != 1:  # MPEG-2, Layer III
        return None
    kbps = _BITRATES_V2_L3_KBPS[(head[2] >> 4) & 15]
    rate = _RATES_V2[(head[2] >> 2) & 3]
    if kbps == 0 or rate == 0:
        return None
    pad = (head[2] >> 1) & 1
    return {
        "frame_length": 72 * kbps * 1000 // rate + pad,
        "sample_rate": rate,
        "bitrate_kbps": kbps,
        "channels": 1 if (head[3] >> 6) == 3 else 2,
    }


@dataclass
class Walk:
    frames: List[Tuple[int, int, bool]] = field(default_factory=list)  # (offset, length, copyright bit)
    cues: List[Tuple[int, bytes]] = field(default_factory=list)       # (frames before the cue, payload)
    end: int = 0                                                      # offset just after the last frame or cue
    first: Optional[Dict[str, int]] = None


def walk(data: bytes) -> Walk:
    result = Walk()
    pos = 0
    while pos + 4 <= len(data):
        if data[pos:pos + 2] == _CUE_PREFIX:
            nul = data.find(b"\x00", pos)
            if nul < 0:
                break
            result.cues.append((len(result.frames), bytes(data[pos:nul])))
            pos = nul + 1
            continue
        header = frame_header(data[pos:pos + 4])
        if header is None:
            break
        if result.first is None:
            result.first = header
        result.frames.append((pos, header["frame_length"], bool(data[pos + 3] & _COPYRIGHT_BIT)))
        pos += header["frame_length"]
    result.end = pos
    return result


@dataclass
class StreamInfo:
    frames: int = 0
    sample_rate: int = 0
    bitrate_kbps: int = 0
    channels: int = 0
    cues: List[bytes] = field(default_factory=list)
    trailer_bytes: int = 0

    @property
    def seconds(self) -> float:
        return self.frames * _SAMPLES_PER_FRAME_V2_L3 / self.sample_rate if self.sample_rate else 0.0


def describe(data: bytes) -> StreamInfo:
    found = walk(data)
    info = StreamInfo(frames=len(found.frames), cues=[payload for _, payload in found.cues],
                      trailer_bytes=len(data) - found.end)
    if found.first is not None:
        info.sample_rate = found.first["sample_rate"]
        info.bitrate_kbps = found.first["bitrate_kbps"]
        info.channels = found.first["channels"]
    return info


def splice_cues(original: bytes, encoded: bytes) -> bytes:
    """Rebuild a cue-free encoding with the cues of ``original`` at the same frame numbers.

    A cue goes after the frame with the same number (clamped to the new length). The frame before each cue
    gets the copyright bit, which the game needs before it reads a cue. The original trailer is appended.
    """
    source = walk(original)
    target = walk(encoded)
    if any(flag for _, _, flag in target.frames):
        raise ValueError("the encoded stream already has copyright bits set")
    cues_at: Dict[int, List[bytes]] = {}
    marked = set()
    for before, payload in source.cues:
        index = min(before, len(target.frames))
        cues_at.setdefault(index, []).append(payload)
        if index > 0:
            marked.add(index - 1)
    out = bytearray()
    for payload in cues_at.get(0, []):
        out += payload + b"\x00"
    for index, (offset, length, _) in enumerate(target.frames):
        frame = bytearray(encoded[offset:offset + length])
        if index in marked:
            frame[3] |= _COPYRIGHT_BIT
        out += frame
        for payload in cues_at.get(index + 1, []):
            out += payload + b"\x00"
    out += original[source.end:]
    return bytes(out)
