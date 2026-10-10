"""Tag manager of the Tomodachi Life / Miitopia plugin: the A Link Between Worlds one with these games' tags."""
from plugins.zelda_albw.tag_manager import TagManager as _AlbwTagManager

from . import tags


class TagManager(_AlbwTagManager):
    """``{Name:args}`` tags of Tomodachi Life's message project and raw ``{tag:G:T:hex}`` tags."""

    tags = tags
