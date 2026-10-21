"""PS1 CD-XA ADPCM for the Lunar voice channel: mono, 37.8 kHz, 4-bit, one sector = 4032 samples.

A Form 2 audio sector holds 18 sound groups of 128 bytes at raw offset 0x18: 16 parameter bytes (one per
unit, shift in the low nibble and filter in the high nibble: units 0-3 at bytes 0-3, units 4-7 at bytes
8-11, each copied 4 bytes later; see ``_param_at``), then 28 rows of 4 bytes.
Row i holds one nibble per unit (unit u in byte u >> 1, low nibble for even u). Unit u holds 28 samples in
row order, and the 8 units of a group follow each other in time. Each sample is
``(nibble << 12) >> shift`` plus a prediction from the two previous decoded samples (filter 0..3).

The filter history runs across sectors: a decoder or an encoder must keep ``state`` from one sector to the
next. ``encode_clip`` searches all four filters and all shifts of each unit and keeps the one with the
least squared error against the decoded result (the same arithmetic as ``decode_sector``).
"""
from __future__ import annotations

from typing import List, Sequence

RATE = 37800
UNITS = 8
UNIT_SAMPLES = 28
GROUP_SAMPLES = UNITS * UNIT_SAMPLES        # 224
GROUPS = 18
SECTOR_SAMPLES = GROUP_SAMPLES * GROUPS    # 4032
RAW = 2352
AUDIO = 0x18                               # first audio byte of a raw Form 2 sector
AUDIO_LEN = GROUPS * 128                   # 2304
EDC_AT = 0x92C                             # Form 2 EDC, over raw bytes 0x10 .. 0x92B
_POS = (0, 60, 115, 98, 122)
_NEG = (0, 0, -52, -55, -60)
_EDC = []
for _i in range(256):
    _r = _i
    for _ in range(8):
        _r = (_r >> 1) ^ (0xD8018001 if _r & 1 else 0)
    _EDC.append(_r)


class XaError(ValueError):
    """A sector or sample list this codec cannot read or write."""


def _clamp(v: int) -> int:
    return max(-32768, min(32767, v))


def _param_at(unit: int) -> int:
    """Byte of the group's parameter block that holds ``unit``'s parameter: units 0-3 at bytes 0-3, units
    4-7 at bytes 8-11; the same byte + 4 holds the copy (bytes 4-7 and 12-15)."""
    return unit if unit < 4 else unit + 4


def edc(data: bytes) -> int:
    value = 0
    for byte in data:
        value = (value >> 8) ^ _EDC[(value ^ byte) & 0xFF]
    return value


def is_audio(raw: bytes) -> bool:
    """True for a Form 2 sector with the audio bit set in its submode."""
    return len(raw) == RAW and bool(raw[0x12] & 0x04) and bool(raw[0x12] & 0x20)


def subheader(raw: bytes):
    """(file, channel, submode, coding) of a raw sector."""
    return raw[0x10], raw[0x11], raw[0x12], raw[0x13]


def decode_sector(raw: bytes, state: List[int]) -> List[int]:
    """The 4032 mono samples of one audio sector. ``state`` = [previous, older] decoded sample (kept)."""
    if len(raw) != RAW:
        raise XaError("not a raw sector")
    out: List[int] = []
    for g in range(GROUPS):
        base = AUDIO + g * 128
        params = raw[base:base + 16]
        data = raw[base + 16:base + 128]
        for u in range(UNITS):
            p = params[_param_at(u)]
            shift, filt = p & 0x0F, (p >> 4) & 0x0F
            if shift > 12:
                shift = 9
            for i in range(UNIT_SAMPLES):
                byte = data[i * 4 + (u >> 1)]
                nib = (byte >> 4) & 0xF if u & 1 else byte & 0xF
                s = nib - 16 if nib >= 8 else nib
                s = (s << 12) >> shift
                v = _clamp(s + ((state[0] * _POS[filt] + state[1] * _NEG[filt] + 32) >> 6))
                state[1], state[0] = state[0], v
                out.append(v)
    return out


def decode_clip(sectors: Sequence[bytes]) -> List[int]:
    """All samples of consecutive audio sectors, with one filter history."""
    state = [0, 0]
    out: List[int] = []
    for raw in sectors:
        out.extend(decode_sector(raw, state))
    return out


def _search_unit(unit: Sequence[int], state: List[int]):
    """Best (error, filter, shift, nibbles, decoded) of one unit against the history in ``state``."""
    best = None
    for filt in range(4):
        pos, neg = _POS[filt], _NEG[filt]
        for shift in range(12, -1, -1):
            step = 1 << (12 - shift)
            o1, o2 = state[0], state[1]
            err = 0
            nibs = []
            dec = []
            for x in unit:
                pred = (o1 * pos + o2 * neg + 32) >> 6
                nib = max(-8, min(7, round((x - pred) / step)))
                v = _clamp(nib * step + pred)
                err += (x - v) * (x - v)
                nibs.append(nib)
                dec.append(v)
                o2, o1 = o1, v
            if best is None or err < best[0]:
                best = (err, filt, shift, nibs, dec)
    return best


def encode_clip(samples: Sequence[int], sectors: int) -> List[bytes]:
    """Audio bytes (2304 each) for ``sectors`` sectors holding ``samples`` (silence after them).

    Raises XaError if the samples do not fit. Encoding keeps the filter history across sectors, the same
    as the decoder, so ``decode_clip`` of the result gives back what the encoder decoded.
    """
    if len(samples) > sectors * SECTOR_SAMPLES:
        raise XaError("more samples than the sectors hold")
    pcm = list(samples) + [0] * (sectors * SECTOR_SAMPLES - len(samples))
    state = [0, 0]
    blobs: List[bytes] = []
    pos = 0
    for _ in range(sectors):
        out = bytearray()
        for _g in range(GROUPS):
            params = bytearray(16)
            data = bytearray(112)
            for u in range(UNITS):
                unit = pcm[pos:pos + UNIT_SAMPLES]
                pos += UNIT_SAMPLES
                _err, filt, shift, nibs, dec = _search_unit(unit, state)
                at = _param_at(u)
                params[at] = params[at + 4] = shift | (filt << 4)
                for i, nib in enumerate(nibs):
                    idx = i * 4 + (u >> 1)
                    if u & 1:
                        data[idx] = (data[idx] & 0x0F) | ((nib & 0xF) << 4)
                    else:
                        data[idx] = (data[idx] & 0xF0) | (nib & 0xF)
                for v in dec:
                    state[1], state[0] = state[0], v
            out += params + data
        blobs.append(bytes(out))
    return blobs


def write_sector(raw: bytes, audio: bytes) -> bytes:
    """The raw sector with its 2304 audio bytes replaced. Header and subheader stay; EDC is recomputed."""
    if not is_audio(raw):
        raise XaError("not an audio sector")
    if len(audio) != AUDIO_LEN:
        raise XaError("audio must be 2304 bytes")
    sector = bytearray(raw)
    sector[AUDIO:AUDIO + AUDIO_LEN] = audio
    if any(sector[EDC_AT:EDC_AT + 4]):
        sector[EDC_AT:EDC_AT + 4] = edc(bytes(sector[0x10:EDC_AT])).to_bytes(4, "little")
    return bytes(sector)
