# Wave 3 splits (move-only)

Copy method bodies verbatim. No behavior changes. Keep import shims.

Do **not** edit: chapter_picker, project_manager, global_settings, wiki, locales, bookmark_handler, project_action_handler, zelda_bmg/window_kinds, layout_builder, main_window_plugin_handler, string_settings_updater, title_status_bar_updater, warnings_filter_dialog, CHANGELOG, tests (except if a split forces an import path that tests already use — prefer shims so tests stay untouched).

Do **not** invent a `_ShimName` helper unless a test actually `patch("this.module.SomeName")` and that name is used as a global in a mixin. QMessageBox class-attribute patches (`patch("mod.QMessageBox.warning")`) work globally if the shim still imports `QMessageBox`; mixins can import QMessageBox from PyQt6.

Do **not** leave 1000+ line backup copies under `.grok/`.

Target: no implementation file > ~800 lines (prefer ~400–700).

---

## A. `ui/components/bfn_preview_widget.py` (~2182)

Current working-tree file includes unpublished user edits — move **that** content.

Package `ui/components/bfn_preview/`:

- `helpers.py` — `_looks_like_bfn_editor`, `_looks_like_bfn_core`, `_preview_icon`, `_letter_icon`
- `chrome.py` — `BfnSideButton`, `BfnPreviewWindowBar`, `BfnPreviewSideBar`
- `adapter.py` — `BfnEditorAdapter`
- `widget.py` — `BfnPreviewWidget` `__init__` + mixin composition
- `geometry_mixin.py` — load_translation_map, activate_preview, update_preview_text, window presets, get_bg_top_left, get_absolute_text_rect, get_active_bfn_font, handles, draw_bounding_box
- `chrome_mixin.py` — stylesheets, source button, page bar build/position, sidebar position, resize/enter/leave
- `paging_mixin.py` — editor line follow, pages, _slice_page
- `mouse_mixin.py` — mouse events, show_context_menu
- `effects_mixin.py` — color/shadow/glow dialogs, _save_effects_settings
- `paint_mixin.py` — glyph/halo/icon render helpers + paintEvent / `_paint_event_impl`  
  If paint_mixin would exceed ~800 lines, split icon helpers (`_tinted_icon_texture`, `_draw_icon_texture`, `_draw_icon`) into `icons.py` as module-level functions (they are already `@staticmethod`-like).

Shim `ui/components/bfn_preview_widget.py` must re-export at least:

```
BfnPreviewWidget, BfnPreviewWindowBar, BfnPreviewSideBar, BfnSideButton,
BfnEditorAdapter, _looks_like_bfn_editor, _looks_like_bfn_core
```

Verify:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_bfn_preview_widget.py tests/test_ui/test_preview_font_loading.py tests/test_core/test_bfn_tp_layout.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check ui/components/bfn_preview ui/components/bfn_preview_widget.py
```

Write `.grok/bfn_preview_split_result.md`.

---

## B. `ui/updaters/block_list_updater.py` (~1774)

Current working-tree file includes unpublished user edits — move **that** content.

Package `ui/updaters/block_list/`:

- `updater.py` — `__init__` + mixin composition, subclass `BaseUIUpdater`
- `ready_mixin.py` — invalidate_mempalace_story_cache, force_refresh_virtual_folders, refresh_virtual_folder_labels, when_*_ready, notify, _data_shape_signature
- `virtual_cache_mixin.py` — _rows_from_cache through _virtual_scope / _story_linked_rows / story overrides
- `virtual_tree_mixin.py` — _add_virtual_role_leaf through _add_windows_projection_root, _set_item_style_icon, _register_item_in_cache, _start_chapters_worker_when_ready, _get_block_display_name_with_ext
- `tree_state_mixin.py` — get_tree_state, apply_tree_state, locators, _get_item_id
- `problems_mixin.py` — _get_aggregated_problems_for_block, _apply_issues_and_tooltip, _create_block_tree_item, unsaved helpers, _add_virtual_folder_to_tree
- `populate_mixin.py` — populate_blocks (keep the method whole)
- `highlight_mixin.py` — update_block_item_text_with_problem_count, highlight/clear, chapters loaded/failed

Shim `ui/updaters/block_list_updater.py`:

```python
from ui.updaters.block_list import BlockListUpdater
__all__ = ["BlockListUpdater"]
```

Verify:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/updaters/test_block_list_updater.py tests/test_ui/test_updaters/test_small_updaters.py tests/test_handlers/test_speaker_folders.py tests/test_asterisk_logic.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check ui/updaters/block_list ui/updaters/block_list_updater.py
```

Write `.grok/block_list_split_result.md`.

---

## C. `ui/mempalace_builder_dialog.py` (~1642)

UI/pipeline mixins already exist in `ui/mempalace/`. Split the **remaining** dialog methods into more mixins there. Keep `MemePalaceBuilderUiMixin` and `MemePalacePipelineMixin`.

Add:

- `hierarchy_mixin.py` — browse script/hierarchy, load/apply markup studio project, hierarchy status, wizard step, story tree, import sync
- `dialogue_mixin.py` — dialogue mapping start/progress/complete, review table, approve/reject, markup studio jump
- `analysis_mixin.py` — timeline + character profiling starts, chapter mapping/analysis queue, worker progress, AI provider warn, char mining/speech
- `session_mixin.py` — sleep toggles, finish_and_maybe_sleep, refresh_chapters_list, append_log, clear_database, load/save builder settings, reject/closeEvent, _handle_close_or_cancel, _init_composer_and_client

`ui/mempalace_builder_dialog.py` keeps `__init__` + class composition + constants `_HIERARCHY_*_KEY`. Re-export `QMessageBox` and `MemePalaceChapterAIAnalyzerWorker` (tests patch those on this module). If analysis_mixin constructs `MemePalaceChapterAIAnalyzerWorker` as a global, late-bind **only that name** from the shim onto the mixin module so `patch("ui.mempalace_builder_dialog.MemePalaceChapterAIAnalyzerWorker")` still works.

Verify:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_mempalace_builder.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check ui/mempalace ui/mempalace_builder_dialog.py
```

Write `.grok/mempalace_builder_split_result.md`.

---

## D. `core/glossary_manager.py` (~1287)

Keep `core/glossary_manager.py` as an **identity-preserving barrel** (same pattern as `utils/utils.py`). Implementation in new package `core/glossary/` (do not confuse with existing `core/glossary_build/`).

- `models.py` — STATUS_*, TERM_PLACEHOLDER, UNCONFIRMED_STATUSES, OCC_*, dataclasses
- `notes.py` — `render_notes`, `possible_duplicate_pairs`, `_fragments_from_raw`, `_variants_from_raw`, `_entry_to_dict`
- `parse_mixin.py` — `_parse_markdown`, `_table_lines`, `_generate_markdown`, `_persist`, load_from_text, refresh_from_disk, get_raw_text, glossary_path, backup_file, save_to_disk
- `occurrence_mixin.py` — find_matches, build_occurrence_index, _append_owned_occurrences*, update_occurrences_for_entry, getters
- `pattern_mixin.py` — _build_pattern_cache, _build_regex, build_translation_regex, _get_word_stem_pattern, get_compiled_pattern, iter_compiled
- `mutation_mixin.py` — add/update/rename/delete/clear/seed/suggest, global_replace, bind_project_rows, session changes
- `replace.py` — `preserve_case`, `replace_preserve_case` (module-level)
- `manager.py` — `GlossaryManager` composition + `__init__` + small getters (get_entries, get_entry, get_entries_sorted_by_length)

Barrel `core/glossary_manager.py` must re-export every name currently imported from it, including `GlossaryManager`, dataclasses, STATUS_*, `render_notes`, `possible_duplicate_pairs`, OCC_*, `preserve_case`, `replace_preserve_case`, `TERM_PLACEHOLDER`.

Grep `from core.glossary_manager import` and keep those names.

Verify:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_glossary_manager.py tests/test_core/test_glossary_entry_lifecycle.py tests/test_core/test_glossary_occurrence_bridge.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check core/glossary core/glossary_manager.py
```

Write `.grok/glossary_manager_split_result.md`.
