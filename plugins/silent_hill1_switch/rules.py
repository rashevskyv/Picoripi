"""Silent Hill 1 (Switch port, PAL disc): the Silent Hill (PlayStation) text rules with the PAL font grid.

The text code is ``silent_hill_ps1`` (PAL overlays, PAL item tables). This plugin only owns the font and
texture lists of the PAL disc, because a plugin's font list is one per plugin folder.
"""
from plugins.silent_hill_ps1.rules import GameRules as PsxGameRules


class GameRules(PsxGameRules):
    """Silent Hill 1 (Switch port, PAL disc SLES_015.14)."""

    pal_glyphs = True

    def get_display_name(self) -> str:
        return "Silent Hill 1 (Switch, PAL)"
