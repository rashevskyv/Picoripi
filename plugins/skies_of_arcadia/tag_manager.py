"""Tag manager of the Skies of Arcadia Legends plugin: the byte tokens {00} to {ff} are the legitimate tags."""
from plugins.common.tag_manager import GenericTagManager

from . import text


class TagManager(GenericTagManager):
    extra_legitimate_tags = tuple(sorted(text.TOKENS))
