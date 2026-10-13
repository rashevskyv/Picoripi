"""Stella Glow plugin: string tables and event flows on synthetic data, then on the real EU game files (skipped
where the workspace is not on this machine)."""
import romhacking_root
import json
import struct
from pathlib import Path

import pytest

from plugins.stella_glow.flw import Flow, StrTable, TooLong
from plugins.stella_glow.rules import GameRules


def _utf16(text: str) -> bytes:
    return text.encode("utf-16-le") + b"\0\0"


def _flow(pool_texts, pointer_slot=0x30):
    """A flow with a header, a pointer word at ``pointer_slot`` (self-relative) and a pool after it."""
    head = bytearray(0x40)
    head[:4] = b"FLW\0"
    pool_at = 0x40
    struct.pack_into("<I", head, pointer_slot, pool_at - pointer_slot)
    body = b"".join(_utf16(t) for t in pool_texts)
    body += bytes(-len(body) % 4)
    tail = struct.pack("<III", 0x7DD, 4, 1)         # the next record: its opcode is no string
    return bytes(head) + body + tail


def test_str_table_round_trip_and_growth():
    raw = "- -\0Sword\0A very long description\0".encode("utf-16-le")
    table = StrTable(raw)
    assert table.strings == ["- -", "Sword", "A very long description"]
    assert table.build(table.strings) == raw
    grown = table.build(["- -", "Меч", "Дуже довгий опис, довший за оригінал"])
    assert StrTable(grown).strings[1] == "Меч" and len(grown) != len(raw)


def test_flow_pool_found_by_its_pointer():
    data = _flow(["Where... is this?", "It burns...\r\nMy body...", "\u2026", "Goodbye, Alto!"])
    flow = Flow(data)
    assert flow.strings == ["Where... is this?", "It burns...\nMy body...", "\u2026", "Goodbye, Alto!"]
    assert flow.build(flow.strings) == data


def test_flow_text_keeps_its_room():
    data = _flow(["Where... is this?", "Goodbye, Alto!"])
    flow = Flow(data)
    shorter = flow.build(["Де це?", "Бувай!"])
    again = Flow(shorter)
    assert again.strings[0].rstrip() == "Де це?" and again.strings[1].rstrip() == "Бувай!"
    assert len(shorter) == len(data) and shorter[:0x40] == data[:0x40]
    with pytest.raises(TooLong):
        flow.build(["x" * 40, "Goodbye, Alto!"])
    texts, cut = flow.fit(["x" * 40, "Goodbye, Alto!"])
    assert cut == 1 and len(texts[0]) == flow.room(0) and flow.build(texts)


def test_flow_without_pointer_has_no_text():
    data = bytearray(_flow(["Hello there"]))
    struct.pack_into("<I", data, 0x30, 0)
    assert Flow(bytes(data)).strings == []


def test_rules_load_and_save():
    rules = GameRules()
    data = _flow(["Where... is this?", "Goodbye, Alto!"])
    blocks, _names = rules.load_data_from_json_obj(data)
    assert blocks == [["Where... is this?", "Goodbye, Alto!"]]
    assert rules.save_data_to_json_obj(blocks, {}) == data
    out = rules.save_data_to_json_obj([["Де це?", "Бувай!"]], {})
    assert Flow(out).strings[0].rstrip() == "Де це?"
    raw = "A\0B\0".encode("utf-16-le")
    blocks, _names = rules.load_data_from_json_obj(raw)
    assert blocks == [["A", "B"]] and rules.save_data_to_json_obj(blocks, {}) == raw


WS = romhacking_root.under('Stella Glow')
SOURCE = WS / "source"
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "stella_glow"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_real_tables_and_flows_save_back_byte_for_byte():
    tables = sorted(_need(SOURCE / "romfs/param").glob("*.str"))
    assert len(tables) == 18
    count = 0
    for path in tables:
        raw = path.read_bytes()
        table = StrTable(raw)
        assert table.build(table.strings) == raw, path.name
        count += len(table.strings)
    assert count == 4330
    flows = sorted((SOURCE / "romfs/event").glob("*.flw"))
    assert len(flows) == 1554
    strings = 0
    for path in flows[::7]:
        raw = path.read_bytes()
        flow = Flow(raw)
        assert flow.build(flow.strings) == raw, path.name
        strings += len(flow.strings)
    assert strings > 2000


def test_real_fonts_open_and_pack_back_unchanged():
    from core import font_formats
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    for item in descriptors:
        data = _need(SOURCE / item["path"]).read_bytes()
        metadata, sheets = font_formats.extract(item["format"], data)
        assert font_formats.pack(item["format"], metadata, sheets, data) == data, item["path"]
