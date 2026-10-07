"""Tag manager of the Tri Force Heroes plugin: the A Link Between Worlds one with this game's tags."""
from plugins.zelda_albw.tag_manager import TagManager as _AlbwTagManager

from . import tags


class TagManager(_AlbwTagManager):
    """``{Name:args}`` tags of ``Alice.msbp`` and raw ``{tag:G:T:hex}`` tags."""

    tags = tags
