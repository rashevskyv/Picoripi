"""Miitopia plugin (Switch, base game 1.0 + update 1.1.0): the 3DS game's MSBT engine again.

``1_unpack.bat`` (``zt/r3bnx.py``) decrypts the .nsp files and writes each archive as a folder of its members at
the path a LayeredFS mod replaces: ``romfs/eu/svn_message/EU_English.sarc/**/*.msbt`` (and ``us/.../US_English``),
``romfs/eu/svn_font/EU_English.sarc/*.bffnt`` and ``romfs/cmn/lyt/**/*.arc.szs/timg/__Combined.bntx``.
The text rules are those of ``plugins.mii_3ds`` (Miitopia's own tags stay raw ``{tag:G:T:hex}``).
"""
from __future__ import annotations

from plugins.mii_3ds.rules import GameRules as _MiiRules

from . import tag_manager as _tag_manager
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS


class GameRules(_MiiRules):
    """Miitopia (Switch, English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = _tag_manager.TagManager

    def get_display_name(self) -> str:
        return "Miitopia (Switch)"
