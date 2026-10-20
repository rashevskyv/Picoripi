"""PS1 CD-XA ADPCM for the Lunar voice channel: mono, 37.8 kHz, 4-bit, one sector = 4032 samples.

A Form 2 audio sector holds 18 sound groups of 128 bytes at raw offset 0x18: 16 parameter bytes (8 units,
then the same 8 again), then 28 rows of 4 bytes. Row i holds one nibble per unit (unit u in byte u >> 1,
low nibble for even u). Unit u holds 28 samples in row order; the units follow each other in time.
Sample = (nibble << 12) >> shift, then the filter adds the two previous samples (filter 0 adds nothing).

The encoder writes filter 0 only: quality is low (about 4 bits per sample without prediction).
ponytail: filter 0 only, add the PS-X filters 1-4 when the voice quality matters.
"""
from __future__ import annotations

from typing import List

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


def decode_sector(raw: bytes) -> List[int]:
    """The 4032 mono samples of one audio sector (filter 0 only is decoded exactly; others are handled)."""
    if len(raw) != RAW:
        raise XaError("not a raw sector")
    out: List[int] = []
    old = [0, 0]
    for g in range(GROUPS):
        base = AUDIO + g * 128
        params = raw[base:base + 8]
        data = raw[base + 16:base + 128]
        for u in range(UNITS):
            shift, filt = params[u] & 0x0F, (params[u] >> 4) & 0x0F
            if shift > 12:
                shift = 9
            for i in range(UNIT_SAMPLES):
                byte = data[i * 4 + (u >> 1)]
                nib = (byte >> 4) & 0xF if u & 1 else byte & 0xF
                s = nib - 16 if nib >= 8 else nib
                s = (s << 12) >> shift
                v = _clamp(s + ((old[0] * _POS[filt] + old[1] * _NEG[filt] + 32) >> 6))
                old[1], old[0] = old[0], v
                out.append(v)
    return out


def _unit_shift(samples: List[int]) -> int:
    """The largest shift whose step still fits every sample (finest quantisation that does not clip)."""
    peak = max(abs(s) for s in samples) if samples else 0
    for shift in range(12, -1, -1):
        if peak <= 7.5 * (1 << (12 - shift)):
            return shift
    return 0


def encode_sector_audio(samples: List[int]) -> bytes:
    """2304 bytes of sound groups for up to 4032 samples (the rest is silence)."""
    if len(samples) > SECTOR_SAMPLES:
        raise XaError("more samples than one sector holds")
    pcm = list(samples) + [0] * (SECTOR_SAMPLES - len(samples))
    out = bytearray()
    for g in range(GROUPS):
        group = pcm[g * GROUP_SAMPLES:(g + 1) * GROUP_SAMPLES]
        params = bytearray(16)
        data = bytearray(112)
        for u in range(UNITS):
            unit = group[u * UNIT_SAMPLES:(u + 1) * UNIT_SAMPLES]
            shift = _unit_shift(unit)
            params[u] = params[8 + u] = shift
            step = 1 << (12 - shift)
            for i, x in enumerate(unit):
                nib = max(-8, min(7, round(x / step))) & 0xF
                pos = i * 4 + (u >> 1)
                if u & 1:
                    data[pos] = (data[pos] & 0x0F) | (nib << 4)
                else:
                    data[pos] = (data[pos] & 0xF0) | nib
        out += params + data
    return bytes(out)


def write_sector(raw: bytes, samples: List[int]) -> bytes:
    """The raw sector with its audio replaced; header, subheader and the rest stay as they were."""
    if not is_audio(raw):
        raise XaError("not an audio sector")
    sector = bytearray(raw)
    sector[AUDIO:AUDIO + AUDIO_LEN] = encode_sector_audio(samples)
    if any(sector[EDC_AT:EDC_AT + 4]):
        sector[EDC_AT:EDC_AT + 4] = edc(bytes(sector[0x10:EDC_AT])).to_bytes(4, "little")
    return bytes(sector)
