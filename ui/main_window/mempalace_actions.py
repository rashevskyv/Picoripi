# ui/main_window/mempalace_actions.py
from PyQt6.QtWidgets import QMessageBox
from core.i18n import tr


class MempalaceActions:
    """Helper class containing MemePalace action methods for MainWindow."""
    def __init__(self, main_window):
        self.mw = main_window

    def open_mempalace_builder(self):
        """Open the MemePalace Context Builder dialog in modeless mode."""
        try:
            from PyQt6 import sip
        except ImportError:
            import sip

        if hasattr(self.mw, 'mempalace_builder_dialog') and self.mw.mempalace_builder_dialog:
            try:
                if not sip.isdeleted(self.mw.mempalace_builder_dialog):
                    refresh = getattr(
                        self.mw.mempalace_builder_dialog,
                        "_load_active_markup_studio_project",
                        None,
                    )
                    if callable(refresh):
                        refresh()
                    self.mw.mempalace_builder_dialog.show()
                    self.mw.mempalace_builder_dialog.raise_()
                    self.mw.mempalace_builder_dialog.activateWindow()
                    return
            except (RuntimeError, TypeError, NameError):
                pass
            self.mw.mempalace_builder_dialog = None

        from ui.mempalace_builder_dialog import MemePalaceBuilderDialog
        dialog = MemePalaceBuilderDialog(self.mw)
        self.mw.mempalace_builder_dialog = dialog
        dialog.show()

    def open_mempalace_viewer(self):
        """Open the MemePalace Database Viewer dialog."""
        try:
            from PyQt6 import sip
        except ImportError:
            import sip

        if hasattr(self.mw, 'mempalace_viewer_dialog') and self.mw.mempalace_viewer_dialog:
            try:
                if not sip.isdeleted(self.mw.mempalace_viewer_dialog):
                    self.mw.mempalace_viewer_dialog.show()
                    self.mw.mempalace_viewer_dialog.raise_()
                    self.mw.mempalace_viewer_dialog.activateWindow()
                    return
            except (RuntimeError, TypeError, NameError):
                pass
            self.mw.mempalace_viewer_dialog = None

        from ui.mempalace_viewer_dialog import MemePalaceViewerDialog
        dialog = MemePalaceViewerDialog(self.mw)
        self.mw.mempalace_viewer_dialog = dialog
        dialog.show()

    def inspect_story_context(self):
        """Open (or refresh) the Story Timeline window for the selected row.

        The window draws the story timeline with a 'you are here' marker and the
        maximum available context for the current line — speaker, addressee,
        scene cast, location, character voice, chapter/event summary and the
        game's dialogue-flow. It follows the editor selection while open.
        """
        ds = getattr(self.mw, 'data_store', None)
        if not ds or ds.current_block_idx == -1 or ds.current_string_idx == -1:
            QMessageBox.warning(self.mw, tr('Story Timeline'), tr('Please select a dialogue row to inspect.'))
            return

        block_idx = ds.current_block_idx
        s_idx = ds.current_string_idx

        try:
            from PyQt6 import sip
        except ImportError:
            import sip

        dialog = getattr(self.mw, 'story_timeline_dialog', None)
        if dialog is not None:
            try:
                if not sip.isdeleted(dialog):
                    dialog.show_for(block_idx, s_idx)
                    return
            except (RuntimeError, TypeError, NameError):
                pass
            self.mw.story_timeline_dialog = None

        from ui.story_timeline_dialog import StoryTimelineDialog
        dialog = StoryTimelineDialog(self.mw)
        self.mw.story_timeline_dialog = dialog
        dialog.show_for(block_idx, s_idx)
