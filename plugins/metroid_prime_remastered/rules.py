r"""Metroid Prime Remastered plugin: the English MSBT tables unpacked from the game's Retro packages.

The same formats as Metroid Prime 4 (``plugins.metroid_prime4``), so the rules are reused; only the name,
the problem ids and the font and texture lists differ. A project's source folder is the workspace's
``source\`` (``1_unpack.bat``, ``zt\mpr.py``): ``text\TEXT_*.msbt`` (the labels are the Metroid Prime 1
message names, e.g. ``TEXT_ScansChozoRuins``), ``font\FONT_*.rfont`` and ``texture\<package>\*.txtr``.
"""
from plugins.metroid_prime4.rules import GameRules as Prime4Rules

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS


class GameRules(Prime4Rules):
    """Metroid Prime Remastered (Switch)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS

    def get_display_name(self) -> str:
        return "Metroid Prime Remastered"
