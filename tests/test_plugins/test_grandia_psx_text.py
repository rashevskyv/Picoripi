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
    assert b"Hi.\x02" + b" " * 9 in out


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
