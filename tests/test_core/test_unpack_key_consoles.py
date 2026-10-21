"""The key file is asked for only when the game's unpack reads that console (the unpack_key_consoles hook)."""
from core.project_library import plugin_facts
from plugins.base_game_rules import BaseGameRules

LOCKED_3DS = {"kind": "3ds", "title_id": "0004000000167700", "encrypted": True}


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


def test_key_console_follows_the_games_declaration():
    assert plugin_facts._key_console(LOCKED_3DS, plugin_facts._unpack_consoles(_Game(["3ds"]))) == "3ds"
    assert plugin_facts._key_console(LOCKED_3DS, plugin_facts._unpack_consoles(_Game(["switch"]))) == ""
    assert plugin_facts._key_console(LOCKED_3DS, plugin_facts._unpack_consoles(_Game([]))) == ""


def test_a_failing_hook_asks_for_no_key():
    assert plugin_facts._unpack_consoles(_BrokenGame()) == []
    assert plugin_facts._key_console(LOCKED_3DS, plugin_facts._unpack_consoles(_BrokenGame())) == ""


def test_a_file_that_needs_no_key_gets_no_console():
    plain_disc = {"kind": "gc", "game_id": "GZ2E01", "encrypted": False}
    assert plugin_facts._key_console(plain_disc, ["3ds"]) == ""
    assert plugin_facts._key_console(None, ["3ds"]) == ""
