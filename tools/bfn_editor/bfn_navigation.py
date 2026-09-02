"""BFN navigation mixin composition. Implementation lives in sibling mixins."""
from tools.bfn_editor.glyph_table_mixin import GlyphTableMixin
from tools.bfn_editor.translation_map_mixin import TranslationMapMixin
from tools.bfn_editor.mapping_edit_mixin import MappingEditMixin
from tools.bfn_editor.glyph_nav_mixin import GlyphNavMixin


class BfnNavigationMixin(
    GlyphTableMixin,
    TranslationMapMixin,
    MappingEditMixin,
    GlyphNavMixin,
):
    """Glyph table, translation map, mapping edit, and glyph navigation."""


__all__ = ["BfnNavigationMixin"]
