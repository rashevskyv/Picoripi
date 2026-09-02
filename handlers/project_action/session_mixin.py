from PyQt6.QtWidgets import QMessageBox
from utils.logging_utils import log_info, log_warning
from core.i18n import tr
from handlers.project_action.load_worker import ProjectLoadWorker


class SessionMixin:
    def _restore_project_session_fast_path(self, on_completed=None) -> bool:
        """Restore a project from the session checkpoint before starting the full loader."""
        if not hasattr(self.data_processor, 'load_session_file'):
            return False

        try:
            session_loaded = bool(self.data_processor.load_session_file())
        except Exception as e:
            log_warning(f"Project session restore failed before full load: {e}", category="file_ops")
            return False

        if not session_loaded:
            return False

        if not getattr(self.mw.data_store, 'data', None):
            log_warning(
                "Project session restored no block data; falling back to full project load.",
                category="file_ops"
            )
            return False

        if hasattr(self.mw.data_store, 'block_to_project_file_map'):
            self.mw.block_to_project_file_map = self.mw.data_store.block_to_project_file_map

        self._ensure_project_compat_paths()

        if getattr(self.mw, 'project_manager', None):
            self.mw.project_manager.clear_archive_cache()

        if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            self.mw.translation_handler.load_progress_from_metadata()

        if hasattr(self.ui_updater, 'preview_updater'):
            self.ui_updater.preview_updater.schedule_pre_cache()

        if hasattr(self.ui_updater, 'update_statusbar_paths'):
            self.ui_updater.update_statusbar_paths()

        log_info("Project state restored from session checkpoint; skipped full project file load.")
        if on_completed:
            on_completed(True)
        return True


    def _populate_blocks_from_project(self, on_completed=None) -> None:
        """Populate block list from current project and load data asynchronously."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            if on_completed:
                on_completed(False)
            return

        startup_loading = getattr(self.mw, '_startup_splash', None) is not None
        if startup_loading:
            self.mw._startup_loading_pending = True

        def wait_for_virtual_blocks(callback):
            block_updater = getattr(self.ui_updater, "block_list_updater", None)
            waiter = getattr(block_updater, "when_virtual_blocks_ready", None)
            try:
                from ui.updaters.block_list_updater import BlockListUpdater
                can_wait = isinstance(block_updater, BlockListUpdater)
            except ImportError:
                can_wait = False
            if can_wait and callable(waiter):
                waiter(callback)
            else:
                callback()

        def wait_for_restored_view(callback):
            def virtual_ready():
                block_updater = getattr(
                    self.ui_updater, "block_list_updater", None
                )
                waiter = getattr(block_updater, "when_tree_state_ready", None)
                try:
                    from ui.updaters.block_list_updater import BlockListUpdater
                    can_wait = isinstance(block_updater, BlockListUpdater)
                except ImportError:
                    can_wait = False
                if can_wait and callable(waiter):
                    waiter(callback)
                else:
                    callback()

            wait_for_virtual_blocks(virtual_ready)

        if self._restore_project_session_fast_path():
            self._report_startup(96, "Restoring virtual blocks…")

            def finish_cached_restore():
                self._report_startup(99, "Project view ready")
                if on_completed:
                    on_completed(True)
                if startup_loading:
                    self.mw.finish_startup_loading()

            wait_for_restored_view(finish_cached_restore)
            return

        block_updater = getattr(self.ui_updater, "block_list_updater", None)
        invalidator = getattr(block_updater, "invalidate_mempalace_story_cache", None)
        if callable(invalidator):
            invalidator()

        # Reset block/string selection state to avoid stale index issues
        self.mw.data_store.current_block_idx = -1
        self.mw.data_store.current_string_idx = -1

        # Clear current data
        self.mw.block_list_widget.clear()
        self.mw.data_store.data = []
        self.mw.data_store.edited_data = {}
        self.mw.data_store.block_names = {}
        self.mw.block_to_project_file_map = {} # Mapping data_block_idx -> project_block_idx

        # Reset plugin state if it tracks keys (like pokemon_fr)
        if hasattr(self.mw.current_game_rules, 'original_keys'):
            self.mw.current_game_rules.original_keys = []

        # Setup loading thread and progress dialog
        worker = ProjectLoadWorker(self.mw.project_manager, self.mw.current_game_rules)
        self.mw._project_loading_pending = True

        import sys
        progress_dialog = None
        if 'pytest' not in sys.modules and not startup_loading:
            from PyQt6.QtWidgets import QProgressDialog
            from PyQt6.QtCore import Qt
            total_steps = len(worker.blocks) * 2
            progress_dialog = QProgressDialog("Loading project blocks...", None, 0, total_steps, self.mw)
            progress_dialog.setWindowTitle(tr('Loading Project'))
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setMinimumDuration(0) # show immediately
            progress_dialog.setValue(0)
            worker.progress.connect(progress_dialog.setValue)

        def on_finished(result):
            if not result:
                self.mw._project_loading_pending = False
                if 'pytest' not in sys.modules and progress_dialog:
                    progress_dialog.close()
                if worker.error_occurred:
                    QMessageBox.critical(self.mw, tr('Load Error'), f"An error occurred while loading project files:\n{worker.error_occurred}")
                if on_completed:
                    on_completed(False)
                if startup_loading:
                    self.mw.finish_startup_loading()
                return

            if progress_dialog:
                progress_dialog.setLabelText("Building virtual blocks and scanning issues…")
                progress_dialog.setRange(0, 0)
            self._report_startup(95, "Building virtual blocks and scanning issues…")

            self.mw.data_store.data = result['data']
            self.mw.data_store.edited_file_data = result['edited_file_data']
            self.mw.data_store.block_names = result['block_names']
            self.mw.block_to_project_file_map = result['block_to_project_file_map']
            self.mw.data_store.block_to_project_file_map = result['block_to_project_file_map']

            plugin_keys_backup = result['plugin_keys_backup']
            if plugin_keys_backup is not None and hasattr(self.mw.current_game_rules, 'original_keys'):
                self.mw.current_game_rules.original_keys = plugin_keys_backup

            # Update paths for old-style save/load compatibility
            self._ensure_project_compat_paths()

            self.mw.project_manager.clear_archive_cache()

            if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                self.mw.translation_handler.load_progress_from_metadata()

            readiness = {"issues": True, "virtual": False, "finished": False}

            def finalize_project_view():
                if readiness["finished"] or not readiness["issues"] or not readiness["virtual"]:
                    return
                readiness["finished"] = True
                self.mw._project_loading_pending = False

                state_restored = False
                state = None
                if self.mw.project_manager and self.mw.project_manager.project_file_path:
                    p_path = str(self.mw.project_manager.project_file_path)
                    if self.mw.project_manager.project:
                        state = self.mw.project_manager.project.metadata.get("session_state")
                    if not state:
                        state = self.mw.settings_manager.session_state.get_state_for_file(p_path)
                    if state and (state.get("selected_id") or state.get("expanded_ids")):
                        log_info(f"Restoring project UI state for {p_path}")
                        state_restored = True

                def complete_ready_view():
                    if progress_dialog:
                        progress_dialog.close()
                    defer_startup_finish = False
                    if on_completed:
                        defer_startup_finish = on_completed(state_restored) is False
                    if startup_loading and not defer_startup_finish:
                        self._report_startup(99, "Finalizing the project view…")
                        self.mw.finish_startup_loading()

                if state_restored:
                    block_updater = getattr(
                        self.ui_updater, "block_list_updater", None
                    )
                    try:
                        from ui.updaters.block_list_updater import BlockListUpdater
                        can_wait = isinstance(block_updater, BlockListUpdater)
                    except ImportError:
                        can_wait = False
                    if can_wait:
                        self.ui_updater.apply_tree_state(
                            state, on_completed=complete_ready_view
                        )
                    else:
                        self.ui_updater.apply_tree_state(state)
                        complete_ready_view()
                else:
                    complete_ready_view()

            scanner = getattr(self.mw, "issue_scan_handler", None)
            try:
                from handlers.issue_scan_handler import IssueScanHandler
                wait_for_issue_scan = isinstance(scanner, IssueScanHandler)
            except ImportError:
                wait_for_issue_scan = False
            if scanner and hasattr(scanner, "_perform_initial_silent_scan_all_issues"):
                if wait_for_issue_scan:
                    readiness["issues"] = False

                    def issues_ready():
                        readiness["issues"] = True
                        finalize_project_view()

                    scanner._perform_initial_silent_scan_all_issues(on_completed=issues_ready)
                else:
                    scanner._perform_initial_silent_scan_all_issues()

            if hasattr(self.data_processor, '_autosave_session'):
                self.data_processor._autosave_session(force=True)

            # Pre-cache preview data for all blocks
            if hasattr(self.ui_updater, 'preview_updater'):
                self.ui_updater.preview_updater.schedule_pre_cache()

            # Update UI
            self.ui_updater.populate_blocks()
            self.ui_updater.update_statusbar_paths()

            def virtual_ready():
                readiness["virtual"] = True
                finalize_project_view()

            wait_for_virtual_blocks(virtual_ready)

        # Store worker reference to prevent garbage collection
        self._active_load_worker = worker
        worker.finished.connect(on_finished)
        if startup_loading:
            def report_worker_progress(current, total):
                ratio = current / max(1, total)
                phase = "Reading original blocks…" if ratio < 0.5 else "Reading translated blocks…"
                self._report_startup(75 + int(ratio * 20), phase)
            worker.progress.connect(report_worker_progress)

        if 'pytest' in sys.modules:
            worker.run()
        else:
            worker.start()

