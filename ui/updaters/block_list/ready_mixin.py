"""Cache invalidation and ready/notify callbacks for the block tree."""
from __future__ import annotations


class ReadyMixin:
    """Cache invalidation and ready/notify callbacks for the block tree."""

    def invalidate_mempalace_story_cache(self) -> None:
        """Force the next tree refresh to read the latest normalized story links."""
        worker_running = bool(
            self._chapters_load_worker and self._chapters_load_worker.isRunning()
        )
        self._chapters_cache = None
        self._chapter_mappings_cache = None
        self._story_projection_cache = None
        self._story_item_mappings_cache = {}
        self._reference_item_groups_cache = None
        self._window_kind_groups_cache = None
        self._script_speaker_raw_cache = None
        self.mw.data_store.virtual_block_cache = {}
        settings_updater = getattr(self.mw, "string_settings_updater", None)
        clear_context = getattr(settings_updater, "clear_story_context_cache", None)
        if callable(clear_context):
            clear_context()
        self._chapters_load_error = None
        self._is_loading_chapters = worker_running

    def force_refresh_virtual_folders(self) -> None:
        """User-triggered full rebuild of the virtual folders from current data.

        Drops every virtual-folder cache (including the persisted session cache
        and the cached per-row marked-script speaker scan) and re-reads the story
        projection from the database, so the Speakers/Chapters/Items folders are
        rebuilt from the single source of truth and match the editor exactly.
        Wired to the ⟳ button in the block toolbar.
        """
        self.invalidate_mempalace_story_cache()

        # Also drop the marked-script parse caches so an edited script re-reads.
        composer = getattr(self.mw, "translation_handler", None)
        prompt_composer = getattr(composer, "prompt_composer", None) if composer else None
        for attr in ("_line_to_speaker_cache", "_line_to_speaker_path", "_script_lines_cache"):
            if prompt_composer is not None and hasattr(prompt_composer, attr):
                try:
                    setattr(prompt_composer, attr, None)
                except Exception:
                    pass

        # Deep pass (button-only): resolve every remaining row against the marked
        # script the same way the editor field does, so live-fuzzy-only rows also
        # move into their speaker folder. Cached so later rebuilds reuse it.
        from core.speaker_resolution import resolve_script_speaker_raw_rows
        try:
            self._script_speaker_raw_cache = resolve_script_speaker_raw_rows(
                self.mw, prompt_composer
            )
        except Exception as exc:
            from utils.logging_utils import log_error
            log_error(f"force_refresh_virtual_folders: deep script scan failed: {exc}")
            self._script_speaker_raw_cache = None

        self.populate_blocks()

        settings = getattr(self.mw, "string_settings_updater", None)
        refresh_panel = getattr(settings, "update_string_settings_panel", None)
        if callable(refresh_panel):
            refresh_panel()

        status_bar = getattr(self.mw, "statusBar", None)
        if callable(status_bar):
            try:
                status_bar().showMessage("Virtual folders rebuilt from current story data.", 4000)
            except Exception:
                pass

    def refresh_virtual_folder_labels(self) -> None:
        """Rebuild folders so glossary-translated speaker names update.

        Cheaper than ``force_refresh_virtual_folders``: it does NOT re-run the
        deep per-row script scan (the raw speaker names are unchanged); it only
        re-applies the current glossary translation. Called after the glossary
        dialog closes so renaming a speaker's translation is reflected at once.
        """
        if getattr(self, "_speaker_pool_cache", None) is None:
            return
        self.populate_blocks()
        settings = getattr(self.mw, "string_settings_updater", None)
        refresh_panel = getattr(settings, "update_string_settings_panel", None)
        if callable(refresh_panel):
            refresh_panel()

    def when_virtual_blocks_ready(self, callback) -> None:
        """Run callback once the complete virtual facet tree is available."""
        if not callable(callback):
            return
        if not self._is_loading_chapters:
            callback()
            return
        self._virtual_ready_callbacks.append(callback)

    def _notify_virtual_blocks_ready(self) -> None:
        callbacks, self._virtual_ready_callbacks = self._virtual_ready_callbacks, []
        for callback in callbacks:
            callback()

    def when_tree_state_ready(self, callback) -> None:
        """Run callback after expansion, selection, string, cursor and scroll restore."""
        if not callable(callback):
            return
        if not self._tree_state_restore_pending:
            callback()
            return
        self._tree_state_ready_callbacks.append(callback)

    def _notify_tree_state_ready(self) -> None:
        self._tree_state_restore_pending = False
        callbacks, self._tree_state_ready_callbacks = (
            self._tree_state_ready_callbacks,
            [],
        )
        for callback in callbacks:
            callback()

    def _data_shape_signature(self) -> list[int]:
        return [len(block) for block in getattr(self.mw.data_store, "data", [])]
