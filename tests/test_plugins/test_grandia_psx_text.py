"""Grandia PS1 text (plugins/grandia/psx_text.py): battle chains, dialogue blocks with control-byte tags, the bounded
writer, and the plugin. Synthetic bytes only; the owner's disc 1 is used when present."""
import json
import os
import struct
from pathlib import Path

import pytest

import romhacking_root

from plugins.grandia import psx_text

REAL_IMG = romhacking_root.under(r"Grandia\Grandia\PlayStation\ISO\Grandia disc 1.img")
SPEAKER_SEQ = b"\x0f\x03\x0a\x0c\x00"
CONFIG = Path(__file__).resolve().parents[2] / "plugins" / "grandia" / "config.json"


def chain(names):
    return b"".join(name.encode("latin-1") + b"\x00\x03" for name in names)


def dialogue(*lines):
    """Synthetic field script: each line is preceded by a speaker sequence and a 0x08 byte, and followed by 0x02."""
    out = b""
    for line in lines:
        out += SPEAKER_SEQ + b"\x08" + line.encode("latin-1") + b"\x02"
    return out


def test_battle_chain_reads_every_record_in_order():
    names = ["Party"] + [f"Skill{i}" for i in range(14)]
    data = b"\x11" * 40 + b"\x03" + chain(names) + b"\x22" * 20
    records = psx_text.battle_records(data)
    assert [text.decode("latin-1") for _, text in records] == names
    assert psx_text.is_ps1_text(data)


def test_short_chain_is_not_battle_text():
    data = chain(["Attack", "Magic", "Items"])
    assert psx_text.battle_records(data) == []
    assert not psx_text.is_ps1_text(data)


def test_chain_breaks_at_a_gap_and_keeps_the_longer_side():
    names = [f"Name{i}" for i in range(18)]
    data = chain(names[:13]) + b"\x01\x01\x01" + chain(names[13:])
    records = psx_text.battle_records(data)
    assert len(records) == 13 and records[0][1] == b"Name0"


def test_dialogue_runs_stop_at_control_bytes():
    data = b"\x30\x7e Synthetic line one.\x01Synthetic line two,\x07\x02\x0e Hi"
    texts = [text for _, text in psx_text.dialogue_runs(data)]
    assert texts == [b"0~ Synthetic line one.", b"Synthetic line two,"]


def test_dialogue_is_detected_by_the_speaker_sequence():
    data = dialogue("Hello there.", "Bye.")
    assert psx_text.is_dialogue(data)
    assert not psx_text.is_dialogue(b"Hello there. Bye.")
    kind, found = psx_text.entries(data)
    assert kind == "dialogue"
    assert [block for _, block in found] == [b"Hello there.\x02", b"Bye.\x02"]


def test_dialogue_text_shows_control_bytes_as_tags():
    data = dialogue("Hello there.", "Bye.")
    texts, names = psx_text.blocks(data)
    assert texts == ["Hello there.<02>", "Bye.<02>"]
    assert names["0"].startswith("dialogue")


def test_no_speaker_sequence_means_not_routed():
    assert psx_text.blocks(b"\x01 Hello there, Justin.\x02")[0] == []


def test_render_and_parse_are_exact_inverses_for_every_byte():
    raw = bytes(range(256))
    assert psx_text.parse(psx_text.render(raw)) == raw


def test_unchanged_text_writes_back_byte_exact():
    data = dialogue("Hello there.", "Bye now.") + b"\x07\x01 no-speaker run\x02"
    texts, _ = psx_text.blocks(data)
    out, refused = psx_text.write(data, texts)
    assert out == data and refused == []


def test_shorter_text_is_padded_to_the_original_length():
    data = dialogue("Hello there.", "Bye now.")
    out, refused = psx_text.write(data, ["Hi.<02>", "Bye now.<02>"])
    assert refused == []
    assert len(out) == len(data)
    assert b"Hi." + b" " * 9 + b"\x02" in out


def test_longer_text_is_refused_and_keeps_the_original():
    data = dialogue("Hi.", "Bye.")
    out, refused = psx_text.write(data, ["Hello there, friend.<02>", "Bye.<02>"])
    assert refused == [0]
    assert out == data


def test_non_ascii_text_is_refused():
    data = dialogue("Hello.", "Bye.")
    out, refused = psx_text.write(data, ["Привіт<02>", "Bye.<02>"])
    assert refused == [0] and out == data


def test_battle_write_keeps_the_record_separators():
    names = [f"Item{i:02d}" for i in range(13)]
    data = chain(names)
    out, refused = psx_text.write(data, ["Item00", "Itm"] + names[2:])
    assert refused == []
    assert out.count(b"\x00\x03") == len(names)
    assert len(out) == len(data)
    assert psx_text.battle_records(out)[1][1] == b"Itm" + b" " * 3


def test_config_aliases_name_real_tags():
    mappings = json.loads(CONFIG.read_text(encoding="utf-8")).get("default_tag_mappings", {})
    assert mappings, "the Grandia config should ship default tag aliases"
    for alias, raw in mappings.items():
        assert alias.startswith("{") and alias.endswith("}")
        assert psx_text.parse(raw) is not None, raw


@pytest.mark.skipif(not os.path.exists(REAL_IMG), reason="the owner's Grandia disc 1 is not on disk")
def test_real_battle_file_has_the_party_chain():
    from core.containers.psx_disc import open_psx

    image = open_psx(str(REAL_IMG).replace(".img", ".cue"))
    entry = {f.path: f for f in image.files()}["BATLE/B001.BBG"]
    data = image.read_file(entry)
    texts = [text for _, text in psx_text.battle_records(data)]
    assert b"Party" in texts and b"Justin" in texts and b"Magic" in texts
    image.stream.close()


@pytest.mark.skipif(not os.path.exists(REAL_IMG), reason="the owner's Grandia disc 1 is not on disk")
def test_real_field_script_round_trips_byte_exact():
    from core.containers.psx_disc import open_psx

    image = open_psx(str(REAL_IMG).replace(".img", ".cue"))
    data = image.read_file({f.path: f for f in image.files()}["FIELD/3034.MDP"])
    image.stream.close()
    texts, _ = psx_text.blocks(data)
    assert len(texts) > 100
    out, refused = psx_text.write(data, texts)
    assert out == data and refused == []


def test_plugin_identifies_a_psx_cue_as_base(tmp_path):
    from plugins.grandia.rules import GameRules
    from test_core.test_psx_disc import make_disc

    cue = make_disc(tmp_path)
    assert GameRules().identify_source(cue) == {"role": "base", "platform": "psx"}
    assert {p["id"] for p in GameRules().get_platforms()} == {"gdrom", "psx"}


def test_plugin_loads_and_saves_dialogue_through_the_bounded_writer():
    from plugins.grandia.rules import GameRules

    rules = GameRules()
    data = dialogue("Hello there.", "Bye now.")
    texts, names = rules.load_data_from_json_obj(data)
    assert texts[0] == ["Hello there.<02>", "Bye now.<02>"]
    out = rules.save_data_to_json_obj([["Hi.<02>", "Bye now.<02>"]], names)
    assert out == psx_text.write(data, ["Hi.<02>", "Bye now.<02>"])[0]
    assert len(out) == len(data)


def test_budget_counts_blocks_and_bytes():
    data = dialogue("Hello there.", "Bye.")
    measured = psx_text.budget(data)
    assert measured["blocks"] == 2
    assert measured["bytes"] == len(b"Hello there.\x02") + len(b"Bye.\x02")
    assert measured["largest"] == len(b"Hello there.\x02")
    assert psx_text.budget(b"nothing here") == {"blocks": 0, "bytes": 0, "largest": 0}


def _table(*entries):
    """A field script's entry table: (offset word, size) pairs, then empty entries up to 0x200."""
    out = b"".join(struct.pack("<II", word, size) for word, size in entries)
    return out + b"\xff" * (0x200 - len(out))


def test_script_section_is_the_entry_that_holds_the_speakers():
    data = bytearray(_table((0x100, 0x80), (0x01000200, 0x80)) + b"\x00" * (0x400 - 0x200))
    for at in (0x110, 0x130):
        data[at:at + 5] = SPEAKER_SEQ
    data[0x210:0x215] = SPEAKER_SEQ
    assert psx_text.script_section(bytes(data)) == (0x100, 0x80)


def test_script_section_ignores_the_flag_byte_and_empty_entries():
    data = bytearray(_table((0x07000100, 0x80)) + b"\x00" * 0x200)
    data[0x120:0x125] = SPEAKER_SEQ
    assert psx_text.script_section(bytes(data)) == (0x100, 0x80)


def test_script_section_is_none_without_speakers_or_outside_every_entry():
    assert psx_text.script_section(_table() + b"\x00" * 0x200) is None
    data = bytearray(_table((0x100, 0x80)) + b"\x00" * 0x300)
    data[0x300:0x305] = SPEAKER_SEQ
    assert psx_text.script_section(bytes(data)) is None


def test_script_section_skips_an_entry_that_runs_past_the_data():
    data = bytearray(_table((0x100, 0x10000)) + b"\x00" * 0x200)
    data[0x120:0x125] = SPEAKER_SEQ
    assert psx_text.script_section(bytes(data)) is None


def test_plugin_psx_build_target_writes_the_edited_text_into_a_disc_copy(tmp_path):
    from core.containers.psx_disc import open_psx
    from plugins.grandia.rules import PSX_TARGET_ID, GameRules
    from test_core.test_psx_disc import make_disc

    disc_dir = tmp_path / "disc"
    disc_dir.mkdir()
    cue = make_disc(disc_dir)
    source = tmp_path / "source"
    (source / "FIELD").mkdir(parents=True)
    (source / "FIELD" / "3034.MDP").write_bytes(b"hello")
    (source / "source_image.ref").write_text(json.dumps({"game_id": "SCUS-94457", "cue": cue}), encoding="utf-8")
    translation = tmp_path / "translation"
    (translation / "FIELD").mkdir(parents=True)
    (translation / "FIELD" / "3034.MDP").write_bytes(b"HOLA!")
    rules = GameRules()
    assert PSX_TARGET_ID in {t["id"] for t in rules.get_build_targets()}
    result = rules.build_target(PSX_TARGET_ID, str(source), str(translation), str(tmp_path / "build"),
                                lambda p, n: None, lambda: False)
    disc = open_psx(result)
    assert disc.read_file(next(e for e in disc.files() if e.path == "FIELD/3034.MDP")) == b"HOLA!"
    assert open_psx(cue).read_file(next(e for e in open_psx(cue).files() if e.path == "FIELD/3034.MDP")) == b"hello"


def test_growth_is_paid_by_the_next_shrunk_block_and_the_length_stays(monkeypatch):
    monkeypatch.setattr(psx_text, "POOLED_GROWTH", True)
    data = dialogue("Hello.", "Bye now, friend.")
    out, refused = psx_text.write(data, ["Hello, sir.<02>", "Bye now.<02>"])
    assert refused == []
    assert len(out) == len(data)
    assert out.startswith(SPEAKER_SEQ + b"\x08Hello, sir.\x02")
    assert b"Bye now." + b" " * 3 + b"\x02" in out          # the lender pays 5 bytes: 17 - 5 = 12


def test_growth_with_no_later_shrunk_block_is_refused(monkeypatch):
    monkeypatch.setattr(psx_text, "POOLED_GROWTH", True)
    data = dialogue("Hello.", "Bye.")
    out, refused = psx_text.write(data, ["Hi there, my friend.<02>", "Bye.<02>"])
    assert refused == [0] and out == data


def test_two_growers_share_one_lender(monkeypatch):
    monkeypatch.setattr(psx_text, "POOLED_GROWTH", True)
    data = dialogue("Hello.", "Okay now.", "Long line here to give away.")
    out, refused = psx_text.write(data, ["Hello there.<02>", "Okay now, sir.<02>", "Short.<02>"])
    assert refused == [] and len(out) == len(data)
    assert b"Hello there.\x02" in out and b"Okay now, sir.\x02" in out
    assert b"Short." + b" " * 11 + b"\x02" in out          # 29 - 11 owed = 18 bytes for the lender


def test_growth_larger_than_the_lenders_slack_refuses_the_grower_only(monkeypatch):
    monkeypatch.setattr(psx_text, "POOLED_GROWTH", True)
    data = dialogue("Hello.", "Bye now, friend.")
    out, refused = psx_text.write(data, ["Hi there, a much longer hello.<02>", "Bye.<02>"])
    assert refused == [0]
    assert len(out) == len(data)
    assert b"Hello.\x02" in out and b"Bye." + b" " * 12 + b"\x02" in out   # the lender keeps 17 - 5 = 12


def test_build_refuses_a_translated_script_of_another_length(tmp_path):
    from plugins.grandia.rules import GameRules

    source = tmp_path / "source" / "FIELD"
    source.mkdir(parents=True)
    (source / "2000.MDP").write_bytes(dialogue("Hi.", "Bye."))
    translation = tmp_path / "translation" / "FIELD"
    translation.mkdir(parents=True)
    (translation / "2000.MDP").write_bytes(dialogue("Hi.", "Bye.") + b"x")
    with pytest.raises(ValueError):
        GameRules()._psx_replacements(str(tmp_path / "source"), str(tmp_path / "translation"))


def test_over_budget_growth_is_saved_as_typed_and_the_length_grows():
    data = dialogue("Hello.", "Bye.")
    out, unparsed, over = psx_text.write_report(data, ["Hi there, my friend.<02>", "Bye.<02>"], keep_over_budget=True)
    assert unparsed == [] and over == [0]
    assert b"Hi there, my friend.\x02" in out
    assert len(out) == len(data) + len("Hi there, my friend.") - len("Hello.")


def test_over_budget_lists_only_the_growth_no_later_block_pays(monkeypatch):
    monkeypatch.setattr(psx_text, "POOLED_GROWTH", True)
    data = dialogue("Hello.", "Bye now, friend.")
    texts = ["Hello, sir.<02>", "Bye now.<02>"]
    assert psx_text.over_budget(data, texts) == []
    assert psx_text.over_budget(dialogue("Hello.", "Bye."), ["Hi there, my friend.<02>", "Bye.<02>"]) == [0]


class _DirectBodies:
    """Explicit fake of ReadThrough: reads at once."""

    def get(self, key, reader):
        return reader()


class _Block:
    def __init__(self, source_file):
        self.source_file = source_file


class _Project:
    def __init__(self, blocks):
        self.blocks = blocks


class _ProjectManager:
    def __init__(self, project, paths):
        self.project = project
        self._paths = paths

    def get_absolute_path(self, rel):
        return self._paths[rel]


class _Processor:
    def __init__(self, texts):
        self._texts = texts

    def get_block_texts(self, block_idx):
        return list(self._texts)


class _MainWindow:
    def __init__(self, source_file, path, texts):
        self.project_manager = _ProjectManager(_Project([_Block(source_file)]), {source_file: path})
        self.block_to_project_file_map = {}
        self.data_processor = _Processor(texts)


def test_plugin_saves_an_over_budget_script_and_the_build_refuses_it(tmp_path):
    from plugins.grandia.rules import GameRules

    source = tmp_path / "source" / "FIELD"
    source.mkdir(parents=True)
    (source / "2000.MDP").write_bytes(dialogue("Hello.", "Bye."))
    rules = GameRules()
    texts, names = rules.load_data_from_json_obj(dialogue("Hello.", "Bye."))
    out = rules.save_data_to_json_obj([["Hi there, my friend.<02>", "Bye.<02>"]], names)
    assert len(out) > len(dialogue("Hello.", "Bye."))   # saved as typed: the script is longer
    translation = tmp_path / "translation" / "FIELD"
    translation.mkdir(parents=True)
    (translation / "2000.MDP").write_bytes(out)
    with pytest.raises(ValueError, match="over its script budget by"):
        GameRules()._psx_replacements(str(tmp_path / "source"), str(tmp_path / "translation"))


def test_over_budget_line_is_flagged_and_a_fitting_line_is_not(tmp_path):
    from plugins.grandia.rules import GameRules

    path = tmp_path / "2000.MDP"
    path.write_bytes(dialogue("Hello.", "Bye."))
    rules = GameRules()
    rules.mw = _MainWindow("FIELD/2000.MDP", path, ["Hello.<02>", "Bye.<02>"])
    rules._sources = _DirectBodies()
    assert rules.exceeds_byte_budget(0, 0, "Hi there, my friend.<02>") is True
    assert "budget" in rules.get_problem_detail(0, 0, "GR2_BYTE_BUDGET").lower()
    assert rules.exceeds_byte_budget(0, 0, "Hi.<02>") is False
    assert rules.get_problem_detail(0, 0, "GR2_BYTE_BUDGET") == ""


def test_disc_block_is_never_flagged_by_the_budget(tmp_path):
    from plugins.grandia.rules import GameRules

    path = tmp_path / "archive.afs"
    path.write_bytes(b"not a script")
    rules = GameRules()
    rules.mw = _MainWindow("files/MAP/ARCHIVE.AFS", path, ["Any text at all, a long one."])
    rules._sources = _DirectBodies()
    assert rules.exceeds_byte_budget(0, 0, "Any text at all, a much longer one, here.") is False


def test_growth_pair_is_refused_until_relocation_is_proven():
    data = dialogue("Hello.", "Bye now, friend.")
    out, refused = psx_text.write(data, ["Hello, sir.<02>", "Bye now.<02>"])
    assert refused == [0] and len(out) == len(data)
    assert b"Hello." in out                       # the grower keeps its original text


def message(*lines):
    """Synthetic message: one speaker sequence, the lines joined by 0x01 (line break), closed by 0E 00 (message end)."""
    return SPEAKER_SEQ + b"\x08" + b"\x01".join(line.encode("latin-1") for line in lines) + b"\x0e\x00"


def test_lines_of_one_message_share_a_budget_and_the_length_stays():
    data = message("Line one", "Line two") + message("Ok fine")
    texts, _ = psx_text.blocks(data)
    assert texts[:2] == ["Line one<01>", "Line two<0E><00>"]
    out, refused = psx_text.write(data, ["Line one, long<01>", "Tw<0E><00>", "Ok fine<0E><00>"])
    assert refused == [] and len(out) == len(data)
    assert b"Line one, long\x01" in out and b"Tw\x0e\x00" in out


def test_a_growth_no_line_of_its_message_pays_is_refused_and_the_other_message_is_written():
    data = message("Hello") + message("Bye now!")
    out, refused = psx_text.write(data, ["Hello there, friend.<0E><00>", "Bye.<0E><00>"])
    assert refused == [0] and len(out) == len(data)
    assert b"Hello\x0e\x00" in out                       # the grower keeps its original text
    assert b"Bye." + b" " * 4 + b"\x0e\x00" in out        # the other message is shortened, padded before its end


def test_padding_is_placed_inside_the_printable_run_never_after_the_message_end():
    data = message("Bye now!") + message("Hi there")
    out, refused = psx_text.write(data, ["Bye.<0E><00>", "Hi there<0E><00>"])
    assert refused == [] and len(out) == len(data)
    assert b"Bye." + b" " * 4 + b"\x0e\x00" in out
