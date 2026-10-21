"""Lunar SSSC voice clips in Picoripi: the worker, the rules hooks, import and apply, and the dialog.

Everything runs on synthetic sectors and a fake rules object; no game data is read.
"""
import math

import pytest

from plugins.lunar_sssc import voice, xa
from plugins.lunar_sssc.rules import GameRules
from plugins.lunar_sssc.voice_dialog import VoiceClipsDialog, VoiceJob

RAW = xa.RAW


def _sector(channel=8):
    raw = bytearray(RAW)
    raw[0x10:0x14] = bytes([1, channel, 0x64, 0x00])
    raw[0x14:0x18] = raw[0x10:0x14]
    return bytes(raw)


def _disc(tmp_path, channels, name="disc.bin"):
    path = tmp_path / name
    path.write_bytes(b"".join(_sector(c) for c in channels))
    return path


def _clip(count):
    return voice.Clip("test_clip", "Test clip", file=1, channel=8, first=0, count=count)


def test_job_reports_its_result(qtbot):
    job = VoiceJob(lambda a, b: a + b, 2, 3)
    with qtbot.waitSignal(job.done, timeout=5000) as blocker:
        job.start()
    assert blocker.args == [5]
    qtbot.waitUntil(lambda: not job.isRunning(), timeout=5000)


def test_job_reports_its_error_message(qtbot):
    def broken():
        raise voice.VoiceError("clip is too long")

    job = VoiceJob(broken)
    with qtbot.waitSignal(job.failed, timeout=5000) as blocker:
        job.start()
    assert blocker.args == ["clip is too long"]
    qtbot.waitUntil(lambda: not job.isRunning(), timeout=5000)


def test_rules_list_the_monologue_with_its_folders(tmp_path):
    project = tmp_path / "Silver Star Story" / "picoripi"
    project.mkdir(parents=True)
    iso = tmp_path / "Silver Star Story" / "ISO" / "EN"
    iso.mkdir(parents=True)
    disc = iso / "Lunar - Silver Star Story Complete (USA) (Disc 1) (Track 1).bin"
    disc.write_bytes(b"")
    clips = GameRules(None).get_voice_clips(str(project))
    assert [c["id"] for c in clips] == ["opening_monologue"]
    assert clips[0]["disc"] == str(disc)
    assert clips[0]["voice_dir"] == str(tmp_path / "Silver Star Story" / "translation" / "voice")


def test_rules_without_a_disc_give_an_empty_disc_path(tmp_path):
    clips = GameRules(None).get_voice_clips(str(tmp_path / "picoripi"))
    assert clips[0]["disc"] == ""


def test_import_keeps_a_fitting_wav_and_refuses_a_long_one(tmp_path):
    disc = _disc(tmp_path, [8, 8, 9, 8])
    clip = _clip(count=4)                       # 3 slots of channel 8
    voice_dir = tmp_path / "voice"
    short = tmp_path / "short.wav"
    voice.write_wav(short, [1000] * 100)
    seconds = voice.import_translation(disc, clip, short, voice_dir)
    assert seconds == pytest.approx(100 / xa.RATE)
    assert (voice_dir / "test_clip.wav").is_file()
    long = tmp_path / "long.wav"
    voice.write_wav(long, [0] * (3 * xa.SECTOR_SAMPLES + 1))
    with pytest.raises(voice.VoiceError, match="too long"):
        voice.import_translation(disc, clip, long, voice_dir)


def test_apply_writes_only_the_clip_slots_of_a_build_disc(tmp_path):
    disc = _disc(tmp_path, [8, 9, 8, 8])
    original = disc.read_bytes()
    voice_dir = tmp_path / "voice"
    voice_dir.mkdir()
    tone = [int(5000 * math.sin(2 * math.pi * 440 * n / xa.RATE)) for n in range(2 * xa.SECTOR_SAMPLES)]
    voice.write_wav(voice_dir / "test_clip.wav", tone)
    build = tmp_path / "build.bin"
    build.write_bytes(original)
    assert voice.apply_translation(build, _clip(count=4), voice_dir) is True
    after = build.read_bytes()
    changed = [i for i in range(4) if after[i * RAW:(i + 1) * RAW] != original[i * RAW:(i + 1) * RAW]]
    assert changed == [0, 2, 3]               # the slots of channel 8, not the channel 9 sector
    # apply without a translation changes nothing
    empty = tmp_path / "empty"
    empty.mkdir()
    assert voice.apply_translation(build, _clip(count=4), empty) is False


class _FakeRules:
    def __init__(self, clips):
        self._clips = clips

    def get_voice_clips(self, project_dir):
        return list(self._clips)


def test_dialog_lists_clips_and_disables_actions_without_any(qtbot, tmp_path):
    rules = _FakeRules([{"id": "c1", "title": "Clip one", "disc": "", "voice_dir": str(tmp_path)}])
    dialog = VoiceClipsDialog(rules, str(tmp_path))
    qtbot.addWidget(dialog)
    assert dialog._list.count() == 1
    assert dialog._export_btn.isEnabled() is True
    empty = VoiceClipsDialog(_FakeRules([]), str(tmp_path))
    qtbot.addWidget(empty)
    assert empty._export_btn.isEnabled() is False
    assert empty._list.item(0).text()


def test_a_clip_at_18900_hz_takes_only_its_own_rate(tmp_path):
    disc = _disc(tmp_path, [8, 8])
    clip = voice.Clip("slow", "Slow clip", file=1, channel=8, first=0, count=2, rate=18900)
    voice_dir = tmp_path / "voice"
    ok = tmp_path / "ok.wav"
    voice.write_wav(ok, [500] * 1000, rate=18900)
    assert voice.import_translation(disc, clip, ok, voice_dir) == pytest.approx(1000 / 18900)
    wrong = tmp_path / "wrong.wav"
    voice.write_wav(wrong, [500] * 1000, rate=37800)
    with pytest.raises(voice.VoiceError, match="18900 Hz"):
        voice.import_translation(disc, clip, wrong, voice_dir)
