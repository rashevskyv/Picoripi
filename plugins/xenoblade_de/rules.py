"""Xenoblade Chronicles: Definitive Edition plugin (Switch, 1.1.1 / update 196608): the Xenoblade 2 engine again.

``1_unpack.bat`` (``_shared/scripts/zt/r3bnx.py``, game ``CHRONICLES_DE_SWITCH``) copies the romfs files Picoripi
needs into the source folder at their romfs paths: the English text tables ``bdat/gb/*_ms.bdat`` (legacy BDAT, the
format of ``plugins.xenoblade_2``: 60 files, 58,336 text cells), the fonts ``menu/font/*.wifnt`` (LAFT; the game
stores them zlib-packed in an ``xbc1`` block, ``source`` holds the plain font and ``2_build.bat`` packs it again) and
the layouts with pictures ``menu/image/*.wilay`` (``menu/image/tutorial_gb`` has the English tutorial pictures).
The game keeps every file loose in its romfs, so the LayeredFS mod replaces the files themselves.
"""
from __future__ import annotations

from plugins.xenoblade_2.rules import GameRules as _Xc2Rules

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS


class GameRules(_Xc2Rules):
    """Xenoblade Chronicles: Definitive Edition (Switch, English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS

    def get_display_name(self) -> str:
        return "Xenoblade Chronicles: Definitive Edition (Switch)"
