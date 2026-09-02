"""TreeContextMenuMixin composition."""
from components.tree_context_menu.menu_mixin import MenuMixin
from components.tree_context_menu.story_mixin import StoryMixin
from components.tree_context_menu.block_actions_mixin import BlockActionsMixin


class TreeContextMenuMixin(MenuMixin, StoryMixin, BlockActionsMixin):
    """Builds and shows the right-click context menu."""
