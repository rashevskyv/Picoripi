# Wave 4 splits (move-only)

Copy bodies verbatim. No behavior changes. Shims keep old import paths.

Do **not** edit: wiki, locales, CHANGELOG, chapter_picker, project_manager, global_settings, bookmark_handler, zelda_bmg/window_kinds, layout_builder, main_window_plugin_handler, string_settings_updater, title_status_bar_updater, warnings_filter_dialog.

`handlers/project_action_handler.py` **is** in scope — split the current working-tree file (includes unpublished user edits).

No 1000-line backups under `.grok/`.
No `_ShimName` unless tests `patch("this.module.Name")` and a mixin uses `Name` as a global. Then late-bind **only those names**.
QMessageBox class-attribute patches work globally; mixins may import QMessageBox from PyQt6.
Target: implementation files ~400–800 lines.

---

## A. `tools/bfn_editor/bfn_widgets.py` (~1421)

Split **by class** into sibling modules; keep `bfn_widgets.py` as a barrel that re-exports every class currently imported from it (`ImageView`, `SimGlyphItem`, `SimImageView`, `GridItem`, `FillRangeDialog`, `ScaleSliderWidget`, `RenderFontDialog`).

Suggested files:
- `image_view.py` — `ImageView`
- `sim_view.py` — `SimGlyphItem`, `SimImageView`
- `grid_item.py` — `GridItem`
- `fill_range_dialog.py` — `FillRangeDialog`
- `scale_slider.py` — `ScaleSliderWidget`
- `render_font_dialog.py` — `RenderFontDialog`

Callers (`bfn_editor_window.py`, `bfn_io.py`, `bfn_simulation.py`, `bfn_navigation.py`) keep `from tools.bfn_editor.bfn_widgets import ...`.

## A2. `tools/bfn_editor/bfn_navigation.py` (~1306)

Same agent. Split `BfnNavigationMixin` into mixins composed in `bfn_navigation.py` (or `bfn_nav/` package with `BfnNavigationMixin` re-export). Keep `from tools.bfn_editor.bfn_navigation import BfnNavigationMixin`.

- `glyph_table_mixin.py` — mapping helpers + populate/refresh/filter table through `on_table_item_changed` start if needed
- `translation_map_mixin.py` — get/load/save translation map, generate_translation_map, get_next_free_char_code, get_original_char_for_glyph
- `mapping_edit_mixin.py` — update_char_mapping, double click, context menu, fill_sequence, clear_selected
- `glyph_nav_mixin.py` — copy/paste values, goto empty, jump_to_glyph_index

If `on_table_item_changed` is huge, it stays in mapping_edit or glyph_table — do not rewrite it.

Verify:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_bfn_editor.py tests/test_core/test_bfn_core.py tests/test_core/test_bfn_tp_layout.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check tools/bfn_editor
```

Write `.grok/bfn_editor_split_result.md`.

---

## B. `handlers/translation/ai_prompt_composer.py` (~1137)

Package `handlers/translation/prompt_composer/` OR mixins beside the file. Keep `handlers/translation/ai_prompt_composer.py` as shim exporting `AIPromptComposer`.

- `composer.py` — `__init__` + cache properties (`_script_lines_cache` through `_distill_cache_version`)
- `script_mixin.py` — `_find_script_path`, `_translate_speaker`, `_find_speaker_in_script`
- `story_mixin.py` — mempalace/wing/block label, `_fetch_story_context`, `_get_structured_story_context`, `_layout_contract_for_string`
- `glossary_mixin.py` — glossary helpers, `prepare_text_for_translation`, `restore_placeholders`, `_relevant_tag_aliases`
- `batch_mixin.py` — `compose_batch_request` (keep whole)
- `messages_mixin.py` — `_resolve_prompt_speaker`, `compose_variation_request`, `compose_messages`, glossary occurrence/request composers

Grep `from handlers.translation.ai_prompt_composer import`.

Verify:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_ai_prompt_composer.py tests/test_core/test_ai_prompt_services.py tests/test_handlers/test_translation/test_surrounding_context_and_metadata.py tests/test_core/test_story_context_bundle.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check handlers/translation/ai_prompt_composer.py handlers/translation/prompt_composer
```

If package path differs, ruff the actual new files.

Write `.grok/ai_prompt_composer_split_result.md`.

---

## C. `core/mempalace/story_timeline.py` (~1057)

Keep `core/mempalace/story_timeline.py` as identity-preserving barrel. Implementation in `core/mempalace/timeline/` (or sibling modules `story_timeline_models.py` etc. if a subpackage is heavier). Prefer subpackage `core/mempalace/timeline/`.

- `models.py` — exceptions + dataclasses
- `projection.py` — `story_virtual_projection_to_dict` / `from_dict`
- `normalize.py` — `normalize_reference_items`, `normalize_hierarchy_project`, `story_stable_id_for_mark`, private mark helpers used only there
- `sync.py` — `sync_hierarchy_project`, conflict record/get/resolve
- `queries.py` — all `get_story_*`, `get_reference_*`
- private helpers (`_story_timeline`, `_record`, `_story_node_type`, `_stable_id`, `_marked_text`, `_mark_payload`) go with the caller that needs them; do not duplicate.

Barrel must re-export every name imported from `core.mempalace.story_timeline` (grep it).

Verify:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_story_timeline.py tests/test_core/test_hierarchy_project.py tests/test_handlers/test_speaker_folders.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check core/mempalace/story_timeline.py core/mempalace/timeline
```

Write `.grok/story_timeline_split_result.md`.

---

## D. `handlers/text_operation_handler.py` (~1049)

Keep shim `handlers/text_operation_handler.py` exporting `TextOperationHandler` **and** names tests patch on that module:

`AsyncIssueScanner`, `get_scanner_thread_pool`, `AutofixSelectionDialog`, `QProgressDialog`, `AutofixWorker`

Late-bind those onto mixins that use them as globals.

Package `handlers/text_operation/`:

- `handler.py` — `__init__` + composition, `PREVIEW_UPDATE_DELAY`
- `scan_mixin.py` — thresholds, rescan, launch scanner, `_on_issue_scan_finished`, `sync_subline_asterisks`
- `preview_mixin.py` — `_update_preview_content`, stop_and_flush, `_editor_shows_current_row`, `text_edited`, timer timeout (the big scan-in-timeout stays here)
- `edit_mixin.py` — paste_block_text, revert_single_line, calculate_width_for_data_line_action
- `autofix_mixin.py` — auto_fix*, fix_all_strings, autofix worker lifecycle

Verify:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_text_operation_handler.py tests/test_text_operation_handler.py tests/test_handlers/test_text_autofix_logic.py tests/test_asterisk_logic.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check handlers/text_operation handlers/text_operation_handler.py
```

Write `.grok/text_operation_split_result.md`.

---

## E. `dialogs/search_review_dialog.py` (~1024)

Package `dialogs/search_review/` (there is already `dialogs/search/` for worker/utils — do not mix).

Keep `dialogs/search_review_dialog.py` exporting `SearchReviewDialog`.

- `dialog.py` — `__init__`, setup panels, set_controls_enabled, reject/done, `_shutdown_worker`
- `search_mixin.py` — load/search worker callbacks, find_matches, pre_highlight, show_current, perform_search
- `replace_mixin.py` — skip/replace/replace_all, jump, navigate block/string
- `persist_mixin.py` — rebuild_text*, save_changes_to_project, refresh_from_project, spacing/line numbers
- `context_mixin.py` — eventFilter, show_context_menu, `_ctx_*`

Verify:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_search_review_dialog.py tests/test_dialogs -q --tb=short --maxfail=20
.\venv\Scripts\python.exe -m ruff check dialogs/search_review dialogs/search_review_dialog.py
```

If glob is noisy, run files that import SearchReviewDialog.

Write `.grok/search_review_split_result.md`.

---

## F. `handlers/project_action_handler.py` (~1047, dirty working tree)

Split **current file**. Keep shim exporting `ProjectActionHandler`, `ProjectLoadWorker`, and patched names: `ProjectManager`, `QMessageBox`, `QFileDialog`, `Path`, `load_json_file`.

Late-bind `ProjectManager`, `Path`, `load_json_file` onto mixins that construct/use them as globals. `QMessageBox` class patches are global.

Package `handlers/project_action/`:

- `load_worker.py` — `ProjectLoadWorker`
- `handler.py` — `__init__`, `_report_startup`, `_set_project_actions_enabled`
- `lifecycle_mixin.py` — create/open/close project
- `blocks_mixin.py` — import block/directory, delete/move block, folder add actions, `_ensure_project_compat_paths`
- `session_mixin.py` — `_restore_project_session_fast_path`, `_populate_blocks_from_project`
- `recent_mixin.py` — recent menu, open recent, clear recent, restore view timer
- `tree_mixin.py` — expand/collapse all, `_update_all_folder_expansion_state`

Verify:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_project_action_handler.py tests/test_dialogs/test_real_workers_lifecycle.py tests/test_ui/test_preview_font_loading.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check handlers/project_action handlers/project_action_handler.py
```

Write `.grok/project_action_split_result.md`.

---

## G. `tests/test_ui/test_script_markup_studio.py` (~3465)

Split tests, **not** product code. Shared fixtures (`qapp`, `_FakeMainWindow`, `_FakeSettingsManager`, `_fresh_autosave_path`) go in `tests/test_ui/script_markup/conftest.py`.

Group files (~300–700 lines) by theme, e.g.:
- `test_construct_and_session.py` — construct, geometry, autosave, buttons, mode toggle
- `test_search.py`
- `test_caches.py` — highlighter/outline/line-style caches
- `test_modes_and_marks.py` — picoripi/custom/manual marks/teacher
- `test_hierarchy_tree.py`
- `test_range_edit.py`
- `test_ai_and_project.py` — AI markup, hierarchy project IO, mempalace publish

Leave `tests/test_ui/test_script_markup_studio.py` **without test functions** (a short comment pointing at the package) so pytest does not collect duplicates.

Do not change assertions. Move test functions verbatim; fix imports only.

Verify:

```
$env:PYTHONPATH = "."
$env:TMPDIR = "$PWD\.tmp_test_run"; $env:TEMP = $env:TMPDIR; $env:TMP = $env:TMPDIR
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/script_markup tests/test_ui/test_script_markup_studio.py -q --tb=short
```

Expect the same count as before (~140+ tests) collected from the package, **0** from the old file.

Write `.grok/sms_tests_split_result.md`.
