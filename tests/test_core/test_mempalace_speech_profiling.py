# tests/test_core/test_mempalace_speech_profiling.py
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from core.mempalace.character_profiler import MemePalaceCharacterProfilerWorker
from core.mempalace_client import MemePalaceClient

@pytest.fixture
def mock_client():
    return MagicMock(spec=MemePalaceClient)

@pytest.fixture
def mock_ai():
    provider = MagicMock()
    # Mock AI response
    response = MagicMock()
    response.text = "Translated context details."
    provider.translate.return_value = response
    return provider

@pytest.fixture
def profiler(mock_client, mock_ai):
    return MemePalaceCharacterProfilerWorker(
        client=mock_client,
        ai_provider=mock_ai,
        wing_name="Zelda_TP",
        target_lang="Ukrainian"
    )

# The Zelda Wiki fetch itself moved into the plugin that owns it; its cases now
# live in tests/test_plugins/test_zelda_wiki_lore.py. What stays here is the
# engine's half: asking whichever plugin is active, and translating the answer.


def test_fetch_external_lore_asks_the_active_plugin(profiler):
    profiler.mw = MagicMock()
    profiler.mw.current_game_rules.get_external_lore.return_value = (
        "Page: Midna\nMidna is a character in Twilight Princess."
    )

    lore = profiler._fetch_external_lore("Midna")

    profiler.mw.current_game_rules.get_external_lore.assert_called_once_with("Midna")
    assert "Translated context details." in lore
    assert "Midna" in lore


def test_fetch_external_lore_without_a_plugin_source(profiler):
    """A plugin with no lore source grounds the profile in the script alone."""
    profiler.mw = SimpleNamespace(current_game_rules=SimpleNamespace())
    assert profiler._fetch_external_lore("Midna") == ""


def test_fetch_external_lore_survives_a_broken_plugin(profiler):
    profiler.mw = MagicMock()
    profiler.mw.current_game_rules.get_external_lore.side_effect = RuntimeError("boom")
    assert profiler._fetch_external_lore("Midna") == ""


def test_fetch_external_lore_treats_nothing_found_as_nothing(profiler):
    profiler.mw = MagicMock()
    profiler.mw.current_game_rules.get_external_lore.return_value = None
    assert profiler._fetch_external_lore("Midna") == ""


def test_translate_wiki_to_target_lang_english(mock_client, mock_ai):
    # When target lang is English, translation is skipped
    english_profiler = MemePalaceCharacterProfilerWorker(
        client=mock_client,
        ai_provider=mock_ai,
        target_lang="English"
    )
    res = english_profiler._translate_wiki_to_target_lang("Link", "Link is a hero.")
    assert "Page: Link" in res
    assert "Link is a hero." in res
    assert not mock_ai.translate.called

def test_translate_wiki_to_target_lang_failure_fallback(profiler):
    # When AI translation fails, fallback to original English text
    profiler.ai_provider.translate.side_effect = Exception("AI error")
    res = profiler._translate_wiki_to_target_lang("Midna", "Original English wiki text")
    assert "Page: Midna (Original English Context)" in res
    assert "Original English wiki text" in res

def test_character_profiler_skips_existing_long_profile(mock_client, mock_ai):
    mock_client.get_all_character_lines.return_value = {
        "RUSL": [
            "Tell me about the forest",
            "Take care of the children",
            "A strange sadness falls",
        ]
    }
    existing_entry = SimpleNamespace(
        original="RUSL",
        translation="Rusl",
        notes="line one\nline two\nline three",
        profiled=True,
    )
    glossary_manager = MagicMock()
    glossary_manager.get_entry.return_value = existing_entry

    worker = MemePalaceCharacterProfilerWorker(
        client=mock_client,
        ai_provider=mock_ai,
        wing_name="Zelda_TP",
        glossary_manager=glossary_manager,
        target_lang="English",
    )
    worker._fetch_external_lore = MagicMock(return_value="")

    worker.run()

    mock_ai.translate.assert_not_called()
    glossary_manager.update_entry.assert_called_with(
        original="RUSL",
        translation="Rusl",
        notes="line one\nline two\nline three",
        profiled=True,
    )

def test_character_profiler_reprofiles_short_existing_profile(mock_client):
    mock_client.get_all_character_lines.return_value = {
        "RUSL": [
            "Tell me about the forest",
            "Take care of the children",
            "A strange sadness falls",
        ]
    }
    existing_entry = SimpleNamespace(
        original="RUSL",
        translation="Rusl",
        notes="short",
        profiled=True,
    )
    glossary_manager = MagicMock()
    glossary_manager.get_entry.return_value = existing_entry

    ai_provider = MagicMock()
    profile_response = MagicMock()
    profile_response.text = json.dumps({
        "name_translation": "Rusl",
        "speech_profile": "Fresh detailed speech profile.",
    })
    synth_response = MagicMock()
    synth_response.text = "Final synthesized notes."
    ai_provider.translate.side_effect = [profile_response, synth_response]

    worker = MemePalaceCharacterProfilerWorker(
        client=mock_client,
        ai_provider=ai_provider,
        wing_name="Zelda_TP",
        glossary_manager=glossary_manager,
        target_lang="English",
    )
    worker._fetch_external_lore = MagicMock(return_value="")

    worker.run()

    assert ai_provider.translate.call_count == 2
    first_update = glossary_manager.update_entry.call_args_list[0].kwargs
    assert first_update == {
        "original": "RUSL",
        "translation": "Rusl",
        "notes": "short",
        "profiled": False,
    }
    glossary_manager.update_entry.assert_any_call(
        original="RUSL",
        translation="Rusl",
        notes="Final synthesized notes.",
        profiled=True,
    )
