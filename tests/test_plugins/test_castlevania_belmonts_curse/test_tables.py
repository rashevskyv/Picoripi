"""Castlevania: Belmont's Curse project files: the table JSON round trip, the changed-text detection and the SWUK
import's file writing. The tests write their own files; no game data is used."""
import json

from plugins.castlevania_belmonts_curse import build, tables


def test_table_json_round_trips_ids_and_texts():
    data = tables.table_json("World_Catacombs_en", [(2522254586, "Catacombs of Paris"), (7, "Внутрішній двір")])
    name, entries = tables.parse_table_json(data)
    assert name == "World_Catacombs_en"
    assert entries == [(2522254586, "Catacombs of Paris"), (7, "Внутрішній двір")]
    assert data.endswith(b"\n")
    assert json.loads(data.decode("utf-8"))["table"] == "World_Catacombs_en"


def test_only_translated_texts_that_differ_from_the_source_are_edits(tmp_path):
    source = tmp_path / "source" / "message"
    translation = tmp_path / "translation" / "message"
    source.mkdir(parents=True)
    translation.mkdir(parents=True)
    (source / "UI_A_en.json").write_bytes(tables.table_json("UI_A_en", [(1, "Equipment"), (2, "Items"), (3, "")]))
    (translation / "UI_A_en.json").write_bytes(tables.table_json("UI_A_en", [(1, "Спорядження"), (2, "Items"), (3, "")]))
    edits = build.changed_texts(tmp_path / "source", tmp_path / "translation")
    assert edits == {"UI_A_en": {1: "Спорядження"}}


def test_an_unchanged_translation_gives_no_edits(tmp_path):
    source = tmp_path / "source" / "message"
    translation = tmp_path / "translation" / "message"
    source.mkdir(parents=True)
    translation.mkdir(parents=True)
    data = tables.table_json("UI_B_en", [(5, "Credits")])
    (source / "UI_B_en.json").write_bytes(data)
    (translation / "UI_B_en.json").write_bytes(data)
    assert build.changed_texts(tmp_path / "source", tmp_path / "translation") == {}
