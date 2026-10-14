"""The key file is asked for only when the game's unpack reads that console (the unpack_key_consoles hook)."""
from core.project_library import images, plugin_facts
from plugins.base_game_rules import BaseGameRules


class _Game:
    def __init__(self, consoles):
        self._consoles = consoles

    def unpack_key_consoles(self):
        return self._consoles


class _BrokenGame:
    def unpack_key_consoles(self):
        raise RuntimeError("a plugin bug")


def test_default_hook_declares_no_console():
    assert BaseGameRules(None).unpack_key_consoles() == []


def test_key_console_follows_the_games_declaration(monkeypatch):
    monkeypatch.setattr(images, "needs_key", lambda path: "3ds")

    assert plugin_facts._key_console(_Game(["3ds"]), "game.cci") == "3ds"
    assert plugin_facts._key_console(_Game(["switch"]), "game.cci") == ""
    assert plugin_facts._key_console(_Game([]), "game.cci") == ""


def test_a_failing_hook_asks_for_no_key(monkeypatch):
    monkeypatch.setattr(images, "needs_key", lambda path: "3ds")

    assert plugin_facts._key_console(_BrokenGame(), "game.cci") == ""


def test_a_file_that_needs_no_key_gets_no_console(monkeypatch):
    monkeypatch.setattr(images, "needs_key", lambda path: None)

    assert plugin_facts._key_console(_Game(["3ds"]), "game.gcm") == ""
