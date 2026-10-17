"""The message-box preview of a Game Boy Color Pokemon project (Generation II): the same two-row box as Generation I.

The widget is plugins/pokemon_gen1/preview_panel.py; this module only points it at the Generation II facts.
"""
from __future__ import annotations

from pathlib import Path

from plugins.pokemon_gen1 import preview_panel as gb

ROM_FACTS_DIR = Path(__file__).with_name("rom_facts")


class MessageWindowPreview(gb.MessageWindowPreview):
    """The Game Boy Color message box in the game's font, for the editor's preview column."""

    context_loader = staticmethod(gb.make_loader(ROM_FACTS_DIR))
