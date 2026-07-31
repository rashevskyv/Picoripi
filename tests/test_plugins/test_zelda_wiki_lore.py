"""Zelda Wiki lookup, moved out of the engine and into the plugin that owns it.

These cases came over from tests/test_core/test_mempalace_speech_profiling.py,
where they were testing a Zelda-specific network call through a generic worker.
The lookup returns English prose as published; translating it stays in the
engine, which owns the AI provider and the target language.
"""
import json
import socket
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from plugins.zelda_bmg.wiki import lookup


def _responder(routes):
    """Serve canned JSON per API query, keyed by a substring of the URL."""
    def urlopen_side_effect(request, timeout=5):
        url = getattr(request, "full_url", request)
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        data = next((body for key, body in routes.items() if key in url), {})
        response.read.return_value = json.dumps(data).encode("utf-8")
        return response
    return urlopen_side_effect


SEARCH = "list=search"
EXTRACT = "prop=extracts"
REVISIONS = "prop=revisions"


class TestSuccessfulLookup:
    @patch("urllib.request.urlopen")
    def test_intro_extract_is_returned_with_its_page(self, mock_urlopen):
        mock_urlopen.side_effect = _responder({
            SEARCH: {"query": {"search": [{"title": "Midna"}]}},
            EXTRACT: {"query": {"pages": {"101": {
                "extract": "Midna is a character in Twilight Princess."}}}},
        })

        lore = lookup("Midna")

        assert lore.startswith("Page: Midna\n")
        assert "Midna is a character" in lore

    @patch("urllib.request.urlopen")
    def test_raw_wikitext_covers_an_empty_intro(self, mock_urlopen):
        """Pages that are all infobox have no extract; fall back to the source."""
        mock_urlopen.side_effect = _responder({
            SEARCH: {"query": {"search": [{"title": "Zelda"}]}},
            EXTRACT: {"query": {"pages": {"102": {"extract": ""}}}},
            REVISIONS: {"query": {"pages": {"102": {"revisions": [{"slots": {"main": {
                "*": "{{Infobox}} [[File:Zelda.png]] Princess Zelda is a key character."
            }}}]}}}},
        })

        lore = lookup("Zelda")

        assert "Princess Zelda is a key character." in lore
        # Templates and file links are noise, not lore.
        assert "Infobox" not in lore
        assert "File:" not in lore

    @patch("urllib.request.urlopen")
    def test_piped_links_keep_only_their_label(self, mock_urlopen):
        mock_urlopen.side_effect = _responder({
            SEARCH: {"query": {"search": [{"title": "Ordon"}]}},
            EXTRACT: {"query": {"pages": {"1": {"extract": ""}}}},
            REVISIONS: {"query": {"pages": {"1": {"revisions": [{"slots": {"main": {
                "*": "A village in [[Ordon Province|the south]] of [[Hyrule]]."
            }}}]}}}},
        })

        lore = lookup("Ordon")

        assert "A village in the south of Hyrule." in lore
        assert "[[" not in lore


class TestNothingUsable:
    """A missing or unreachable wiki is a missing nicety, never an error."""

    @patch("urllib.request.urlopen")
    def test_no_search_results(self, mock_urlopen):
        mock_urlopen.side_effect = _responder({SEARCH: {"query": {"search": []}}})
        assert lookup("UnknownCharacter") is None

    @patch("urllib.request.urlopen")
    def test_server_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError("url", 500, "boom", {}, None)
        assert lookup("Link") is None

    @patch("urllib.request.urlopen")
    def test_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = socket.timeout("timeout")
        assert lookup("Link") is None

    @patch("urllib.request.urlopen")
    def test_invalid_json(self, mock_urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"invalid json content"
        mock_urlopen.return_value = response
        assert lookup("Link") is None

    @pytest.mark.parametrize("term", ["", "   ", None])
    def test_a_blank_term_never_reaches_the_network(self, term):
        with patch("urllib.request.urlopen") as mock_urlopen:
            assert lookup(term) is None
            mock_urlopen.assert_not_called()


class TestPluginExposesIt:
    @patch("plugins.zelda_bmg.wiki.lookup", return_value="Page: Midna\nlore")
    def test_get_external_lore_delegates_to_the_wiki(self, mock_lookup):
        from plugins.zelda_bmg.rules import GameRules

        rules = GameRules.__new__(GameRules)
        assert rules.get_external_lore("Midna") == "Page: Midna\nlore"
        mock_lookup.assert_called_once_with("Midna")

    def test_capability_is_declared(self):
        from plugins.zelda_bmg.rules import GameRules

        assert "external_lore" in GameRules.__new__(GameRules).get_capabilities()
