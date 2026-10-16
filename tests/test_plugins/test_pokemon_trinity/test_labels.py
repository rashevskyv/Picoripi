"""A message block's line labels come from the ``.tbl`` beside its ``.dat`` (Scarlet / Violet, Legends: Z-A and Sword / Shield)."""
import struct
from pathlib import Path
from types import SimpleNamespace

from plugins.common import gfmsg, message_block


def _tbl(labels):
    """An ``AHTB`` label table: u32 count, then per line a u64 hash, a u16 length and the zero-terminated label."""
    out = struct.pack("<I", len(labels))
    for index, label in enumerate(labels):
        raw = label.encode("utf-8") + b"\0"
        out += struct.pack("<Q", index) + struct.pack("<H", len(raw)) + raw
    return b"AHTB" + out


def test_labels_and_flags_of_a_block_come_from_its_dat_and_tbl(tmp_path):
    (tmp_path / "language_select.dat").write_bytes(
        gfmsg.write([(gfmsg.from_editor("Which language?"), 0), (gfmsg.from_editor("Second line"), 0)]))
    (tmp_path / "language_select.tbl").write_bytes(_tbl(["guide_01", "guide_02"]))
    project = SimpleNamespace(blocks=[SimpleNamespace(source_file="message/language_select.dat")])
    manager = SimpleNamespace(project=project, get_absolute_path=lambda rel: str(tmp_path / Path(rel).name))
    mw = SimpleNamespace(project_manager=manager, block_to_project_file_map={})
    assert message_block.locate(mw, 0, "test") == ("message/language_select.dat", [0, 0], ["guide_01", "guide_02"])


def test_a_block_without_a_message_file_gives_none():
    mw = SimpleNamespace(project_manager=SimpleNamespace(project=SimpleNamespace(blocks=[]),
                                                         get_absolute_path=str), block_to_project_file_map={})
    assert message_block.locate(mw, 5, "test") is None
