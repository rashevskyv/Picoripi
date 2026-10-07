"""Wind Waker text outside zel_00.bmg: the Hylian lines (Shift-JIS), the disc-error messages and font inside
main.dol, the disc banner; fonts inside nested archives; a session that predates new project files."""
import struct
from types import SimpleNamespace

import pytest

from core import formats
from core.containers import ContainerManager
from core.containers.base_container import BaseArchiveContainer
from core.font_formats import sources as font_sources
from handlers.project_action.session_mixin import SessionMixin
from plugins.zelda_bmg.bmg_tool import BMGFile
from plugins.zelda_tww import banner
from plugins.zelda_tww.dol import DolResources
from plugins.zelda_tww.rules import GameRules

from .test_zelda_tww_rules import _info, _ww_bmg


@pytest.fixture
def rules():
    return GameRules()


def test_hylian_lines_in_shift_jis_load_and_save_byte_for_byte(rules):
    data = _ww_bmg([(_info(3401, textbox_type=12), "ヒサシブリダナ　ハイラル".encode("shift_jis"))])
    blocks, _names = rules.load_data_from_json_obj(data)
    assert blocks == [["ヒサシブリダナ　ハイラル"]]
    assert rules.save_data_to_json_obj(blocks, {}) == data
    bmg = BMGFile()
    bmg.load(data)
    assert bmg.encoding == "shift_jis" and bmg.original_enc_val == 1


def _dol(text=b"", font_body=b"glyphs" * 8):
    bmg = bytearray(_ww_bmg([(_info(1), b"Reading the Game Disc..."), (_info(2), b"The Disc Cover is open.")]))
    struct.pack_into(">I", bmg, 8, len(bmg) // 32)               # the size field counts 32-byte blocks
    font = bytearray(b"FONTbfn1" + bytes(8) + font_body)
    struct.pack_into(">I", font, 8, len(font))
    head = bytearray(0x100)
    head[:4] = b"\x00\x00\x01\x00"
    head[0xE0:0xE4] = b"\x00\x00\x40\x00"
    return bytes(head + b"code" * 16 + bmg + bytes(64) + font + b"rest")


def test_main_dol_exposes_its_messages_and_font_and_keeps_its_size(rules):
    dol = _dol()
    assert DolResources.can_handle(dol) and not DolResources.can_handle(dol[:0x100] + b"x" * 64)
    container = DolResources(dol)
    assert container.list_files() == ["disc_errors.bmg", "disc_error_font.bfn"]
    assert container.pack() == dol
    blocks, names = rules.load_data_from_json_obj(container.read_file("disc_errors.bmg"))
    assert blocks[0] == ["Reading the Game Disc...", "The Disc Cover is open."]
    blocks[0][1] = "UA TEST"
    container.write_file("disc_errors.bmg", rules.save_data_to_json_obj(blocks, names))
    packed = container.pack()
    assert len(packed) == len(dol) and b"UA TEST" in packed and packed.endswith(b"rest")
    assert DolResources(packed).read_file("disc_error_font.bfn") == container.read_file("disc_error_font.bfn")
    with pytest.raises(ValueError, match="room"):
        container.write_file("disc_errors.bmg", bytes(4096))


def test_the_plugin_registers_main_dol_and_reads_banners_not_fonts(rules):
    assert ".dol" in ContainerManager.extensions()
    assert isinstance(ContainerManager.open(_dol()), DolResources)
    extensions = formats.supported_extensions(rules)
    assert ".bnr" in extensions and ".bmg" in extensions and ".bfn" not in extensions


def _bnr():
    data = bytearray(0x1960)
    data[:4] = b"BNR1"
    for (at, _size, _label), text in zip(banner.FIELDS, (b"The Legend of Zelda", b"Nintendo",
                                                         b"The Legend of Zelda: The Wind Waker", b"Nintendo",
                                                         b"Tragedy strikes a peaceful island,\nand...")):
        data[at:at + len(text)] = text
    data[0x18A0 + 20] = 0x55                                       # junk after a NUL stays where it is
    return bytes(data)


def test_banner_texts_round_trip_through_the_save_hooks(rules):
    raw = _bnr()
    blocks, names = rules.load_data_from_json_obj(raw)
    assert blocks[0][2] == "The Legend of Zelda: The Wind Waker" and len(blocks[0]) == 5
    context = formats.SaveContext(relative_path="files/opening.bnr", existing_versions=lambda: iter([raw]))
    rules.prepare_save_context(context)
    assert rules.save_data_to_json_obj(blocks, names) == raw
    blocks[0][2] = "UA TEST"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert banner.read(saved)[2] == "UA TEST" and saved[0x18A0 + 20] == 0x55 and saved[0x20:0x1820] == raw[0x20:0x1820]
    blocks[0][2] = "Легенда"
    with pytest.raises(ValueError, match="Latin"):
        rules.save_data_to_json_obj(blocks, names)
    rules.prepare_save_context(formats.SaveContext(relative_path="files/res/Msg/bmgres.arc/zel_00.bmg"))
    assert rules._banner is None


class _Pack(BaseArchiveContainer):
    """A tiny test archive: b"PACK" + u32 count + (name, length, bytes)*."""

    @classmethod
    def can_handle(cls, data):
        return data[:4] == b"PACK"

    def __init__(self, data):
        self._files, at = {}, 8
        for _ in range(struct.unpack_from(">I", data, 4)[0]):
            name_len, size = struct.unpack_from(">HI", data, at)
            name = data[at + 6:at + 6 + name_len].decode()
            self._files[name] = data[at + 6 + name_len:at + 6 + name_len + size]
            at += 6 + name_len + size

    def list_files(self):
        return list(self._files)

    def read_file(self, path):
        return self._files[path]

    def write_file(self, path, data):
        self._files[path] = bytes(data)

    def pack(self):
        return _pack(self._files)


def _pack(files):
    out = b"PACK" + struct.pack(">I", len(files))
    for name, data in files.items():
        out += struct.pack(">HI", len(name), len(data)) + name.encode() + data
    return out


def test_a_font_inside_an_archive_inside_an_archive(tmp_path):
    ContainerManager.register(_Pack)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Stage.pack").write_bytes(_pack({"dat/inner.pack": _pack({"font/name.bfn": b"FONT-A"}),
                                                         "other.bin": b"x"}))
    meta = {"source_path": str(tmp_path / "src"), "translation_path": str(tmp_path / "tr"), "is_directory_mode": True}
    (found,) = font_sources.resolve([{"label": "File select", "format": "bfn", "path": "Stage.pack",
                                      "member": "dat/inner.pack/font/*.bfn"}], meta)
    assert found.member == "dat/inner.pack/font/name.bfn" and found.read_current() == b"FONT-A"
    found.write(b"FONT-B")
    assert found.read_current() == b"FONT-B" and found.read_original() == b"FONT-A"
    outer = _Pack((tmp_path / "tr" / "Stage.pack").read_bytes())
    assert outer.read_file("other.bin") == b"x"


def _session(mapping, blocks, edited=None):
    store = SimpleNamespace(block_to_project_file_map=mapping, edited_data=edited or {}, unsaved_changes=False)
    project = SimpleNamespace(blocks=[object()] * blocks)
    mixin = SessionMixin()
    mixin.mw = SimpleNamespace(data_store=store, project_manager=SimpleNamespace(project=project))
    return mixin


def test_a_session_from_before_new_project_files_is_not_used():
    assert _session({0: 0, 1: 1}, 2)._session_misses_project_blocks() is False
    assert _session({"0": 0, "1": 1}, 4)._session_misses_project_blocks() is True
    # unsaved edits live only in the session: keep it
    assert _session({0: 0}, 2, edited={(0, 1): "text"})._session_misses_project_blocks() is False
