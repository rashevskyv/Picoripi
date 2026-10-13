"""Attack on Titan: Humanity in Chains plugin: the system.cf text written in place (synthetic data and, skipped where
the workspace is not on this machine, the real file) and the CTPK pictures."""
import romhacking_root
import struct
from pathlib import Path

import pytest

from core import texture_formats
from plugins.attack_on_titan_3ds import cf
from plugins.attack_on_titan_3ds.rules import GameRules
from plugins.testing import check_loads, check_validator

PLUGIN_NAME = "attack_on_titan_3ds"
WS = romhacking_root.under('Attack on Titan Humanity in Chains')
SOURCE = WS / "source" / "romfs"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def _system(texts) -> bytes:
    raw = bytearray(cf.FILE_SIZE)
    struct.pack_into("<I", raw, 0x14, cf.TEXT_END)
    struct.pack_into("<I", raw, 0x20, cf.FILE_SIZE)
    at = cf.TEXT_START
    for text in texts:
        blob = text.encode("utf-16-le") + b"\0\0"
        raw[at:at + len(blob)] = blob
        at += len(blob)
    # the rest of the section holds empty strings (NUL units), which parse as empty texts
    return bytes(raw)


def test_the_plugin_loads_and_validates():
    check_loads(PLUGIN_NAME)
    check_validator(PLUGIN_NAME)


def test_strings_are_written_in_place_and_must_fit():
    raw = _system(["Attack", "Evade", "Hello\nworld @"])
    system = cf.SystemCf(raw)
    assert system.texts[:3] == ["Attack", "Evade", "Hello\nworld @"]
    assert system.build(system.texts) == raw
    texts = list(system.texts)
    texts[0] = "Бій"
    out = cf.SystemCf(system.build(texts))
    assert out.texts[0].rstrip() == "Бій" and out.spans == system.spans and len(out.raw) == len(raw)
    texts[0] = "Атакувати титана"
    with pytest.raises(cf.FormatError):
        system.build(texts)
    assert system.capacity(0) == 6


def test_plugin_load_and_save_round_trip():
    raw = _system(["One", "Two"])
    rules = GameRules()
    blocks, _names = rules.load_data_from_json_obj(raw)
    assert blocks[0][:2] == ["One", "Two"]
    assert rules.save_data_to_json_obj(blocks, {}) == raw
    blocks[0][1] = "Tw"
    assert cf.SystemCf(rules.save_data_to_json_obj(blocks, {})).texts[1].rstrip() == "Tw"


def test_real_system_text_round_trips():
    raw = _need(SOURCE / "_catfiles_lists" / "system.cf").read_bytes()
    system = cf.SystemCf(raw)
    assert len(system.texts) == 5501 and sum(1 for t in system.texts if t) == 5379
    assert system.build(system.texts) == raw
    i = next(k for k, t in enumerate(system.texts) if t.startswith("Check newest version"))
    texts = list(system.texts)
    texts[i] = "UA TEST"
    out = cf.SystemCf(system.build(texts))
    assert out.texts[i].rstrip() == "UA TEST" and out.spans == system.spans


def test_real_pictures_round_trip():
    files = sorted(_need(SOURCE).rglob("*.ctpk"))
    assert len(files) == 293
    for path in files[::40]:
        data = path.read_bytes()
        textures = texture_formats.read("ctpk", data)
        assert texture_formats.write("ctpk", data, {i: t.image for i, t in enumerate(textures)}) == data, path.name
