"""Fire Emblem Awakening plugin: message archives (synthetic and the real game), the plugin's load / save."""
import struct
from pathlib import Path

import pytest

from plugins.fire_emblem_awakening.archive import Archive
from plugins.testing import check_loads, check_validator, load_rules

PLUGIN = "fire_emblem_awakening"
REAL = Path(r"E:\Emulators\RomHacking\Fire Emblem\Awakening\source\romfs\m\U")


def make_archive(messages, name="MESS_ARCHIVE_T", shared=()):
    """A message archive of ``(label, text)`` pairs; ``shared`` = indices that reuse the previous message's copy."""
    region = bytearray(name.encode("ascii") + b"\0")
    region += bytes(-len(region) % 4)
    offsets, labels = [], bytearray()
    table = b""
    for i, (label, text) in enumerate(messages):
        if i in shared:
            offsets.append(offsets[-1])
        else:
            offsets.append(len(region))
            region += text.encode("utf-16-le") + b"\0\0"
            region += bytes(-len(region) % 4)
        table += struct.pack("<II", offsets[-1], len(labels))
        labels += label.encode("cp932") + b"\0"
    body = bytes(region) + table + bytes(labels)
    return struct.pack("<4I", 0x20 + len(body), len(region), 0, len(messages)) + bytes(16) + body


SAMPLE = make_archive([("MCID_T", "Test chapter"), ("MID_T_1", "$t1$Wmクロム|3$w0|Hello.$k"),
                       ("MID_T_2", "Hello.$k"), ("MID_T_3", "Hello.$k")], shared=(3,))


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_archive_parses_and_rebuilds_byte_for_byte():
    archive = Archive(SAMPLE)
    assert archive.labels == ["MCID_T", "MID_T_1", "MID_T_2", "MID_T_3"]
    assert archive.texts[1] == "$t1$Wmクロム|3$w0|Hello.$k"
    assert archive.build(archive.texts) == SAMPLE


def test_an_edit_grows_the_text_and_keeps_the_shared_copy():
    archive = Archive(SAMPLE)
    texts = list(archive.texts)
    texts[1] = "$t1$Wmクロム|3$w0|A much longer greeting than before.$k"
    texts[3] = "Shared edit.$k"
    again = Archive(archive.build(texts))
    assert again.texts[1] == texts[1]
    assert again.texts[2] == again.texts[3] == "Shared edit.$k"   # messages 2 and 3 share one copy
    assert again.labels == archive.labels


def test_plugin_load_and_save_round_trip():
    rules = load_rules(PLUGIN)
    blocks, _names = rules.load_data_from_json_obj(SAMPLE)
    assert blocks == [Archive(SAMPLE).texts]
    assert rules.save_data_to_json_obj(blocks, {}) == SAMPLE


@pytest.mark.skipif(not REAL.is_dir(), reason="the unpacked game is not on this machine")
def test_every_real_archive_rebuilds_byte_for_byte():
    files = sorted(REAL.glob("*.bin"))
    assert len(files) >= 800
    messages = 0
    for path in files:
        raw = path.read_bytes()
        archive = Archive(raw)
        messages += len(archive.texts)
        assert archive.build(archive.texts) == raw, path.name
    assert messages > 15000
