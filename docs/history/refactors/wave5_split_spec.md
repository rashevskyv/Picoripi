# Wave 5 splits (move-only)

Verbatim method bodies. Shims keep old imports. No `.grok/` monolith backups.
No `_ShimName` unless tests `patch("this.module.Name")` and mixins use that global.
Do not edit wiki/locales/CHANGELOG/chapter_picker/project_manager/global_settings/bookmark_handler/zelda_bmg/window_kinds/layout_builder.

Target ~400–800 lines per file.

---

## A. `handlers/translation/glossary_handler.py` (~972)

Package `handlers/translation/glossary/` (do not collide with `glossary_builder_handler.py`).

Keep `handlers/translation/glossary_handler.py` exporting `GlossaryHandler`, `CategorySelectionDialog`, `GlossaryOccurrenceWorker`.

- `dialogs.py` — CategorySelectionDialog, GlossaryOccurrenceWorker
- `handler.py` — __init__, properties, load_prompts/bind/save_prompt, highlighting helpers
- `dialog_mixin.py` — install_menu_actions, show_glossary_dialog, closed, refresh, prepare_to_close, jump
- `edit_mixin.py` — add/edit entry, AI fill, notes variation
- `crud_mixin.py` — entry update/delete/clear, apply speaker, global_replace
- `classify_mixin.py` — classify_glossary_via_ai + handlers
- `speaker_mixin.py` — placeholder callback, aliases, reassign, discuss variants

Grep `from handlers.translation.glossary_handler import`.

Verify:
```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_translation/test_glossary_handler.py tests/test_handlers/test_glossary_logic.py tests/test_handlers/test_glossary_refresh.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check handlers/translation/glossary handlers/translation/glossary_handler.py
```
Write `.grok/glossary_handler_split_result.md`.

---

## B. `handlers/translation_handler.py` (~946)

This is already a facade over `handlers/translation/*` sub-handlers. Split remaining methods into mixins in `handlers/translation/facade/` or sibling mixins; keep `handlers/translation_handler.py` exporting `TranslationHandler`.

- `handler.py` — __init__ + composition
- `glossary_proxy_mixin.py` — glossary pass-throughs + append_selection
- `session_mixin.py` — provider/session/progress/cancel/revert
- `translate_mixin.py` — translate_current/specific/preview/block/resume/selected/all chrono
- `apply_mixin.py` — chunk timer, format/wrap, batch initiate, success/error handlers, variation, `_translate_and_apply`

Grep patches on `handlers.translation_handler`.

Verify:
```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_translation_handler.py tests/test_handlers/test_translation -q --tb=short --maxfail=25
.\venv\Scripts\python.exe -m ruff check handlers/translation_handler.py handlers/translation
```
Write `.grok/translation_handler_split_result.md`.

---

## C. `tools/bfn_editor/bfn_io.py` + `bfn_editor_window.py`

Same agent. Keep `BfnIoMixin` / `BfnEditorWindow` import paths.

`bfn_io.py` mixins composed as `BfnIoMixin`:
- `io_load_mixin.py` — choose/load/select/display/clear/close
- `io_save_mixin.py` — save_changes, _sync_with_global_preview_cache, export/import png
- `io_render_mixin.py` — render_system_font_to_glyphs (keep whole even if long)
- `io_detect_mixin.py` — auto_detect_width, load_original_bfn_bytes

`bfn_editor_window.py`:
- keep window class __init__ + composition
- `window_ui_mixin.py` — setup_ui, theme, shortcuts, eventFilter, header
- `window_tree_mixin.py` — scan_fonts, rebuild_tree, select/switch sheet
- `window_sync_mixin.py` — save column widths, save_changes, auto_sync, keyPress, showEvent

Verify:
```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_bfn_editor.py tests/test_core/test_bfn_core.py tests/test_core/test_bfn_tp_layout.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check tools/bfn_editor
```
Write `.grok/bfn_io_window_split_result.md`.

---

## D. `utils/syntax_highlighter.py` (~885)

Keep `utils/syntax_highlighter.py` exporting `JsonTagHighlighter`. Mixins:

- `highlighter.py` — __init__, setters, on_contents_change
- `styles_mixin.py` — _apply_css_to_format, reconfigure_styles
- `cache_mixin.py` — glossary/translation/icon caches and match getters
- `highlight_mixin.py` — highlightBlock + tag/spell helpers used only there

Verify:
```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_utils/test_syntax_highlighter.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check utils/syntax_highlighter.py utils
```
Write `.grok/syntax_highlighter_split_result.md`.

---

## E. `core/mempalace/dialogue_alignment.py` (~878)

Barrel at old path. Package `core/mempalace/alignment/`:

- `models.py` — MarkedDialogue, GameMessage, Proposal
- `normalize.py` — normalize_tokens, is_stage_direction, classify_alignment_exclusions, infer_tag_equivalents
- `simulate.py` — simulate + private _features/_proposal/_resolve/_ratio helpers
- `persist.py` — load_dialogues, load_messages, save_relations, lock_relation_choice
- keep `main()` on barrel or persist

Verify:
```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_dialogue_mapping.py tests/test_core/test_mempalace_flow_validation.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check core/mempalace/dialogue_alignment.py core/mempalace/alignment
```
Write `.grok/dialogue_alignment_split_result.md`.

---

## F. `core/mempalace/client.py` (~1380)

Keep `core/mempalace/client.py` as composition + `__init__` / connection / preload / get_cached_context / _init_local_db. Mixins in `core/mempalace/client_mixins/` or sibling:

- `story_api_mixin.py` — story timeline/dialogue/character getters (through get_story_timeline_position)
- `palace_write_mixin.py` — add_wing/room/drawer/relation, has_room
- `palace_read_mixin.py` — search_context, get_room_visual, get_relations, get_wings/rooms/drawers, clear_*
- `chapter_mixin.py` — chapter/script mappings, save chapter/mappings, get_all_character_lines

`core/mempalace_client.py` already re-exports MemePalaceClient — keep that working.

Verify:
```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_mempalace_client.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check core/mempalace/client.py core/mempalace
```
Write `.grok/mempalace_client_split_result.md`.

---

## G. `core/script_markup/local_autofill.py` (~950)

Barrel. Package `core/script_markup/autofill/`:

- `text.py` — _clean, _mode, line/keyword/delimiter/action/speaker predicates
- `patterns.py` — generic surface patterns, inline speaker parts, structure patterns
- `scenes.py` — _infer_scene_structures and helpers
- `infer.py` — `infer_hierarchy_marks_from_examples` + LocalAutofillResult

`core/script_markup/__init__.py` already exports infer_hierarchy_marks_from_examples — keep.

Verify:
```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_local_autofill.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check core/script_markup/local_autofill.py core/script_markup/autofill
```
Write `.grok/local_autofill_split_result.md`.

---

## H. `ui/settings/plugin_mixin.py` (~922) + `components/speaker_merge_dialog.py` (~838)

Same agent if time; else plugin_mixin first.

`SettingsPluginMixin` split in `ui/settings/`:
- keep plugin_mixin.py as composition of:
  - `plugin_tabs_mixin.py` — setup/rebuild plugin tab, font list, display, rules, zelda window rules
  - `plugin_tables_mixin.py` — context tags tables
  - `plugin_paths_mixin.py` — paths subtab
  - `plugin_checkboxes_mixin.py` — detection/autofix populate
  - `plugin_aliases_mixin.py` — aliases
  - `plugin_fontmap_mixin.py` — font map table

`components/speaker_merge_dialog.py`:
- `components/speaker_merge/widgets.py` — NameOnlyDelegate
- `dialog.py` — __init__
- `tree_mixin.py` — populate, groups, filter, check
- `inspector_mixin.py` — inspector, names, apply

Keep `components/speaker_merge_dialog.py` shim.

Verify:
```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_settings tests/test_ui/test_settings_dialog.py tests/test_handlers/test_speaker_merge_handler.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check ui/settings components/speaker_merge components/speaker_merge_dialog.py
```
Write `.grok/plugin_speaker_split_result.md`.
