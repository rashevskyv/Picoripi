# tests/test_core/test_mempalace_speech_profiling.py
import json
import urllib.request
import urllib.error
import socket
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
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

@patch("urllib.request.urlopen")
def test_fetch_zelda_wiki_description_success(mock_urlopen, profiler):
    # Mock search and extracts responses
    def urlopen_side_effect(req, timeout=5):
        url = req.full_url if hasattr(req, "full_url") else req
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.status = 200

        if "list=search" in url:
            data = {"query": {"search": [{"title": "Midna"}]}}
        elif "prop=extracts" in url:
            data = {"query": {"pages": {"101": {"extract": "Midna is a character in Twilight Princess."}}}}
        else:
            data = {}

        resp.read.return_value = json.dumps(data).encode("utf-8")
        return resp

    mock_urlopen.side_effect = urlopen_side_effect

    desc = profiler._fetch_zelda_wiki_description("Midna")
    assert "Midna" in desc
    assert "Translated context details." in desc
    assert profiler.ai_provider.translate.called

@patch("urllib.request.urlopen")
def test_fetch_zelda_wiki_description_raw_wikitext_fallback(mock_urlopen, profiler):
    # Mock search, empty extracts, and successful wikitext revision response
    def urlopen_side_effect(req, timeout=5):
        url = req.full_url if hasattr(req, "full_url") else req
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.status = 200

        if "list=search" in url:
            data = {"query": {"search": [{"title": "Zelda"}]}}
        elif "prop=extracts" in url:
            # Empty extract
            data = {"query": {"pages": {"102": {"extract": ""}}}}
        elif "prop=revisions" in url:
            data = {
                "query": {
                    "pages": {
                        "102": {
                            "revisions": [
                                {
                                    "slots": {
                                        "main": {
                                            "*": "{{Infobox}} [[File:Zelda.png]] Princess Zelda is a key character."
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        else:
            data = {}

        resp.read.return_value = json.dumps(data).encode("utf-8")
        return resp

    mock_urlopen.side_effect = urlopen_side_effect

    desc = profiler._fetch_zelda_wiki_description("Zelda")
    assert "Zelda" in desc
    assert "Translated context details." in desc
    assert profiler.ai_provider.translate.called

@patch("urllib.request.urlopen")
def test_fetch_zelda_wiki_description_not_found(mock_urlopen, profiler):
    # Mock search response with no results
    resp = MagicMock()
    resp.__enter__.return_value = resp
    resp.status = 200
    resp.read.return_value = json.dumps({"query": {"search": []}}).encode("utf-8")
    mock_urlopen.return_value = resp

    desc = profiler._fetch_zelda_wiki_description("UnknownCharacter")
    assert desc == ""

@patch("urllib.request.urlopen")
def test_fetch_zelda_wiki_description_http_500_error(mock_urlopen, profiler):
    # Mock server error
    mock_urlopen.side_effect = urllib.error.HTTPError("url", 500, "Internal Server Error", {}, None)

    desc = profiler._fetch_zelda_wiki_description("Link")
    assert desc == ""

@patch("urllib.request.urlopen")
def test_fetch_zelda_wiki_description_timeout(mock_urlopen, profiler):
    # Mock socket timeout
    mock_urlopen.side_effect = socket.timeout("timeout")

    desc = profiler._fetch_zelda_wiki_description("Link")
    assert desc == ""

@patch("urllib.request.urlopen")
def test_fetch_zelda_wiki_description_invalid_json(mock_urlopen, profiler):
    resp = MagicMock()
    resp.__enter__.return_value = resp
    resp.status = 200
    resp.read.return_value = b"invalid json content"
    mock_urlopen.return_value = resp

    desc = profiler._fetch_zelda_wiki_description("Link")
    assert desc == ""

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
    worker._fetch_zelda_wiki_description = MagicMock(return_value="")

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
    worker._fetch_zelda_wiki_description = MagicMock(return_value="")

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
