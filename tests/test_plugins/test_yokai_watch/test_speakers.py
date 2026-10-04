"""Speakers and the glossary seed from the game's own tables (a tiny workspace of invented tables)."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from plugins.testing import load_rules
from plugins.yokai_watch.glossary import seed_entries
from plugins.yokai_watch.speakers import GAME, Speakers

from .samples import cfg_file, noun_info, text_info

HERO_NOUN = GAME["player_nouns"]["m"]
HEROINE_NOUN = GAME["player_nouns"]["f"]
WHISPER_NOUN, WHISPER_BASE = 0x100, 0x200
CLERK_NOUN, CLERK_BASE, CLERK_NPC = 0x300, 0x400, 0x500


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


@pytest.fixture
def workspace(tmp_path):
    source, meta = tmp_path / "source", tmp_path / "meta"
    _write(source / "data/res/text/chara_text_en.cfg.bin", cfg_file([
        noun_info(HERO_NOUN, "Nate"), noun_info(HEROINE_NOUN, "Katie"), noun_info(WHISPER_NOUN, "Whisper"),
        noun_info(CLERK_NOUN, "Clerk"), text_info(0x600, 0, "A ghostly butler.\\nKnows everything.")]))
    _write(source / "data/res/text/system_text_en.cfg.bin", cfg_file([
        noun_info(0x700, "???"), text_info(1, 0, "Uptown Springdale")] +
        [text_info(10 + i, 0, f"Uptown - Street {chr(65 + i)}{chr(97 + i)}") for i in range(9)] + [text_info(99, 0, "Save?")]))
    _write(source / "data/res/text/help_text_en.cfg.bin", cfg_file([text_info(5, 0, "<CR>Brave Tribes</C> attack!")]))
    _write(meta / "data/res/character/chara_base_0.04j.cfg.bin", cfg_file([
        ("CHARA_BASE_INFO", [CLERK_BASE, 0, 1, 0, CLERK_NOUN, 0]),
        ("CHARA_BASE_YOKAI_INFO", [WHISPER_BASE, 6, 1, 0, WHISPER_NOUN, 0, 0, 0, 0, 0, 0x600])]))
    _write(meta / "data/txt/ev/ev01_0010_map_m.cfg.bin", cfg_file([
        ("TEXT_WASHA_MAP", [0x11, 0, WHISPER_BASE, 1, -1, 0]),
        ("TEXT_WASHA_MAP", [0x11, 1, GAME["player"], 1, -1, 0]),
        ("TEXT_WASHA_MAP", [0x12, 0, GAME["narrator"], 0, -1, 0]),
        ("TEXT_WASHA_MAP", [0x13, 0, GAME["narrator"], 0, 1, 0x700])]))
    _write(meta / "data/res/map/t101g00/t101g00_npc_set_0.02.cfg.bin", cfg_file([("NPC_BASE", [CLERK_NPC, 0, CLERK_BASE, 0])]))
    _write(meta / "data/res/map/t101g00/t101g00_npc_talk_0.02.cfg.bin", cfg_file([
        ("TALK_INFO", [WHISPER_BASE, 0, 1]), ("TALK_CONFIG", [1, 0x21, 0]),
        ("TALK_INFO", [CLERK_NPC, 1, 1]), ("TALK_CONFIG", [1, 0x22, 0])]))
    _write(meta / "data/res/map/t101g00/t101g00_npc_base_talk_c05_0.02.cfg.bin", cfg_file([
        ("BASE_TALK_INFO", [CLERK_NPC, 0, 1, 1, 0]), ("BASE_TALK_CONFIG", [0x31, 60010, 0])]))
    return source, meta


def test_event_lines_name_the_speaker_the_hero_by_file_and_the_override(workspace):
    speakers = Speakers(*workspace)
    assert speakers.speaker("data/txt/ev/ev01_0010_m_en.cfg.bin", 0x11, 0) == "Whisper"
    assert speakers.speaker("data/txt/ev/ev01_0010_m_en.cfg.bin", 0x11, 1) == "Nate"
    assert speakers.speaker("data/txt/ev/ev01_0010_m_en.cfg.bin", 0x12, 0) is None
    assert speakers.speaker("data/txt/ev/ev01_0010_m_en.cfg.bin", 0x13, 0) == "???"
    assert speakers.speaker("data/txt/ev/ev01_0010_f_en.cfg.bin", 0x11, 0) is None   # no _map_f table


def test_map_npc_lines_name_characters_and_npcs(workspace):
    speakers = Speakers(*workspace)
    talk = "data/res/map/t101g00/t101g00_npc_text_en.cfg.bin"
    assert speakers.speaker(talk, 0x21, 0) == "Whisper"
    assert speakers.speaker(talk, 0x22, 3) == "Clerk"
    assert speakers.speaker("data/res/map/t101g00/t101g00_npc_base_text_c05_0.02_en.cfg.bin", 0x31, 0) == "Clerk"
    assert speakers.speaker(talk, 0x99, 0) is None


def test_the_hook_reads_the_meta_folder_next_to_the_source(workspace):
    source, _meta = workspace
    data = cfg_file([text_info(0x11, 0, "Yo!"), text_info(0x11, 1, "Hi.")])
    rel = "data/txt/ev/ev01_0010_m_en.cfg.bin"
    _write(source / rel, data)
    block = SimpleNamespace(source_file=rel)
    pm = SimpleNamespace(project=SimpleNamespace(blocks=[block], metadata={"source_path": str(source)}),
                         get_absolute_path=lambda rel_path: str(source / rel_path))
    rules = load_rules("yokai_watch", SimpleNamespace(project_manager=pm, block_to_project_file_map={0: 0}))
    assert [rules.get_speaker_for_string(0, i) for i in (0, 1)] == ["Whisper", "Nate"]
    assert rules.get_translation_context_for_string(0, 0)["content_role"] == "Dialogue"
    assert rules.get_scene_context_for_string(0, 0)["chapter"] == "01"
    assert rules.get_ai_flow_group_for_string(0, 0) == rules.get_ai_flow_group_for_string(0, 1)
    assert rules.get_string_layout(0, 0)["lines_per_page"] == 2
    sections = {entry["term"]: entry["section"] for entry in rules.get_glossary_seed_entries()}
    assert sections["Whisper"] == "Yo-kai" and sections["Clerk"] == "Characters"


def test_glossary_seed_sections(workspace):
    entries = {entry["term"]: entry for entry in seed_entries(*workspace)}
    assert entries["Whisper"]["section"] == "Yo-kai"
    assert "A ghostly butler. Knows everything." in entries["Whisper"]["description"]
    assert entries["Brave Tribe"]["section"] == "Tribes"
    assert entries["Uptown Springdale"]["section"] == "Places" and "Street Aa" in entries
    assert "Save?" not in entries


def test_yokai_watch_3_heroes_by_voice_clip_and_language_folder(tmp_path):
    import zlib
    from plugins.yokai_watch.speakers import GAMES, game_of
    source, meta = tmp_path / "source", tmp_path / "meta"
    nate, mermaid = 0x900, 0x901
    _write(source / "data/res/text/chara_text_en.cfg.bin", cfg_file([noun_info(nate, "<PNAMEM>"),
                                                                     noun_info(mermaid, "Mermadonna")]))
    _write(source / "data/txt/ev/en/ev01_0010_en.cfg.bin", cfg_file([text_info(0x11, 0, "<PV#pv_c001000_23>Yeah.")]))
    _write(meta / "data/res/character/chara_base_0.03.25.cfg.bin", cfg_file([
        ("CHARA_BASE_INFO", [zlib.crc32(b"c001000"), 0, 1, 0, nate, 0]),
        ("CHARA_BASE_YOKAI_INFO", [zlib.crc32(b"y327000"), 6, 1, 0, mermaid, 0])]))
    _write(meta / "data/txt/ev/ev01_0010_map.cfg.bin", cfg_file([("TEXT_WASHA_MAP", [0x11, 0, GAMES["yw3"]["player"], 1, -1, 0])]))
    assert game_of(source) == "yw3"
    speakers = Speakers(source, meta)
    rel = "data/txt/ev/en/ev01_0010_en.cfg.bin"
    assert speakers.speaker(rel, 0x11, 0, "<PV#pv_c001000_23>Yeah.") == "Nate"
    assert speakers.speaker(rel, 0x99, 0, "<V#y327000>Let us begin!") == "Mermadonna"
    assert speakers.speaker(rel, 0x99, 0, "No clip.") is None
    assert {e["term"] for e in seed_entries(source, meta)} >= {"Nate", "Mermadonna"}
