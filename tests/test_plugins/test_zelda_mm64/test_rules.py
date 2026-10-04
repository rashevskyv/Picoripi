"""Majora's Mask (N64): message codec, ROM file swap and CRC, load and save of a ROM-shaped image."""
import struct

import pytest

from core.containers import yaz0
from plugins.common.n64_rom import N64Rom, compute_crc, retarget_constant, to_big_endian
from plugins.testing import check_loads, check_validator
from plugins.zelda_mm64.msg_codec import decode_body, encode_body
from plugins.zelda_mm64.rules import TYPE_LINE_WIDTH, GameRules

PLUGIN = "zelda_mm64"
TABLE = 0x1210D8


def _header(textbox_type=0):
    return bytes([textbox_type, 0, 0xFE, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])


MESSAGES = [
    (0x0002, _header() + b"\x17You got a \x03Blue Rupee\x00!\x18\x11\x1f\x00\x0aIt's worth 5!"),
    (0x0003, _header() + b"Press \xb0 to talk.\x10Next box\x1e\x69\x79"),
    (0x21CC, _header(6) + b"\x01Notebook\x00 entry\x1a"),
]


def _rom():
    """A 2 MB image shaped like the US ROM: dmadata, file 29 = text, file 31 = Yaz0 code."""
    rom = bytearray(0x200000)
    rom[0:4] = b"\x80\x37\x12\x40"
    rom[0x3B:0x3F] = b"NZSE"
    text = bytearray()
    code = bytearray(TABLE + 8 * (len(MESSAGES) + 1) + 0x20)
    for n, (message_id, raw) in enumerate(MESSAGES):
        struct.pack_into(">HBBI", code, TABLE + 8 * n, message_id, 0, 0, 0x08000000 | len(text))
        text += raw + b"\xbf"
        text += b"\0" * (-len(text) % 4)
    struct.pack_into(">HBBI", code, TABLE + 8 * len(MESSAGES), 0xFFFF, 0, 0, 0x08000000 | len(text))
    text += b"\0" * (-len(text) % 16)
    stored_code = yaz0.compress(bytes(code))
    files = [(0, 0x1060, 0, 0)]
    files += [(0x2000 + i * 0x10, 0x2000 + i * 0x10, 0x2000 + i * 0x10, 0) for i in range(1, 29)]
    # As in the retail ROM, the next file starts just after the text: little room to grow.
    after_text = 0x100000 + len(text) + 0x40
    files += [(0x100000, 0x100000 + len(text), 0x100000, 0), (after_text, after_text, 0x180000, 0)]
    files += [(0x200000, 0x200000 + len(code), 0x110000, 0x110000 + len(stored_code))]
    for n, entry in enumerate(files):
        struct.pack_into(">IIII", rom, 0x1A500 + 16 * n, *entry)
    rom[0x100000:0x100000 + len(text)] = text
    rom[0x110000:0x110000 + len(stored_code)] = stored_code
    struct.pack_into(">II", rom, 0x10, *compute_crc(bytes(rom)))
    return bytes(rom)


@pytest.fixture(scope="module")
def raw_rom():
    return _rom()


@pytest.fixture
def loaded(raw_rom):
    rules = GameRules()
    blocks, _ = rules.load_data_from_json_obj(raw_rom)
    return rules, raw_rom, blocks


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_validator_passes():
    check_validator(PLUGIN)


class TestCodec:
    def test_every_kind_of_code_reads_as_a_tag_and_encodes_back(self):
        body = MESSAGES[0][1][11:] + b"\xb0\x10after\x14\x05\x99\x1b\x00\x1e\x11"
        text = decode_body(body)
        assert text == ("{quicktext-on}You got a {color:blue}Blue Rupee{color:default}!{quicktext-off}\n"
                        "{delay:10}It's worth 5!{btn:A}{box-break}\nafter{shift:5}{x:99}"
                        "{box-break-delayed:30}\n\n")
        assert encode_body(text) == body

    def test_a_line_break_typed_after_a_box_break_is_not_saved(self):
        assert encode_body("a{box-break}\nb") == b"a\x10b"
        assert encode_body("a{box-break}\n\nb") == b"a\x10\x11b"

    def test_bad_input_is_refused(self):
        with pytest.raises(ValueError, match="Unknown tag"):
            encode_body("{nonsense}")
        with pytest.raises(ValueError, match="No font slot"):
            encode_body("Привіт")


class TestRom:
    def test_every_byte_order_becomes_big_endian(self):
        z64 = b"\x80\x37\x12\x40" + bytes(range(4, 16))
        v64 = bytes(b for pair in zip(z64[1::2], z64[0::2]) for b in pair)
        n64 = bytes(b for i in range(0, 16, 4) for b in reversed(z64[i:i + 4]))
        assert to_big_endian(v64) == z64 and to_big_endian(n64) == z64
        with pytest.raises(ValueError):
            to_big_endian(b"\0" * 16)

    def test_a_replaced_file_keeps_its_place_when_it_fits_and_the_crc_follows(self, raw_rom):
        rom = N64Rom(raw_rom)
        same_size = rom.read_file(29)[:-4] + b"\1\2\3\4"
        out = N64Rom(rom.replace_files({29: same_size, 31: rom.read_file(31)}))
        assert out.files[29][2] == rom.files[29][2] and out.files[31][2] == rom.files[31][2]
        assert out.read_file(29) == same_size
        assert struct.unpack_from(">II", out.data, 0x10) == compute_crc(bytes(out.data))

    def test_a_file_that_grows_moves_to_the_end_and_nothing_else_moves(self, raw_rom):
        rom = N64Rom(raw_rom)
        longer = rom.read_file(29) + b"x" * 64
        out = N64Rom(rom.replace_files({29: longer}))
        assert out.read_file(29) == longer and out.files[29][2] > rom.files[29][2]
        assert [f for i, f in enumerate(out.files) if i != 29] == [f for i, f in enumerate(rom.files) if i != 29]

    def test_an_address_built_by_lui_and_addiu_is_retargeted(self):
        # lui t6, 0x00AD ; nop ; addiu a1, t6, 0x1000  -> 0x00AD1000
        code = bytes.fromhex("3c0e00ad" "00000000" "25c51000")
        out = retarget_constant(code, 0x00AD1000, 0x02EE8040, expected=1)
        assert out == bytes.fromhex("3c0e02ef" "00000000" "25c58040")  # 0x02EF0000 - 0x7FC0
        with pytest.raises(ValueError, match="expected 2"):
            retarget_constant(code, 0x00AD1000, 0x02EE8040, expected=2)

    def test_a_file_may_not_overrun_the_next_virtual_range(self, raw_rom):
        rom = N64Rom(raw_rom)
        with pytest.raises(ValueError, match="has room for"):
            rom.replace_files({29: b"x" * (rom.file_capacity(29) + 1)})


class TestRules:
    def test_the_rom_opens_as_one_block_of_messages(self, loaded):
        rules, _raw, blocks = loaded
        assert blocks[0][1] == "Press {btn:A} to talk.{box-break}\nNext box{sfx:27001}"
        assert rules.get_message_attributes(0, 2)["message_id"] == 0x21CC

    def test_an_unchanged_project_saves_the_identical_rom(self, loaded):
        rules, raw, blocks = loaded
        assert rules.save_data_to_json_obj(blocks, {}) == raw

    def test_an_edit_lands_in_the_rom_and_nothing_else_changes(self, loaded):
        rules, _raw, blocks = loaded
        blocks[0][0] = blocks[0][0].replace("Blue Rupee", "Sapphire Rupee of the Great Ocean")
        again, _ = GameRules().load_data_from_json_obj(rules.save_data_to_json_obj(blocks, {}))
        assert again == blocks

    def test_saving_starts_from_the_source_rom(self, loaded):
        rules, raw, blocks = loaded
        blocks[0][0] += " More."
        translated = rules.save_data_to_json_obj(blocks, {})

        class Context:
            def existing_versions(self):
                return iter([translated, raw])

        rules.prepare_save_context(Context())
        assert rules.save_data_to_json_obj(blocks, {}) == translated

    def test_text_that_outgrows_its_range_moves_and_the_code_follows(self, loaded, monkeypatch):
        import plugins.common.z64_rules as z64_rules
        rules, raw, blocks = loaded
        calls = []

        def fake_retarget(code, old, new, expected):
            calls.append((old, new, expected))
            return code

        monkeypatch.setattr(z64_rules, "retarget_constant", fake_retarget)
        original = blocks[0][0]
        blocks[0][0] += "x" * 1300
        with pytest.raises(ValueError, match="the game reads at most 1280"):
            rules.save_data_to_json_obj(blocks, {})
        blocks[0][0] = original
        blocks[0][1] = blocks[0][1] + "y" * 1000
        blocks[0][2] = blocks[0][2] + "z" * 1000
        out = N64Rom(rules.save_data_to_json_obj(blocks, {}))
        assert calls == [(0x100000, N64Rom(raw).free_vrom(), 4)]
        assert out.files[29][0] == N64Rom(raw).free_vrom()
        again, _ = GameRules().load_data_from_json_obj(bytes(out.data))
        assert again == blocks

    def test_saving_without_a_rom_is_refused(self):
        with pytest.raises(ValueError, match=r"Open the Zelda: Majora's Mask \(N64\) ROM"):
            GameRules().save_data_to_json_obj([["text"]], {})

    def test_line_width_follows_the_game_table_and_the_box_type(self, loaded):
        rules, _raw, _blocks = loaded
        assert rules.calculate_string_width_override("AV", {}) == 12 + 11
        assert rules.calculate_string_width_override("{btn:A}{color:red}", {}) == 14
        assert rules.get_string_layout(0, 2)["max_width"] == TYPE_LINE_WIDTH[6]

    def test_another_game_is_refused(self, raw_rom):
        raw = bytearray(raw_rom)
        raw[0x3B:0x3F] = b"CZLE"
        with pytest.raises(ValueError, match="supports NZSE v0"):
            GameRules().load_data_from_json_obj(bytes(raw))


class TestContext:
    @pytest.fixture
    def rules(self, raw_rom, tmp_path, monkeypatch):
        import json
        (tmp_path / "context.json").write_text(json.dumps({
            "messages": {
                "0x0002": {"item": "Blue Rupee"},
                "0x0003": {"speakers": ["Romani"], "actors": ["En_Ma4"], "scenes": ["Romani Ranch"]},
                "0x21CC": {"speakers": ["En_Go2", "Anju"], "place": "Clock Town"},
            },
            "glossary": [{"term": "Romani", "section": "Characters", "message_ids": ["0x0003"], "note": "rancher"}],
        }), encoding="utf-8")
        monkeypatch.setattr(GameRules, "data_dir", str(tmp_path))
        game = GameRules()
        game.load_data_from_json_obj(raw_rom)
        return game

    def test_a_single_known_speaker_is_returned_and_ambiguity_is_not(self, rules):
        assert rules.get_speaker_for_string(0, 1) == "Romani"
        assert rules.get_speaker_for_string(0, 2) is None and rules.get_speaker_for_string(0, 0) is None
        assert rules.is_placeholder_speaker("En_Go2") and not rules.is_placeholder_speaker("Romani")

    def test_item_and_place_messages_carry_their_role(self, rules):
        assert rules.get_translation_context_for_string(0, 0)["content_role"] == "ItemGet"
        place = rules.get_translation_context_for_string(0, 2)
        assert place["content_role"] == "PlaceName" and place["has_speaker"] is False
        assert rules.get_translation_context_for_string(0, 1) == {}

    def test_scene_context_and_glossary_seeds(self, rules):
        assert rules.get_scene_context_for_string(0, 1) == {"candidate_actors": ["Romani"],
                                                            "location_candidates": ["Romani Ranch"]}
        assert rules.get_glossary_seed_entries() == [{"term": "Romani", "section": "Characters",
                                                      "description": "rancher", "blocks": [0],
                                                      "source_ref": "messages 0x0003"}]
        assert rules.get_capabilities() == {"glossary_seed", "speaker_attribution"}

    def test_without_context_nothing_is_claimed(self, raw_rom, tmp_path, monkeypatch):
        monkeypatch.setattr(GameRules, "data_dir", str(tmp_path))
        game = GameRules()
        game.load_data_from_json_obj(raw_rom)
        assert game.get_capabilities() == set() and game.get_speaker_for_string(0, 1) is None


class TestReference:
    @pytest.fixture
    def seed(self, tmp_path):
        import json
        path = tmp_path / "mm3d_seed.json"
        path.write_text(json.dumps({"source": {}, "messages": {
            "0x0002": {"index": 0, "uk": "Ти отримав {color:blue}Синю Рупію{color:default}!", "status": "exact"},
            "0x21CC": {"index": 1, "uk": "Запис у щоденнику", "status": "needs_review"},
            "0x9999": {"index": 7, "uk": "Немає в ROM"},
        }}, ensure_ascii=False), encoding="utf-8")
        return path

    def test_the_seed_is_keyed_by_message_id_from_a_file_or_its_folder(self, loaded, seed):
        rules = loaded[0]
        assert rules.supports_reference_patch()
        expected = {(0, 0): "Ти отримав {color:blue}Синю Рупію{color:default}!", (0, 2): "Запис у щоденнику"}
        assert rules.load_reference_patch(str(seed)) == expected
        assert rules.load_multi_reference(str(seed.parent)) == {rules.get_reference_language_label(): expected}

    def test_without_a_rom_the_stored_index_is_used(self, seed):
        assert GameRules().load_reference_patch(str(seed)) == {
            (0, 0): "Ти отримав {color:blue}Синю Рупію{color:default}!", (0, 1): "Запис у щоденнику",
            (0, 7): "Немає в ROM"}

    def test_an_unreadable_seed_gives_nothing(self, tmp_path):
        (tmp_path / "mm3d_seed.json").write_text("not json", encoding="utf-8")
        assert GameRules().load_reference_patch(str(tmp_path)) == {}
        assert GameRules().load_reference_patch(str(tmp_path / "missing.json")) == {}


def test_the_shipped_context_belongs_to_this_rom():
    import json
    from pathlib import Path
    data = json.loads((Path("plugins") / "zelda_mm64" / "context.json").read_text(encoding="utf-8"))
    assert data["source"]["rom_sha1"] == "d6133ace5afaa0882cf214cf88daba39e266c078"
    assert len(data["messages"]) > 3000 and len(data["glossary"]) > 100
