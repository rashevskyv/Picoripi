from utils.logging_utils import log_debug


class TreeMixin:
    def expand_all_action(self) -> None:
        """Expand all nodes in the tree."""
        if hasattr(self.mw, 'block_list_widget'):
            tree = self.mw.block_list_widget
            tree._is_programmatic_expansion = True
            old_blocked = tree.blockSignals(True)
            tree.setUpdatesEnabled(False)
            try:
                tree.expandAll()
            finally:
                tree.blockSignals(old_blocked)
                tree.setUpdatesEnabled(True)
                tree._is_programmatic_expansion = False
            self._update_all_folder_expansion_state(True, persist=False)
            tree.viewport().update()
            log_debug("Tree expanded all.")

    def collapse_all_action(self) -> None:
        """Collapse all nodes in the tree."""
        if hasattr(self.mw, 'block_list_widget'):
            tree = self.mw.block_list_widget
            tree._is_programmatic_expansion = True
            old_blocked = tree.blockSignals(True)
            tree.setUpdatesEnabled(False)
            try:
                tree.collapseAll()
            finally:
                tree.blockSignals(old_blocked)
                tree.setUpdatesEnabled(True)
                tree._is_programmatic_expansion = False
            self._update_all_folder_expansion_state(False, persist=False)
            tree.viewport().update()
            log_debug("Tree collapsed all.")

    def _update_all_folder_expansion_state(
        self, expanded: bool, persist: bool = True
    ) -> None:
        """Internal helper to update the all folder expansion state."""
        self.mw.virtual_folder_handler.update_all_folder_expansion_state(
            expanded, persist=persist
        )

