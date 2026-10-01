# Wave 2 splits (move-only)

Do not touch dirty user files: chapter_picker, project_manager, global_settings, wiki, locales, bookmark_handler, project_action_handler, zelda_bmg/window_kinds, layout_builder, bfn_preview_widget, main_window_plugin_handler, block_list_updater, string_settings_updater, title_status_bar_updater, warnings_filter_dialog, CHANGELOG.

No behavior changes. Copy method bodies verbatim. Keep import shims.

## A. handlers/list_selection_handler.py

Package `handlers/list_selection/`:

- `__init__.py` re-export `ListSelectionHandler`
- `handler.py` — `__init__`, `cleanup`, mixin composition, subclass of `BaseHandler`
- `navigation_mixin.py` — navigate_between_blocks/folders, _select_virtual_tree_item, navigate_to_current_*, navigate_to_physical_string
- `virtual_selection_mixin.py` — refresh_empty_virtual_view_on_click, _handle_virtual_row_selection, _handle_speaker_selection, _handle_item_selection, _handle_notated_selection, _handle_chapter_selection, _handle_folder_selection, _handle_aggregate_virtual_selection
- `physical_selection_mixin.py` — block_selected, _handle_physical_block_selection, cursor/selection timers, _restore_block_selection, _update_block_toolbar_button_states, resolve_bmg_id_to_indices, select_string_by_absolute_index, string_selected_from_preview, handle_preview_selection_changed, scroll_to_current_string_in_preview, _get_displayed_indices, _get_relative_index
- `rename_mixin.py` — rename_block, handle_block_item_text_changed
- `filter_mixin.py` — all toggle_* , warnings_filter_changed, open_warnings_filter_dialog, move_selection_to_category, rename_category, delete_category
- `problem_mixin.py` — _data_string_has_any_problem, navigate_to_problem_string
- `speaker_retention_mixin.py` — _pending_speaker_retention*, save_speaker/chapter/character, _expand_item_ancestors, _restore_editor_focus_after_speaker_save

`handlers/list_selection_handler.py` becomes:

```python
from handlers.list_selection import ListSelectionHandler
__all__ = ["ListSelectionHandler"]
```

Grep `from handlers.list_selection_handler import` and keep working.

Target: no file > ~500 lines.

Verify:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_list_selection_handler.py tests/test_asterisk_logic.py -q --tb=short
.\venv\Scripts\python.exe -m ruff check handlers/list_selection handlers/list_selection_handler.py
```

If test_list_selection_handler.py does not exist, grep tests for ListSelectionHandler and run those files.

Write `.grok/list_selection_split_result.md`.

## B. components/glossary_dialog.py

Package `components/glossary/`:

- `__init__.py` re-export `GlossaryDialog`
- `widgets.py` — `_GlossaryTermTable`, `_DetailPane`, `_RichTextItemDelegate`, `_VariantItemDelegate`
- `dialog.py` — `__init__`, mixin composition, QDialog subclass
- `table_mixin.py` — tabs, populate entries, select/focus term, row selection, filter, reload_data
- `editor_mixin.py` — notes editor dirty/save/delete/context menu/review state
- `details_mixin.py` — populate/clear details, occurrences, speaker apply/validate, variants
- `actions_mixin.py` — AI classify, build, clear, global replace, confirm, persistence (load/save dialog state, show/close/key)

`components/glossary_dialog.py` becomes a re-export shim. Keep every name tests import from that module.

Grep `from components.glossary_dialog import`.

Verify:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_glossary_ui_logic.py tests/test_components -q --tb=short --maxfail=20
.\venv\Scripts\python.exe -m ruff check components/glossary components/glossary_dialog.py
```

If that test glob is too broad/slow, run files that import GlossaryDialog.

Write `.grok/glossary_dialog_split_result.md`.
