from __future__ import annotations


class MainWindowToolsActionsMixin:
    """Markup / mempalace / pipeline / BFN actions."""

    def open_script_markup_studio(self):
        """Open the Script Markup Studio dialog in modeless mode."""
        try:
            from PyQt6 import sip
        except ImportError:
            import sip

        if hasattr(self.mw, 'script_markup_studio_dialog') and self.mw.script_markup_studio_dialog:
            try:
                if not sip.isdeleted(self.mw.script_markup_studio_dialog):
                    self.mw.script_markup_studio_dialog.show()
                    self.mw.script_markup_studio_dialog.raise_()
                    self.mw.script_markup_studio_dialog.activateWindow()
                    return
            except (RuntimeError, TypeError, NameError):
                pass
            self.mw.script_markup_studio_dialog = None

        from ui.script_markup_studio_dialog import ScriptMarkupStudioDialog
        dialog = ScriptMarkupStudioDialog(self.mw)
        self.mw.script_markup_studio_dialog = dialog
        dialog.show()

    def open_mempalace_builder(self):
        """Open the MemePalace Context Builder dialog in modeless mode."""
        self.mempalace_actions.open_mempalace_builder()

    def open_mempalace_viewer(self):
        """Open the MemePalace Database Viewer dialog."""
        self.mempalace_actions.open_mempalace_viewer()

    def inspect_story_context(self):
        """Query and display visual context/timeline for the selected row from MemePalace without translating."""
        self.mempalace_actions.inspect_story_context()

    def build_glossary_from_text(self):
        """Build the glossary by sweeping project text with AI (see docs/PIPELINE_ROADMAP.md)."""
        handler = getattr(self.mw, 'glossary_pipeline_handler', None)
        if handler is None:
            from handlers.translation.glossary_pipeline_handler import GlossaryPipelineHandler
            handler = GlossaryPipelineHandler(self.mw)
            self.mw.glossary_pipeline_handler = handler
        handler.build_from_text()

    def merge_speakers_from_script(self):
        """Name the plugin's speaker codes from the marked-up script."""
        handler = getattr(self.mw, 'speaker_merge_handler', None)
        if handler is None:
            from handlers.speaker_merge_handler import SpeakerMergeHandler
            handler = SpeakerMergeHandler(self.mw)
            self.mw.speaker_merge_handler = handler
        handler.merge_from_script()

    def open_pipeline_wizard(self):
        """Open the guided localization pipeline.

        Shown, never exec'd: the wizard's whole job is to launch other tools, so
        a modal wizard would block the very window it just opened. Kept on the
        main window and reused, so returning to it finds the same window rather
        than stacking copies.
        """
        self._show_pipeline_wizard()

    def _show_pipeline_wizard(self, step_key: str = ""):
        """Raise the wizard, optionally on a named step."""
        from ui.pipeline_wizard_dialog import PipelineWizardDialog
        dialog = getattr(self.mw, 'pipeline_wizard_dialog', None)
        if dialog is None:
            dialog = PipelineWizardDialog(self.mw)
            self.mw.pipeline_wizard_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        if step_key:
            dialog.select_step(step_key)
        return dialog

    def open_bfn_editor_standalone(self):
        """Open BFN Font Editor as a standalone window (no archive binding)."""
        self.bfn_actions.open_bfn_editor_standalone()

    def open_bfn_editor_for_block(self, block_idx: int):
        """
        Open BFN Font Editor bound to a specific .bfn block (may be inside an archive).
        After saving, updates the archive in RAM and reloads font metrics.
        """
        self.bfn_actions.open_bfn_editor_for_block(block_idx)

    def _bfn_font_sync(self):
        """Reload font metrics in Picoripi after BFN editor saves changes."""
        self.bfn_actions._bfn_font_sync()

    def export_current_bmg_to_json(self):
        """Export the currently selected BMG file's text content to a JSON file for inspection."""
        self.bfn_actions.export_current_bmg_to_json()

    def import_current_bmg_from_json(self):
        """Import BMG text content from an exported JSON file into the currently selected block."""
        self.bfn_actions.import_current_bmg_from_json()
