"""Lunar SSSC voice clips: XA codec, slot fit and in-place sector writes, on synthetic sectors only."""
import io
import math
import struct
import wave

import pytest

from plugins.lunar_sssc import voice, xa


def _sector(file_no=1, channel=8, submode=0x64, coding=0x00, edc=True):
    raw = bytearray(xa.RAW)
    raw[0:12] = b"\x00" + b"\xff" * 10 + b"\x00"
    raw[0x10:0x14] = bytes([file_no, channel, submode, coding])
    raw[0x14:0x18] = raw[0x10:0x14]
    if edc:
        raw[xa.EDC_AT:xa.EDC_AT + 4] = xa.edc(bytes(raw[0x10:xa.EDC_AT])).to_bytes(4, "little")
    return bytes(raw)


def _tone(n, amp=6000, freq=440):
    return [int(amp * math.sin(2 * math.pi * freq * i / xa.RATE)) for i in range(n)]


def test_codec_round_trip_tone_error_is_small():
    tone = _tone(xa.SECTOR_SAMPLES)
    blob = xa.encode_clip(tone, 1)[0]
    back = xa.decode_clip([xa.write_sector(_sector(), blob)])
    assert len(back) == xa.SECTOR_SAMPLES
    assert max(abs(a - b) for a, b in zip(tone, back)) <= 320


def test_filter_history_runs_across_sectors():
    tone = _tone(2 * xa.SECTOR_SAMPLES, freq=300)
    blobs = xa.encode_clip(tone, 2)
    back = xa.decode_clip([xa.write_sector(_sector(), b) for b in blobs])
    assert max(abs(a - b) for a, b in zip(tone, back)) <= 320


def test_parameter_bytes_follow_the_psxavenc_layout():
    # units 0-3 at bytes 0-3 (copied to 4-7), units 4-7 at bytes 8-11 (copied to 12-15)
    blob = xa.encode_clip(_tone(xa.SECTOR_SAMPLES, freq=200), 1)[0]
    for g in range(xa.GROUPS):
        params = blob[g * 128:g * 128 + 16]
        assert params[0:4] == params[4:8]
        assert params[8:12] == params[12:16]


def test_silence_stays_silent():
    blob = xa.encode_clip([], 1)[0]
    assert set(xa.decode_clip([xa.write_sector(_sector(), blob)])) == {0}


def test_write_sector_keeps_header_and_recomputes_edc():
    raw = _sector()
    out = xa.write_sector(raw, xa.encode_clip([1000, -1000] * 100, 1)[0])
    assert out[:0x18] == raw[:0x18]
    assert out[xa.EDC_AT:xa.EDC_AT + 4] == xa.edc(out[0x10:xa.EDC_AT]).to_bytes(4, "little")
    assert out[xa.EDC_AT:xa.EDC_AT + 4] != raw[xa.EDC_AT:xa.EDC_AT + 4]


def test_sector_without_edc_stays_without_edc():
    out = xa.write_sector(_sector(edc=False), xa.encode_clip([5] * 10, 1)[0])
    assert out[xa.EDC_AT:xa.EDC_AT + 4] == b"\0\0\0\0"


def test_non_audio_sector_is_refused():
    with pytest.raises(xa.XaError):
        xa.write_sector(_sector(submode=0x08), bytes(xa.AUDIO_LEN))


def test_fit_pads_shorter_and_refuses_longer():
    budget = voice.budget_samples(2)
    assert len(voice.fit([7] * 10, 2)) == budget
    assert voice.fit([7] * 10, 2)[10:12] == [0, 0]
    with pytest.raises(voice.VoiceError, match="too long"):
        voice.fit([0] * (budget + xa.RATE), 2)


def test_slots_pick_only_the_clip_channel_in_range():
    sectors = {
        100: _sector(channel=8),
        101: _sector(channel=9),
        102: _sector(channel=8, submode=0x08),     # data sector, not audio
        103: _sector(channel=8),
        104: _sector(channel=8),                    # outside the range below
    }
    clip = voice.Clip("t", "t", file=1, channel=8, first=100, count=4)
    assert voice.slots(lambda lba: sectors[lba], clip) == [100, 103]


def test_write_clip_changes_only_slot_sectors():
    raws = [_sector(channel=8), _sector(channel=9), _sector(channel=8), _sector(channel=8)]
    disc = io.BytesIO(b"".join(raws))
    lbas = [0, 2, 3]
    voice.write_clip(disc, xa.RAW, lbas, _tone(xa.SECTOR_SAMPLES // 2))
    after = disc.getvalue()
    changed = [i for i in range(4) if after[i * xa.RAW:(i + 1) * xa.RAW] != raws[i]]
    assert changed == lbas


def test_wav_round_trip_and_format_refusal(tmp_path):
    path = tmp_path / "clip.wav"
    voice.write_wav(path, [1, -2, 300])
    assert voice.read_wav(path) == [1, -2, 300]
    bad = tmp_path / "bad.wav"
    with wave.open(str(bad), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(struct.pack("<4h", 0, 0, 0, 0))
    with pytest.raises(voice.VoiceError, match="need mono"):
        voice.read_wav(bad)


def test_sector_rate_follows_the_coding_byte():
    assert xa.sector_rate(_sector(coding=0x00)) == 37800
    assert xa.sector_rate(_sector(coding=0x04)) == 18900      # Eternal Blue V.XA sectors
