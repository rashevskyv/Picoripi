"""Voice clips of Lunar: Silver Star Story Complete: export to WAV, import a WAV, write it into the disc.

The opening monologue is XA audio in ``_AUDIO.XA``. The game starts it with ``Setmode 0xC8`` and
``Setfilter File=1 Channel=8``, then reads the file from its first sector (track sector ``first``).
A clip is the set of sectors of one (file, channel) inside a sector range of the file; each sector
holds 4032 samples (mono, 37.8 kHz, 16-bit WAV on the Picoripi side).

Fit rule (XA sectors cannot grow): a new clip must fit its sector slots. Shorter audio is padded
with silence. Longer audio is refused with ``VoiceError`` and the seconds that are too long. Only the
slot sectors change; every other byte of the disc stays as it was.
"""
from __future__ import annotations

import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, List, Sequence

from . import xa


class VoiceError(ValueError):
    """A clip that cannot be read, fitted or written."""


@dataclass(frozen=True)
class Clip:
    """One voice clip: sectors of channel ``channel`` in ``file`` between ``first`` and ``first + count``."""

    id: str
    title: str
    file: int
    channel: int
    first: int          # track sector of the file's first sector (LBA from the ISO directory)
    count: int          # sectors of the range (the game's read range)


# The opening monologue: the game's first XA read on disc 1 (see the report). Disc 1 track sector 18108.
OPENING_MONOLOGUE = Clip(
    id="opening_monologue",
    title="Alex's opening monologue (XA file 1, channel 8)",
    file=1,
    channel=8,
    first=18108,
    count=4422,
)
CLIPS = (OPENING_MONOLOGUE,)


def slots(read_raw: Callable[[int], bytes], clip: Clip) -> List[int]:
    """Track sectors of the clip's channel, in play order."""
    out = []
    for lba in range(clip.first, clip.first + clip.count):
        raw = read_raw(lba)
        if xa.is_audio(raw):
            file_no, channel, _sub, _coding = xa.subheader(raw)
            if file_no == clip.file and channel == clip.channel:
                out.append(lba)
    return out


def budget_samples(slot_count: int) -> int:
    return slot_count * xa.SECTOR_SAMPLES


def read_wav(path: str | Path) -> List[int]:
    """Mono 16-bit 37.8 kHz WAV as a list of samples. Other formats are refused, not converted."""
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != xa.RATE:
            raise VoiceError(
                f"{Path(path).name}: need mono 16-bit {xa.RATE} Hz WAV, got {w.getnchannels()} ch, "
                f"{8 * w.getsampwidth()}-bit, {w.getframerate()} Hz")
        raw = w.readframes(w.getnframes())
    return list(struct.unpack("<%dh" % (len(raw) // 2), raw))


def write_wav(path: str | Path, samples: Sequence[int]) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(xa.RATE)
        w.writeframes(struct.pack("<%dh" % len(samples), *samples))


def fit(samples: Sequence[int], slot_count: int) -> List[int]:
    """The samples padded to the slots' length; refuses audio that does not fit."""
    limit = budget_samples(slot_count)
    if len(samples) > limit:
        over = (len(samples) - limit) / xa.RATE
        raise VoiceError(f"clip is {over:.2f} s too long for its {slot_count} sectors "
                         f"({limit / xa.RATE:.2f} s); shorten the text")
    return list(samples) + [0] * (limit - len(samples))


def decode_clip(read_raw: Callable[[int], bytes], lbas: Sequence[int]) -> List[int]:
    out: List[int] = []
    for lba in lbas:
        out.extend(xa.decode_sector(read_raw(lba)))
    return out


def write_clip(disc: BinaryIO, raw_size: int, lbas: Sequence[int], samples: Sequence[int]) -> None:
    """Write the samples into the slot sectors of an open .bin (raw 2352-byte sectors, in place)."""
    padded = fit(samples, len(lbas))
    step = xa.SECTOR_SAMPLES
    for n, lba in enumerate(lbas):
        disc.seek(lba * raw_size)
        raw = disc.read(raw_size)
        disc.seek(lba * raw_size)
        disc.write(xa.write_sector(raw, padded[n * step:(n + 1) * step]))
