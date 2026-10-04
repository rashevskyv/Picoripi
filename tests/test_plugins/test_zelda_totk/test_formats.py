"""TotK file formats: MSBT, readable tags, SARC, zstd with dictionaries, BFFNT widths, RESTBL."""
import struct
import zlib

import pytest

from plugins.zelda_totk import sarc as sarc_module
from plugins.zelda_totk.font_tool import font_map
from plugins.zelda_totk.msbt import EndTag, Msbt, Tag
from plugins.zelda_totk.restbl import Restbl, scaled_size
from plugins.zelda_totk.tags import from_editor, parse_tag, render_tag, to_editor

from . import samples

COLOR_RED = ("tag", 0, 3, struct.pack("<h", 2))
ICON_A = ("tag", 1, 4, bytes([10, 0xCD]))
PLAYER = ("tag", 2, 29, b"")


def _talk():
    return samples.msbt([
        ("Talk_00", samples.text("Hello, ", PLAYER, "!\nPress ", ICON_A, ".")),
        ("Talk_01", samples.text(COLOR_RED, "Danger", ("end", 0, 3), " ahead.")),
        ("Talk_02", samples.text("")),
    ])


class TestMsbt:
    def test_texts_tags_and_labels_are_read(self):
        msbt = Msbt(_talk())

        assert msbt.labels == {0: "Talk_00", 1: "Talk_01", 2: "Talk_02"}
        assert msbt.messages[0] == ["Hello, ", Tag(2, 29), "!\nPress ", Tag(1, 4, b"\x0a\xcd"), "."]
        assert msbt.messages[1] == [Tag(0, 3, b"\x02\x00"), "Danger", EndTag(0, 3), " ahead."]
        assert msbt.messages[2] == []

    def test_unchanged_texts_rebuild_the_same_bytes(self):
        raw = _talk()
        msbt = Msbt(raw)
        assert msbt.build(msbt.messages) == raw

    def test_a_longer_text_moves_the_offsets_and_keeps_the_other_sections(self):
        msbt = Msbt(_talk())
        messages = list(msbt.messages)
        messages[0] = ["Привіт, ", Tag(2, 29), "! Це значно довший рядок."]

        again = Msbt(msbt.build(messages))

        assert again.messages == messages
        assert again.labels == msbt.labels
        assert [name for name, _body in again.sections] == [b"LBL1", b"ATR1", b"TSY1", b"TXT2"]
        assert again.sections[:3] == msbt.sections[:3]

    def test_the_message_count_cannot_change(self):
        msbt = Msbt(_talk())
        with pytest.raises(ValueError):
            msbt.build(msbt.messages[:1])

    def test_other_files_are_refused(self):
        with pytest.raises(ValueError):
            Msbt(b"SARC" + b"\x00" * 40)


class TestTags:
    @pytest.mark.parametrize("tag, shown", [
        (Tag(0, 3, b"\x02\x00"), "{color:2}"),
        (Tag(1, 4, b"\x0a\xcd"), "{icon:AButton0}"),
        (Tag(2, 29), "{playerName}"),
        (Tag(0, 4), "{pageBreak}"),
        (Tag(0, 1, struct.pack("<h", -1)), "{font:Default}"),
        (Tag(3, 0, b"\x08\x01"), "{emotion:Pleasure:1}"),
        (Tag(0, 0, struct.pack("<HH", 4, 4) + "かな".encode("utf-16-le")), "{ruby:4:かな}"),
        (Tag(201, 6, b"".join(struct.pack("<H", len(w) * 2) + w.encode("utf-16-le") for w in ("яблуко", "яблука", "яблук"))),
         "{plural:яблуко:яблука:яблук}"),
        (Tag(42, 7, b"\x01\x02"), "{tag:42:7:0102}"),
        (Tag(1, 4, b"\x0a\x00"), "{tag:1:4:0a00}"),          # a pad that is not 0xCD stays raw
        (Tag(0, 3, b"\x02"), "{tag:0:3:02}"),                # too short for its argument
        (EndTag(0, 3), "{/color}"),
        (EndTag(9, 9), "{/tag:9:9}"),
    ])
    def test_each_tag_shows_readably_and_encodes_back(self, tag, shown):
        assert render_tag(tag) == shown
        assert parse_tag(shown) == tag

    def test_a_string_argument_with_a_colon_falls_back_to_raw(self):
        params = struct.pack("<H", 6) + "a:b".encode("utf-16-le")
        assert render_tag(Tag(4, 0, params)) == "{tag:4:0:" + params.hex() + "}"

    def test_icons_and_numbers_are_accepted_by_value_too(self):
        assert parse_tag("{icon:10}") == parse_tag("{icon:AButton0}")

    @pytest.mark.parametrize("bad", ["{colour:2}", "{color}", "{color:red}", "{tag:1}", "{tag:1:2:zz}", "{icon:1:2}"])
    def test_wrong_tags_are_refused(self, bad):
        with pytest.raises(ValueError):
            parse_tag(bad)

    def test_editor_text_round_trips(self):
        tokens = Msbt(_talk()).messages[1]
        shown = to_editor(tokens)
        assert shown == "{color:2}Danger{/color} ahead."
        assert from_editor(shown) == tokens

    def test_braces_that_are_not_tags_stay_text(self):
        assert from_editor("a {b c} {nope:1}") == ["a {b c} {nope:1}"]


class TestSarc:
    def test_parse_and_rebuild_the_same_bytes(self):
        raw = samples.sarc({"EventFlowMsg/A.msbt": _talk(), "StaticMsg/B.msbt": samples.msbt([("X", samples.text("x"))])})
        archive = sarc_module.Sarc(raw)

        assert sorted(archive.files) == ["EventFlowMsg/A.msbt", "StaticMsg/B.msbt"]
        assert archive.build() == raw

    def test_a_changed_file_moves_the_next_one_and_keeps_its_alignment(self):
        archive = sarc_module.Sarc(samples.sarc({"A.msbt": b"a" * 16, "B.msbt": b"b" * 16, "C.msbt": b"c" * 16}))
        first = next(name for name in archive.files)
        archive.files[first] = b"longer" * 5

        again = sarc_module.Sarc(archive.build())

        assert again.files == archive.files
        assert all(start % again.alignment == 0 for _name, start, _end in again._nodes)

    def test_a_plain_sarc_container_writes_back_and_untouched_returns_the_input(self):
        raw = samples.sarc({"A.msbt": _talk()})
        container = sarc_module.SarcContainer(raw)
        assert container.pack() is raw or container.pack() == raw

        container.write_file("A.msbt", b"new")
        assert sarc_module.Sarc(container.pack()).files == {"A.msbt": b"new"}
        with pytest.raises(KeyError):
            container.write_file("missing.msbt", b"")


@pytest.fixture
def dictionaries(monkeypatch, tmp_path):
    """A clean dictionary registry that looks in ``tmp_path``."""
    pytest.importorskip("compression.zstd")
    monkeypatch.setattr(sarc_module, "_dictionaries", {})
    monkeypatch.setattr(sarc_module, "_searched", set())
    monkeypatch.setattr(sarc_module, "dictionary_dirs", lambda: [tmp_path / "romfs" / "Mals"])
    return tmp_path


class TestZstd:
    def test_an_archive_compressed_with_the_game_dictionary_opens_and_saves_with_it(self, dictionaries):
        from compression import zstd

        zs_dictionary = samples.dictionary()
        dict_id = struct.unpack_from("<I", zs_dictionary, 4)[0]
        (dictionaries / "romfs" / "Pack").mkdir(parents=True)
        (dictionaries / "romfs" / "Mals").mkdir()
        (dictionaries / "romfs" / "Pack" / "ZsDic.pack.zs").write_bytes(samples.zsdic_pack(zs_dictionary))
        plain = samples.sarc({"A.msbt": _talk()})
        raw = zstd.compress(plain, zstd_dict=zstd.ZstdDict(zs_dictionary))
        assert zstd.get_frame_info(raw).dictionary_id == dict_id

        assert sarc_module.SarcContainer.can_handle(raw)
        container = sarc_module.SarcContainer(raw)
        assert container.read_file("A.msbt") == _talk()
        assert container.pack() is raw

        container.write_file("A.msbt", b"changed")
        packed = container.pack()
        assert zstd.get_frame_info(packed).dictionary_id == dict_id
        assert sarc_module.SarcContainer(packed).read_file("A.msbt") == b"changed"

    def test_a_missing_dictionary_says_which_file_to_provide(self, dictionaries):
        from compression import zstd

        raw = zstd.compress(samples.sarc({"A.msbt": _talk()}), zstd_dict=zstd.ZstdDict(samples.dictionary()))

        assert sarc_module.SarcContainer.can_handle(raw)
        with pytest.raises(ValueError, match="ZsDic.pack.zs"):
            sarc_module.SarcContainer(raw)

    def test_other_zstd_files_are_not_archives(self, dictionaries):
        from compression import zstd

        assert not sarc_module.SarcContainer.can_handle(zstd.compress(b"BYML not an archive"))
        assert not sarc_module.SarcContainer.can_handle(b"RARC....")


def _ffnt(chars, widths) -> bytes:
    """A minimal NX BFFNT: FINF, one CWDH and one scan CMAP (32-bit codes)."""
    header = b"FFNT" + b"\xff\xfe" + struct.pack("<HIIHH", 0x14, 0x04010000, 0, 3, 0)
    finf_at = len(header)
    cwdh_at = finf_at + 0x20
    cwdh = b"CWDH" + struct.pack("<IHHI", 0, 0, len(widths) - 1, 0) + b"".join(bytes([0, w, w]) for w in widths)
    cwdh += b"\x00" * (-len(cwdh) % 4)
    cmap_at = cwdh_at + len(cwdh)
    entries = b"".join(struct.pack("<IhH", ord(c), i, 0) for i, c in enumerate(chars))
    cmap = b"CMAP" + struct.pack("<IIIHHI", 0, 0, 0x10FFFF, 2, 0, 0) + struct.pack("<HH", len(chars), 0) + entries
    finf = b"FINF" + struct.pack("<I", 0x20) + bytes([1, 30, 20, 24]) + struct.pack("<HH", 30, 0) + bytes([0, 0, 0, 1])
    finf += struct.pack("<III", 0, cwdh_at + 8, cmap_at + 8)
    finf += b"\x00" * (0x20 - len(finf))
    return header + finf + cwdh + cmap


def test_font_widths_come_from_cwdh_through_cmap():
    assert font_map(_ffnt("AБї", [21, 18, 9])) == {"A": {"width": 21}, "Б": {"width": 18}, "ї": {"width": 9}}


class TestRestbl:
    def _table(self) -> bytes:
        key = zlib.crc32(b"Mals/USen.Product.121.sarc")
        crc = sorted([(key, 1000), (5, 7)])
        name = b"Collided/Path.bin".ljust(0xA0, b"\x00")
        return (b"RESTBL" + struct.pack("<IIII", 1, 0xA0, len(crc), 1)
                + b"".join(struct.pack("<II", h, s) for h, s in crc) + name + struct.pack("<I", 55))

    def test_entries_are_found_by_crc_and_by_name_and_change_in_place(self):
        raw = self._table()
        table = Restbl(raw)
        assert table.build() == raw
        assert (table.size("Mals/USen.Product.121.sarc"), table.size("Collided/Path.bin")) == (1000, 55)
        assert table.size("Mals/EUfr.Product.121.sarc") is None

        table.set_size("Mals/USen.Product.121.sarc", 4096)
        assert Restbl(table.build()).size("Mals/USen.Product.121.sarc") == 4096

    def test_an_entry_only_grows_in_proportion(self):
        assert scaled_size(1000, 800, 800) == 1000
        assert scaled_size(1000, 800, 700) == 1000
        assert scaled_size(1000, 800, 1200) == 1536    # 1500 rounded up to 0x100
