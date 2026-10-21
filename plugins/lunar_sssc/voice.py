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

RAW = xa.RAW                    # raw CD sector size of the .bin files


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
    rate: int = xa.RATE  # 37800 (double speed) or 18900 Hz: the coding byte of the clip's sectors


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


def read_wav(path: str | Path, rate: int = xa.RATE) -> List[int]:
    """Mono 16-bit WAV at ``rate`` as a list of samples. Other formats are refused, not converted."""
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != rate:
            raise VoiceError(
                f"{Path(path).name}: need mono 16-bit {rate} Hz WAV, got {w.getnchannels()} ch, "
                f"{8 * w.getsampwidth()}-bit, {w.getframerate()} Hz")
        raw = w.readframes(w.getnframes())
    return list(struct.unpack("<%dh" % (len(raw) // 2), raw))


def write_wav(path: str | Path, samples: Sequence[int], rate: int = xa.RATE) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % len(samples), *samples))


def fit(samples: Sequence[int], slot_count: int, rate: int = xa.RATE) -> List[int]:
    """The samples padded to the slots' length; refuses audio that does not fit."""
    limit = budget_samples(slot_count)
    if len(samples) > limit:
        over = (len(samples) - limit) / rate
        raise VoiceError(f"clip is {over:.2f} s too long for its {slot_count} sectors "
                         f"({limit / rate:.2f} s); shorten the text")
    return list(samples) + [0] * (limit - len(samples))


def decode_clip(read_raw: Callable[[int], bytes], lbas: Sequence[int]) -> List[int]:
    """The clip's samples, one filter history across its slots."""
    return xa.decode_clip([read_raw(lba) for lba in lbas])


def write_clip(disc: BinaryIO, raw_size: int, lbas: Sequence[int], samples: Sequence[int],
               rate: int = xa.RATE) -> None:
    """Encode the samples into the slot sectors of an open .bin (raw 2352-byte sectors, in place)."""
    fit(samples, len(lbas), rate)                 # refuses a clip that is too long
    blobs = xa.encode_clip(samples, len(lbas))
    for lba, blob in zip(lbas, blobs):
        disc.seek(lba * raw_size)
        raw = disc.read(raw_size)
        disc.seek(lba * raw_size)
        disc.write(xa.write_sector(raw, blob))


# ---------------------------------------------------------------- disc and translation folder

def _read_raw_from(disc_path: str | Path):
    """Open a .bin and return (file, read_raw); the caller closes the file."""
    f = open(disc_path, "rb")

    def read_raw(lba: int) -> bytes:
        f.seek(lba * RAW)
        return f.read(RAW)
    return f, read_raw


def export_original(disc_path: str | Path, clip: Clip, wav_path: str | Path) -> float:
    """Decode the clip of the original disc to a WAV; returns its length in seconds."""
    f, read_raw = _read_raw_from(disc_path)
    with f:
        lbas = slots(read_raw, clip)
        if not lbas:
            raise VoiceError(f"{clip.title}: no sectors of file {clip.file} channel {clip.channel} on this disc")
        samples = decode_clip(read_raw, lbas)
    write_wav(wav_path, samples, clip.rate)
    return len(samples) / clip.rate


def import_translation(disc_path: str | Path, clip: Clip, wav_path: str | Path, voice_dir: str | Path) -> float:
    """Check a translated WAV against the clip's slots and keep it in ``voice_dir``; returns its length."""
    f, read_raw = _read_raw_from(disc_path)
    with f:
        lbas = slots(read_raw, clip)
    samples = read_wav(wav_path, clip.rate)
    fit(samples, len(lbas), clip.rate)            # refuses a clip that is too long
    Path(voice_dir).mkdir(parents=True, exist_ok=True)
    write_wav(Path(voice_dir) / f"{clip.id}.wav", samples, clip.rate)
    return len(samples) / clip.rate


def apply_translation(build_disc_path: str | Path, clip: Clip, voice_dir: str | Path) -> bool:
    """Write the clip's translated WAV (``voice_dir/<id>.wav``) into a build .bin. False: no translation."""
    wav = Path(voice_dir) / f"{clip.id}.wav"
    if not wav.is_file():
        return False
    samples = read_wav(wav, clip.rate)
    f, read_raw = _read_raw_from(build_disc_path)
    with f:
        lbas = slots(read_raw, clip)
    with open(build_disc_path, "r+b") as out:
        write_clip(out, RAW, lbas, samples, clip.rate)
    return True


def clip_by_id(clip_id: str) -> Clip:
    """The clip with this id; VoiceError for an unknown one."""
    for clip in CLIPS:
        if clip.id == clip_id:
            return clip
    raise VoiceError(f"no voice clip {clip_id!r}")
